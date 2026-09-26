#!/usr/bin/env python3
"""Score held-out answer sets on both the full and decontaminated panels.

    python3 t/score_heldout.py [--split SPLIT.json] [--outcomes OUTCOMES.json] [--allow-partial] TAG [TAG ...]

``TAG`` is a directory under ``t/out/spec-experiment/`` with ``raw/``,
``extract.json``, ``tests.json``, and ``kernels.md``. The Markdown table keeps
its established columns and emits one row for all split evaluation IDs and one
for the clean panel after registered same-task training overlaps are removed.

Two refusals guard every number in the table (r12 blockers A4 and A6):

* A set that answers fewer held-out problems than the split names is refused
  by name, with the missing ids, unless ``--allow-partial`` says the caller
  knows it is scoring a partial set. Answers are counted as eval ids that have
  a ``raw/<id>.json``, never as raw files: a pool-wide set holds 649 files and
  answers 232, and one 27B set held 368 files and answered 161 of 232.
* A set whose records were decoded under different settings is refused. The
  key is the model plus every option except the free-text ``note``, with
  numbers compared as numbers (``--temperature 0`` is stored as ``0.0``). The
  digest is deliberately not part of it: one adapter was decoded on two
  machines with two torch builds, which is the same model.

``--outcomes`` additionally writes schema-2 JSON for paired comparison: each
``all-N`` and ``clean-N`` panel records its sorted task IDs and, for every tag,
complete task-id -> Boolean ``clean``, ``spec_agrees`` and ``tests_pass`` maps
plus their matching counts, ``recited`` (a clean answer that is a training
document, names erased) when ``--corpus`` names that tag's corpus, and the
``answered_count`` with a ``partial`` flag. ``spec_agrees`` is true only for a
clean answer with current-task agreement evidence. Missing, malformed,
untested, or incompletely graded answers are explicitly ``false`` rather than
omitted, so a comparison cannot quietly change its paired population. The
human-readable table remains on standard output. Schema 1 (clean and
spec_agrees only) is what ``t/evaluation_compare.py`` first read; it still
reads both.

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
OUTCOME_SCHEMA_VERSION = 2
# Free text in a record's options: a rerun's reason, never a decoding setting.
DECODING_FREE_TEXT = ("note",)


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
    from loop_filter import is_spec_document, key, strip_head
    import surface
    text = path.read_text(encoding="utf-8")
    keys: dict = {}
    spec_documents = 0
    for block in re.split(r"\n\s*\n\s*\n", text):
        if not block.strip():
            continue
        if is_spec_document(block):
            # a `Spec:` document (corpus --spec-docs, 2026-09-25) holds a declaration
            # and its clauses, no program: nothing a reply could recite as a program
            spec_documents += 1
            continue
        try:
            task = surface.parse(strip_head(block.strip() + "\n"))
        except Exception as e:
            raise SystemExit(f"{path}: a corpus document does not parse ({e}): {block[:80]!r}")
        keys.setdefault(key(task), []).append(task.get("name"))
    documents, tasks = sum(map(len, keys.values())), len(re.findall(r"(?m)^task ", text))
    if documents + spec_documents != tasks:
        raise SystemExit(f"{path}: {tasks} tasks but {documents} program documents and {spec_documents} "
                         f"spec documents read; the split merged some")
    return keys


def _canonical(value):
    """Numbers compare as numbers: ``--temperature 0`` is stored as ``0.0`` by one
    generator and as ``0`` by another, and both mean the same decoding."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        return {k: _canonical(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [_canonical(v) for v in value]
    return value


def decoding_key(record: dict) -> str:
    """The settings a record was decoded under, as one comparable string.

    PCheck (Xu et al., OSDI'16, usenix.org/conference/osdi16/technical-sessions/presentation/xu)
    shows that a setting nobody checks where its used value is observable stays
    a latent error until the damage shows; here the observable value is the
    options block every record carries. The key is the model plus every option
    except free text, which is wider than the five names the r12 plan listed
    on purpose: a survey of the 84 answer sets on 2026-09-21 found the only
    mixed set (deepseek-coder-v2-16b-v4-s1) differing in num_ctx and
    num_predict, names an ollama generator uses and the five-name rule would
    never have compared. The digest is left out: student-r6-v3 carries torch
    2.13 on 125 records and 2.11 on 107 around one adapter, which is one model.
    """
    options = record.get("options") if isinstance(record.get("options"), dict) else {}
    settings = {k: v for k, v in options.items() if k not in DECODING_FREE_TEXT}
    return json.dumps({"model": record.get("model"), "options": _canonical(settings)}, sort_keys=True)


def _differing_settings(records: list[dict]) -> list[str]:
    names = set()
    for r in records:
        options = r.get("options") if isinstance(r.get("options"), dict) else {}
        names.update(k for k in options if k not in DECODING_FREE_TEXT)
    differ = []
    if len({json.dumps(_canonical(r.get("model"))) for r in records}) > 1:
        differ.append("model")
    for name in sorted(names):
        values = {json.dumps(_canonical((r.get("options") or {}).get(name)), sort_keys=True) for r in records}
        if len(values) > 1:
            differ.append(name)
    return differ


def answered_records(tag: str, d: Path, eval_ids: set[int]) -> dict[int, dict]:
    """The raw record of every eval id that has one; an unreadable record is refused by name."""
    records = {}
    for tid in sorted(eval_ids):
        path = d / "raw" / f"{tid}.json"
        if not path.exists():
            continue
        try:
            records[tid] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise SystemExit(f"{tag}: raw/{path.name} is not a readable record ({e}); "
                             "a truncated file is a killed generator, not an answer")
        if not isinstance(records[tid], dict):
            raise SystemExit(f"{tag}: raw/{path.name} is not a record object")
    return records


def refuse_mixed_decoding(tag: str, records: dict[int, dict]) -> None:
    """A6: every record of a set must have been decoded under one setting."""
    by_key: dict[str, list[int]] = {}
    for tid, r in records.items():
        by_key.setdefault(decoding_key(r), []).append(tid)
    if len(by_key) <= 1:
        return
    combos = sorted(by_key.items(), key=lambda kv: -len(kv[1]))
    differ = _differing_settings([records[ids[0]] for _k, ids in combos])
    shown = "; ".join(f"{len(ids)} records at {k}" for k, ids in combos[:3])
    raise SystemExit(f"{tag}: records were decoded under {len(by_key)} different settings, differing in "
                     f"{', '.join(differ) or 'an option'} ({shown}); one set, one setting, or it is not one row")


def score(tag: str, eval_ids: set[int], corpus: dict | None = None,
          clean_outcomes: dict[int, bool] | None = None,
          spec_agrees_outcomes: dict[int, bool] | None = None,
          allow_partial: bool = False,
          tests_pass_outcomes: dict[int, bool] | None = None,
          recited_outcomes: dict[int, bool] | None = None) -> dict:
    d = se.outdir(tag)
    records = answered_records(tag, d, eval_ids)
    # A4, in the shape of Deequ's hasSize/isComplete constraints checked before data is consumed
    # (github.com/awslabs/deequ): the count that matters is eval ids with a record, not files.
    missing = sorted(set(eval_ids) - set(records))
    if missing and not allow_partial:
        raise SystemExit(f"{tag}: {len(records)} of {len(eval_ids)} held-out problems have a raw answer; "
                         f"missing {len(missing)}: {missing[:10]}{' ...' if len(missing) > 10 else ''}; "
                         "pass --allow-partial to score it as a partial set")
    refuse_mixed_decoding(tag, records)
    raw = set(records)
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
    for outcomes in (clean_outcomes, spec_agrees_outcomes, tests_pass_outcomes, recited_outcomes):
        if outcomes is not None:
            outcomes.clear()
            outcomes.update({tid: False for tid in eval_ids})
    for tid in eval_ids:
        if tid in raw:
            r["answered"] += 1
        e = ext.get(str(tid), {})
        if e.get("stage") == "task":
            r["task"] += 1
        t = tests.get(str(tid), {})
        passed = t.get("overall") == "pass"
        r["tests pass"] += passed
        if tests_pass_outcomes is not None:
            tests_pass_outcomes[tid] = bool(passed)
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
            recited = key(task) in corpus
            r["clean, recited" if recited else "clean, novel"] += 1
            if recited_outcomes is not None:
                recited_outcomes[tid] = recited
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
                    help="write schema-2 per-panel Boolean outcomes (clean, spec_agrees, tests_pass, "
                         "recited with --corpus) for paired comparison by t/compare_arms.py")
    ap.add_argument("--allow-partial", action="store_true",
                    help="score a set that answers fewer held-out problems than the split names; "
                         "without this such a set is refused by name")
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
            export = a.outcomes is not None
            maps = {name: ({} if export else None)
                    for name in ("clean", "spec_agrees", "tests_pass", "recited")}
            if training_corpus is None:
                maps["recited"] = None
            r = score(tag, ids, training_corpus, maps["clean"], maps["spec_agrees"],
                      allow_partial=a.allow_partial, tests_pass_outcomes=maps["tests_pass"],
                      recited_outcomes=maps["recited"])
            r["tag"] = f"{tag}{suffix}"
            print("| " + " | ".join(str(r[h]) for h in heads) + " |")
            if export:
                entry = {"answered_count": r["answered"], "partial": r["answered"] < len(ids)}
                for name, count in (("clean", "clean"), ("spec_agrees", "clean, spec checked"),
                                    ("tests_pass", "tests pass"), ("recited", "clean, recited")):
                    if maps[name] is None:
                        continue
                    entry[name] = {str(tid): maps[name][tid] for tid in sorted(maps[name])}
                    entry[f"{name}_count"] = r[count]
                panels[panel_name]["tags"][tag] = entry
    if a.outcomes is not None:
        outcome_export = {"schema_version": OUTCOME_SCHEMA_VERSION, "split": str(a.split),
                          "overlap_ids": sorted(eval_ids - clean_ids), "allow_partial": a.allow_partial,
                          "panels": panels}
        a.outcomes.write_text(json.dumps(outcome_export, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
