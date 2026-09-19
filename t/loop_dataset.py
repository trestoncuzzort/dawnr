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

A second mode, --from-samples, builds a later round's dataset from K sampled
answers per problem (one tag directory per sample, out/spec-experiment/<tag>/
in spec_experiment.py's own layout) instead of round 0 and the lifted tasks.
Positives and negatives are graded per problem over the fixed train/eval
split (out/loop/split.json); only the train split yields pairs, the eval
split is graded and reported as a pass@K measurement of the sampler. See
run_from_samples's docstring for the exact rules.

    python3 loop_dataset.py --from-samples TAG0 TAG1 ... \\
        --split out/loop/split.json --min-kernels 4 --out-suffix r2 \\
        --include out/loop/pairs.jsonl
"""
from __future__ import annotations

import argparse
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


# Answers whose specification disagrees with the problem's own solution (t/spec_check.py, 2026-09-18). They
# passed their tests, all seven proofs and a refuted twin, and they still do not say what the problem asked, so
# they are not training data. Rebuilt by spec_check.py; an absent file excludes nothing.
def _spec_disagree() -> set:
    try:
        return set(json.loads((HERE / "out" / "spec-disagree.json").read_text())["disagree"])
    except (OSError, ValueError, KeyError):
        return set()


SPEC_DISAGREE = _spec_disagree()


def positives_of(samples: list[dict], min_kernels: int) -> list[dict]:
    return [s for s in samples
            if s["wellformed"] and s["tests_pass"] and s["kernel_count"] >= min_kernels
            and f"{s['tag']}/{s['name']}" not in SPEC_DISAGREE]


def negatives_for_positive(pos: dict, samples: list[dict]) -> list[dict]:
    """Priority order, capped at 4 total (structurally, from the per-tier
    caps below, never needs the extra slice at the end to bite):
    (a) the positive's own twins (build_negatives, primary first, cap 2);
    (b) the problem's other well-formed samples that fail the tests, the
        ones that verified in some kernel column first, cap 2;
    (c) only when (b) found fewer than 2: samples that failed extract (do
        not parse or are not well-formed), the reply's fenced block
        verbatim, cap 1."""
    negs: list[dict] = []

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
        if (s["wellformed"] and s["text"] != pos["text"]
                and f"{s['tag']}/{s.get('name')}" in SPEC_DISAGREE):
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


def pair_sort_key(p: dict):
    return (p.get("task_id"), p.get("source", ""), p.get("task", ""),
            p.get("operator") or p.get("kind") or "", p.get("rejected", ""))


def _write_dataset_r2_md(args, tags: list[str], split: dict, pool: dict, passk: dict,
                          hist: dict, kind_tally: dict, op_tally: dict, merged: list[dict],
                          pairs: list[dict], include_pairs: list[dict], sft: list[dict],
                          no_samples_train: list[int], no_positive_train: list[int],
                          no_negatives_train: list[tuple]) -> None:
    suffix = args.out_suffix
    lines = []
    L = lines.append
    L(f"# The loop dataset -- --from-samples round ({suffix})")
    L("")
    L(f"Built by `loop_dataset.py --from-samples` from {len(tags)} sample tag(s): "
      + ", ".join(f"`{t}`" for t in tags) + ". The reward now includes the problem's "
      f"own MBPP tests: a positive passes every test and verifies with a refuted twin "
      f"in at least {args.min_kernels} of 7 kernels. Graded over the fixed split "
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
      f"`sft-{suffix}.jsonl`: {len(sft)} distinct positives.")
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
    L("Deduplicated by printed t text across the K tags (step 1's dedup rule); this is "
      "the bar (`--min-kernels`, currently %d) that step 2 checks against." % args.min_kernels)
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

    L("## Regenerating this dataset")
    L("")
    L("```")
    cmd = ("python3 loop_dataset.py --from-samples " + " ".join(tags)
           + f" --split {args.split} --min-kernels {args.min_kernels} --out-suffix {suffix}")
    if args.include:
        cmd += f" --include {args.include}"
    L(cmd)
    L("```")
    L("")
    (OUT / f"DATASET-{suffix}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_from_samples(args) -> int:
    """Round 2+ from K sampled answers per problem, tests folded into the
    reward. Per TRAIN-split problem: every well-formed sample is graded on
    tests, kernels and its printed t text (deduplicated across tags by that
    text). A POSITIVE passes every test and verifies with a refuted twin in
    at least --min-kernels columns. Every positive gets up to 4 negatives in
    priority order (see negatives_for_positive). EVAL-split problems are
    graded the same way for a pass@K table but never produce pairs. Round
    1's pairs.jsonl can be merged in with --include, deduplicated by
    (task_id, chosen, rejected). Deterministic: sorted task_id iteration, no
    randomness anywhere."""
    OUT.mkdir(parents=True, exist_ok=True)
    tags = args.from_samples
    tag_dirs = [load_tag_dir(t) for t in tags]

    split = json.loads(Path(args.split).read_text(encoding="utf-8"))
    train_ids = set(split.get("train_ids", split.get("used_task_ids", [])))
    eval_ids = set(split.get("eval_ids", split.get("heldout_task_ids", [])))

    # the split names its pool (split-v3.json, 2026-09-16); older splits are v1
    pool = spec_experiment.pool(split.get("pool", "v1"))
    min_kernels = args.min_kernels

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
        positives = positives_of(samples, min_kernels)

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
            negs = negatives_for_positive(pos, samples)
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

    include_pairs = load_pairs_jsonl(Path(args.include)) if args.include else []
    merged: list[dict] = []
    seen_keys: set[tuple] = set()
    for p in include_pairs + pairs:
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
                          no_positive_train, no_negatives_train)

    print(f"train: {passk['train']['problems']} problems, "
          f"{passk['train']['positive']} with a positive")
    print(f"eval:  {passk['eval']['problems']} problems, "
          f"{passk['eval']['positive']} with a positive")
    print(f"samples pairs: {len(pairs)}  include pairs: {len(include_pairs)}  "
          f"merged (deduped): {len(merged)}")
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
    ap.add_argument("--min-kernels", type=int, default=KERNEL_GATE,
                     help="columns of 7 that must read verified/refuted (default 4)")
    ap.add_argument("--out-suffix", default="r2",
                     help="writes pairs-<suffix>.jsonl, sft-<suffix>.jsonl, DATASET-<suffix>.md")
    ap.add_argument("--include", default=None,
                     help="a round's pairs.jsonl to merge in, deduplicated by "
                          "(task_id, chosen, rejected)")
    args = ap.parse_args()
    if args.from_samples:
        return run_from_samples(args)
    return run_default()


if __name__ == "__main__":
    raise SystemExit(main())
