#!/usr/bin/env python3
"""t/rl_spec_pool.py -- vericoding's specification-only Dafny tasks as RL prompts (2026-09-26).

    python3 t/rl_spec_pool.py stage --vericoding DIR --out OUT [--limit N]   # stub bodies, run the lifter
    python3 t/rl_spec_pool.py gate  --out OUT [--split SPLIT]                # held-out and twin gates
    python3 t/rl_spec_pool.py prompts --out OUT                              # prompts.jsonl

vericoding-benchmark (github.com/Beneficial-AI-Foundation/vericoding-benchmark, MIT)
ships 2,334 Dafny specifications, each a method signature with requires/ensures,
the predicates and functions they use, English (`vc-description`), and the body
`assume {:axiom} false;`. A prompt pool with no reference answer: the reward is the
verifier alone. Expert iteration keeps every sample that verifies as a new
training document (STaR, arXiv:2203.14465: generate, keep what the checker
accepts, retrain; ReST-EM, arXiv:2312.06585, the same with a binary reward).

How a specification becomes a t prompt. The lifter (t/lifter.py) only lifts a
method with a body, so the staged copy replaces `assume {:axiom} false;` by a stub
that assigns every return value a default of its type (0, false, [] or "") and
nothing else; the lifter then lifts the declaration, the clauses and every
predicate and function the clauses use exactly as it lifts a verified program,
refusing by name what t cannot express. The stub never reaches a prompt: the
prompt is the head (`Problem:` the task's English, `Signature:`) followed by the
lifted task printed up to its body's opening brace, which is where every program
document in locallm's corpus continues with the body. The answer is that
prefix plus what the model writes, so the specification cannot be changed by the
model, and the proof (Dafny `verified / refuted`) is the whole reward.

Gates before a specification is asked (t/lift_corpora.screen's order, applied to
the specification because there is no program yet): the held-out ids, dev ids and
same-task exclusions under every alias in the file and its row
(loop_filter.TrainingDataGate over the merged policy, t/r12-dev-ids.json), and a
specification twin: the lifted `ensures`, evaluated at the test points of every
gated problem whose signature matches (spec_check.check_points), holds at all of a
gated problem's points with at least one not vacuous -> the specification
describes a held-out problem and is refused. A sample that verifies is gated
again as a program (lift_corpora's behavioural twin, on 100 drawn inputs) before
it may become a training document.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import loop_filter                                               # noqa: E402
import loop_locallm                                              # noqa: E402
import rl_reward                                                 # noqa: E402
import spec_experiment as se                                     # noqa: E402
import surface                                                   # noqa: E402

ASSUME_BODY = re.compile(r"\{\s*assume\s*\{:axiom\}\s*false\s*;\s*\}")
RETURNS = re.compile(r"returns\s*\(([^)]*)\)")


def default_for(ty: str) -> str | None:
    ty = ty.strip()
    if ty in ("int", "nat"):
        return "0"
    if ty == "bool":
        return "false"
    if ty == "string":
        return '""'
    if ty.startswith("seq<"):
        return "[]"
    return None


def stub_source(text: str) -> str | None:
    """The spec file with its `assume false` body replaced by a stub assigning each
    return a default; None when a return type has no default t can lift."""
    m = RETURNS.search(text[text.find("<vc-spec>"):] if "<vc-spec>" in text else text)
    if not m or not ASSUME_BODY.search(text):
        return None
    assigns = []
    for part in m.group(1).split(","):
        if ":" not in part:
            return None
        name, ty = part.split(":", 1)
        value = default_for(ty)
        if value is None:
            return None
        assigns.append(f"  {name.strip()} := {value};")
    return ASSUME_BODY.sub("{\n" + "\n".join(assigns) + "\n}", text, count=1)


def cmd_stage(a) -> int:
    src = Path(a.vericoding)
    out = Path(a.out)
    staged = out / "staged"
    if staged.exists():
        shutil.rmtree(staged)
    staged.mkdir(parents=True)
    rows = {}
    for line in (src / "jsonl" / "dafny_tasks.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            rows[row["id"]] = row
    census = Counter()
    files = sorted((src / "specs").glob("D*_specs.dfy"))
    if a.limit:
        files = files[: a.limit]
    for f in files:
        stem = f.name.split("_")[0]
        stub = stub_source(f.read_text(encoding="utf-8"))
        if stub is None:
            census["refused:return-type-without-default"] += 1
            continue
        (staged / f"vericoding_{stem}.dfy").write_text(stub, encoding="utf-8")
        census["staged"] += 1
    (out / "rows.json").write_text(json.dumps(rows), encoding="utf-8")
    lift = out / "lift"
    subprocess.run([sys.executable, str(HERE / "lifter.py"), "--dir", str(staged), "--out", str(lift),
                    "--jobs", str(a.jobs), "--skip-check"], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    lifted = sorted(lift.glob("*.lift.json"))
    census["lifted"] = sum(1 for s in lifted if s.with_name(s.name[:-len(".lift.json")] + ".json").exists())
    summary = lift / "run_summary.json"
    census_out = {"specs": len(files), "counts": dict(census),
                  "lifter": json.loads(summary.read_text(encoding="utf-8")) if summary.exists() else None}
    (out / "stage-census.json").write_text(json.dumps(census_out, indent=1), encoding="utf-8")
    print(json.dumps(census_out["counts"]))
    return 0


def lifted(out: Path):
    for sidecar in sorted((out / "lift").glob("*.lift.json")):
        task_file = sidecar.with_name(sidecar.name[:-len(".lift.json")] + ".json")
        if task_file.exists():
            yield task_file, json.loads(task_file.read_text(encoding="utf-8")), json.loads(sidecar.read_text(encoding="utf-8"))


def stem_of(sidecar: dict, task_file: Path) -> str:
    text = json.dumps(sidecar)
    m = re.search(r"D[A-Z]\d{4}", text) or re.search(r"D[A-Z]\d{4}", task_file.name)
    return m.group(0) if m else task_file.stem


def coarse(ty) -> str:
    """int, bool or seq: the pool's point kinds with nesting erased (seq-of-seq is a seq)."""
    import head_align_corpus
    name = head_align_corpus.type_name(ty)
    return "seq" if name.startswith("seq") else name


def signature_key(task: dict) -> tuple:
    return (tuple(coarse(p["type"]) for p in task["params"]),
            coarse(task["returns"][0]["type"]) if task.get("returns") else None)


def spec_twin(task: dict, gated: list[int], pool: dict) -> int | None:
    """A gated problem at whose every test point this specification's ensures holds
    (with the problem's own expected output bound to the result), at least one of
    them inside the precondition: the specification describes that problem."""
    import spec_check
    for tid in gated:
        entry = pool[tid]
        try:
            r = spec_check.check_points(task, entry)
        except Exception:                                       # noqa: BLE001
            continue
        if not (r["points_held"] > 0 and r["points_failed"] == 0):
            continue
        # One to three points are a coincidence as often as a twin (the smoke run of
        # 2026-09-26 "twinned" a champagne-pyramid spec with binomial coefficients),
        # so, as lift_corpora does for programs, the problem's reference is asked on
        # 100 drawn inputs: the spec is its twin unless one of them contradicts it.
        # No reference or no draws keeps the refusal: unknown is not admitted.
        import random
        try:
            deep = spec_check.check_task(task, entry, 100, random.Random(0))
        except Exception:                                       # noqa: BLE001
            return tid
        if deep.get("status") != "disagrees":
            return tid
    return None


def cmd_gate(a) -> int:
    out = Path(a.out)
    split = json.loads(Path(a.split).read_text(encoding="utf-8"))
    pool = se.pool(split.get("pool", "v1"))
    eval_ids = {int(i) for i in split["eval_ids"]}
    dev = set(loop_filter.r12_dev_ids())
    policy = loop_filter.decontamination()
    gate = loop_filter.TrainingDataGate(frozenset(eval_ids | dev), policy)
    gated_ids = sorted((eval_ids | dev | set(policy.exclude_train_ids) | set(policy.overlap_eval_ids)) & set(pool))
    by_sig: dict[tuple, list[int]] = {}
    for tid in gated_ids:
        e = pool[tid]
        if not e.get("points"):
            continue
        kinds = tuple("seq" if k == "seq-of-seq" else k for k, _v in e["points"][0]["args"])
        ret = e["points"][0]["expected"][0]
        by_sig.setdefault((kinds, "seq" if ret == "seq-of-seq" else ret), []).append(tid)
    rows = json.loads((out / "rows.json").read_text(encoding="utf-8"))
    kept, refused = [], Counter()
    decisions = []
    for task_file, task, sidecar in lifted(out):
        stem = stem_of(sidecar, task_file)
        row = rows.get(stem, {})
        if not row:
            # a spec file with no row in jsonl/dafny_tasks.jsonl has no English and was
            # not in the benchmark's released task list: not asked
            refused["no task row (no English)"] += 1
            decisions.append({"stem": stem, "refused": "no task row"})
            continue
        try:
            errs = se.fuzz_lower.check_wf(task)
        except Exception as e:                                  # noqa: BLE001
            errs = [f"check_wf raised {type(e).__name__}"]
        if errs:
            # the lift ran without its kernel check; a specification t itself rejects
            # (a seq-valued function lifted as int, 2026-09-26 DA0000) is unanswerable
            refused["lifted specification not well formed"] += 1
            decisions.append({"stem": stem, "refused": "not well formed", "why": "; ".join(errs)[:200]})
            continue
        text = json.dumps(row) + "\n" + surface.print_task(task)
        # vericoding names a HumanEval problem `humaneval_NNN`, which is not one of the
        # aliases loop_filter reads (he_N); lift_corpora.humaneval_index maps it to the
        # pool id (100000 + N), passed to the gate as an explicit task id
        from lift_corpora import humaneval_index
        he = humaneval_index(row.get("source-id"), "") if row.get("source") == "humaneval" else None
        task_ids = [se.HUMANEVAL_BASE + he] if he is not None else []
        if not gate.admit(text, names=[task.get("name")], task_ids=task_ids):
            refused["held-out or excluded id in the row or task"] += 1
            decisions.append({"stem": stem, "refused": "id gate"})
            continue
        twin = spec_twin(task, by_sig.get(signature_key(task), []), pool)
        if twin is not None:
            refused["specification twin of a gated problem"] += 1
            decisions.append({"stem": stem, "refused": f"spec twin of {twin}"})
            continue
        kept.append({"stem": stem, "task_file": str(task_file), "source": row.get("source"),
                     "source_id": row.get("source-id"), "description": row.get("vc-description", "")})
        decisions.append({"stem": stem, "kept": True})
    (out / "gated.jsonl").write_text("".join(json.dumps(k) + "\n" for k in kept), encoding="utf-8")
    (out / "gate-decisions.jsonl").write_text("".join(json.dumps(d) + "\n" for d in decisions), encoding="utf-8")
    census = {"lifted": len(decisions), "kept": len(kept), "refused": dict(refused),
              "kept_by_source": dict(Counter(k["source"] for k in kept))}
    (out / "gate-census.json").write_text(json.dumps(census, indent=1), encoding="utf-8")
    print(json.dumps(census))
    return 0


def spec_prompt(description: str, task: dict) -> str:
    """Head plus the task printed up to its body's brace (see the module docstring)."""
    import head_align_corpus
    printed = surface.print_task(task)
    brace = printed.find("\n{")
    if brace < 0:
        raise ValueError("printed task has no body brace")
    head = f"Problem: {' '.join(description.split())}\n" + head_align_corpus.head_for(task)
    return head + printed[: brace + 2] + "\n"


def cmd_prompts(a) -> int:
    out = Path(a.out)
    rows = [json.loads(line) for line in (out / "gated.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    written = 0
    with open(out / "prompts.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            task = json.loads(Path(r["task_file"]).read_text(encoding="utf-8"))
            try:
                prompt = spec_prompt(r["description"], task)
            except Exception:                                   # noqa: BLE001
                continue
            f.write(json.dumps({"stem": r["stem"], "name": task["name"], "prompt": prompt,
                                "source": r["source"]}) + "\n")
            written += 1
    print(f"prompts: {written}")
    return 0


# ---------------------------------------------------------------- scoring --

def answer_task(prompt: str, completion: str) -> str:
    """The t text of an answer: the prompt's task prefix and the model's body, cut
    where cmd_generate cuts a reply."""
    start = prompt.find("\nt ", prompt.find("Signature:")) + 1
    full = prompt + completion
    # the boundary is searched in the whole text from the prompt's last newline, since
    # the prompt ends in "{\n" and a completion that opens "\nProblem: " is a boundary
    # only together with it (the stop fired on the whole text too)
    m = loop_locallm.REPLY_BOUNDARY.search(full, len(prompt) - 1)
    end = max(len(prompt), m.start()) if m else len(full)
    return full[start:end]


def score_spec_answers(items: list[dict], cache_path: Path, *, jobs: int = 2, host: str | None = None,
                       batch: str = "spec") -> list[dict]:
    """Proof-only reward for spec prompts: 0 unparseable, 0.05 parses, 0.10 well
    formed, 1.0 Dafny `verified / refuted`. Items carry name, prompt, completion."""
    cache = rl_reward.RewardCache(cache_path)
    fresh, keys = {}, []
    for it in items:
        text = answer_task(it["prompt"], it["completion"])
        key = hashlib.sha256(f"spec:{it['name']}\n{text}".encode("utf-8")).hexdigest()
        keys.append(key)
        if cache.get(key) is not None or key in fresh:
            continue
        sig: dict = {"stem": it.get("stem")}
        try:
            task = surface.parse(text)
        except Exception as e:                                  # noqa: BLE001
            fresh[key] = ({**sig, "stage": "parse", "why": str(e)[:200]}, None)
            continue
        task = se.rename_task(task, f"{it['name']}__rl{key[:10]}")
        errs = se.fuzz_lower.check_wf(task)
        if errs:
            fresh[key] = ({**sig, "stage": "wf", "why": "; ".join(errs)[:300]}, None)
            continue
        fresh[key] = ({**sig, "stage": "task"}, task)
    tasks = {t["name"]: t for (_s, t) in fresh.values() if t is not None}
    cells = rl_reward.prove(tasks, jobs=jobs, host=host, batch=batch) if tasks else {}
    for key, (sig, task) in fresh.items():
        cache.put(key, sig, cells.get(task["name"]) if task is not None else None)
    out = []
    for key in keys:
        row = cache.get(key)
        sig, proof = row["signals"], row["proof"]
        tier = ("none" if sig["stage"] == "parse" else "parses" if sig["stage"] == "wf"
                else "proved" if proof == rl_reward.CLEAN else "typed")
        out.append({"key": key, "tier": tier, "reward": rl_reward.TIERS[tier], "proof": proof})
    return out


def cmd_sample(a) -> int:
    """k samples per spec prompt from a locallm checkpoint (GPU), then score."""
    import torch
    sys.path.insert(0, str(HERE.parent / "locallm"))
    import checkpoint
    import pilot_sampling
    out = Path(a.out)
    prompts = [json.loads(line) for line in (out / "prompts.jsonl").read_text(encoding="utf-8").splitlines()
               if line.strip()]
    import random
    random.Random(a.seed).shuffle(prompts)
    prompts = prompts[: a.n]
    model, tok, _ = checkpoint.load_checkpoint(a.model)
    dst = out / f"samples-t{a.temperature}"
    dst.mkdir(parents=True, exist_ok=True)
    for i, p in enumerate(prompts):
        path = dst / f"{p['stem']}.jsonl"
        if path.exists():
            continue
        ids = tok.encode(p["prompt"])
        budget = max(16, a.context - len(ids))
        g = torch.Generator(device=next(model.parameters()).device)
        g.manual_seed(pilot_sampling.derive_seed(a.seed, int(p["stem"][2:]), a.temperature))
        rows = checkpoint.sample_batch(model, tok, p["prompt"], a.k, tokens=budget, temperature=a.temperature,
                                       top_k=a.top_k, stop=loop_locallm.reply_stop(p["prompt"]), generator=g)
        path.write_text("".join(json.dumps({"stem": p["stem"], "name": p["name"], "prompt": p["prompt"],
                                            "completion": r["text"][len(p["prompt"]):] if r["text"].startswith(p["prompt"]) else r["text"],
                                            "prompt_tokens": len(ids)}) + "\n" for r in rows), encoding="utf-8")
    print(f"sampled {len(prompts)} prompts x {a.k}")
    return 0


def cmd_score(a) -> int:
    out = Path(a.out)
    dst = out / f"samples-t{a.temperature}"
    items = [json.loads(line) for f in sorted(dst.glob("*.jsonl"))
             for line in f.read_text(encoding="utf-8").splitlines() if line.strip()]
    res = score_spec_answers(items, out / "rewards.jsonl", jobs=a.jobs, host="local" if a.local else None)
    per = {}
    for it, r in zip(items, res):
        per.setdefault(it["stem"], []).append(r["tier"])
    tiers = Counter(r["tier"] for r in res)
    anyp = sum("proved" in ts for ts in per.values())
    anyw = sum(any(t in ("typed", "proved") for t in ts) for ts in per.values())
    summary = {"prompts": len(per), "samples": len(res), "tiers": dict(tiers),
               "prompts_any_well_formed": anyw, "prompts_any_proved": anyp,
               "proved_stems": sorted(s for s, ts in per.items() if "proved" in ts)}
    (out / f"score-t{a.temperature}.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps(summary))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("stage")
    p.add_argument("--vericoding", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--jobs", type=int, default=4)
    p = sub.add_parser("gate")
    p.add_argument("--out", required=True)
    p.add_argument("--split", default=str(rl_reward.SPLIT))
    p = sub.add_parser("prompts")
    p.add_argument("--out", required=True)
    p = sub.add_parser("sample")
    p.add_argument("--out", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--n", type=int, default=100)
    p.add_argument("--k", type=int, default=16)
    p.add_argument("--temperature", type=float, default=0.8)
    p.add_argument("--top-k", type=int, default=20)
    p.add_argument("--context", type=int, default=512)
    p.add_argument("--seed", type=int, default=1)
    p = sub.add_parser("score")
    p.add_argument("--out", required=True)
    p.add_argument("--temperature", type=float, default=0.8)
    p.add_argument("--jobs", type=int, default=2)
    p.add_argument("--local", action="store_true")
    a = ap.parse_args(argv)
    return {"stage": cmd_stage, "gate": cmd_gate, "prompts": cmd_prompts, "sample": cmd_sample,
            "score": cmd_score}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
