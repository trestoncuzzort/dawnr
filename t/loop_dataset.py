#!/usr/bin/env python3
"""loop_dataset.py -- build the verdict dataset for round 1 of the loop.

The training thesis (spec_experiment.py's docstring): a model can write a t
task, spec included, from an English problem, and the seven kernels grading
it give a signal worth training on. This module turns round 0's measurements
into that signal: preference pairs (chosen task, rejected BUGGY task) and an
SFT set of chosen tasks alone.

The argument-free mode reproduces the legacy round-1 gate, without current
spec-check evidence. It is not an acceptance gate for new training data.
Its two positive sources are gated the same way -- a task VERIFIES with a
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

A second mode, --from-samples, builds a later round's dataset from K sampled
answers per problem (one tag directory per sample, out/spec-experiment/<tag>/
in spec_experiment.py's own layout) instead of round 0 and the lifted tasks.
Positives and negatives are graded per problem over the fixed train/eval
split (out/loop/split.json); only the train split yields pairs, the eval
split is graded and reported as a pass@K measurement of the sampler. See
run_from_samples's docstring for the exact rules. New positives require all
seven named clean kernels and explicit spec agreement for the current task
hash, problem ID and pool, with at least one valid draw. Imported pairs must
pass the same checks and match a currently admissible negative.

    python3 loop_dataset.py --from-samples TAG0 TAG1 ... \\
        --split out/loop/split.json --min-kernels 7 --out-suffix r2 \\
        --include out/loop/pairs.jsonl
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import harness          # noqa: E402
import interp           # noqa: E402
import mbpp_dfy         # noqa: E402
import spec_experiment  # noqa: E402
import spec_check       # noqa: E402
import surface          # noqa: E402

OUT = HERE / "out" / "loop"
KERNEL_GATE = 4          # of 7 columns must read "verified / refuted"
MAX_NEG = 4               # negatives per positive, primary included
ROUND0_TAG = "qwen2.5-coder:7b"
LIFTED_NAME_RE = re.compile(r"^dafny-synthesis_task_id_(\d+)\.")

# --from-samples mode: per-positive negative caps (priority a, b, c below).
SAMPLES_MAX_TWINS = 2
SAMPLES_MAX_FAIL = 2
SAMPLES_MAX_MALFORMED = 1
# 2026-09-18, from the round 5 score: the student writes 42 well-formed answers to Phi-4-mini's 12 and turns
# 11 of them into test-passing answers against Phi's 6 -- and then converts only 3 of those 11 into clean ones
# where Phi converts 3 of 6. The gate it loses at is the proof, not the notation, and until now no pair ever
# showed it that gate: every rejected side was a program that was WRONG (a twin, a test-failing answer, a
# malformed reply). A program that is right and cannot be proved was never in the training signal at all.
ALL_KERNELS = 7                      # a clean answer is verified with its twin refuted in every one of them
SAMPLES_MAX_UNPROVED = 2
# and the round 5 student's 12 answers that all seven proved while disagreeing with the problem, up from 8:
# a specification the provers like and the problem does not is its own failure mode and its own negative
SAMPLES_MAX_DISAGREE = 1


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

def build_negatives(task: dict, max_neg: int = MAX_NEG) -> list[tuple[list, str, dict]]:
    """(twin_body, operator_tag, witness) up to max_neg, primary twin first
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

    if len(negs) >= max_neg:
        return negs

    ref = interp.Reference(task)
    if not ref.points:
        return negs

    scope = harness._scope(task)
    for op_name, gen in harness.EXTENSIONAL:
        for k, twin in enumerate(gen(task["body"], scope)):
            if len(negs) >= max_neg:
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

def run_default() -> int:
    """The original, argument-free round-1 build: round0-7b + lifted.
    Byte-identical to before --from-samples was added."""
    print("Legacy round-1 reproduction: four-kernel gate, without current spec evidence; "
          "this is not the gate for new training rounds.")
    OUT.mkdir(parents=True, exist_ok=True)
    pool = spec_experiment.pool()

    r0_pos, r0_skip = round0_positives(pool)
    lf_pos, lf_skip = lifted_positives(pool)
    positives = r0_pos + lf_pos
    # A2: a train id with a same-task held-out twin (t/decontamination-2026-09-21.json)
    # never enters a pool file; the corpus builder and preflight refuse it too
    import loop_filter
    listed = loop_filter.decontamination().exclude_train_ids
    for p in positives:
        if int(p["task_id"]) in listed:
            r0_skip.append((p["task_id"], p["name"], p["source"], "decontamination: same-task held-out twin"))
    positives = [p for p in positives if int(p["task_id"]) not in listed]
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


# --------------------------------------------------------- --from-samples --
#
# A later round samples K answers per problem into K tag directories
# (out/spec-experiment/<tag>/, spec_experiment.py's own layout: raw/,
# tasks/, extract.json, tests.json, kernels.md). This mode reads those K
# tags in the order given -- sample index k is position in --from-samples --
# and builds pairs the same way run_default() does, but per problem instead
# of per already-known-good task, with the tests folded into the same bar
# as the kernels, and only over the fixed train split (out/loop/split.json).

def load_tag_dir(tag: str) -> dict:
    """One sample source: a tag directory in spec_experiment.py's layout.
    Missing files read as empty, the same as spec_experiment.py's own
    stages do before they have run."""
    d = spec_experiment.outdir(tag)
    ext_path = d / "extract.json"
    ext = json.loads(ext_path.read_text(encoding="utf-8")) if ext_path.exists() else {}
    tests_path = d / "tests.json"
    tests = json.loads(tests_path.read_text(encoding="utf-8")) if tests_path.exists() else {}
    cols, cells = spec_experiment.parse_kernel_table(d / "kernels.md")
    return {"tag": tag, "dir": d, "extract": ext, "tests": tests, "cols": cols, "cells": cells}


def grade_sample(tagdata: dict, k: int, tid: int) -> dict | None:
    """One (tag, sample-index) answer to one problem, graded the three ways
    step 1 needs: well-formed? (extract.json has a name for it), tests.json's
    overall verdict, kernels.md's verified/refuted count and its printed t
    text. None if this tag has no recorded answer for tid at all."""
    e = tagdata["extract"].get(str(tid))
    if e is None:
        return None
    raw_path = tagdata["dir"] / "raw" / f"{tid}.json"
    raw = json.loads(raw_path.read_text(encoding="utf-8")) if raw_path.exists() else {}
    rec = {"tag": tagdata["tag"], "k": k, "task_id": tid, "stage": e["stage"],
           "prompt": raw.get("messages")}
    if e["stage"] == "task":
        name = e["name"]
        task = harness.load(tagdata["dir"] / "tasks" / f"{name}.json")
        row = tagdata["cells"].get(name, {})
        overall = tagdata["tests"].get(str(tid), {}).get("overall")
        rec.update({
            "wellformed": True, "name": name, "task": task,
            "text": fence(surface.print_task(task)),
            "tests_overall": overall, "tests_pass": overall == "pass",
            "kernel_count": kernels_verified_refuted(row, tagdata["cols"]),
            "kernel_columns": tagdata["cols"], "kernel_row": row,
            "refuted_kernels": refuted_kernels(row, tagdata["cols"]),
        })
    else:
        rec.update({"wellformed": False, "tests_pass": False, "kernel_count": 0})
        block = spec_experiment.find_block(raw.get("reply", "")) if raw else None
        rec["malformed_text"] = fence(block) if block else None
    return rec


def gather_samples(tag_dirs: list[dict], tid: int) -> list[dict]:
    out = []
    for k, tagdata in enumerate(tag_dirs):
        s = grade_sample(tagdata, k, tid)
        if s is not None:
            out.append(s)
    return out


def dedup_wellformed(samples: list[dict]) -> list[dict]:
    """Step 1's dedup rule: the first (lowest sample index) well-formed
    sample wins per distinct printed t text. Malformed samples pass through
    unchanged -- they have no parsed text to compare, so each (tag, k)
    malformed reply stays its own candidate for priority (c) below."""
    seen: set[str] = set()
    out = []
    for s in samples:
        if s["wellformed"]:
            if s["text"] in seen:
                continue
            seen.add(s["text"])
        out.append(s)
    return out


def load_spec_results() -> dict:
    """Legacy tag membership and an absent disagreement are not evidence."""
    path = HERE / "out" / "spec-disagree.json"
    try:
        results = json.loads(path.read_text(encoding="utf-8")).get("results", {})
    except FileNotFoundError:
        return {}
    if not isinstance(results, dict):
        raise ValueError("spec-check results must be an object")
    return results


# Statuses that mean check_task produced NO verdict because the problem's
# reference solution could not be exercised, as opposed to a verdict against the
# specification. Only these may fall back to the problem's own stated examples.
#
# PRIOR ART, and it splits. "Correct Tests Are Not Enough: Measuring and Training
# Oracle Conversion in Specification-Based Test Generation"
# (arXiv:2609.05879) builds the same distinction and states it directly:
# "Reference timeouts or disagreements invalidate that input's oracle, not treated
# as negative evidence." That is exactly the half of this rule that says a
# reference which cannot run is a missing verdict, not a failing one.
#
# It takes the OPPOSITE choice on the other half. Where the oracle is invalid it
# sets the detection set to the empty set -- it drops the case -- and it removes
# stated examples and sample I/O from its prompts on purpose rather than falling
# back to them. Under that design the 14 string answers stay out.
#
# Admitting them on a weaker, labelled tier is a deliberate divergence, and the
# reason is the objective. That paper is measuring how well a model generates
# tests, where dropping an uncheckable case costs only sample size. Here the
# supervised pool is 75 examples and is the binding constraint on every locallm
# round, so 14 answers that passed their tests and read verified / refuted in all
# seven kernels are worth admitting with their provenance recorded. The tier is
# visible in the evidence, not hidden: a reader can separate the two populations
# by asking which rows have status "agrees".
#
# That paper also names this project's own scoreboard column. Its
# Oracle-Conversion Efficiency, OCE = sum|E_q| / sum|P_q| over potential and
# effective detection sets, is the published form of "converts", and it measures a
# conversion gap of 11.83 points, 24.06% input kill against 12.23% full kill.
# "arity differs from the problem" and "interpreter refused" are deliberately NOT
# here: the first means the answer is shaped for a different problem and the
# second that the specification could not be evaluated, and neither is a missing
# verdict. Measured 2026-09-20: 0 rows in either status hold at their examples
# anyway, so nothing is lost by excluding them and a real signal is kept.
NO_REFERENCE_VERDICT = frozenset({"no valid draws", "reference result has no t value"})


def positive_rejection(sample: dict, results: dict, pool_name: str | None = None) -> str | None:
    """First failed gate, or None for a current, explicitly checked positive."""
    if not sample["wellformed"]:
        return "not-wellformed"
    if not sample["tests_pass"]:
        return "tests-not-passing"
    columns = sample.get("kernel_columns", [])
    if len(columns) != ALL_KERNELS or set(columns) != set(spec_check.KERNELS):
        return "kernel-names-not-exact-seven"
    if any(sample.get("kernel_row", {}).get(k) != "verified / refuted"
           for k in spec_check.KERNELS):
        return "kernels-not-clean-seven"
    result = results.get(f"{sample['tag']}/{sample['name']}")
    if not isinstance(result, dict):
        return "spec-unchecked"
    status = result.get("status")
    # Two evidence paths, and the order here is the whole design.
    #
    # The strong one is check_task: the problem's reference solution supplying the
    # result on up to --n random arguments. The weak one is check_points: the
    # specification evaluated at the input/output pairs the problem itself states.
    # The weak path exists because the strong one cannot run at all for a whole
    # class of problems -- every string problem, since t has no string type, so no
    # drawn argument shape fits the reference and the status reads
    # "no valid draws". 14 answers that pass their tests and read
    # verified / refuted in all seven kernels were being dropped for want of
    # evidence rather than for being wrong (t/FINDINGS-examples-evidence-2026-09-20.md).
    #
    # The weak path may only supply a MISSING verdict. It may never overturn a
    # negative one, and the measurement is unambiguous about why: of the 12
    # specifications known to disagree with their reference solution that carry
    # these columns, 6 hold at every example their problem states. Three stated
    # examples do not catch what 100 draws catch. phi4-mini-v3/mbpp_20__is_woodall
    # is false at n=63 and holds at all three; locallm-r9-seed42/mbpp_541__check_abundant
    # is false at n=2 and holds at all three. A rule that let the examples answer
    # for the draws would have readmitted every one of them.
    examples_hold = (type(result.get("points_held")) is int and result["points_held"] > 0
                     and result.get("points_failed") == 0
                     and result.get("over_constrained") is not True)
    if status == "agrees":
        if type(result.get("draws")) is not int or result["draws"] <= 0:
            return "spec-no-valid-draws"
    elif status in NO_REFERENCE_VERDICT and examples_hold:
        pass                               # admitted on the problem's own examples
    else:
        return "spec-not-agrees"
    if type(result.get("task_id")) is not int or result["task_id"] != sample["task_id"]:
        return "spec-problem-mismatch"
    if pool_name is not None and result.get("pool") != pool_name:
        return "spec-pool-mismatch"
    if result.get("task_sha256") != spec_check.task_sha256(sample["task"]):
        return "spec-hash-missing-or-stale"
    # The specification must also hold at the problem's OWN stated examples, not
    # only at the random arguments check_task draws. spec_check.check_points
    # computes this and, until now, nothing gated on it: the column existed only
    # in the scorecard. A specification false at an input the problem itself
    # supplies is wrong however many random draws agreed, and the stated examples
    # are the cases a problem author chose as discriminating, so the draws are the
    # weaker instrument on exactly the inputs that matter most.
    #
    # Measured before it was added (2026-09-20): of the 42 result rows carrying
    # these columns, 7 contradict a stated example and all 7 are already rejected
    # for disagreeing or for a reference that would not run, and 0 agree on random
    # draws while contradicting an example. So this rejects nothing today. It is a
    # guard that removes the dependence on a draw happening to land in the wrong
    # region, and it is the mechanism VeriAct's PostCorr and Coins' Pass_all both
    # gate on. It cannot silently shrink the pool without saying so, because a
    # rejection here is counted and named like every other.
    #
    # NOTE, and it is the reason this is worded as it is: a MISSING points_failed
    # is not a pass. check_points landed on 2026-09-20, so 470 of 512 existing
    # rows predate it and carry no such column. Those rows are unchecked on this
    # dimension, not clean on it, and re-running spec_check is what supplies the
    # evidence. Treating absence as a pass is the exact mistake this file's own
    # history records twice (see CORRECTIONS.md); it is tolerated here only
    # because every other gate above still applies, and a positive_rejection of
    # None has never meant "every check that exists was run".
    if type(result.get("points_failed")) is int and result["points_failed"] > 0:
        return "spec-contradicts-example"
    if result.get("over_constrained") is True:
        return "spec-refuses-every-example"
    return None


def positives_of(samples: list[dict], min_kernels: int = ALL_KERNELS,
                 results: dict | None = None, pool_name: str | None = None) -> list[dict]:
    if min_kernels != ALL_KERNELS:
        raise ValueError("new sample rounds require exactly the seven named kernels")
    if results is None:
        results = load_spec_results()
    # Dedup after the evidence gate: an unchecked first copy must not hide a
    # later checked copy of the same canonical program.
    return dedup_wellformed([s for s in samples
                            if positive_rejection(s, results, pool_name) is None])


def validate_included_pairs(rows: list[dict], samples: dict, current_pairs: list[dict],
                            tags: list[str], train_ids: set, eval_ids: set, pool: dict,
                            results: dict, pool_name: str) -> tuple[list[dict], Counter]:
    """Import only currently admissible pairs, using regenerated provenance."""
    current = {(p["task_id"], p["chosen"], p["rejected"]): p for p in current_pairs}
    accepted, rejected = [], Counter()
    for row in rows:
        tid, tag = row.get("task_id"), row.get("tag")
        reason = None
        if type(tid) is not int or tid not in train_ids or tid in eval_ids or tid not in pool:
            reason = "include-not-train-pool-id"
        elif not isinstance(tag, str) or tag not in tags:
            reason = "include-tag-not-selected"
        else:
            sample = samples.get((tag, tid))
            if sample is None:
                reason = "include-sample-missing"
            else:
                failure = positive_rejection(sample, results, pool_name)
                if failure:
                    reason = "include-" + failure
                elif row.get("task") != sample["name"] or row.get("chosen") != sample["text"]:
                    reason = "include-program-mismatch"
                elif not row.get("prompt") or not sample.get("prompt"):
                    reason = "include-prompt-missing"
                elif row["prompt"] != sample["prompt"]:
                    reason = "include-prompt-mismatch"
                elif not isinstance(row.get("rejected"), str) or (tid, row["chosen"], row["rejected"]) not in current:
                    reason = "include-negative-not-current"
        if reason:
            rejected[reason] += 1
        else:
            # Imported metadata cannot replace the measured witness or verdict.
            accepted.append(current[(tid, row["chosen"], row["rejected"])])
    return accepted, rejected


def negatives_for_positive(pos: dict, samples: list[dict], results: dict | None = None,
                           pool_name: str | None = None) -> list[dict]:
    """Priority order, with the per-tier caps below:
    (a) the positive's own twins (build_negatives, primary first, cap 2);
        then test-passing unproved samples and current spec disagreements;
    (b) the problem's other well-formed samples that fail the tests, the
        ones that verified in some kernel column first, cap 2;
    (c) only when (b) found fewer than 2: samples that failed extract (do
        not parse or are not well-formed), the reply's fenced block
        verbatim, cap 1."""
    negs: list[dict] = []
    if results is None:
        results = load_spec_results()

    for body, op, w in build_negatives(pos["task"], max_neg=SAMPLES_MAX_TWINS):
        negs.append({"kind": f"twin:{op}", "operator": op,
                      "rejected": twin_task_text(pos["task"], body), "witness": w,
                      "neg_tag": None, "neg_sample_index": None})

    # (a2) the answer that is RIGHT and cannot be proved: same problem, well formed, its own tests pass, and
    # the seven do not all verify it with the twin refuted. Against a clean chosen side this is the only pair
    # in the set whose difference is the specification rather than the program, which is the difference the
    # round 5 student could not make (2026-09-18).
    unproved = [s for s in samples
                if s["wellformed"] and s["text"] != pos["text"] and s["tests_pass"]
                and s["kernel_count"] < ALL_KERNELS]
    unproved.sort(key=lambda s: (-s["kernel_count"], s["k"]))    # the near misses first: they differ by least
    for s in unproved[:SAMPLES_MAX_UNPROVED]:
        negs.append({"kind": f"unproved:{s['kernel_count']}of7", "operator": None, "rejected": s["text"],
                     "witness": None, "neg_tag": s["tag"], "neg_sample_index": s["k"]})

    # (a3) the answer all seven proved whose specification disagrees with the problem's own solution
    for s in samples:
        checked = results.get(f"{s['tag']}/{s.get('name')}", {})
        if (s["wellformed"] and s["text"] != pos["text"]
                and isinstance(checked, dict) and checked.get("status") == "disagrees"
                and type(checked.get("task_id")) is int and checked["task_id"] == s["task_id"]
                and (pool_name is None or checked.get("pool") == pool_name)
                and checked.get("task_sha256") == spec_check.task_sha256(s["task"])):
            negs.append({"kind": "spec-disagrees", "operator": None, "rejected": s["text"],
                         "witness": None, "neg_tag": s["tag"], "neg_sample_index": s["k"]})
            break

    others = [s for s in samples
              if s["wellformed"] and s["text"] != pos["text"] and not s["tests_pass"]]
    others.sort(key=lambda s: (0 if s["kernel_count"] > 0 else 1, s["k"]))
    b_negs = []
    for s in others[:SAMPLES_MAX_FAIL]:
        kind = "tests-fail-verified" if s["kernel_count"] > 0 else "tests-fail"
        b_negs.append({"kind": kind, "operator": None, "rejected": s["text"], "witness": None,
                        "neg_tag": s["tag"], "neg_sample_index": s["k"]})
    negs.extend(b_negs)

    if len(b_negs) < SAMPLES_MAX_FAIL:
        malformed = [s for s in samples if not s["wellformed"] and s.get("malformed_text")]
        malformed.sort(key=lambda s: s["k"])
        for s in malformed[:SAMPLES_MAX_MALFORMED]:
            negs.append({"kind": "malformed", "operator": None, "rejected": s["malformed_text"],
                         "witness": None, "neg_tag": s["tag"], "neg_sample_index": s["k"]})

    return negs[:SAMPLES_MAX_TWINS + SAMPLES_MAX_UNPROVED + SAMPLES_MAX_DISAGREE + SAMPLES_MAX_FAIL]


def load_pairs_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


# ------------------------------------------------------------ --relabel-rows --
#
# t/relabel.py's rows: verified-but-wrong programs relabeled with the train problem
# they actually solve (CodeIt, https://arxiv.org/html/2402.04858: hindsight
# relabeling took a 220M model from 24/400 to 49/400, and uniform mixing of the
# relabeled data with the real solutions fell back to 38/400, so the source is
# kept on every row for a later builder to weight). The rows join the positives
# through the same refusals as everything else here: a row for a held-out id under
# any alias, a listed same-task id, or a dev-split id stops the build by name.
RELABEL_SOURCE = "relabel"


def load_relabel_rows(path: Path, train_ids: set[int], eval_ids: set[int], pool: dict,
                      pool_name: str, split_path: str | Path | None) -> list[dict]:
    """Every row of a relabel pool file, or a refusal naming the first row that is not admissible."""
    import loop_filter
    policy = loop_filter.decontamination()
    dev = loop_filter.r12_dev_ids(split_path=split_path)
    gated = (("held-out", set(eval_ids)), ("listed same-task", set(policy.exclude_train_ids)), ("dev-split", set(dev)))
    rows = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise SystemExit(f"cannot read --relabel-rows {path}: {error}")
    for number, line in enumerate(lines, 1):
        where = f"{path.name}:{number}"
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise SystemExit(f"{where}: not a JSON row ({error})")
        if not isinstance(row, dict) or row.get("source") != RELABEL_SOURCE:
            raise SystemExit(f"{where}: not a relabel row (source must be {RELABEL_SOURCE!r})")
        tid = row.get("task_id")
        if type(tid) is not int:
            raise SystemExit(f"{where}: task_id must be an integer, got {tid!r}")
        for label, ids in gated:
            if tid in ids:
                raise SystemExit(f"{where}: relabel row for task_id={tid} names a {label} problem; refused")
        if tid not in train_ids:
            raise SystemExit(f"{where}: task_id={tid} is not a train-split id")
        if tid not in pool:
            raise SystemExit(f"{where}: task_id={tid} is not in pool {pool_name}")
        provenance = row.get("relabel")
        if not isinstance(provenance, dict):
            raise SystemExit(f"{where}: no relabel provenance block")
        if provenance.get("pool") != pool_name:
            raise SystemExit(f"{where}: row was relabeled under pool {provenance.get('pool')!r}, this build is "
                             f"{pool_name}; regenerate it under the same pool")
        name, chosen, prompt = row.get("task"), row.get("chosen"), row.get("prompt")
        if not isinstance(name, str) or loop_filter.problem_id(name) != tid:
            raise SystemExit(f"{where}: task name {name!r} does not name problem {tid}")
        if not prompt:
            raise SystemExit(f"{where}: no prompt")
        m = re.search(r"```t\n(.*?)```", chosen or "", re.S)
        if m is None:
            raise SystemExit(f"{where}: chosen has no fenced t block")
        try:
            task = surface.parse(m.group(1))
        except Exception as error:                                # noqa: BLE001 -- name it, whatever broke
            raise SystemExit(f"{where}: chosen does not parse ({error})")
        if task.get("name") != name:
            raise SystemExit(f"{where}: chosen declares task {task.get('name')!r}, row says {name!r}")
        if provenance.get("task_sha256") != spec_check.task_sha256(task):
            raise SystemExit(f"{where}: provenance task_sha256 does not match the chosen program")
        # the whole row, provenance included: a held-out alias anywhere is refused, as preflight refuses it
        held = loop_filter.validate_training_data(json.dumps(row, sort_keys=True), set(eval_ids) | set(dev),
                                                  names=[name], task_ids=[tid], policy=policy)
        if not held.ok:
            detail = (loop_filter.held_out_detail(held.held_out) if held.held_out
                      else loop_filter.same_task_detail(held))
            raise SystemExit(f"{where}: refused, {detail}")
        rows.append(row)
    return rows


def cap_relabel_rows(rows: list[dict], cap: int) -> tuple[list[dict], int]:
    """At most `cap` relabeled rows per target problem, in file order (the file
    is deterministic), so three problems cannot carry a third of the rows: the
    2026-09-25 run put 33 of 118 rows on three problems, and CodeIt
    (arXiv:2402.04858) reports that mixing relabeled data uniformly with the real
    solutions fell from 49 to 38 of 400. cap 0 keeps every row."""
    if cap <= 0:
        return list(rows), 0
    kept, per_problem = [], {}
    for row in rows:
        tid = int(row["task_id"])
        per_problem[tid] = per_problem.get(tid, 0) + 1
        if per_problem[tid] <= cap:
            kept.append(row)
    return kept, len(rows) - len(kept)


def append_relabel_rows(sft: list[dict], rows: list[dict]) -> dict:
    """Relabel rows join the SFT set with their source kept; one already a positive is counted, not doubled."""
    present = {(s["task_id"], s["chosen"]) for s in sft}
    counts: dict = {"read": len(rows), "appended": 0, "already_positive": 0, "per_problem": {}}
    for row in rows:
        if (row["task_id"], row["chosen"]) in present:
            counts["already_positive"] += 1
            continue
        present.add((row["task_id"], row["chosen"]))
        sft.append({"prompt": row["prompt"], "chosen": row["chosen"], "source": RELABEL_SOURCE,
                    "task_id": row["task_id"], "task": row["task"], "relabel": row["relabel"]})
        counts["appended"] += 1
        # every distinct relabeled program is appended, where the samples path above keeps one positive
        # per (task_id, source, task): the per-problem count is what a builder that caps needs to see
        counts["per_problem"][row["task_id"]] = counts["per_problem"].get(row["task_id"], 0) + 1
    sft.sort(key=lambda s: (s["task_id"], s["source"], s["task"]))
    return counts


def pair_sort_key(p: dict):
    return (p.get("task_id"), p.get("source", ""), p.get("task", ""),
            p.get("operator") or p.get("kind") or "", p.get("rejected", ""))


def _write_dataset_r2_md(args, tags: list[str], split: dict, pool: dict, passk: dict,
                          hist: dict, kind_tally: dict, op_tally: dict, merged: list[dict],
                          pairs: list[dict], include_pairs: list[dict], sft: list[dict],
                          no_samples_train: list[int], no_positive_train: list[int],
                          no_negatives_train: list[tuple], gate_rejections: dict,
                          include_accepted: list[dict], include_rejections: Counter,
                          relabel: dict | None = None) -> None:
    suffix = args.out_suffix
    lines = []
    L = lines.append
    L(f"# The loop dataset -- --from-samples round ({suffix})")
    L("")
    L(f"Built by `loop_dataset.py --from-samples` from {len(tags)} sample tag(s): "
      + ", ".join(f"`{t}`" for t in tags) + ". The reward now includes the problem's "
      "own tests: a positive passes every test and has exactly the seven named "
      "kernels marked `verified / refuted`, without flaked verdicts. A current "
      "spec-check result must explicitly agree on at least one valid draw, with "
      "the same canonical task hash, problem ID and pool. Graded over the fixed split "
      f"`{args.split}` (pool {len(pool)}: {len(split.get('train_ids', []))} train, "
      f"{len(split.get('eval_ids', []))} eval); only train-split positives produce "
      "pairs, the eval-split rows below measure the sampler, not training data.")
    L("")

    L("## Pairs per source (after merging --include and deduplicating)")
    L("")
    by_source: dict[str, int] = {}
    for p in merged:
        by_source[p.get("source", "?")] = by_source.get(p.get("source", "?"), 0) + 1
    L("| source | pairs |")
    L("|---|---:|")
    for src in sorted(by_source):
        L(f"| {src} | {by_source[src]} |")
    L(f"| **total (merged, deduped)** | **{len(merged)}** |")
    L("")
    L(f"Samples pairs before merge: {len(pairs)}. Include pairs read "
      f"(`{args.include or 'none given'}`): {len(include_pairs)}. "
      f"Currently admissible include pairs: {len(include_accepted)}; rejected: "
      f"{sum(include_rejections.values())}. "
      f"`sft-{suffix}.jsonl`: {len(sft)} distinct positives.")
    L("")
    L("Included pairs must match a selected tag's current program and recorded prompt, "
      "pass the current positive gate, belong exclusively to the training split, and "
      "match a currently regenerated admissible negative. Regenerated provenance is used.")
    L("")
    L("## Rejections by first failed gate")
    L("")
    L("Positive gates run before text deduplication; these are raw sample counts.")
    L("")
    L("| source | reason | count |")
    L("|---|---|---:|")
    for split_name, counts in sorted(gate_rejections.items()):
        for reason, count in sorted(counts.items()):
            L(f"| {split_name} samples | {reason} | {count} |")
    for reason, count in sorted(include_rejections.items()):
        L(f"| include | {reason} | {count} |")
    L("")

    L("## Negatives per kind (samples source only)")
    L("")
    L("| kind | pairs |")
    L("|---|---:|")
    for k in sorted(kind_tally):
        L(f"| {k} | {kind_tally[k]} |")
    L("")

    L("## Pairs per twin operator (base tag, `#k` rungs folded together, all merged pairs)")
    L("")
    op_all: dict[str, int] = {}
    for p in merged:
        op = p.get("operator")
        if op:
            base = op.split("#", 1)[0]
            op_all[base] = op_all.get(base, 0) + 1
    L("| operator | pairs |")
    L("|---|---:|")
    for op in sorted(op_all):
        L(f"| {op} | {op_all[op]} |")
    L("")

    L("## Histogram: tests pass x kernel count, over train-split well-formed samples")
    L("")
    L("Deduplicated by printed t text across the K tags for this diagnostic histogram. "
      "Kernel counts alone are insufficient: positive acceptance also requires current "
      "spec evidence, checked before positive deduplication.")
    L("")
    L("| tests | " + " | ".join(str(k) for k in range(8)) + " | total |")
    L("|---|" + "---:|" * 9)
    for tp, label in ((True, "pass"), (False, "fail/other")):
        row = [hist.get((tp, k), 0) for k in range(8)]
        L(f"| {label} | " + " | ".join(str(v) for v in row) + f" | {sum(row)} |")
    L("")

    L("## pass@K, over the fixed split")
    L("")
    L("| split | problems | with a well-formed sample | with a tests-passing sample | with a positive |")
    L("|---|---:|---:|---:|---:|")
    for name in ("train", "eval"):
        b = passk[name]
        L(f"| {name} | {b['problems']} | {b['wellformed']} | {b['tests_pass']} | {b['positive']} |")
    L("")
    L("Eval-split rows are a measurement of the sampler: no eval-split problem contributes a pair.")
    L("")

    if no_samples_train:
        L(f"{len(no_samples_train)} train-split problem(s) had no recorded sample from any of "
          "the given tags: " + ", ".join(str(t) for t in sorted(no_samples_train)))
        L("")
    if no_positive_train:
        L(f"{len(no_positive_train)} train-split problem(s) had at least one sample but no "
          "positive at the bar: " + ", ".join(str(t) for t in sorted(no_positive_train)))
        L("")
    if no_negatives_train:
        L(f"{len(no_negatives_train)} positive(s) produced zero negatives (no twin, no failing "
          "sample, no malformed sample to contrast against):")
        L("")
        for tid, name, k in sorted(no_negatives_train):
            L(f"- {tid} `{name}` (sample {k})")
        L("")

    if relabel is not None:
        L("## Relabeled rows (`--relabel-rows`)")
        L("")
        per_problem = relabel.get("per_problem") or {}
        loaded = sorted(per_problem.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
        L(f"Read {relabel['read']} row(s) from `{relabel['path']}`; appended {relabel['appended']} to "
          f"`sft-{suffix}.jsonl` with `source: relabel` kept; {relabel['already_positive']} already a "
          "positive under the same problem (counted, not doubled). No pairs are built from them.")
        L("")
        L("They are not one per problem: the samples path keeps one positive per (task_id, source, task) "
          "while every distinct relabeled program is appended, so "
          f"{relabel['appended']} relabeled row(s) on {len(per_problem)} problem(s); the most loaded: "
          + (", ".join(f"{tid} ({n})" for tid, n in loaded) if loaded else "none")
          + ". Nothing weights or caps them yet: CodeIt's uniform mixing fell from 49/400 to 38/400 "
          "(https://arxiv.org/html/2402.04858, Table 2), and the source field is what a builder needs to "
          "weight real positives higher or cap a problem's relabeled rows before a model trains on them.")
        L("")
    L("## Regenerating this dataset")
    L("")
    L("```")
    cmd = ("python3 loop_dataset.py --from-samples " + " ".join(tags)
           + f" --split {args.split} --min-kernels {args.min_kernels} --out-suffix {suffix}")
    if args.include:
        cmd += f" --include {args.include}"
    if getattr(args, "relabel_rows", None):
        cmd += f" --relabel-rows {args.relabel_rows}"
    L(cmd)
    L("```")
    L("")
    (OUT / f"DATASET-{suffix}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_from_samples(args) -> int:
    """New rounds require seven named clean kernels and current hash-bound spec
    agreement. Evidence is checked before positive text deduplication. Eval
    problems are measured but never included; imported pairs face the same gate
    and must match a currently regenerated admissible pair."""
    if args.min_kernels != ALL_KERNELS:
        raise ValueError("--from-samples requires --min-kernels 7; lower bars are legacy only")
    OUT.mkdir(parents=True, exist_ok=True)
    tags = args.from_samples
    tag_dirs = [load_tag_dir(t) for t in tags]

    split = json.loads(Path(args.split).read_text(encoding="utf-8"))
    train_ids = set(split.get("train_ids", split.get("used_task_ids", [])))
    eval_ids = set(split.get("eval_ids", split.get("heldout_task_ids", [])))
    if any(type(tid) is not int for tid in train_ids | eval_ids):
        raise ValueError("split IDs must be integers")
    if train_ids & eval_ids:
        raise ValueError("train and eval splits overlap")

    # the split names its pool (split-v3.json, 2026-09-16); older splits are v1
    pool_name = split.get("pool", "v1")
    pool = spec_experiment.pool(pool_name)
    min_kernels = args.min_kernels
    results = load_spec_results()
    include_pairs = load_pairs_jsonl(Path(args.include)) if args.include else []
    include_keys = {(row.get("tag"), row.get("task_id")) for row in include_pairs
                    if isinstance(row.get("tag"), str) and type(row.get("task_id")) is int}
    include_samples = {}
    gate_rejections = {"train": Counter(), "eval": Counter()}

    passk = {"train": {"problems": 0, "wellformed": 0, "tests_pass": 0, "positive": 0},
             "eval": {"problems": 0, "wellformed": 0, "tests_pass": 0, "positive": 0}}
    hist: dict[tuple, int] = {}
    kind_tally: dict[str, int] = {}
    op_tally: dict[str, int] = {}
    pairs: list[dict] = []
    no_samples_train: list[int] = []
    no_positive_train: list[int] = []
    no_negatives_train: list[tuple] = []

    for tid in sorted(pool):
        if tid in train_ids:
            split_name = "train"
        elif tid in eval_ids:
            split_name = "eval"
        else:
            continue  # not in either half of the fixed split

        raw_samples = gather_samples(tag_dirs, tid)
        samples = dedup_wellformed(raw_samples)
        positives = positives_of(raw_samples, min_kernels, results, pool_name)
        for sample in raw_samples:
            reason = positive_rejection(sample, results, pool_name)
            if reason:
                gate_rejections[split_name][reason] += 1
            if (sample["tag"], tid) in include_keys:
                include_samples[(sample["tag"], tid)] = sample

        b = passk[split_name]
        b["problems"] += 1
        if any(s["wellformed"] for s in raw_samples):
            b["wellformed"] += 1
        if any(s["wellformed"] and s["tests_pass"] for s in raw_samples):
            b["tests_pass"] += 1
        if positives:
            b["positive"] += 1

        if split_name != "train":
            continue

        for s in samples:
            if s["wellformed"]:
                key = (s["tests_pass"], min(s["kernel_count"], 7))
                hist[key] = hist.get(key, 0) + 1

        if not raw_samples:
            no_samples_train.append(tid)
            continue
        if not positives:
            no_positive_train.append(tid)
            continue

        for pos in positives:
            negs = negatives_for_positive(pos, samples, results, pool_name)
            if not negs:
                no_negatives_train.append((tid, pos["name"], pos["k"]))
                continue
            for neg in negs:
                kind_tally[neg["kind"]] = kind_tally.get(neg["kind"], 0) + 1
                if neg["operator"]:
                    base = neg["operator"].split("#", 1)[0]
                    op_tally[base] = op_tally.get(base, 0) + 1
                pairs.append({
                    "source": "samples", "tag": pos["tag"], "sample_index": pos["k"],
                    "task_id": tid, "task": pos["name"],
                    "prompt": pos["prompt"], "chosen": pos["text"], "rejected": neg["rejected"],
                    "kind": neg["kind"], "operator": neg["operator"], "witness": neg["witness"],
                    "kernel_count": pos["kernel_count"], "refuted_kernels": pos["refuted_kernels"],
                    "neg_tag": neg["neg_tag"], "neg_sample_index": neg["neg_sample_index"],
                })

    include_accepted, include_rejections = validate_included_pairs(
        include_pairs, include_samples, pairs, tags, train_ids, eval_ids, pool, results, pool_name)
    merged: list[dict] = []
    seen_keys: set[tuple] = set()
    for p in include_accepted + pairs:
        key = (p.get("task_id"), p.get("chosen"), p.get("rejected"))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        merged.append(p)
    merged.sort(key=pair_sort_key)

    sft_seen: dict[tuple, dict] = {}
    for p in merged:
        key = (p.get("task_id"), p.get("source"), p.get("task"))
        if key not in sft_seen:
            sft_seen[key] = {"prompt": p.get("prompt"), "chosen": p.get("chosen"),
                              "source": p.get("source"), "task_id": p.get("task_id"),
                              "task": p.get("task")}
    sft = sorted(sft_seen.values(), key=lambda s: (s["task_id"], s["source"], s["task"]))
    relabel_counts = None
    relabel_path = getattr(args, "relabel_rows", None)
    if relabel_path:
        relabel_rows = load_relabel_rows(Path(relabel_path), train_ids, eval_ids, pool, pool_name, args.split)
        cap = getattr(args, "relabel_cap", 3)            # the CLI default, for callers that build args themselves
        relabel_rows, capped = cap_relabel_rows(relabel_rows, cap)
        if capped:
            print(f"relabel: {capped} row(s) beyond --relabel-cap {cap} per problem left out "
                  f"(CodeIt fell from 49 to 38 of 400 when relabeled rows were mixed uniformly with real ones)")
        relabel_counts = {"path": str(relabel_path), **append_relabel_rows(sft, relabel_rows)}
    # A row's prompt is the recorded messages in that answer's raw/<id>.json, and an answer graded on the lab
    # workstation has its raw file there, not here. Five such rows went into sft-r5 on 2026-09-18 with a null
    # prompt and killed the student's training three minutes in, inside a chat template, saying only "None has
    # no element 0". A dataset that cannot be trained on is worse than a smaller one, and worse still is one
    # that says nothing about what it dropped.
    noprompt = [s for s in sft if not s.get("prompt")]
    if noprompt:
        where = ", ".join(sorted({str(s.get("source")) for s in noprompt}))
        raise SystemExit(f"{len(noprompt)} of {len(sft)} answers have no recorded prompt, from: {where}\n"
                         f"their raw/<id>.json is missing here -- fetch it from the machine that generated "
                         f"them (rsync the tag's raw/ directory) and run this again")

    suffix = args.out_suffix
    (OUT / f"pairs-{suffix}.jsonl").write_text(
        "\n".join(json.dumps(p, sort_keys=True) for p in merged) + ("\n" if merged else ""),
        encoding="utf-8")
    (OUT / f"sft-{suffix}.jsonl").write_text(
        "\n".join(json.dumps(s, sort_keys=True) for s in sft) + ("\n" if sft else ""),
        encoding="utf-8")

    _write_dataset_r2_md(args, tags, split, pool, passk, hist, kind_tally, op_tally,
                          merged, pairs, include_pairs, sft, no_samples_train,
                          no_positive_train, no_negatives_train, gate_rejections,
                          include_accepted, include_rejections, relabel_counts)

    print(f"train: {passk['train']['problems']} problems, "
          f"{passk['train']['positive']} with a positive")
    if relabel_counts is not None:
        print(f"relabel rows: {relabel_counts['read']} read, {relabel_counts['appended']} appended with source "
              f"kept, {relabel_counts['already_positive']} already a positive")
    print(f"eval:  {passk['eval']['problems']} problems, "
          f"{passk['eval']['positive']} with a positive")
    print(f"samples pairs: {len(pairs)}  include accepted/read: {len(include_accepted)}/{len(include_pairs)}  "
          f"merged (deduped): {len(merged)}")
    print("sample gate rejections: " + json.dumps(gate_rejections, sort_keys=True))
    print("include rejections: " + json.dumps(include_rejections, sort_keys=True))
    print(f"sft-{suffix}: {len(sft)}")
    print(f"kinds: {', '.join(f'{k}={v}' for k, v in sorted(kind_tally.items()))}")
    print(f"operators: {', '.join(f'{k}={v}' for k, v in sorted(op_tally.items()))}")
    print(f"wrote {OUT / f'pairs-{suffix}.jsonl'}, {OUT / f'sft-{suffix}.jsonl'}, "
          f"{OUT / f'DATASET-{suffix}.md'}")
    return 0


# ------------------------------------------------------------------ main --

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--from-samples", nargs="+", default=None, metavar="TAG",
                     help="build a later round from these K sample tag directories "
                          "(out/spec-experiment/<tag>/) instead of round0-7b + lifted")
    ap.add_argument("--split", default=str(OUT / "split.json"),
                     help="fixed train/eval split, e.g. out/loop/split.json")
    ap.add_argument("--min-kernels", type=int, default=ALL_KERNELS,
                     help="new sample rounds require all seven named kernels (default 7)")
    ap.add_argument("--out-suffix", default="r2",
                     help="writes pairs-<suffix>.jsonl, sft-<suffix>.jsonl, DATASET-<suffix>.md")
    ap.add_argument("--include", default=None,
                     help="prior pairs to revalidate against current evidence, prompts, "
                          "train IDs and admissible negatives before deduplicating")
    ap.add_argument("--relabel-cap", type=int, default=3, metavar="N",
                    help="at most N relabeled rows per target problem, in file order (0: no cap); the "
                         "2026-09-25 run put 33 of 118 rows on three problems")
    ap.add_argument("--relabel-rows", default=None, metavar="PATH",
                     help="t/relabel.py's rows (verified-but-wrong programs relabeled with the train "
                          "problem they solve), appended to sft-<suffix>.jsonl with source 'relabel' kept; "
                          "a row for a held-out, listed or dev-split id stops the build by name")
    args = ap.parse_args()
    if args.relabel_rows and not args.from_samples:
        ap.error("--relabel-rows joins a --from-samples build; the legacy round-1 build takes no relabel rows")
    if args.from_samples:
        return run_from_samples(args)
    return run_default()


if __name__ == "__main__":
    raise SystemExit(main())
