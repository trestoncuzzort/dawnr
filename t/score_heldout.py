#!/usr/bin/env python3
"""Score held-out answer sets on both the full and decontaminated panels.

    python3 t/score_heldout.py [--split SPLIT.json] [--outcomes OUTCOMES.json] TAG [TAG ...]

``TAG`` is a directory under ``t/out/spec-experiment/`` with ``raw/``,
``extract.json``, ``tests.json``, and ``kernels.md``. The Markdown table keeps
its established columns and emits one row for all split evaluation IDs and one
for the clean panel after registered same-task training overlaps are removed.

``--outcomes`` additionally writes schema-v1 JSON for paired comparison: each
``all-N`` and ``clean-N`` panel records its sorted task IDs and, for every tag,
complete task-id -> Boolean ``clean`` and ``spec_agrees`` maps plus their
matching counts. ``spec_agrees`` is true only for a clean answer with
current-task agreement evidence. Missing, malformed, untested, or incompletely graded answers are explicitly
``false`` rather than omitted, so a comparison cannot quietly change its paired
population. The human-readable table remains on standard output.

A clean answer passes the problem's tests and is ``verified / refuted`` in all
seven named kernels; partial kernel tables cannot contribute clean answers.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import spec_experiment as se                                    # noqa: E402

CLEAN = "verified / refuted"
KERNELS = {"dafny", "verus", "spark", "framac", "lean", "rocq", "fstar"}
FAILING_TESTS = {"fail", "signature", "requires-excluded", "undefined"}


def clean_eval_ids(eval_ids: set[int]) -> set[int]:
    """Return evaluation ids without known same-task training sources."""
    from loop_filter import decontamination
    return set(eval_ids) - set(decontamination().overlap_eval_ids)


def checked_spec(result: dict, task_file: Path) -> str | None:
    """A set was checked only for the exact task contents its evidence describes."""
    from spec_check import task_sha256
    if result.get("status") not in {"agrees", "disagrees"}:
        return None
    if result.get("status") == "agrees" and result.get("draws", 0) <= 0:
        return None
    try:
        task = json.loads(task_file.read_text(encoding="utf-8"))
        if result.get("task_sha256") == task_sha256(task):
            return result["status"]
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def corpus_keys(path: Path) -> dict:
    """Name-erased program -> the training documents that are that program.

    Answer overlap in the sense of Lewis, Stenetorp and Riedel, "Question and
    Answer Test-Train Overlap in Open-Domain Question Answering Datasets"
    (arXiv:2008.02637): a test answer counts as overlapping when, after
    normalization, it appears among the training answers, and every score is
    reported on the overlapping and the non-overlapping part separately. They
    found closed-book models score mostly on the overlap; locallm is closed-book.
    The normalization here is loop_filter.key, the copy check the loop has used
    since 2026-09-16: name erased, gate dropped, version pinned, surface.canon.

    Measured 2026-09-21: 10 of the 23 clean answers across every locallm arm are
    a training document under another problem's id (mbpp_729 add_list is
    mbpp_728 sum_list; r4 and r5 scored only such answers), against 1 of 23 for
    Phi-4-mini, the untrained 1.5B, DeepSeek-Prover-V2-7B and the 235B, none of
    which saw these corpora. That base rate is what makes a match read as
    recitation rather than two models converging on the only way to write it.

    A document that does not parse is refused rather than skipped, and so is a
    corpus whose task count the split does not account for: a recited answer
    missed that way would be reported as novel, which is the wrong direction.
    """
    from loop_filter import key, strip_head
    import surface
    text = path.read_text(encoding="utf-8")
    keys: dict = {}
    for block in re.split(r"\n\s*\n\s*\n", text):
        if not block.strip():
            continue
        try:
            task = surface.parse(strip_head(block.strip() + "\n"))
        except Exception as e:
            raise SystemExit(f"{path}: a corpus document does not parse ({e}): {block[:80]!r}")
        keys.setdefault(key(task), []).append(task.get("name"))
    documents, tasks = sum(map(len, keys.values())), len(re.findall(r"(?m)^task ", text))
    if documents != tasks:
        raise SystemExit(f"{path}: {tasks} tasks but {documents} documents read; the split merged some")
    return keys


def score(tag: str, eval_ids: set[int], corpus: dict | None = None,
          clean_outcomes: dict[int, bool] | None = None,
          spec_agrees_outcomes: dict[int, bool] | None = None) -> dict:
    d = se.outdir(tag)
    raw = {int(p.stem) for p in (d / "raw").glob("*.json") if p.stem.isdigit()}
    ext = json.loads((d / "extract.json").read_text(encoding="utf-8")) if (d / "extract.json").exists() else {}
    tests = json.loads((d / "tests.json").read_text(encoding="utf-8")) if (d / "tests.json").exists() else {}
    cols, cells = (se.parse_kernel_table(d / "kernels.md") if (d / "kernels.md").exists() else ([], {}))
    # Set-level provenance cannot prove that any particular answer was checked.
    # Refusals, zero valid draws and evidence for an older task all stay unchecked.
    spec_results = {}
    try:
        sd = json.loads((HERE / "out" / "spec-disagree.json").read_text())
        spec_results = sd.get("results", {})
    except (OSError, ValueError, KeyError, IndexError):
        pass
    r = {"tag": tag, "eval": len(eval_ids), "answered": 0, "task": 0, "tests pass": 0, "graded": 0,
         "clean": 0, "spec disagrees": 0, "clean, spec checked": 0, "spec unchecked": 0,
         "wrong but proven": 0, "kernels": len(cols),
         "clean, recited": 0 if corpus is not None else "-",
         "clean, novel": 0 if corpus is not None else "-"}
    if corpus is not None:
        from loop_filter import key
    if clean_outcomes is not None:
        clean_outcomes.clear()
        clean_outcomes.update({tid: False for tid in eval_ids})
    if spec_agrees_outcomes is not None:
        spec_agrees_outcomes.clear()
        spec_agrees_outcomes.update({tid: False for tid in eval_ids})
    for tid in eval_ids:
        if tid in raw:
            r["answered"] += 1
        e = ext.get(str(tid), {})
        if e.get("stage") == "task":
            r["task"] += 1
        t = tests.get(str(tid), {})
        passed = t.get("overall") == "pass"
        r["tests pass"] += passed
        row = cells.get(t.get("name") or e.get("name") or "")
        if not row:
            continue
        r["graded"] += 1
        proven = len(cols) == 7 and set(cols) == KERNELS and all(row.get(c) == CLEAN for c in KERNELS)
        name = t.get("name") or e.get("name") or ""
        outcome = checked_spec(spec_results.get(f"{tag}/{name}", {}), d / "tasks" / f"{name}.json") \
            if proven and passed else None
        is_clean = bool(proven and passed)
        spec_agrees = bool(is_clean and outcome == "agrees")
        r["clean"] += is_clean
        r["spec disagrees"] += bool(is_clean and outcome == "disagrees")
        r["clean, spec checked"] += spec_agrees
        r["spec unchecked"] += bool(is_clean and outcome is None)
        r["wrong but proven"] += proven and t.get("overall") in FAILING_TESTS
        if clean_outcomes is not None:
            clean_outcomes[tid] = is_clean
        if spec_agrees_outcomes is not None:
            spec_agrees_outcomes[tid] = spec_agrees
        if corpus is not None and is_clean:
            task = json.loads((d / "tasks" / f"{name}.json").read_text(encoding="utf-8"))
            r["clean, recited" if key(task) in corpus else "clean, novel"] += 1
    # The gate this project loses at, as one number: of the answers that pass their own tests, how many the
    # seven can prove. Round 6's student converts 3 of 9 where Phi-4-mini converts 3 of 6 and a proof-trained
    # 7B converts 6 of 10, and that difference is the whole story of where the loop is stuck -- it belongs in
    # the table rather than in a paragraph someone has to recompute (2026-09-19).
    r["converts"] = (f"{r['clean']}/{r['tests pass']}"
                     + (f" ({100 * r['clean'] / r['tests pass']:.0f}%)" if r["tests pass"] else ""))
    return r


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--split", type=Path, default=HERE / "out" / "loop" / "split-v3.json")
    ap.add_argument("--corpus", action="append", default=[], metavar="TAG=PATH",
                    help="the corpus TAG's model was trained on; splits its clean answers into "
                         "recited and novel (repeatable, one per tag)")
    ap.add_argument("--outcomes", type=Path, metavar="PATH",
                    help="write schema-v1 per-panel Boolean clean outcomes for paired comparison")
    ap.add_argument("tags", nargs="+")
    a = ap.parse_args()
    eval_ids = {int(i) for i in json.loads(a.split.read_text(encoding="utf-8"))["eval_ids"]}
    clean_ids = clean_eval_ids(eval_ids)
    if a.outcomes is not None and len(set(a.tags)) != len(a.tags):
        ap.error("--outcomes needs distinct tags")
    panel_specs = (
        (f"all-{len(eval_ids)}", "", eval_ids),
        (f"clean-{len(clean_ids)}", f" clean-{len(clean_ids)}", clean_ids),
    )
    panels = {
        panel_name: {"task_ids": sorted(ids), "tags": {}}
        for panel_name, _suffix, ids in panel_specs
    }
    corpora = {}
    for pair in a.corpus:
        tag, sep, path = pair.partition("=")
        if not sep or tag not in a.tags:
            ap.error(f"--corpus {pair!r}: want TAG=PATH for one of the tags being scored")
        corpora[tag] = Path(path)
    parsed = {p: corpus_keys(p) for p in set(corpora.values())}
    heads = ["tag", "kernels", "eval", "answered", "task", "tests pass", "graded", "clean", "converts",
             "spec disagrees", "clean, spec checked", "spec unchecked", "wrong but proven",
             "clean, recited", "clean, novel"]
    print("| " + " | ".join(heads) + " |")
    print("|" + "---|" * len(heads))
    for tag in a.tags:
        training_corpus = parsed[corpora[tag]] if tag in corpora else None
        for panel_name, suffix, ids in panel_specs:
            clean_map = {} if a.outcomes is not None else None
            spec_agrees_map = {} if a.outcomes is not None else None
            r = score(tag, ids, training_corpus, clean_map, spec_agrees_map)
            r["tag"] = f"{tag}{suffix}"
            print("| " + " | ".join(str(r[h]) for h in heads) + " |")
            if clean_map is not None and spec_agrees_map is not None:
                panels[panel_name]["tags"][tag] = {
                    "clean": {str(tid): clean_map[tid] for tid in sorted(clean_map)},
                    "clean_count": r["clean"],
                    "spec_agrees": {str(tid): spec_agrees_map[tid] for tid in sorted(spec_agrees_map)},
                    "spec_agrees_count": r["clean, spec checked"],
                }
    if a.outcomes is not None:
        outcome_export = {"schema_version": 1, "panels": panels}
        a.outcomes.write_text(json.dumps(outcome_export, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
