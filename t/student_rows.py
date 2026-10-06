#!/usr/bin/env python3
"""t/student_rows.py -- "specification given, write the body" rows for the student (2026-10-01).

    python3 t/student_rows.py --corpus t/out/loop/corpus-r12-headed.txt --split t/out/loop/split-v5.json \
        --split-seed 1338 --train-rows english.jsonl debug.jsonl --out rows.jsonl --heldout questions.jsonl

The setting every published success uses: the vericoding benchmark (arXiv:2509.22908) gives the
model a formal specification and asks for verified code, SAFE (arXiv:2410.15756) trains its
student on (program and specification) to proof, and AlphaVerus (arXiv:2412.06176) generates
verified code "given only the specifications". Each document of a registered corpus is a `t`
task every kernel proved; it is printed once with an empty body as the question and once in full
as the answer. The header, the parameters, the requires and ensures and the spec funs are given
(they are the specification); the body, its invariants and its decreases are what is asked for.

Held out first, rows second. The corpus is split by the project's own rule
(locallm/data.split_documents: a hash of each document, --split-seed), training rows come from
the train side only, and the held-out side becomes the question set after three removals, each
counted by reason:

  - its problem has an answer in the other training rows (--train-rows, by problem id);
  - the same program, its own name aside, is a training document;
  - the same specification, its own name aside, is a training document.

The first version of this file (a763b388) built rows from every document. All of the corpus's
validation documents were therefore in the training rows, and nothing was held out. Measured on
the r12 corpus at seed 1338: 55 documents held out by the hash; 14 share a problem with the
English or debugging rows, 6 are a renamed copy of a training document's program and 2 of its
specification; 33 are left. The comparison is textual (identical once the task's name is
normalised); a program that differs by a variable name is not caught, and
t/behavioural_decontam.py is the tool for that level.

Rows are t/loop_train.py's and t/student_sft.py's shape (`prompt` messages, `chosen` fenced
answer) with `kind: "spec-given"`. A document named for a held-out, dev or policy-excluded problem
of the problem split stops the build by name.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import loop_dataset                                             # noqa: E402
import loop_filter                                              # noqa: E402
import spec_experiment                                          # noqa: E402
import surface                                                  # noqa: E402

ASK = ("Complete this t task. Keep its header, parameters, requires, ensures and spec funs exactly "
       "as given and write the body, with loop invariants and decreases where there is a loop, so "
       "that the provers can verify it.\n\n")


def documents(corpus_text: str) -> list[dict]:
    """The corpus's tasks, parsed; a document is its optional head lines and one t program."""
    out = []
    for doc in re.split(r"\n\n\n+", corpus_text):
        if not doc.strip():
            continue
        lines = doc.split("\n")
        start = next((k for k, l in enumerate(lines) if re.match(r"^(t [01]$|datatype )", l)), None)
        if start is None:
            raise SystemExit(f"student_rows: a document has no t program: {doc[:80]!r}")
        out.append(surface.parse("\n".join(lines[start:]) + "\n"))
    return out


def blocked_ids(split_path: Path) -> set[int]:
    split = json.loads(split_path.read_text(encoding="utf-8"))
    policy = loop_filter.decontamination()
    return ({int(i) for i in split["eval_ids"]} | set(loop_filter.r12_dev_ids(HERE / "r12-dev-ids.json"))
            | set(policy.exclude_train_ids) | set(policy.overlap_eval_ids))


def row_for(task: dict) -> dict:
    question = surface.print_task(dict(task, body=[])).strip()
    answer = surface.print_task(task).strip()
    return {"kind": "spec-given", "name": task["name"], "source": "corpus",
            "prompt": [{"role": "system", "content": spec_experiment.STUDENT_SYSTEM},
                       {"role": "user", "content": ASK + loop_dataset.fence(question)}],
            "chosen": loop_dataset.fence(answer)}


def _normalised(task: dict, body: bool) -> str:
    """The task printed under one fixed name, so a renamed copy compares equal."""
    import copy
    t = copy.deepcopy(task if body else dict(task, body=[]))
    return surface.print_task(spec_experiment.rename_task(t, "f"))


def split_corpus(corpus_text: str, split_seed: int, val_frac: float = 0.1) -> tuple[list[dict], list[dict]]:
    """(train tasks, held-out tasks) by the project's own document split (hash of the document)."""
    sys.path.insert(0, str(HERE.parent / "locallm"))
    import data
    train, held = data.split_documents(corpus_text, val_frac, split_seed, "hash")
    return documents("\n\n\n".join(train)), documents("\n\n\n".join(held))


def clean_heldout(train: list[dict], held: list[dict], train_problem_ids: set[int]) -> tuple[list[dict], dict]:
    """The held-out tasks that share nothing textual with training, and why the others were removed."""
    programs = {_normalised(t, body=True) for t in train}
    specs = {_normalised(t, body=False) for t in train}
    keep, removed = [], {"problem answered in the other training rows": 0,
                         "same program as a training document": 0,
                         "same specification as a training document": 0}
    for t in held:
        tid = loop_filter.problem_id(t["name"])
        if tid is not None and tid in train_problem_ids:
            removed["problem answered in the other training rows"] += 1
        elif _normalised(t, body=True) in programs:
            removed["same program as a training document"] += 1
        elif _normalised(t, body=False) in specs:
            removed["same specification as a training document"] += 1
        else:
            keep.append(t)
    return keep, removed


def _spec_without_gate(task: dict) -> str:
    """The specification printed under one name with the header's gate line and the version left out: a gate says
    which features the program uses, not what it promises."""
    import copy
    t = copy.deepcopy(dict(task, body=[]))
    for key in ("gate", "gates"):
        t.pop(key, None)
    t["t"] = 1
    return surface.print_task(spec_experiment.rename_task(t, "f"))


_VERICODING_STEM = re.compile(r"vericoding_([a-z]{2}\d{4})")


def leaks_heldout(rows: list[dict], held: list[dict]) -> list[tuple[int, str]]:
    """(index, reason) for every training row that answers one of the held-out specification-given questions:
    `stem`, the same vericoding source problem (its DA/DD/... number); `text`, the program or the specification equal
    once names are normalised (clean_heldout's test); `spec-without-gate`, the specification equal once the header's
    gate line and version are left out too. The textual test alone let vericoding_DD0680 through, whose held-out copy
    (vericoding_dd0680__replaceBlanksWithChar) carries `gate loops` (2026-10-04). Rows without a t block are skipped."""
    def task_of(text):
        return surface.parse(spectext(text))

    def spectext(text):
        block = spec_experiment.find_block(text)
        if block is None:
            raise ValueError("no t block")
        return block

    held_tasks = [task_of(h["chosen"]) for h in held]
    programs = {_normalised(t, body=True) for t in held_tasks}
    specs = {_normalised(t, body=False) for t in held_tasks}
    gateless = {_spec_without_gate(t) for t in held_tasks}
    stems = {m.group(1) for h in held for m in [_VERICODING_STEM.match(str(h.get("name", "")).lower())] if m}
    out = []
    for i, row in enumerate(rows):
        m = _VERICODING_STEM.match(str(row.get("name", "")).lower())
        if m and m.group(1) in stems:
            out.append((i, "stem"))
            continue
        try:
            t = task_of(row.get("chosen", ""))
        except (ValueError, surface.SurfaceError):
            continue
        if _normalised(t, body=True) in programs or _normalised(t, body=False) in specs:
            out.append((i, "text"))
        elif _spec_without_gate(t) in gateless:
            out.append((i, "spec-without-gate"))
    return out


def build(corpus_path: Path, split_path: Path, split_seed: int, train_rows: list[Path],
          val_frac: float = 0.1) -> tuple[list[dict], list[dict], dict]:
    """(training rows from the train side, held-out question rows, a report)."""
    blocked = blocked_ids(split_path)
    train, held = split_corpus(corpus_path.read_text(encoding="utf-8"), split_seed, val_frac)
    for task in train + held:
        tid = loop_filter.problem_id(task["name"])
        if tid is not None and tid in blocked:
            raise SystemExit(f"student_rows: {task['name']} is a held-out, dev or excluded problem")
    other_ids = set()
    for path in train_rows:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                if "task_id" in row:
                    other_ids.add(int(row["task_id"]))
    keep, removed = clean_heldout(train, held, other_ids)
    rows, seen = [], set()
    for task in train:
        row = row_for(task)
        if row["chosen"] not in seen:
            seen.add(row["chosen"])
            rows.append(row)
    questions = [dict(row_for(t), heldout=True) for t in keep]
    report = {"corpus": str(corpus_path), "split_seed": split_seed, "val_frac": val_frac,
              "train_documents": len(train), "heldout_documents": len(held), "removed": removed,
              "training_rows": len(rows), "heldout_questions": len(questions),
              "comparison": "textual, task name normalised; not behavioural"}
    return rows, questions, report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", type=Path, required=True)
    ap.add_argument("--split", type=Path, required=True, help="the problem split (held-out and dev problem ids)")
    ap.add_argument("--split-seed", type=int, required=True, help="the corpus document split's seed")
    ap.add_argument("--val-frac", type=float, default=0.1)
    ap.add_argument("--train-rows", type=Path, nargs="*", default=[],
                    help="the other training rows; a held-out document whose problem they answer is removed")
    ap.add_argument("--out", type=Path, required=True, help="training rows, from the train side only")
    ap.add_argument("--heldout", type=Path, required=True, help="the held-out questions (never trained on)")
    a = ap.parse_args(argv)
    rows, questions, report = build(a.corpus, a.split, a.split_seed, a.train_rows, a.val_frac)
    for path, items in ((a.out, rows), (a.heldout, questions)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in items), encoding="utf-8")
    print(json.dumps(report))
    return 0


if __name__ == "__main__":                                      # pragma: no cover
    raise SystemExit(main())
