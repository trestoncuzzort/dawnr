#!/usr/bin/env python3
"""t/proof_repair.py -- hand a failed proof back with Dafny's own message; keep what Dafny then accepts
(2026-10-01).

    ~/.venv-t/bin/python t/proof_repair.py --model DIR --from TAG --tag OUT --ids-file ids.txt \\
        [--rounds 2] [--samples 2] [--lab user@host]

SAFE's self-debugging (arXiv:2410.15756, 3.3 and 4.2): a proof that fails is given back to the
fine-tuned model with the verifier's error, K debugging samples are drawn for it, and a task
counts if any of them verifies. One debugging sample after one proof sample beat two proof
samples in their table 1.

Here the candidates are the answers of the set TAG that pass their problem's tests (an answer
that fails them is not this step's business). Dafny judges each (t/dafny_feedback.judge: one
`dafny verify` on the lowered program). What it verifies is carried over unchanged. What it does
not is sent back as the conversation the debugging rows trained: the original question, the
attempt, and Dafny's lines naming the clause that failed, then "Write the corrected task." One
greedy repair and --samples sampled ones (temperature 0.7) a round. A repair is looked at by
Dafny only if it parses, is well formed, passes the problem's tests and, where the question gave
a specification, carries it unchanged (t/spec_given.kept). The first repair Dafny verifies is the
problem's answer; otherwise the first repair that passes those cheap gates becomes the attempt
for the next round, with its own message.

Dafny is the judge inside the loop only. The answer set OUT is in t/spec_experiment.py's layout
and goes to all seven kernels, the twins and the reference check like any other; nothing is
counted here. OUT/repair.json says how many were verified untouched and how many each round
repaired.

Dafny runs where it is installed: on this machine if it is, else on --lab over ssh (the copy of
t/dafny_feedback.py at --remote-module, with that machine's checkout on its path).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import dafny_feedback                                           # noqa: E402
import fuzz_lower                                               # noqa: E402
import harness                                                  # noqa: E402
import loop_dataset                                             # noqa: E402
import spec_experiment as se                                    # noqa: E402
import spec_given                                               # noqa: E402
import student_rows                                             # noqa: E402
import surface                                                  # noqa: E402

TEMPERATURE, TOP_P = 0.7, 0.95


def lab_judge(tasks: list[dict], lab: str, remote_module: str, jobs: int = 8) -> list[dict]:
    """Dafny's verdict on each task, computed on `lab` (or here when lab is "local")."""
    if not tasks:
        return []
    if lab == "local":
        return [dafny_feedback.judge(t) for t in tasks]
    stem = f"/tmp/proof-repair-{os.getpid()}-{int(time.time() * 1000)}"
    with tempfile.TemporaryDirectory(prefix="proof-repair-") as tmp:
        src, dst = Path(tmp) / "in.jsonl", Path(tmp) / "out.jsonl"
        src.write_text("".join(json.dumps(t) + "\n" for t in tasks), encoding="utf-8")
        ssh = ["ssh", "-o", "BatchMode=yes", "-o", "ServerAliveInterval=30"]
        subprocess.run(["scp", "-q", "-o", "BatchMode=yes", str(src), f"{lab}:{stem}-in.jsonl"], check=True)
        cmd = (f"cd ~/tup && . ~/scratch/lab-env.sh > /dev/null 2>&1; PYTHONPATH=$HOME/tup/t nice -n 19 python3 "
               f"{remote_module} --judge {stem}-in.jsonl {stem}-out.jsonl --jobs {jobs} > /dev/null")
        subprocess.run(ssh + [lab, cmd], check=True, timeout=3600)
        subprocess.run(["scp", "-q", "-o", "BatchMode=yes", f"{lab}:{stem}-out.jsonl", str(dst)], check=True)
        subprocess.run(ssh + [lab, f"rm -f {stem}-in.jsonl {stem}-out.jsonl"], check=False)
        out = [json.loads(l) for l in dst.read_text(encoding="utf-8").splitlines() if l.strip()]
    if len(out) != len(tasks):
        raise RuntimeError(f"proof_repair: {len(tasks)} tasks went to {lab}, {len(out)} verdicts came back")
    return out


def given_specification(question: list[dict]) -> dict | None:
    """The specification a specification-given question shows, parsed; None for any other question."""
    user = question[-1]["content"]
    if not user.startswith(student_rows.ASK):
        return None
    block = se.find_block(user)
    return surface.parse(block) if block else None


def cheap(reply: str, entry: dict, spec: dict | None) -> tuple[dict | None, str]:
    """(the parsed task, "ok") when a repair parses, keeps a given specification, is well formed
    and passes the problem's tests; else (None, the gate that refused it)."""
    block = se.find_block(reply)
    if block is None:
        return None, "no task block"
    try:
        task = surface.parse(block)
    except Exception:                                           # noqa: BLE001
        return None, "does not parse"
    if spec is not None and spec_given.kept(spec, task) is not None:
        return None, "specification changed"
    try:
        errs = fuzz_lower.check_wf(task)
        if errs and task.get("t") == 0 and not fuzz_lower.check_wf(dict(task, t=1)):
            task, errs = dict(task, t=1), []
    except Exception as e:                                      # noqa: BLE001
        errs = [str(e)]
    if errs:
        return None, "not well formed"
    if not all(se.run_point(task, p)["verdict"] == "pass" for p in entry["points"]):
        return None, "fails a test"
    return task, "ok"


def repair_question(question: list[dict], attempt: dict, said: list[str]) -> list[dict]:
    return question + [{"role": "assistant", "content": loop_dataset.fence(surface.print_task(attempt).strip())},
                       {"role": "user", "content": dafny_feedback.message(said) + dafny_feedback.ASK_AGAIN}]


def run(candidates: dict, P: dict, decode, judge, rounds: int, samples: int, batch: int, max_new: int) -> tuple[dict, dict]:
    """candidates: tid -> {"question", "task"}. Returns (tid -> {"task", "verified", "round", ...}, counts)."""
    ids = list(candidates)
    verdicts = judge([candidates[t]["task"] for t in ids])
    state = {t: {"question": candidates[t]["question"], "task": candidates[t]["task"],
                 "spec": given_specification(candidates[t]["question"]), "verified": v["verified"],
                 "said": v["said"], "round": 0, "asked": 0} for t, v in zip(ids, verdicts)}
    counts = {"candidates": len(ids), "verified untouched": sum(1 for s in state.values() if s["verified"]),
              "nothing to act on": sum(1 for s in state.values() if not s["verified"] and not s["said"]), "rounds": []}
    for rnd in range(1, rounds + 1):
        open_ = [t for t in ids if not state[t]["verified"] and state[t]["said"]]
        repaired, moved, refusals = 0, 0, {}
        passing: dict[str, list[dict]] = {t: [] for t in open_}
        for attempt in range(samples + 1):
            for start in range(0, len(open_), batch):           # every open problem gets every sample (SAFE's K)
                chunk = open_[start:start + batch]
                convs = [repair_question(state[t]["question"], state[t]["task"], state[t]["said"]) for t in chunk]
                replies = decode(convs, 0.0 if attempt == 0 else TEMPERATURE, rnd * 100 + attempt, chunk[0], max_new)
                for t, (text, _stopped, _ntok) in zip(chunk, replies):
                    state[t]["asked"] += 1
                    task, why = cheap(text, P[t], state[t]["spec"])
                    if task is None:
                        refusals[why] = refusals.get(why, 0) + 1
                    else:
                        passing[t].append(task)
        flat = [(t, k) for t in open_ for k in range(len(passing[t]))]
        judged = judge([passing[t][k] for t, k in flat])
        by = {}
        for (t, k), v in zip(flat, judged):
            by.setdefault(t, []).append((passing[t][k], v))
        for t in open_:
            got = by.get(t, [])
            win = next(((task, v) for task, v in got if v["verified"]), None)
            if win is not None:
                state[t].update(task=win[0], verified=True, said=[], round=rnd)
                repaired += 1
            elif got:
                state[t].update(task=got[0][0], said=got[0][1]["said"], round=rnd)
                moved += 1
        counts["rounds"].append({"round": rnd, "sent back": len(open_), "repaired (Dafny verifies)": repaired,
                                 "replaced by a repair that passes the cheap gates": moved, "refusals": refusals})
    return state, counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True)
    ap.add_argument("--from", dest="source", nargs="+", required=True, metavar="TAG",
                    help="answer sets to take test-passing answers from (the first that has one, per problem)")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--ids-file", type=Path, required=True)
    ap.add_argument("--pool", choices=se.POOL_VERSIONS, default="v5")
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--samples", type=int, default=2)
    ap.add_argument("--lab", default=os.environ.get("T_LAB", ""))
    ap.add_argument("--remote-module", default="~/scratch/speccheck-repair/dafny_feedback.py")
    ap.add_argument("--max-new", type=int, default=1024)
    ap.add_argument("--batch", type=int, default=8)
    a = ap.parse_args(argv)
    if not a.lab:
        conf = HERE / "lab-workstation.conf"
        if conf.exists():
            for line in conf.read_text(encoding="utf-8").splitlines():
                if line.startswith("T_LAB="):
                    a.lab = line.split("=", 1)[1].strip()
    if not a.lab:
        ap.error("no --lab and no T_LAB: Dafny has to run somewhere")

    P = {str(k): v for k, v in se.pool(a.pool).items()}
    ids = [x for x in a.ids_file.read_text(encoding="utf-8").split() if x.strip()]
    candidates = {}
    for tid in ids:
        for tag in a.source:
            d = se.OUT_ROOT / se.model_tag(tag)
            try:
                e = json.loads((d / "extract.json").read_text(encoding="utf-8")).get(tid) or {}
                t = json.loads((d / "tests.json").read_text(encoding="utf-8")).get(tid) or {}
                raw = json.loads((d / "raw" / f"{tid}.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if e.get("stage") == "task" and t.get("overall") == "pass":
                candidates[tid] = {"question": raw["messages"][:2], "source": f"{tag}/{e['name']}",
                                   "task": harness.load(d / "tasks" / f"{e['name']}.json")}
                break
    print(f"proof_repair: {len(candidates)} of {len(ids)} problems have a test-passing answer", flush=True)

    import student_generate                                     # noqa: E402  (loads torch)
    d = se.outdir(a.tag)
    lock = se.tag_lock(d)
    if lock is None:
        raise SystemExit(f"proof_repair: another generator holds {a.tag}")
    model, tokenizer = student_generate.load(a.model)

    def decode(conversations, temperature, salt, first, max_new):
        return student_generate.decode(model, tokenizer, conversations, max_new, temperature, TOP_P,
                                       student_generate.problem_seed(salt, first))

    state, counts = run(candidates, P, decode, lambda tasks: lab_judge(tasks, a.lab, a.remote_module),
                        a.rounds, a.samples, a.batch, a.max_new)
    options = {"temperature": TEMPERATURE, "top_p": TOP_P, "num_predict": a.max_new, "decoder": "transformers-batched",
               "proof_repair": {"from": a.source, "rounds": a.rounds, "samples": a.samples, "judge": "dafny"}}
    for t, s in state.items():
        se.write_record(d / "raw" / f"{t}.json", {
            "task_id": t, "fn": P[t]["fn"], "model": str(a.model), "digest": "", "pool_version": a.pool,
            "prompt_version": "proof-repair", "options": options, "messages": s["question"],
            "reply": loop_dataset.fence(surface.print_task(s["task"]).strip()), "reply_tokens": None,
            "done_reason": "stop",
            "proof_repair": {"source": candidates[t]["source"], "dafny_verifies": s["verified"], "round": s["round"],
                             "asked": s["asked"]}})
    counts["dafny verifies at the end"] = sum(1 for s in state.values() if s["verified"])
    (d / "repair.json").write_text(json.dumps(counts, indent=1) + "\n", encoding="utf-8")
    lock.close()
    print("proof_repair: " + json.dumps(counts), flush=True)
    return 0


if __name__ == "__main__":                                      # pragma: no cover
    raise SystemExit(main())
