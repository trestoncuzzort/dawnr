#!/usr/bin/env python3
"""t/twin_hints.py -- one twin per hint: strip one proof annotation at a time
from a program the seven kernels verified (2026-09-25, r12 data build, track
W6; internal/RESEARCH-NEXT-2026-09-20.md "four more" item 4; ROADMAP-LOG
WS-19).

    python3 t/twin_hints.py emit --twins t/twins --split t/out/loop/split-v5.json --out DIR
    python3 t/twin_hints.py emit --tasks t/tasks --table t/AGREEMENT.md --split ... --out DIR
    python3 t/twin_hints.py classify --out DIR --table DIR/grade/table.md

t/twins holds 426 pairs over 213 programs, one twin family each, every twin a
change to the BODY. This is the other family: the body and the ensures stay
byte-identical and one HINT goes, so the program still passes every test it
passed (same executable semantics by construction, asserted per twin) and
only the proof side can move. A program with N hints yields N twins, one per
hint, each named by the hint it lost.

WHAT A HINT IS IN t, read off surface.py's grammar and check_wf's gates:

  strippable    `invariant` on a `while` (zero or more are allowed);
                `requires` on the task (zero or more are allowed; stripping
                one widens the precondition, so this twin can change what the
                spec says about inputs the program never had to handle).
  unstrippable  a loop's `decreases` (the grammar requires it: `while Expr
                invariant* decreases Expr`, so its absence is a parse error);
                a task's `decreases` (check_wf gate 3, decreases-selfcall:
                a self-recursive body without one is ill-formed);
                a spec fun's `decreases` (grammar-required);
                `assert` (t has no assert statement).
                These are COUNTED per program (the census the report needs)
                and never emitted: a twin that fails to parse or to type
                teaches syntax, not proof.

WHY EVERY TWIN IS GRADED BEFORE IT IS CALLED ANYTHING. DafnyBench
(arXiv:2406.08467, fetched 2026-09-25 from ar5iv.labs.arxiv.org/html/
2406.08467) strips every hint from a verified file at once and still finds
113 of its 556 GitHub programs verify with no hints at all; the retired
forge/dafny_pairs.py (git a736d82) measured single-hint strips on the same
benchmark and 210 of 782 (26.9 percent) still verified. "Hint removed, so
the proof fails" is false often enough that assuming it would mint negatives
pointing the wrong way. AlphaVerus (arXiv:2412.06176, fetched 2026-09-25
from ar5iv.labs.arxiv.org/html/2412.06176) keeps only what the real verifier
accepts and adds a filter against specifications weakened to pass, which is
exactly what a stripped `requires` is. So a twin here is written with
class `ungraded` and earns a class only from its own seven-kernel run
(t/run_par.py over the grade/ directory this writes), read back by
`classify`:

  redundant       verified in all seven without the hint: not a twin, the
                  hint was decorative for every kernel (data about the
                  lowerings, kept, never a negative);
  proof-breaking  at least one kernel UNPROVED (the certificate is the only
                  door to REFUTED in every adapter, and a body that still
                  meets its ensures has no certificate), the rest verified
                  or unproved: the negative this project wants, and
                  `breaks_in` names which kernels needed the hint;
  behavioural     at least one kernel REFUTED: only a `requires` strip can
                  do this, the widened precondition admits an input where
                  the body violates `ensures` or is undefined, the
                  interpreter's real witness (harness.real_witness) is
                  lowered into the certificate, and a sound kernel refutes;
                  `witness` is recorded at emit time so the run can be
                  checked against the prediction;
  undecided       some column is timeout, tool_error, malformed, vacuous,
                  abstain, flaked or absent, and nothing above applies:
                  not a verdict, re-run before it is anything.

THE GATES every training-data change goes through (t/RUN-NEXT-locallm-r12.md
section A, blockers A1 and A2): a source program that names a held-out id
under any alias (loop_filter.problem_id over the name, the text and the
recorded task id), a same-task exclusion (t/decontamination-2026-09-21.json)
or a dev-split id (t/r12-dev-ids.json, valid for the one split it was drawn
from) is REFUSED by name, printed, and written to REFUSED.tsv; without
--skip-refused a refusal stops the run. Nothing is dropped quietly.

LAYOUT, the one t/twins uses (t/twins_artifact.py), so a reader of one can
read the other: `pairs/<task>.<id>.json` with the same fields (`program`,
`twin`, `operator`, `witness`, `witness_reads`, `verified_by`,
`twin_refuted_by`, `written_by`) plus `hint` (kind, loop, index, text),
`class`, `twin_verified_by`, `breaks_in`, `unknown_in`, `twin_outcomes` and
`grading_name`; `INDEX.tsv` with t/twins' five columns then `hint` and
`class`; `README.md` with the counts; `REFUSED.tsv`; `census.json`; and
`grade/tasks/<task>__h<id>.t`, one renamed copy per twin for run_par (rows
are keyed by task name, several programs answer one problem under one name,
and a self-recursive task's call is renamed with it), with
`grade/MANIFEST.tsv` mapping row to pair file.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import check_wf                 # noqa: E402
import loop_filter              # noqa: E402
import surface                  # noqa: E402
import tasks_io                 # noqa: E402
from twins_artifact import KERNELS   # noqa: E402  (the same seven, the same order of record)

SEVEN = sorted(KERNELS)
UNSTRIPPABLE = ("loop-decreases", "task-decreases", "spec-fun-decreases", "assert")
CLASSES = ("ungraded", "redundant", "proof-breaking", "behavioural", "undecided")
INDEX_HEADER = "task\tproblem\toperator\twritten by\tfile\thint\tclass"
CELLS_PER_TWIN = len(SEVEN)


class TwinRefused(Exception):
    """A twin, a source or a table this module will not write or read. Always
    named; never a silent skip."""


@dataclass(frozen=True)
class Source:
    """One program verified in all seven, as the record says."""
    name: str
    problem: int | None
    written_by: str
    text: str                      # canonical print of the task, stripped
    verified_by: list


# ---------------------------------------------------------------- the hints --

def _loops(body: list, out: list) -> list:
    """Every `while` node under `body`, pre-order across `if` branches, the
    same order harness.py's operators walk a body."""
    for s in body:
        if "while" in s:
            out.append(s["while"])
            _loops(s["while"]["body"], out)
        elif "if" in s:
            _loops(s["if"]["then"], out)
            _loops(s["if"]["else"], out)
    return out


def executable_body(body: list) -> list:
    """The body with every loop's invariants erased: what runs. A hint strip
    must leave this byte-identical, which is why the program's tests pass
    by construction (the invariants are read by kernels, never executed)."""
    out = copy.deepcopy(body)
    for w in _loops(out, []):
        w["invariants"] = []
    return out


def hints(task: dict) -> tuple[list[dict], dict]:
    """(strippable hints in emission order, unstrippable census).

    Order: the task's `requires` clauses, then each loop's invariants in
    pre-order. A hint carries enough to find it again and to name it:
    kind, loop (invariants only, the loop's pre-order number), index and
    its printed text."""
    out = []
    for j, e in enumerate(task.get("requires", [])):
        out.append({"kind": "requires", "index": j, "text": surface.pexpr(e)})
    loops = _loops(task["body"], [])
    for k, w in enumerate(loops):
        for j, inv in enumerate(w["invariants"]):
            out.append({"kind": "invariant", "loop": k, "index": j, "text": surface.pexpr(inv)})
    census = {"loop-decreases": len(loops),
              "task-decreases": 1 if "decreases" in task else 0,
              "spec-fun-decreases": len(task.get("spec_funs", [])),
              "assert": 0}
    return out, census


def strip_hint(task: dict, hint: dict) -> dict:
    """The task without `hint`, or TwinRefused when the hint is not where it
    says it is (index and text both checked) or the result is not
    well-formed t (check_wf; it never is for these two kinds, and the guard
    stays so a future hint kind cannot slip an ill-formed twin through)."""
    v = copy.deepcopy(task)
    kind = hint.get("kind")
    if kind == "requires":
        clauses = v.get("requires", [])
        j = hint.get("index")
        if not isinstance(j, int) or not 0 <= j < len(clauses) \
                or surface.pexpr(clauses[j]) != hint.get("text"):
            raise TwinRefused(f"{task['name']}: no requires clause {j!r} reading {hint.get('text')!r}")
        del clauses[j]
    elif kind == "invariant":
        loops = _loops(v["body"], [])
        k, j = hint.get("loop"), hint.get("index")
        if not isinstance(k, int) or not 0 <= k < len(loops):
            raise TwinRefused(f"{task['name']}: no loop {k!r} ({len(loops)} loop(s))")
        invs = loops[k]["invariants"]
        if not isinstance(j, int) or not 0 <= j < len(invs) \
                or surface.pexpr(invs[j]) != hint.get("text"):
            raise TwinRefused(f"{task['name']}: loop {k} has no invariant {j!r} reading {hint.get('text')!r}")
        del invs[j]
    else:
        raise TwinRefused(f"{task['name']}: {kind!r} is not a hint kind this module strips "
                          f"(invariant, requires); decreases and assert are unstrippable by rule")
    errs = check_wf.check_wf(v)
    if errs:
        raise TwinRefused(f"{task['name']} without its {kind} is not well-formed t: "
                          + "; ".join(str(e) for e in errs))
    return v


def twins_of(task: dict) -> list[dict]:
    """One twin per strippable hint: {operator, hint, twin (AST), twin_text}.
    Each is checked to differ from the program's canonical print by exactly
    one removed line, to keep body and ensures byte-identical, and to round
    trip through surface.parse; any failure is TwinRefused, never a twin
    with a footnote."""
    hs, _ = hints(task)
    program = surface.print_task(task).strip()
    plines = program.splitlines()
    out, per_kind = [], Counter()
    for h in hs:
        n = per_kind[h["kind"]]
        per_kind[h["kind"]] += 1
        op = f"drop-{h['kind']}" + ("" if n == 0 else f"#{n}")
        v = strip_hint(task, h)
        text = surface.print_task(v).strip()
        if surface.parse(text + "\n") != v:
            raise TwinRefused(f"{task['name']} {op}: the twin does not round trip through surface.parse")
        if executable_body(v["body"]) != executable_body(task["body"]) or v["ensures"] != task["ensures"]:
            raise TwinRefused(f"{task['name']} {op}: a hint strip changed the executable body or the ensures")
        # A multiset difference, not a set one: a program may state the same
        # clause twice (a lifted DafnyBench task does), and stripping one of
        # the two removes a line whose text is still present.
        removed = Counter(plines) - Counter(text.splitlines())
        if len(plines) - len(text.splitlines()) != 1 or sum(removed.values()) != 1:
            raise TwinRefused(f"{task['name']} {op}: the twin is not the program less one line")
        out.append({"operator": op, "hint": h, "twin": v, "twin_text": text})
    return out


def real_witness_sentence(w: dict | None) -> str:
    """harness.real_witness's three shapes as a line a person can read. It is
    the REAL body's own witness (the twin has the same body), so unlike
    twins_artifact.witness_sentence it never says what "the twin answers":
    the input was outside the precondition the twin no longer has."""
    if not isinstance(w, dict) or not w:
        return ""
    args = ", ".join(f"{k}={json.dumps(v)}" for k, v in sorted(w.items()) if not k.startswith("_"))
    admitted = f"at {args}, an input the stripped requires excluded,"
    kind = w.get("_kind")
    if kind == "value":
        return f"{admitted} the program answers {json.dumps(w.get('_real'))} and `ensures` is false"
    if kind == "undefined":
        if w.get("_site") == "ensures":
            return (f"{admitted} the program answers {json.dumps(w.get('_value'))} and `ensures` "
                    f"is undefined at {json.dumps(w.get('_expr'))}")
        return f"{admitted} the body is undefined ({w.get('_twin')})"
    if kind == "measure":
        return (f"{admitted} the measure at {json.dumps(w.get('_site'))} does not decrease "
                f"({json.dumps(w.get('_caller_measure'))} to {json.dumps(w.get('_callee_measure'))})")
    return f"{admitted} the program breaks the specification ({kind})"


# ------------------------------------------------------- names and renaming --

def grading_name(task: str, twin_id: str) -> str:
    """The row name a twin has in run_par's table. `<task>__h<id>` keeps
    loop_filter.problem_id's reading of the task (the family prefix is
    followed by `__`), so the gates fire on the grading copy too."""
    return f"{task}__h{twin_id}"


def _rename_calls(node, old: str, new: str):
    if isinstance(node, dict):
        if "call" in node and isinstance(node["call"], dict) and node["call"].get("fun") == old:
            node["call"]["fun"] = new
        for v in node.values():
            _rename_calls(v, old, new)
    elif isinstance(node, list):
        for v in node:
            _rename_calls(v, old, new)


def rename_task(task: dict, new_name: str) -> dict:
    """A copy of `task` named `new_name`, its self-calls renamed with it (a
    recursive task calls itself by name; check_wf's decreases-selfcall gate
    would otherwise refuse the copy). Spec funs keep their names."""
    v = copy.deepcopy(task)
    old = v["name"]
    v["name"] = new_name
    for key in ("requires", "ensures", "body"):
        _rename_calls(v.get(key), old, new_name)
    if "decreases" in v:
        _rename_calls(v["decreases"], old, new_name)
    _rename_calls(v.get("spec_funs"), old, new_name)
    return v


# ------------------------------------------------------------------ the gates --

def held_out_ids(split, dev_ids) -> set[int]:
    """The ids no twin may name: the split's eval_ids (loop_locallm.held_out's
    own reading; a run with no split is refused, "no unscoped training corpus
    is permitted") plus the dev-split ids when they belong to this split
    (loop_filter.r12_dev_ids checks the split's digest; a missing dev file
    is no dev ids, a malformed one is refused by name)."""
    if not split or not Path(split).exists():
        raise SystemExit(f"twin_hints needs --split <split.json> with eval_ids; not found: {split}")
    try:
        ids = {int(i) for i in json.loads(Path(split).read_text(encoding="utf-8"))["eval_ids"]}
    except (OSError, KeyError, TypeError, ValueError) as e:
        raise SystemExit(f"cannot read held-out ids from {split}: {e}")
    return ids | set(loop_filter.r12_dev_ids(Path(dev_ids), split_path=split))


def gate(source: Source, eval_ids: set[int], policy) -> str | None:
    """None when `source` may become twins, else the refusal text, by name."""
    task_ids = () if source.problem is None else [source.problem]
    v = loop_filter.validate_training_data(source.text, eval_ids, names=[source.name],
                                           task_ids=task_ids, policy=policy)
    if v.ok:
        return None
    why = []
    if v.held_out:
        why.append("names a held-out or dev id: " + loop_filter.held_out_detail(v.held_out))
    if v.same_task_names or v.same_task_ids:
        why.append("same-task exclusion: " + loop_filter.same_task_detail(v))
    return f"REFUSED {source.name} ({source.written_by}): " + "; ".join(why)


# ---------------------------------------------------------------- the sources --

def canonical(task: dict) -> str:
    return surface.print_task(task).strip()


def sources_from_twins(twins_dir: Path) -> list[Source]:
    """Every distinct program in a t/twins-layout directory whose record says
    verified in all seven (t/twins_artifact.py writes nothing weaker, so a
    pair that says less is a foreign file and is refused by name)."""
    seen, out = {}, []
    for path in sorted(Path(twins_dir).glob("pairs/*.json")):
        d = json.loads(path.read_text(encoding="utf-8"))
        if sorted(d.get("verified_by") or []) != SEVEN:
            raise TwinRefused(f"{path.name}: verified_by is not all seven; not a t/twins pair")
        text = canonical(surface.parse(d["program"] + "\n"))
        if text in seen:
            continue
        seen[text] = True
        out.append(Source(name=str(d["task"]), problem=d.get("problem"),
                          written_by=str(d.get("written_by")), text=text, verified_by=SEVEN))
    return out


def read_table(text: str) -> dict[str, dict[str, tuple[str, bool]]]:
    """A run_par/grade.py table (format_table's format): row name -> {kernel:
    (real outcome, flaked)}. All seven columns are required; a partial table
    is refused because a partial column is not a verdict on the twin."""
    lines = text.splitlines()
    header = next((l for l in lines if l.startswith("| task |")), None)
    if header is None:
        raise TwinRefused("not a run_par table: no `| task | ... |` header")
    cols = [c.strip() for c in header.strip().strip("|").split("|")][1:]
    if sorted(cols) != SEVEN:
        raise TwinRefused(f"the table has columns {cols}; all seven kernels are needed")
    rows, started = {}, False
    for line in lines:
        if line == header:
            started = True
            continue
        if not started:
            continue
        if not line.startswith("|"):
            break                                   # the task table is contiguous
        if line.startswith("|---"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != len(cols) + 1:
            raise TwinRefused(f"a table row has {len(cells) - 1} cells for {len(cols)} columns: {line!r}")
        row = {}
        for k, cell in zip(cols, cells[1:]):
            flaked = "(FLAKED)" in cell
            real = cell.replace("(FLAKED)", "").strip().split("/")[0].strip()
            row[k] = (real, flaked)
        rows[cells[0]] = row
    return rows


def verified_rows(rows: dict) -> set[str]:
    """The rows whose real side reads `verified`, unflaked, in all seven."""
    return {name for name, row in rows.items()
            if all(o == "verified" and not f for o, f in row.values())}


def sources_from_table(tasks_dir: Path, table: Path, written_by: str) -> list[Source]:
    """The tasks in `tasks_dir` (.t, or .json for an unconverted directory)
    whose row in `table` is verified in all seven."""
    ok = verified_rows(read_table(Path(table).read_text(encoding="utf-8")))
    out = []
    for path in tasks_io.load_dir(tasks_dir):
        task = tasks_io.load_task(path)
        if task["name"] not in ok:
            continue
        out.append(Source(name=task["name"], problem=loop_filter.problem_id(task["name"]),
                          written_by=written_by, text=canonical(task), verified_by=SEVEN))
    return out


# ------------------------------------------------------------ classification --

def classify(row: dict[str, tuple[str, bool]]) -> dict:
    """The class of one twin from its seven real-side outcomes (module
    docstring). A flaked cell counts as unknown whatever it reads."""
    verified = sorted(k for k, (o, f) in row.items() if o == "verified" and not f)
    refuted = sorted(k for k, (o, f) in row.items() if o == "refuted" and not f)
    unproved = sorted(k for k, (o, f) in row.items() if o == "unproved" and not f)
    known = set(verified) | set(refuted) | set(unproved)
    unknown = sorted(k for k in SEVEN if k not in known)
    if refuted:
        cls = "behavioural"
    elif unproved:
        cls = "proof-breaking"
    elif unknown:
        cls = "undecided"
    else:
        cls = "redundant"
    return {"class": cls, "twin_verified_by": verified, "twin_refuted_by": refuted,
            "breaks_in": sorted(set(refuted) | set(unproved)), "unknown_in": unknown,
            "twin_outcomes": {k: o + (" (FLAKED)" if f else "") for k, (o, f) in sorted(row.items())}}


UNGRADED = {"class": "ungraded", "twin_verified_by": [], "twin_refuted_by": [],
            "breaks_in": [], "unknown_in": [], "twin_outcomes": {}}


# ------------------------------------------------------------------- writing --

def _pairs(out: Path) -> list[tuple[Path, dict]]:
    rows = []
    for path in sorted((Path(out) / "pairs").glob("*.json")):
        rows.append((path, json.loads(path.read_text(encoding="utf-8"))))
    return sorted(rows, key=lambda pr: (str(pr[1]["task"]), pr[1]["id"]))


def _hint_label(rec: dict) -> str:
    h = rec["hint"]
    where = f"loop {h['loop']} " if h["kind"] == "invariant" else ""
    return f"{h['kind']} {where}#{h['index']}: {h['text']}"


def render_readme(recs: list[dict], census: dict | None) -> str:
    by_class = Counter(r["class"] for r in recs)
    by_op = Counter(str(r["operator"]).split("#")[0] for r in recs)
    programs = len({(r["task"], r["program"]) for r in recs})
    graded = [r for r in recs if r["class"] != "ungraded"]
    per_kernel = {k: Counter() for k in SEVEN}
    for r in graded:
        for k, o in r["twin_outcomes"].items():
            per_kernel[k][o.replace(" (FLAKED)", " flaked")] += 1
    lines = [
        "# t hint twins: verified programs paired with the same program less one hint", "",
        f"{len(recs)} twins from {programs} programs. Written by `t/twin_hints.py` (see its docstring);",
        "the layout is `t/twins/`, so the two artifacts read alike.", "",
        "Each file under `pairs/` holds one pair: `program` (a task in t, verified by all seven proof",
        "systems on the record `verified_by` names), `twin` (the same program with ONE hint removed,",
        "named in `operator` and located in `hint`; body and ensures byte-identical, so the program's",
        "tests pass by construction), and after grading `class`, `twin_outcomes` (the real-side outcome",
        "of every kernel on the twin), `breaks_in` (the kernels that needed the hint) and, for a",
        "`requires` strip, the interpreter's `witness` where the widened precondition breaks the spec.", "",
        "## Classes", "",
        "| class | twins | meaning |", "|---|---:|---|",
        f"| `ungraded` | {by_class.get('ungraded', 0)} | no kernel run on record yet; never a negative |",
        f"| `redundant` | {by_class.get('redundant', 0)} | verified in all seven without the hint: not a twin, data about the lowerings |",
        f"| `proof-breaking` | {by_class.get('proof-breaking', 0)} | some kernel unproved, none refuted: the proof needed the hint |",
        f"| `behavioural` | {by_class.get('behavioural', 0)} | some kernel refuted: the stripped `requires` admits an input the spec fails on |",
        f"| `undecided` | {by_class.get('undecided', 0)} | a timeout, tool error, malformed, vacuous, abstain or flaked column; not a verdict |",
        "", "## Operators", "", "| operator | twins |", "|---|---:|",
        *[f"| `{k}` | {v} |" for k, v in sorted(by_op.items(), key=lambda kv: (-kv[1], kv[0]))],
    ]
    if graded:
        outcomes = sorted({o for c in per_kernel.values() for o in c})
        lines += ["", f"## Per kernel, over the {len(graded)} graded twins", "",
                  "| kernel | " + " | ".join(outcomes) + " |", "|---|" + "---:|" * len(outcomes)]
        for k in SEVEN:
            lines.append(f"| {k} | " + " | ".join(str(per_kernel[k].get(o, 0)) for o in outcomes) + " |")
    if census:
        un = census.get("unstrippable", {})
        lines += ["", "## What could not be stripped", "",
                  "Counted, never emitted: a loop's `decreases` and a spec fun's `decreases` are required by",
                  "the grammar, a task's `decreases` by check_wf's gate 3, and t has no `assert`.", "",
                  "| hint kind | occurrences |", "|---|---:|",
                  *[f"| {k} | {un.get(k, 0)} |" for k in UNSTRIPPABLE],
                  "", f"Sources refused by the held-out, dev-split and same-task gates: "
                      f"{census.get('refused', 0)} (named in `REFUSED.tsv`)."]
    lines += ["", "## Provenance", "",
              "Every program was verified in all seven kernels on the record its `verified_by` names",
              "(`t/twins/`, `t/AGREEMENT.md`, or a sweep table); every twin's class comes from its own",
              "run through `t/run_par.py` over `grade/tasks/`, read back by `twin_hints.py classify`.",
              "", "## Licence", "",
              "Research and education only, as the repository's `LICENSE` states; commercial use, and",
              "training a model on this artifact outside research, need written permission.", ""]
    return "\n".join(lines)


def render_dir(out: Path) -> Counter:
    """INDEX.tsv, README.md, grade/tasks/*.t and grade/MANIFEST.tsv from the
    pairs on disk. Returns the class counts."""
    out = Path(out)
    pairs = _pairs(out)
    census = None
    if (out / "census.json").exists():
        census = json.loads((out / "census.json").read_text(encoding="utf-8"))
    index = [INDEX_HEADER]
    manifest = ["row\tfile"]
    gdir = out / "grade" / "tasks"
    gdir.mkdir(parents=True, exist_ok=True)
    for path in gdir.glob("*.t"):
        path.unlink()                               # regenerated below, never stale
    for path, r in pairs:
        rel = f"pairs/{path.name}"
        problem = "-" if r.get("problem") is None else str(r["problem"])
        index.append(f"{r['task']}\t{problem}\t{r['operator']}\t{r['written_by']}\t{rel}\t"
                     f"{_hint_label(r)}\t{r['class']}")
        manifest.append(f"{r['grading_name']}\t{rel}")
        graded = rename_task(surface.parse(r["twin"] + "\n"), r["grading_name"])
        (gdir / f"{r['grading_name']}.t").write_text(surface.print_task(graded),
                                                    encoding="utf-8", newline="\n")
    (out / "INDEX.tsv").write_text("\n".join(index) + "\n", encoding="utf-8", newline="\n")
    (out / "grade" / "MANIFEST.tsv").write_text("\n".join(manifest) + "\n", encoding="utf-8", newline="\n")
    (out / "README.md").write_text(render_readme([r for _, r in pairs], census),
                                   encoding="utf-8", newline="\n")
    return Counter(r["class"] for _, r in pairs)


# ------------------------------------------------------------------ emitting --

def _select(candidates: list, max_programs, max_cells) -> list:
    """The sample: with no limit, everything. With one, two queues sorted by
    (twins, name, id), programs with an invariant and programs with only
    `requires`, taken alternately so a small sample covers both hint kinds,
    each program admitted only while its twins fit the remaining cells
    (seven per twin) and the program count."""
    if max_programs is None and max_cells is None:
        return candidates
    key = lambda c: (len(c[2]), c[0].name, c[3])          # noqa: E731
    with_inv = sorted((c for c in candidates if any(t["hint"]["kind"] == "invariant" for t in c[2])), key=key)
    req_only = sorted((c for c in candidates if not any(t["hint"]["kind"] == "invariant" for t in c[2])), key=key)
    queues = [with_inv, req_only]
    cells_left = float("inf") if max_cells is None else max_cells
    progs_left = float("inf") if max_programs is None else max_programs
    chosen, turn = [], 0
    while any(queues) and progs_left > 0:
        q = queues[turn % 2]
        turn += 1
        if not q:
            continue
        c = q.pop(0)
        if len(c[2]) * CELLS_PER_TWIN > cells_left:
            q.clear()                               # sorted ascending: nothing later fits either
            continue
        chosen.append(c)
        cells_left -= len(c[2]) * CELLS_PER_TWIN
        progs_left -= 1
    return chosen


def emit(twins_dir, tasks_dir, table, written_by, split, dev_ids, out, max_programs=None,
         max_cells=None, skip_refused=False) -> dict:
    """The whole emission; returns the report main() prints."""
    import harness                                  # interp-backed, imported here so
    #                                               # the parse/strip half needs no verifiers
    eval_ids = held_out_ids(split, dev_ids)
    policy = loop_filter.decontamination()
    sources: list[Source] = []
    if twins_dir:
        sources += sources_from_twins(Path(twins_dir))
    if tasks_dir:
        if not table:
            raise SystemExit("--tasks needs --table, the record that says which of them verified in all seven")
        sources += sources_from_table(Path(tasks_dir), Path(table), written_by)
    if not sources:
        raise SystemExit("no source program: pass --twins DIR and/or --tasks DIR --table TABLE")
    seen, admitted, refused = set(), [], []
    for s in sources:
        if s.text in seen:
            continue
        seen.add(s.text)
        r = gate(s, eval_ids, policy)
        if r:
            print(r, flush=True)
            refused.append((s, r))
        else:
            admitted.append(s)
    if refused and not skip_refused:
        raise SystemExit(f"{len(refused)} source(s) refused by the gates, named above; nothing written. "
                         f"--skip-refused records them in REFUSED.tsv and goes on with the rest.")
    unstrippable = Counter()
    candidates = []
    for s in admitted:
        task = surface.parse(s.text + "\n")
        _, census = hints(task)
        unstrippable.update(census)
        tws = twins_of(task)
        if tws:
            candidates.append((s, task, tws, hashlib.sha256(s.text.encode("utf-8")).hexdigest()[:16]))
    chosen = _select(candidates, max_programs, max_cells)
    out = Path(out)
    (out / "pairs").mkdir(parents=True, exist_ok=True)
    written, duplicates, ids = 0, 0, set()
    for s, task, tws, _ in chosen:
        for tw in tws:
            twin_text = tw["twin_text"]
            key = hashlib.sha256((s.text + "\0" + twin_text).encode("utf-8")).hexdigest()[:16]
            if key in ids:
                # The same twin from two hints: a clause stated twice strips to
                # one text. One file, counted and said, never two files or a
                # silent overwrite (a lifted DafnyBench task, 2026-09-25).
                duplicates += 1
                print(f"  {s.name} {tw['operator']}: the same twin as an earlier hint of this "
                      f"program (a clause stated twice); one file", flush=True)
                continue
            ids.add(key)
            w, w_err = None, None
            if tw["hint"]["kind"] == "requires":
                try:
                    w = harness.real_witness(tw["twin"])
                except Exception as e:              # noqa: BLE001  (recorded, printed, never hidden)
                    w_err = f"{type(e).__name__}: {e}"
                    print(f"  {s.name} {tw['operator']}: witness search failed, {w_err}", flush=True)
            rec = {"id": key, "task": s.name, "problem": s.problem, "operator": tw["operator"],
                   "hint": tw["hint"], "written_by": s.written_by, "program": s.text,
                   "twin": twin_text, "verified_by": list(s.verified_by),
                   "witness": w, "witness_reads": real_witness_sentence(w),
                   "grading_name": grading_name(s.name, key), **UNGRADED}
            if w_err:
                rec["witness_error"] = w_err
            path = out / "pairs" / f"{s.name}.{key}.json"
            if path.exists():
                old = json.loads(path.read_text(encoding="utf-8"))
                for k in UNGRADED:                  # a re-emit keeps a class already earned
                    rec[k] = old.get(k, rec[k])
                rec["graded_from"] = old.get("graded_from")
                if rec.get("graded_from") is None:
                    rec.pop("graded_from")
            path.write_text(json.dumps(rec, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
            written += 1
    (out / "REFUSED.tsv").write_text(
        "source\twritten by\treason\n" + "".join(f"{s.name}\t{s.written_by}\t{r}\n" for s, r in refused),
        encoding="utf-8", newline="\n")
    census = {"sources": len(sources), "distinct": len(seen), "admitted": len(admitted),
              "refused": len(refused), "programs_with_hints": len(candidates),
              "twins_available": sum(len(c[2]) for c in candidates),
              "programs_emitted": len(chosen), "twins_emitted": written,
              "twins_duplicate": duplicates, "unstrippable": dict(unstrippable),
              "max_programs": max_programs, "max_cells": max_cells}
    (out / "census.json").write_text(json.dumps(census, indent=1, sort_keys=True) + "\n",
                                     encoding="utf-8", newline="\n")
    classes = render_dir(out)
    return {"sources": len(sources), "admitted": len(admitted), "refused": len(refused),
            "programs": len(chosen), "twins": written, "duplicates": duplicates,
            "cells": written * CELLS_PER_TWIN, "on_disk": sum(classes.values()),
            "unstrippable": dict(unstrippable)}


def classify_dir(out, table) -> Counter:
    """Read a run_par table over grade/tasks and write each twin's class. A
    row the manifest does not know is refused (the table is for another
    directory); a twin the table does not name goes back to `ungraded`."""
    out = Path(out)
    rows = read_table(Path(table).read_text(encoding="utf-8"))
    pairs = _pairs(out)
    by_name = {r["grading_name"]: (p, r) for p, r in pairs}
    foreign = sorted(set(rows) - set(by_name))
    if foreign:
        raise TwinRefused(f"the table names {len(foreign)} row(s) no twin here has: "
                          + ", ".join(foreign[:5]) + (" ..." if len(foreign) > 5 else ""))
    for name, (path, rec) in by_name.items():
        if name in rows:
            rec.update(classify(rows[name]))
            rec["graded_from"] = Path(table).name
        else:
            rec.update(UNGRADED)
            rec.pop("graded_from", None)
        path.write_text(json.dumps(rec, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return render_dir(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("emit", help="write one twin per hint for every admitted source")
    e.add_argument("--twins", type=Path, default=None, help="a t/twins-layout directory of verified programs")
    e.add_argument("--tasks", type=Path, default=None, help="a directory of .t or .json tasks")
    e.add_argument("--table", type=Path, default=None, help="the run_par table saying which tasks verified in all seven")
    e.add_argument("--written-by", default="committed", help="the provenance tag for --tasks (default committed)")
    e.add_argument("--split", type=Path, required=True, help="the split whose eval_ids are held out")
    e.add_argument("--dev-ids", type=Path, default=HERE / "r12-dev-ids.json")
    e.add_argument("--out", type=Path, required=True)
    e.add_argument("--max-programs", type=int, default=None)
    e.add_argument("--max-cells", type=int, default=None, help="seven cells per twin")
    e.add_argument("--skip-refused", action="store_true",
                   help="record refused sources in REFUSED.tsv and go on; without it a refusal stops the run")
    c = sub.add_parser("classify", help="read a run_par table over grade/tasks and write each twin's class")
    c.add_argument("--out", type=Path, required=True)
    c.add_argument("--table", type=Path, required=True)
    a = ap.parse_args(argv)
    try:
        if a.cmd == "emit":
            rep = emit(a.twins, a.tasks, a.table, a.written_by, a.split, a.dev_ids, a.out,
                       a.max_programs, a.max_cells, a.skip_refused)
            print(f"{rep['sources']} source(s), {rep['admitted']} admitted, {rep['refused']} refused; "
                  f"{rep['programs']} program(s) emitted, {rep['twins']} distinct twin(s) "
                  f"({rep['duplicates']} duplicate hint(s) folded), {rep['cells']} cells "
                  f"to grade; {rep['on_disk']} twin(s) on disk under {a.out}; "
                  f"unstrippable {rep['unstrippable']}")
            print(f"next: python3 t/run_par.py --tasks {a.out}/grade/tasks --out {a.out}/grade/out "
                  f"--table {a.out}/grade/table.md --jobs 4 --no-cache")
            return 0
        counts = classify_dir(a.out, a.table)
        print("; ".join(f"{k} {counts.get(k, 0)}" for k in CLASSES))
        return 0
    except TwinRefused as exc:
        print(f"REFUSED: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
