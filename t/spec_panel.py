#!/usr/bin/env python3
"""t/spec_panel.py -- held-out specification questions with no look-alike left in the rows (2026-10-05)

    python3 t/spec_panel.py draw --rows ROWS.jsonl --k 40 --seed spec-panel-2026-10-05 \\
        [--only-names FILE] [--max-remove 4] --panel PANEL.jsonl --keep KEPT.jsonl [--report OUT.json]
    python3 t/spec_panel.py check --rows ROWS.jsonl --panel PANEL.jsonl [--keep KEPT.jsonl] [--json OUT]

`check` exits 1 when a row matches a question of the panel: the gate of a row build, beside t/heldout_audit.py.

Why. "Given a specification, the model writes a body all seven provers accept on 27 of 33 held-out questions"
was the second headline of the release of 2026-10-05. The 33 were held out by document: a tenth of the corpus,
never trained on, checked for the same name, text and specification (t/student_rows.py leaks_heldout). They were
never checked for behaviour, and they are small common functions: `clover_abs__abs` is held out and three other
`abs` are trained on. Run on each question's own inputs, 19 of the 33 have a program in the training rows that
answers as the held-out program does (t/DECONTAMINATION-2026-10-05.md). The same lesson as the held-out
problems, one level down: a split by document holds out a name, and what a model learns is a function.

`draw` makes a panel the other way round. A candidate is a document the rows hold a specification-given row
for, with no MBPP-DFY lineage and (with --only-names) on a list of documents proved by all seven. Its removal
set is every row that names it or holds, in its answer or its prompt, a t program of the same parameter and
result types that answers the document's own inputs as the document does. A candidate whose removal set is
small (--max-remove) is one whose function the rows hold nowhere else; `k` of them are taken in the order of
sha256(seed:document), which no result can influence, and every row of their removal sets leaves training.

Same behaviour: the document's program is run on up to 120 inputs of its own domain that its `requires` admits
(interp.domain, the interpreter's ladders); another program is the same when the two answer at least 10 of
them and differ on fewer than 10%. That is differential testing on generated inputs, as t/twin_draws.py does
against a Python reference (EvalPlus, arXiv:2305.01210), with the 10% line of that file for a near twin
(arXiv:2602.12413); here both sides are t programs, so the interpreter is the only executor needed. String
matching is not used to decide anything, because it does not survive a renaming (arXiv:2311.04850).

What it cannot see: a program of the same function under other parameter types (a pair where the document
takes two values); a function the document's small input domain cannot tell from its neighbour (two programs
that differ only on long sequences are the same here, which errs on the side of removing); and a document with
fewer than 10 usable inputs is never a candidate, so the panel leans toward functions with a roomy domain.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import heldout_audit                                            # noqa: E402
import interp                                                   # noqa: E402
import spec_experiment as se                                    # noqa: E402
import surface                                                  # noqa: E402

INPUTS = 120                  # inputs of the document's own domain its requires admits, at most
DOMAIN_LIMIT = 400            # points of interp.domain looked at to find them
MIN_BOTH = 10                 # inputs both programs must answer before they are compared at all
NEAR = 0.10                   # differing on fewer than this share is the same function (t/twin_draws.py)
SOURCES = ("https://ar5iv.labs.arxiv.org/html/2305.01210", "https://arxiv.org/html/2602.12413v1",
           "https://arxiv.org/abs/2311.04850")
_STEM = re.compile(r"vericoding_([A-Za-z]{2}\d{4})")
_SILENT = (interp.Undef, interp.Budget, RecursionError, ZeroDivisionError, TypeError, ValueError, KeyError,
           IndexError, AttributeError, OverflowError)


def document_key(row: dict) -> str:
    """The document a row belongs to: its vericoding task whatever the spelling, else its name. A row with no
    name (a repair, a memory conversation) belongs to the vericoding task it mentions, or to nothing."""
    name = row.get("name")
    if isinstance(name, str) and name and name != "None":
        m = _STEM.match(name)
        return f"v:{m.group(1).lower()}" if m else f"n:{name}"
    for text in heldout_audit.strings(row):
        m = _STEM.search(text)
        if m:
            return f"v:{m.group(1).lower()}"
    return "n:"


def signature(task: dict) -> tuple:
    return (tuple(str(p["type"]) for p in task["params"]), str(task["returns"][0]["type"]))


def run(task: dict, values: list):
    """The program's answer on these argument values, or None when it gives none (its requires excludes them,
    the interpreter finds them undefined or runs out of budget)."""
    env = {p["name"]: v for p, v in zip(task["params"], values)}
    try:
        funs = interp.funs_of(task, task["body"])
        st = interp.St()
        if not all(interp.ev(c, dict(env), funs, st) for c in task.get("requires", [])):
            return None
        env2 = dict(env)
        ret = task["returns"][0]["name"]
        env2[ret] = None
        interp.exec_body(task["body"], env2, funs, st)
        return env2[ret]
    except _SILENT:
        return None


def inputs(task: dict, n: int = INPUTS, limit: int = DOMAIN_LIMIT) -> list[tuple[list, object]]:
    """(argument values, the program's answer) for inputs of the program's own domain that it answers."""
    names = [(p["name"], p["type"]) for p in task["params"]]
    out = []
    try:
        for env in interp.domain(task, names, limit):
            values = [env[name] for name, _ in names]
            answer = run(task, values)
            if answer is not None:
                out.append((values, answer))
                if len(out) >= n:
                    break
    except _SILENT:
        pass
    return out


def compare(reference_inputs: list[tuple[list, object]], program: dict) -> tuple[int, int]:
    """(inputs both answer, inputs they answer alike)."""
    both = agree = 0
    for values, want in reference_inputs:
        got = run(program, values)
        if got is None:
            continue
        both += 1
        agree += int(got == want and isinstance(got, bool) == isinstance(want, bool))
    return both, agree


def same(both: int, agree: int) -> bool:
    return both >= MIN_BOTH and (both - agree) / both < NEAR


def parse_program(block: str) -> dict | None:
    """A t program with a body, or None (not t, or a question)."""
    try:
        task = surface.parse(block)
    except Exception:                                           # noqa: BLE001 -- not a t program
        return None
    return task if task.get("body") and task.get("returns") else None


def programs_of(rows: list[dict]) -> dict[str, dict]:
    """digest -> {"block", "rows": the indices of the rows that hold it}, answers and prompts alike."""
    out: dict[str, dict] = {}
    for index, row in enumerate(rows):
        for block in heldout_audit.blocks(row):
            digest = hashlib.sha256(block.encode("utf-8")).hexdigest()[:16]
            out.setdefault(digest, {"block": block, "rows": set()})["rows"].add(index)
    return out


# ---------------------------------------------------------------- workers --

_PROGRAMS: dict[str, tuple[dict, frozenset[int]]] = {}


def _load(programs: dict[str, dict]) -> None:
    global _PROGRAMS
    _PROGRAMS = {}
    for digest, entry in programs.items():
        task = parse_program(entry["block"])
        if task is not None:
            _PROGRAMS[digest] = (task, frozenset(entry["rows"]))


def _matching_rows(item: tuple[str, str]) -> tuple[str, dict]:
    """For one reference program: how many usable inputs it has, and every row holding a program that behaves
    as it does (its own rows among them)."""
    key, block = item
    task = parse_program(block)
    if task is None:
        return key, {"usable": 0, "rows": None}
    ins = inputs(task)
    if len(ins) < MIN_BOTH:
        return key, {"usable": len(ins), "rows": None}
    sig, rows = signature(task), set()
    for other, holders in _PROGRAMS.values():
        if signature(other) == sig and not holders <= rows and same(*compare(ins, other)):
            rows |= holders
    return key, {"usable": len(ins), "rows": sorted(rows)}


def matching_rows(rows: list[dict], references: dict[str, str], jobs: int = 8) -> dict[str, dict]:
    """key -> {"usable": N, "rows": sorted row indices or None when the reference has too few usable inputs}."""
    programs = programs_of(rows)
    items = sorted(references.items())
    if jobs > 1 and len(items) > 4:
        with mp.Pool(jobs, initializer=_load, initargs=(programs,)) as pool:
            return dict(pool.imap_unordered(_matching_rows, items, chunksize=2))
    _load(programs)
    return dict(_matching_rows(item) for item in items)


# ------------------------------------------------------------------- draw --

def candidates(rows: list[dict], only_names: set[str] | None = None, table: dict | None = None) -> dict[str, dict]:
    """document key -> its first specification-given row, for documents that may be held out."""
    table = heldout_audit.lineage() if table is None else table
    out: dict[str, dict] = {}
    lineage_keys = {document_key(row) for row in rows if heldout_audit.gpl_origin(row, table)}
    for row in rows:
        if row.get("kind") != "spec-given":
            continue
        key = document_key(row)
        if key in out or key in lineage_keys or key == "n:":
            continue
        if only_names is not None and row.get("name") not in only_names:
            continue
        block = se.find_block(str(row.get("chosen", "")))
        if block is not None and parse_program(block) is not None:
            out[key] = row
    return out


def order(seed: str, key: str) -> str:
    return hashlib.sha256(f"{seed}:{key}".encode("utf-8")).hexdigest()


def draw(rows: list[dict], k: int, seed: str, only_names: set[str] | None = None, max_remove: int = 4,
         jobs: int = 8) -> tuple[list[dict], list[int], dict]:
    """(panel questions, indices of the rows that leave training, a report)."""
    cands = candidates(rows, only_names)
    by_key: dict[str, set[int]] = {}
    for index, row in enumerate(rows):
        by_key.setdefault(document_key(row), set()).add(index)
    refs = {key: se.find_block(str(row["chosen"])) for key, row in cands.items()}
    found = matching_rows(rows, refs, jobs)
    removal = {key: (None if found[key]["rows"] is None else sorted(set(found[key]["rows"]) | by_key[key]))
               for key in cands}
    eligible = sorted((key for key in cands if removal[key] is not None and len(removal[key]) <= max_remove),
                      key=lambda key: order(seed, key))
    chosen = eligible[:k]
    removed = sorted({index for key in chosen for index in removal[key]})
    panel = [{"name": cands[key].get("name"), "document": key, "prompt": cands[key].get("prompt"),
              "chosen": cands[key].get("chosen"), "heldout": True, "usable_inputs": found[key]["usable"],
              "rows_removed": len(removal[key])} for key in chosen]
    report = {"rule": __doc__.split("`draw` makes")[1].split("\n\n")[0].replace("\n", " ").strip(),
              "sources": list(SOURCES), "seed": seed, "k": k, "max_remove": max_remove,
              "documents_with_a_specification_given_row": len(cands),
              "too_few_usable_inputs": sum(1 for key in cands if removal[key] is None),
              "eligible": len(eligible), "drawn": len(chosen), "rows_removed": len(removed),
              "removal_set_sizes": sorted(len(removal[key]) for key in chosen)}
    return panel, removed, report


# ------------------------------------------------------------------ check --

def check(rows: list[dict], panel: list[dict], jobs: int = 8) -> list[dict]:
    """One finding per (row, question): the row names the question's document, or holds a program that answers
    the question's own inputs as its reference does."""
    refs, names = {}, {}
    for question in panel:
        key = question.get("document") or document_key(question)
        block = se.find_block(str(question.get("chosen", "")))
        if block is not None:
            refs[key] = block
        names[key] = question.get("name")
    findings = []
    for index, row in enumerate(rows):
        key = document_key(row)
        if key in names and key != "n:":
            findings.append({"row": index, "question": names[key], "why": "document"})
    for key, result in matching_rows(rows, refs, jobs).items():
        for index in result["rows"] or []:
            findings.append({"row": index, "question": names[key], "why": "behaviour"})
    for finding in findings:
        row = rows[finding["row"]]
        finding.update(name=row.get("name"), kind=row.get("kind"))
    return findings


# ------------------------------------------------------------------- main --

def _rows(path: Path) -> tuple[list[str], list[dict]]:
    lines = [line for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    return lines, [json.loads(line) for line in lines]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("draw")
    d.add_argument("--rows", type=Path, required=True)
    d.add_argument("--k", type=int, required=True)
    d.add_argument("--seed", required=True, help="no default: the order of the draw is sha256(seed:document)")
    d.add_argument("--only-names", type=Path, help="one document name a line; other documents are not candidates")
    d.add_argument("--max-remove", type=int, default=4)
    d.add_argument("--panel", type=Path, required=True)
    d.add_argument("--keep", type=Path, required=True)
    d.add_argument("--report", type=Path)
    d.add_argument("--jobs", type=int, default=8)
    c = sub.add_parser("check")
    c.add_argument("--rows", type=Path, required=True)
    c.add_argument("--panel", type=Path, required=True)
    c.add_argument("--keep", type=Path)
    c.add_argument("--json", type=Path)
    c.add_argument("--jobs", type=int, default=8)
    a = ap.parse_args(argv)
    lines, rows = _rows(a.rows)
    if a.cmd == "draw":
        only = ({n.strip() for n in a.only_names.read_text(encoding="utf-8").splitlines() if n.strip()}
                if a.only_names else None)
        panel, removed, report = draw(rows, a.k, a.seed, only, a.max_remove, a.jobs)
        if len(panel) < a.k:
            raise SystemExit(f"spec_panel: {len(panel)} eligible documents, {a.k} asked for")
        a.panel.write_text("".join(json.dumps(q, sort_keys=True) + "\n" for q in panel), encoding="utf-8")
        gone = set(removed)
        a.keep.write_text("".join(line + "\n" for k, line in enumerate(lines) if k not in gone), encoding="utf-8")
        report["rows"] = len(rows)
        report["kept"] = len(rows) - len(gone)
        if a.report:
            a.report.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
        print(json.dumps({k: v for k, v in report.items() if k not in ("rule", "sources")}))
        return 0
    panel = [json.loads(line) for line in a.panel.read_text(encoding="utf-8").splitlines() if line.strip()]
    findings = check(rows, panel, a.jobs)
    bad = sorted({f["row"] for f in findings})
    by = {}
    for f in findings:
        by.setdefault(f["question"], set()).add(f["row"])
    print(f"{len(rows)} rows, {len(panel)} questions; {len(bad)} rows match a question"
          + "".join(f"\n  {q}: {len(v)} rows" for q, v in sorted(by.items(), key=lambda kv: str(kv[0]))))
    if a.json:
        a.json.write_text(json.dumps({"sources": SOURCES, "findings": findings}, indent=1) + "\n", encoding="utf-8")
    if a.keep:
        gone = set(bad)
        a.keep.write_text("".join(line + "\n" for k, line in enumerate(lines) if k not in gone), encoding="utf-8")
        print(f"kept {len(rows) - len(gone)} of {len(rows)} rows in {a.keep}")
    return 1 if bad else 0


if __name__ == "__main__":                                      # pragma: no cover
    raise SystemExit(main())
