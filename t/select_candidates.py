#!/usr/bin/env python3
"""One answer per problem from K sampled candidates, seeing only the two examples the prompt showed.

    python3 t/select_candidates.py --candidates t/out/spec-experiment/TAG/candidates \\
        --split t/out/loop/split-v3.json --tag TAG-selected --samples 64 \\
        [--draws 24] [--seed 0] [--reply-format locallm|chat] [--greedy-tag TAG] [--ids-file F] [--train]

Input: `candidates/<id>.jsonl`, exactly --samples lines, one JSON object per sample:
`text` (the model's continuation, or the whole reply with --reply-format chat),
`logprob` (mean per-token log-probability up to the reply's cut, a finite float);
optional `options`, `model`, `messages`, `tokens`, `prompt_version`, `digest`.
`options` and `model` must be identical on every line of every file.

What it may see. The problem's data reaches this module through ONE function,
`shown_pairs()`, which returns only the pair of examples the prompt printed
(`example_holdout.shown_indices`, the prompt builder's own choice). Nothing here
reads the third assertion, the reference solution, or a kernel verdict, and
t/test_select_candidates.py proves it with a tripwire on the hidden point. That
is AlphaCode's rule, arXiv:2203.07814 section 2.2: filtering "should only be
based on information available to competitors", never the hidden tests. Note
that spec_check shapes its own draws from `points[0]`, which is the hidden test
on 20 of the 232 eval problems, so its check_task, check_points-over-the-entry
and exploit are never called; draws here are shaped by the shown arguments only.

How it chooses, from AlphaCode 4.6 and MBR-exec (arXiv:2204.11454, code at
github.com/facebookresearch/mbr-exec, sample_selectors.py):
  1. extract each sample the way spec_experiment.cmd_extract does (mirrored here;
     a test grades this module's output with cmd_extract and cmd_tests);
  2. tier "shown": keep the well-formed samples whose program passes both shown
     examples in t's interpreter (spec_experiment.run_point);
  3. group the survivors by their outputs on --draws inputs drawn with
     spec_check.draw, shaped by the shown arguments;
  4. take the largest group; among equal groups, the one holding the likeliest
     sample, then the earliest;
  5. write the member whose specification holds at the shown examples, then the
     likeliest, then the earliest.
Fallbacks: tier "well-formed" is the same grouping over every well-formed
sample (it cannot pass the tests, since every test-passing sample is in tier 1;
CodeT, arXiv:2207.10397 Appendix I, warns that trivial programs then form one
large wrong group), and tier "greedy" copies the --greedy-tag record's reply
verbatim. Every record of the written tag carries the same `options` and
`model`, so the mixed-options refusal in score_heldout (A6) holds; where an
answer came from is in its `selection` block and in `<tag>/selection.json`.

Two departures from the sources, INVENTED here and supported by the 2026-09-21
measurement on six greedy locallm arms (survivors of the shown-pair filter
defined on only 2 to 5 of the 24 draws all passed the hidden point):
  * on the drawn inputs a refusal verdict (requires-excluded, undefined, budget,
    crash) counts as a behaviour value, AlphaCode-style ("imperfect and even
    invalid test inputs can still be useful for grouping"), where MBR-exec's
    code scores a failed execution as matching nothing, not even itself; a
    sample with no output on ANY drawn input is a group of its own. The shown
    inputs are not part of the signature, so a program defined only at the
    examples cannot form a group with another one;
  * the written member must satisfy its own `ensures` at the shown examples
    (spec_check.check_points over the shown pair only): a program that returns
    the example's output where its specification is false can never be proven.
The tie-break is the highest mean per-token log-probability, where MBR-exec's
code uses sum_logprob and its paper reports mean log-likelihood degrading as
the sample count grows; here it only decides between equal-size groups.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import example_holdout                                          # noqa: E402
import fuzz_lower                                               # noqa: E402
import loop_filter                                              # noqa: E402
import spec_check                                               # noqa: E402
import spec_experiment as se                                    # noqa: E402
import surface                                                  # noqa: E402

VERSION = 1
# The cut loop_locallm.cmd_generate makes before it fences a reply (t/loop_locallm.py, the
# `re.split(...)` after sampling): a corpus whose documents start with a head teaches the model
# to emit the next document's head, so the reply ends where the next head begins.
REPLY_BOUNDARY = re.compile(r"\n\s*\n(?=Problem: |Signature: |t \d)")
REFUSED_TIERS = ("shown", "well-formed", "greedy")


def refuse(message: str):
    raise SystemExit(f"select_candidates: {message}")


# ------------------------------------------------------------- the one door to problem data --

def shown_pairs(ids: list[int], pool_version: str) -> dict[int, dict]:
    """Only the examples the prompt printed, for each id: {tid: {task_id, fn, shown_indices, points}}.

    The pool is a local variable here and nothing of it leaves but JSON copies of
    the shown points. An id missing from the pool is a refusal, not a skip: inside
    a git worktree pools v5 and v6 silently shrink to v4 when their untracked data
    is absent, and a skipped id would then vanish from the selected tag unnoticed.
    """
    pool = se.pool(pool_version)
    out = {}
    for tid in ids:
        entry = pool.get(tid)
        if entry is None:
            refuse(f"problem {tid} is not in pool {pool_version} (a worktree without the pool's data?)")
        idx = example_holdout.shown_indices(entry, 2)
        if not idx:
            refuse(f"problem {tid}: the prompt shows no example, so there is nothing to select on")
        points = json.loads(json.dumps([entry["points"][i] for i in idx]))
        out[tid] = {"task_id": tid, "fn": entry["fn"], "shown_indices": idx, "points": points}
    return out


# ------------------------------------------------------------------------------ the reply --

def reply_of(text: str, fmt: str) -> str:
    """The reply as cmd_generate would have recorded it: cut at the next head, head-stripped, fenced."""
    if fmt == "chat":
        return text
    body = REPLY_BOUNDARY.split(text, maxsplit=1)[0]
    body = loop_filter.strip_head(body)
    return "```t\n" + body.strip() + "\n```"


def extract(reply: str, tid: int, fn: str):
    """spec_experiment.cmd_extract's steps on one reply: (stage, task or None, name)."""
    block = se.find_block(reply)
    if block is None:
        return "no-block", None, None
    try:
        task = surface.parse(block)
    except Exception:                                           # noqa: BLE001
        return "parse", None, None
    prefix = (f"apps_{int(tid) - se.APPS_BASE}" if int(tid) >= se.APPS_BASE else
              f"he_{int(tid) - se.HUMANEVAL_BASE}" if int(tid) >= se.HUMANEVAL_BASE else f"mbpp_{tid}")
    name = f"{prefix}__{fn}"
    if not fuzz_lower.NAME_RE.match(name):
        name = prefix
    task = se.rename_task(task, name)
    try:
        errs = fuzz_lower.check_wf(task)
    except Exception as e:                                      # noqa: BLE001
        errs = [f"check_wf raised {type(e).__name__}: {e}"[:200]]
    if errs:
        return "wf", None, name
    # the round trip harness.load hands cmd_tests, so the interpreter sees the same task the grader will
    return "task", json.loads(json.dumps(task)), name


# ---------------------------------------------------------------------------- behaviour --

def draw_inputs(shown: list[dict], draws: int, seed: int, tid: int) -> list[dict]:
    """The inputs every sample of a problem is run on: spec_check.draw shaped by the shown arguments.

    The `like` value alternates between the shown points, never points[0] (spec_check's
    own choice, and the hidden test on 20 eval problems). The placeholder `expected` is
    a shown point's, a valid value of the right kind; only the output matters here.
    """
    rnd = random.Random(f"select_candidates:{seed}:{tid}")
    kinds = [kind for kind, _value in shown[0]["args"]]
    inputs = []
    for j in range(draws):
        like = shown[j % len(shown)]
        args = []
        for kind, (_kind, value) in zip(kinds, like["args"]):
            drawn = spec_check.draw(kind, rnd, value)
            if drawn is None:
                refuse(f"problem {tid}: spec_check.draw has no draw for kind {kind!r}")
            args.append([kind, drawn])
        inputs.append({"args": args, "expected": like["expected"]})
    return inputs


def behaviour(task: dict, inputs: list[dict]):
    """The signature on the drawn inputs, and whether any draw produced an output."""
    signature, any_output = [], False
    for point in inputs:
        result = se.run_point(task, point)
        if result["verdict"] in ("pass", "fail"):
            signature.append(("=", json.dumps(result["got"], sort_keys=True)))
            any_output = True
        else:
            signature.append(("!", result["verdict"]))
    return tuple(signature), any_output


def passes_shown(task: dict, shown: list[dict]) -> bool:
    return all(se.run_point(task, point)["verdict"] == "pass" for point in shown)


def spec_holds_at_shown(task: dict, shown: list[dict]) -> bool:
    """The specification is not contradicted at a shown example. check_points is handed an entry
    holding ONLY the shown pair; it never sees the problem's other assertions."""
    return spec_check.check_points(task, {"points": shown}).get("points_failed", 0) == 0


def choose(members: list[dict], inputs: list[dict], shown: list[dict]) -> dict:
    """Group by behaviour, take the largest group, write its best member."""
    groups: dict = {}
    for member in members:
        signature, any_output = behaviour(member["task"], inputs)
        key = signature if any_output else ("none", member["index"])
        groups.setdefault(key, []).append(member)
    ranked = sorted(groups.values(),
                    key=lambda g: (-len(g), -max(m["logprob"] for m in g), min(m["index"] for m in g)))
    best = ranked[0]
    ok = {m["index"]: spec_holds_at_shown(m["task"], shown) for m in best}
    representative = sorted(best, key=lambda m: (not ok[m["index"]], -m["logprob"], m["index"]))[0]
    return {"member": representative, "cluster_size": len(best), "clusters": [len(g) for g in ranked],
            "spec_ok": ok[representative["index"]]}


# ------------------------------------------------------------------------------ the run --

def read_candidates(path: Path, samples: int) -> list[dict]:
    if not path.is_file():
        refuse(f"no candidates file {path.name} under {path.parent}")
    lines = path.read_text(encoding="utf-8").splitlines()
    rows = []
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as e:
            refuse(f"{path.name}:{number}: not JSON ({e.msg})")
        if not isinstance(row, dict) or not isinstance(row.get("text"), str):
            refuse(f"{path.name}:{number}: a sample needs a string 'text'")
        logprob = row.get("logprob")
        if isinstance(logprob, bool) or not isinstance(logprob, (int, float)) or not math.isfinite(logprob):
            refuse(f"{path.name}:{number}: a sample needs a finite 'logprob'")
        rows.append(row)
    if not rows:
        refuse(f"{path.name} holds no samples")
    if len(rows) != samples:
        refuse(f"{path.name} holds {len(rows)} samples, --samples says {samples}")
    return rows


def uniform(rows_by_id: dict[int, list[dict]], field: str):
    """The one value a field takes across every line of every file, or a refusal."""
    seen = {}
    for tid, rows in rows_by_id.items():
        for number, row in enumerate(rows, 1):
            key = json.dumps(row.get(field), sort_keys=True)
            seen.setdefault(key, (tid, number))
    if len(seen) > 1:
        first, second = list(seen.items())[:2]
        refuse(f"mixed {field} across the candidates: {first[1][0]}.jsonl:{first[1][1]} has {first[0]} "
               f"and {second[1][0]}.jsonl:{second[1][1]} has {second[0]}")
    return json.loads(next(iter(seen)))


def greedy_record(tag: str, tid: int, fn: str) -> dict:
    path = se.OUT_ROOT / se.model_tag(tag) / "raw" / f"{tid}.json"
    if not path.is_file():
        refuse(f"problem {tid} needs the greedy answer and {path.name} is not under the greedy tag {tag}")
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("task_id") != tid or record.get("fn") != fn:
        refuse(f"greedy record {tag}/{path.name}: task_id {record.get('task_id')!r} fn {record.get('fn')!r} "
               f"do not match problem {tid} fn {fn!r}")
    if not isinstance(record.get("reply"), str):
        refuse(f"greedy record {tag}/{path.name} has no reply")
    return record


def select(ids: list[int], rows_by_id: dict[int, list[dict]], shown: dict[int, dict], draws: int, seed: int,
           fmt: str, greedy_tag: str | None) -> dict[int, dict]:
    """Everything computed before anything is written, so a refusal writes nothing."""
    chosen = {}
    for tid in ids:
        pair = shown[tid]
        members = []
        counts = {"samples": len(rows_by_id[tid]), "well_formed": 0, "shown_pass": 0}
        for index, row in enumerate(rows_by_id[tid]):
            reply = reply_of(row["text"], fmt)
            stage, task, _name = extract(reply, tid, pair["fn"])
            if task is None:
                continue
            counts["well_formed"] += 1
            shown_ok = passes_shown(task, pair["points"])
            counts["shown_pass"] += shown_ok
            members.append({"index": index, "row": row, "reply": reply, "task": task,
                            "logprob": float(row["logprob"]), "shown_ok": shown_ok})
        inputs = draw_inputs(pair["points"], draws, seed, tid) if members else []
        tier1 = [m for m in members if m["shown_ok"]]
        if tier1:
            tier, pick = "shown", choose(tier1, inputs, pair["points"])
        elif members:
            tier, pick = "well-formed", choose(members, inputs, pair["points"])
        else:
            tier, pick = "greedy", None
        selection = {"tier": tier, "counts": counts, "shown_indices": pair["shown_indices"]}
        if pick is not None:
            member = pick["member"]
            selection.update({"sample": member["index"], "logprob": member["logprob"],
                              "tokens": member["row"].get("tokens"), "cluster_size": pick["cluster_size"],
                              "clusters": pick["clusters"], "spec_ok": pick["spec_ok"]})
            chosen[tid] = {"reply": member["reply"], "row": member["row"], "selection": selection}
        else:
            if not greedy_tag:
                refuse(f"problem {tid}: no well-formed sample and no --greedy-tag to fall back on")
            record = greedy_record(greedy_tag, tid, pair["fn"])
            selection.update({"sample": None, "logprob": None, "tokens": None, "cluster_size": 0,
                              "clusters": [], "spec_ok": None,
                              "origin": {"tag": greedy_tag, "model": record.get("model"),
                                         "options": record.get("options"),
                                         "done_reason": record.get("done_reason")}})
            chosen[tid] = {"reply": record["reply"], "row": {}, "selection": selection}
    return chosen


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--candidates", type=Path, required=True, help="directory of <id>.jsonl candidate files")
    ap.add_argument("--split", type=Path, required=True, help="the split whose ids (and pool) to select for")
    ap.add_argument("--ids-file", type=Path, help="select for these ids instead of the split's")
    ap.add_argument("--train", action="store_true", help="the split's train_ids instead of its eval_ids")
    ap.add_argument("--pool", default="", help="pool version; default the split's")
    ap.add_argument("--tag", required=True, help="the answer set to write under out/spec-experiment")
    ap.add_argument("--samples", type=int, required=True, help="exactly this many lines per candidates file")
    ap.add_argument("--draws", type=int, default=24)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--reply-format", choices=("locallm", "chat"), default="locallm")
    ap.add_argument("--greedy-tag", default="", help="fall back to this tag's reply when no sample is well formed")
    a = ap.parse_args(argv)
    if a.samples < 1 or a.draws < 1:
        refuse("--samples and --draws must be positive")
    try:
        split = json.loads(a.split.read_text(encoding="utf-8"))
        which = "train_ids" if a.train else "eval_ids"
        ids = sorted(int(i) for i in split[which])
    except (OSError, KeyError, TypeError, ValueError) as e:
        refuse(f"cannot read the split {a.split}: {e}")
    if a.ids_file:
        ids = sorted(int(x) for x in a.ids_file.read_text(encoding="utf-8").split())
    if not ids:
        refuse("no ids to select for")
    pool_version = a.pool or split.get("pool", "v1")
    out = se.OUT_ROOT / se.model_tag(a.tag)
    present = sorted(p.name for p in (out / "raw").glob("*")) if (out / "raw").is_dir() else []
    if present or (out / "selection.json").exists():
        refuse(f"{out} already holds answers ({present[:3]}...); select into a fresh tag")

    rows_by_id = {tid: read_candidates(a.candidates / f"{tid}.jsonl", a.samples) for tid in ids}
    candidate_options = uniform(rows_by_id, "options")
    candidate_model = uniform(rows_by_id, "model")
    shown = shown_pairs(ids, pool_version)
    chosen = select(ids, rows_by_id, shown, a.draws, a.seed, a.reply_format, a.greedy_tag or None)

    options = {"selector": "select_candidates", "version": VERSION, "draws": a.draws, "seed": a.seed,
               "pool": pool_version, "reply_format": a.reply_format, "samples": a.samples,
               "candidate_options": candidate_options, "candidate_model": candidate_model,
               "greedy_tag": a.greedy_tag or None}
    model = candidate_model if isinstance(candidate_model, str) and candidate_model else f"select:{a.tag}"
    first_rows = [rows[0] for rows in rows_by_id.values()]
    prompt_version = next((r.get("prompt_version") for r in first_rows if r.get("prompt_version")), "candidates")
    digest = next((r.get("digest") for r in first_rows if r.get("digest")), "")

    d = se.outdir(a.tag)
    tiers = {tier: 0 for tier in REFUSED_TIERS}
    per_id = {}
    for tid in ids:
        pick = chosen[tid]
        record = {"task_id": tid, "fn": shown[tid]["fn"], "model": model, "digest": digest,
                  "pool_version": pool_version, "prompt_version": prompt_version, "options": options,
                  "messages": pick["row"].get("messages") or [], "reply": pick["reply"],
                  "done_reason": "selected", "selection": pick["selection"]}
        (d / "raw" / f"{tid}.json").write_text(json.dumps(record, indent=1), encoding="utf-8")
        tiers[pick["selection"]["tier"]] += 1
        per_id[str(tid)] = pick["selection"]
    tasks_dir = d / "tasks"
    if tasks_dir.is_dir() and not any(tasks_dir.iterdir()):
        tasks_dir.rmdir()             # grade_lab.sh skips extraction when tasks/*.json exists; leave nothing there
    (d / "selection.json").write_text(json.dumps(
        {"tag": a.tag, "candidates": str(a.candidates), "options": options, "tiers": tiers, "per_id": per_id},
        indent=1, sort_keys=True), encoding="utf-8")
    print(f"select_candidates: {len(ids)} problems into {d}: " +
          ", ".join(f"{tier} {n}" for tier, n in tiers.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
