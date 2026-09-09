#!/usr/bin/env python3
"""loop_dataset.py -- build the verdict dataset for round 1 of the loop.

The training thesis (spec_experiment.py's docstring): a model can write a t
task, spec included, from an English problem, and the seven kernels grading
it give a signal worth training on. This module turns round 0's measurements
into that signal: preference pairs (chosen task, rejected BUGGY task) and an
SFT set of chosen tasks alone.

Two positive sources, both gated the same way -- a task VERIFIES with a
REFUTED twin in at least four of the seven kernels (parse_kernel_table's
"verified / refuted" cell) AND passes every one of the problem's own MBPP
tests:

  round0-7b  every task in out/spec-experiment/qwen2.5-coder-7b that clears
             the gate. Its prompt is the recorded messages in raw/<id>.json
             (verbatim, so training sees exactly what round 0 saw); its
             chosen answer is tasks/<name>.json re-printed with surface's own
             printer, not the model's raw reply text (whitespace, comments
             and formatting the parser accepts but the printer normalizes
             away are not something to train the model to reproduce).

  lifted     the MBPP-DFY tasks lifted from DafnyBench
             (out/lifted-tasks/dafny-synthesis_task_id_<N>.*.json) whose row
             in COVERAGE-lifted-785.md clears the same four-of-seven bar.
             Their English problem is the MBPP record with the same
             task_id; the prompt is spec_experiment.build_prompt on a
             pool()-shaped entry, so the format matches round 0's exactly.
             A lifted task_id that does not pass pool()'s own fragment
             filter (parse_assertion on every test, single callee, int/bool
             result) cannot be prompted this way and is skipped, named.

Negatives are bugs, not paraphrases: harness.twin_cached(task) is the
primary twin (the one kernels.md's twin column actually graded, so its
refutation record is real), then harness.EXTENSIONAL's other rungs are
walked in their fixed order and every further candidate whose
interp.Reference(task).witness(candidate) has "_ens": true (the ensures is
actually falsified at that input, not merely a different value) is another
bug with a witness. Capped at 4 negatives per positive, primary first, then
ladder order, deterministic throughout: sorted task_id iteration, no
randomness anywhere in this file.

Outputs under out/loop/: pairs.jsonl, sft.jsonl, heldout.json, DATASET.md.
Standard library only, plus t's own modules (harness, interp, mbpp_dfy,
spec_experiment, surface).

    python3 loop_dataset.py
"""
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import harness          # noqa: E402
import interp           # noqa: E402
import mbpp_dfy         # noqa: E402
import spec_experiment  # noqa: E402
import surface          # noqa: E402

OUT = HERE / "out" / "loop"
KERNEL_GATE = 4          # of 7 columns must read "verified / refuted"
MAX_NEG = 4               # negatives per positive, primary included
ROUND0_TAG = "qwen2.5-coder:7b"
LIFTED_NAME_RE = re.compile(r"^dafny-synthesis_task_id_(\d+)\.")


def fence(text: str) -> str:
    return "```t\n" + text.rstrip() + "\n```"


def kernels_verified_refuted(row: dict, cols: list[str]) -> int:
    return sum(1 for c in cols if row.get(c) == "verified / refuted")


def refuted_kernels(row: dict, cols: list[str]) -> list[str]:
    out = []
    for c in cols:
        cell = row.get(c, "")
        if " / " in cell and cell.split(" / ", 1)[1] == "refuted":
            out.append(c)
    return sorted(out)


# --------------------------------------------------------------- negatives --

def build_negatives(task: dict) -> list[tuple[list, str, dict]]:
    """(twin_body, operator_tag, witness) up to MAX_NEG, primary twin first
    (the one kernels.md graded), then the rest of harness.EXTENSIONAL's
    ladder in its fixed order, keeping only candidates whose witness
    falsifies `ensures` (_ens is True). Deterministic: no randomness, no set
    iteration."""
    negs: list[tuple[list, str, dict]] = []
    seen: set[str] = set()

    primary_body, primary_op, primary_w = harness.twin_cached(task)
    if primary_body is not None:
        negs.append((primary_body, primary_op, primary_w))
        seen.add(json.dumps(primary_body, sort_keys=True))

    if len(negs) >= MAX_NEG:
        return negs

    ref = interp.Reference(task)
    if not ref.points:
        return negs

    scope = harness._scope(task)
    for op_name, gen in harness.EXTENSIONAL:
        for k, twin in enumerate(gen(task["body"], scope)):
            if len(negs) >= MAX_NEG:
                return negs
            key = json.dumps(twin, sort_keys=True)
            if key in seen:
                continue
            w = ref.witness(twin)
            if w is not None and w.get("_ens") is True:
                negs.append((twin, harness._tag(op_name, k), w))
                seen.add(key)
    return negs


def twin_task_text(task: dict, twin_body: list) -> str:
    t2 = copy.deepcopy(task)
    t2["body"] = twin_body
    return fence(surface.print_task(t2))


# ------------------------------------------------------------ round0-7b --

def round0_positives(pool: dict) -> tuple[list[dict], list[tuple]]:
    d = spec_experiment.outdir(ROUND0_TAG)
    ext = json.loads((d / "extract.json").read_text(encoding="utf-8"))
    tests_path = d / "tests.json"
    tests = json.loads(tests_path.read_text(encoding="utf-8")) if tests_path.exists() else {}
    cols, cells = spec_experiment.parse_kernel_table(d / "kernels.md")

    positives, skipped = [], []
    for tid_s in sorted(ext, key=int):
        e = ext[tid_s]
        if e["stage"] != "task":
            continue
        tid = int(tid_s)
        name = e["name"]
        row = cells.get(name, {})
        k = kernels_verified_refuted(row, cols)
        overall = tests.get(tid_s, {}).get("overall")
        if k < KERNEL_GATE:
            skipped.append((tid, name, "round0-7b", f"kernels={k}<{KERNEL_GATE}"))
            continue
        if overall != "pass":
            skipped.append((tid, name, "round0-7b", f"tests={overall}"))
            continue
        raw = json.loads((d / "raw" / f"{tid}.json").read_text(encoding="utf-8"))
        task = harness.load(d / "tasks" / f"{name}.json")
        positives.append({
            "source": "round0-7b", "task_id": tid, "name": name, "task": task,
            "prompt": raw["messages"],
            "chosen": fence(surface.print_task(task)),
            "refuted_kernels": refuted_kernels(row, cols),
            "kernel_count": k,
        })
    return positives, skipped


# -------------------------------------------------------------- lifted --

def lifted_positives(pool: dict) -> tuple[list[dict], list[tuple]]:
    cov_path = HERE / "COVERAGE-lifted-785.md"
    cols, cells = spec_experiment.parse_kernel_table(cov_path)
    lifted_dir = HERE / "out" / "lifted-tasks"

    found = []
    for p in sorted(lifted_dir.glob("dafny-synthesis_task_id_*.json")):
        m = LIFTED_NAME_RE.match(p.name)
        if not m:
            continue
        found.append((int(m.group(1)), p))
    found.sort(key=lambda t: t[0])

    positives, skipped = [], []
    for tid, path in found:
        task = harness.load(path)
        name = task["name"]
        row = cells.get(name, {})
        k = kernels_verified_refuted(row, cols)
        if k < KERNEL_GATE:
            skipped.append((tid, name, "lifted", f"kernels={k}<{KERNEL_GATE}"))
            continue
        entry = pool.get(tid)
        if entry is None:
            skipped.append((tid, name, "lifted", "not-in-pool"))
            continue
        positives.append({
            "source": "lifted", "task_id": tid, "name": name, "task": task,
            "prompt": spec_experiment.build_prompt(entry),
            "chosen": fence(surface.print_task(task)),
            "refuted_kernels": refuted_kernels(row, cols),
            "kernel_count": k,
        })
    return positives, skipped


# ------------------------------------------------------------------ main --

def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    pool = spec_experiment.pool()

    r0_pos, r0_skip = round0_positives(pool)
    lf_pos, lf_skip = lifted_positives(pool)
    positives = r0_pos + lf_pos
    skipped = r0_skip + lf_skip

    pairs = []
    op_tally: dict[str, int] = {}
    no_negatives = []
    for pos in positives:
        negs = build_negatives(pos["task"])
        if not negs:
            no_negatives.append((pos["task_id"], pos["name"], pos["source"]))
            continue
        for body, op, w in negs:
            base_op = op.split("#", 1)[0]
            op_tally[base_op] = op_tally.get(base_op, 0) + 1
            pairs.append({
                "prompt": pos["prompt"],
                "chosen": pos["chosen"],
                "rejected": twin_task_text(pos["task"], body),
                "source": pos["source"],
                "task_id": pos["task_id"],
                "task": pos["name"],
                "operator": op,
                "witness": w,
                "refuted_kernels": pos["refuted_kernels"],
            })

    # sft.jsonl: one record per positive that produced at least one pair
    # (a positive with zero negatives has nothing to contrast and is left
    # out of sft.jsonl too, named in DATASET.md, since it never got graded
    # as a bug-bearing task).
    have_pair_ids = {(p["task_id"], p["task"], p["source"]) for p in pairs}
    sft = []
    for pos in positives:
        key = (pos["task_id"], pos["name"], pos["source"])
        if key not in have_pair_ids:
            continue
        sft.append({
            "prompt": pos["prompt"], "chosen": pos["chosen"],
            "source": pos["source"], "task_id": pos["task_id"],
            "task": pos["name"],
        })

    # sort everything deterministically before writing
    pairs.sort(key=lambda p: (p["task_id"], p["source"], p["task"], p["operator"]))
    sft.sort(key=lambda s: (s["task_id"], s["source"], s["task"]))

    (OUT / "pairs.jsonl").write_text(
        "\n".join(json.dumps(p, sort_keys=True) for p in pairs) + ("\n" if pairs else ""),
        encoding="utf-8")
    (OUT / "sft.jsonl").write_text(
        "\n".join(json.dumps(s, sort_keys=True) for s in sft) + ("\n" if sft else ""),
        encoding="utf-8")

    used_ids = sorted({p["task_id"] for p in positives} & set(pool))
    heldout_ids = sorted(set(pool) - set(used_ids))
    heldout = {
        "pool_size": len(pool),
        "used_task_ids": used_ids,
        "heldout_task_ids": heldout_ids,
    }
    (OUT / "heldout.json").write_text(json.dumps(heldout, indent=1) + "\n", encoding="utf-8")

    # ------------------------------------------------------------- report
    by_source = {}
    for pos in positives:
        by_source[pos["source"]] = by_source.get(pos["source"], 0) + 1
    pairs_by_source = {}
    for p in pairs:
        pairs_by_source[p["source"]] = pairs_by_source.get(p["source"], 0) + 1

    lines = []
    L = lines.append
    L("# The loop dataset -- round 1 preference pairs and SFT set")
    L("")
    L("Built by `loop_dataset.py` from round 0's spec experiment "
      f"(`out/spec-experiment/{spec_experiment.model_tag(ROUND0_TAG)}/`) and the "
      "lifted MBPP-DFY tasks (`out/lifted-tasks/`, graded in "
      "`COVERAGE-lifted-785.md`). A positive verifies with a refuted twin "
      f"in at least {KERNEL_GATE} of 7 kernels and passes every one of the "
      "problem's own MBPP tests (round0-7b) or clears the same kernel bar "
      "(lifted, which has no separate MBPP test stage of its own -- the "
      "lifter's own extraction from a verified Dafny program is the test).")
    L("")
    L("## Positives per source")
    L("")
    L("| source | positives | pairs (negatives) | in sft.jsonl |")
    L("|---|---:|---:|---:|")
    for src in sorted(by_source):
        n_sft = sum(1 for s in sft if s["source"] == src)
        L(f"| {src} | {by_source[src]} | {pairs_by_source.get(src, 0)} | {n_sft} |")
    L(f"| **total** | **{len(positives)}** | **{len(pairs)}** | **{len(sft)}** |")
    L("")
    if no_negatives:
        L(f"{len(no_negatives)} positive(s) produced zero negatives (no twin "
          "on any rung falsified `ensures` beyond the primary, or the "
          "primary itself was refused) and are excluded from both "
          "pairs.jsonl and sft.jsonl:")
        L("")
        for tid, name, src in sorted(no_negatives):
            L(f"- {tid} `{name}` ({src})")
        L("")
    L("## Pairs per twin operator (base tag, `#k` rungs folded together)")
    L("")
    L("| operator | pairs |")
    L("|---|---:|")
    for op in sorted(op_tally):
        L(f"| {op} | {op_tally[op]} |")
    L("")
    L("## Held-out split")
    L("")
    L(f"Pool (MBPP problems whose tests are entirely in t's fragment, "
      f"`spec_experiment.pool()`): **{len(pool)}**. Used in at least one "
      f"positive: **{len(used_ids)}**. Held out for round-1 evaluation "
      f"(never trained on): **{len(heldout_ids)}**. Full lists in "
      "`heldout.json`.")
    L("")
    if skipped:
        L(f"## {len(skipped)} candidates that did not clear the gate")
        L("")
        L("| task_id | task | source | why |")
        L("|---:|---|---|---|")
        for tid, name, src, why in sorted(skipped):
            L(f"| {tid} | {name} | {src} | {why} |")
        L("")
    L("## Regenerating this dataset")
    L("")
    L("Round 0 (already on disk under `out/spec-experiment/qwen2.5-coder-7b/`):")
    L("")
    L("```")
    L("python3 spec_experiment.py generate --model qwen2.5-coder:7b")
    L("python3 spec_experiment.py extract  --model qwen2.5-coder:7b")
    L("python3 spec_experiment.py tests    --model qwen2.5-coder:7b")
    L("python3 run_par.py --tasks out/spec-experiment/qwen2.5-coder-7b/tasks \\")
    L("    --out out/spec-experiment/qwen2.5-coder-7b/kernels \\")
    L("    --table out/spec-experiment/qwen2.5-coder-7b/kernels.md")
    L("```")
    L("")
    L("Lifted tasks and `COVERAGE-lifted-785.md` are the lifter pipeline's "
      "own output (`lift_check.py` / `coverage_census.py`), not regenerated "
      "by this script.")
    L("")
    L("Then, deterministically, no arguments:")
    L("")
    L("```")
    L("python3 loop_dataset.py")
    L("```")
    L("")
    (OUT / "DATASET.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"positives: {len(positives)} ({', '.join(f'{k}={v}' for k, v in sorted(by_source.items()))})")
    print(f"pairs: {len(pairs)} ({', '.join(f'{k}={v}' for k, v in sorted(pairs_by_source.items()))})")
    print(f"sft: {len(sft)}")
    print(f"operators: {', '.join(f'{k}={v}' for k, v in sorted(op_tally.items()))}")
    print(f"pool: {len(pool)}  used: {len(used_ids)}  heldout: {len(heldout_ids)}")
    if skipped:
        print(f"skipped: {len(skipped)} candidates below the gate (see DATASET.md)")
    if no_negatives:
        print(f"no-negatives: {len(no_negatives)} positives excluded (see DATASET.md)")
    print(f"wrote {OUT / 'pairs.jsonl'}, {OUT / 'sft.jsonl'}, {OUT / 'heldout.json'}, {OUT / 'DATASET.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
