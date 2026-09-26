#!/usr/bin/env python3
"""t/heads_from_sources.py -- English heads for the head-less lifted documents, from
sources that exist (2026-09-25, r12 data build, plan section B.2).

Three quarters of locallm's corpus is a t program under a one-line Signature
head and no English at all (internal/research/r12-2026-09-21/training-lit.md,
ranked change 3). A model trained on that learns "write a verified program",
not "write the program this English asks for", and its dominant failure is a
proof of the wrong function. Humpback (Li et al., instruction backtranslation,
https://ar5iv.labs.arxiv.org/html/2308.06259, receipt d493bc19d38e) measured
what happens when instructions are attached to existing outputs: uncurated
pairs "do not improve ... despite scaling up data quantity", curated pairs keep
improving. So every head here comes from a source that already exists and is
curated by a rule the report states; nothing is written by a model and nothing
is invented where the data has no English.

  (a) MBPP-DFY lifts, out/lifted-tasks/dafny-synthesis_task_id_N.*.json: N is
      MBPP problem N (loop_filter.problem_id), whose English and test points
      are in the pool. The head is kept only if the lifted program passes that
      problem's own points through the t interpreter (spec_experiment.run_point,
      the same call the runner's tests stage makes), so a lift that solves a
      different function than the English describes gets no head. Example:
      lines are the problem's discriminative pair, as loop_locallm.problem_head
      writes them for a model's answer.
  (b) Clover tasks, out/lifted-tasks/Clover_*.json: the Clover dataset
      (github.com/ChuyueSun/Clover, dataset/CloverBench/textbook_algo, receipt
      7a221947005d) ships a human-written docstring <dir>/<dir>_spec.txt for
      each program. It is the Problem line as written, curated by construction:
      the dataset's authors wrote it for exactly that program. A lifted Clover
      task without a spec file is an error, not a task without a head.
  (c) every other name family is a DafnyBench program (t-corpora/DafnyBench,
      dataset/ground_truth/<stem>.dfy, read-only). A head is taken only from a
      comment that sits directly on the lifted method: a comment block ending on
      the line right before the method header, or a comment between the header
      and its body brace, which the Dafny reference manual, section 2.5
      "Documentation comments" (dafny-lang/dafny docs/DafnyRef/Grammar.md,
      receipt 3ee2eb0f939f), treats as the declaration's documentation. A block
      separated from the header by a blank line is not taken (it may describe
      the previous method) and is counted. The comment must read as English:
      the closed-class word-list test of the language-identification
      literature (Jauhiainen et al., arXiv:1804.08186, receipt 26accc93af71),
      because t/ carries no n-gram model. It must also describe the method
      rather than the exercise around it (META_COMMENTARY below, a refusal
      list written from the candidates seen on 2026-09-25). Tasks with no such
      comment keep no head, and the report says how many.

Every candidate passes the gates the r12 build installed before it is written:
the held-out ids under every alias, the same-task exclusions
(t/decontamination-2026-09-21.json) and the dev split (t/r12-dev-ids.json),
through loop_filter.TrainingDataGate. A refused candidate is listed by name in
the report, never dropped quietly. Only tasks whose row in the coverage table
reads clean in all seven kernels get a row, because those are the documents
`loop_locallm.py corpus --lifted` writes; a head for a task that is not a
document would be refused there.

Output: --out heads.jsonl, one row per head:
  {"name", "problem", "examples": [...], "source", "curation"}
and --report, a Markdown report with counts per source, the refusals by name
and ten examples per source. `loop_locallm.py corpus --heads heads.jsonl`
prefixes the matching documents.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import head_align_corpus                                        # noqa: E402
import loop_filter                                              # noqa: E402
import loop_locallm                                             # noqa: E402
import spec_experiment as se                                    # noqa: E402

LIFTED_DIR = HERE / "out" / "lifted-tasks"
LIFTED_TABLE = HERE / "COVERAGE-lifted-785.md"
GROUND_TRUTH = ("t-corpora", "DafnyBench", "DafnyBench", "dataset", "ground_truth")

SOURCE_MBPP = "mbpp-dfy"
SOURCE_CLOVER = "clover"
SOURCE_DAFNYBENCH = "dafnybench"
CURATION = {
    SOURCE_MBPP: "the lifted program passes every test point of MBPP problem N in the t interpreter "
                 "(spec_experiment.run_point)",
    SOURCE_CLOVER: "human-written docstring shipped by the Clover dataset for this program "
                   "(dataset/CloverBench/textbook_algo/<dir>/<dir>_spec.txt); curated by construction, not by test",
    SOURCE_DAFNYBENCH: "a comment directly on the lifted method in its DafnyBench source file, "
                       "read as English by the closed-class word test and not meta-commentary about "
                       "the exercise (heads_from_sources.META_COMMENTARY)",
}

# --------------------------------------------------------------- English --
# The closed-class ("stop word", "function word") test of Wechsler et al. 1997,
# Giguet 1995 and Stupar et al. 2011 as the survey arXiv:1804.08186 (receipt
# 26accc93af71) describes it, with a rule filter first as lingua-py does: a
# comment that carries a non-ASCII letter, a code operator, or fewer than
# three words is not English prose, whatever its words. The description verbs
# are here because a one-line docstring ("Return the min of two values.") may
# hold no classic stop word but still opens with one of them.
FUNCTION_WORDS = frozenset("""
a an the of to in on at by for with from into as is are was were be been being it its this that these those
and or but not no if then else than which who whose what when where whether each every all any some such
there their them they we you he she his her our your one two first last given input output value values
element elements number numbers array list sequence integer integers
""".split())
DESCRIPTION_VERBS = frozenset("""
return returns returning compute computes computing calculate calculates find finds check checks checking
count counts determine determines test tests swap swaps sort sorts search searches searching double doubles
triple triples multiply multiplies add adds sum sums verify verifies reverse reverses copy copies replace
replaces rotate rotates update updates insert inserts remove removes take takes get gets set sets
""".split())
CODE_OPERATORS = re.compile(r":=|==>|<==|&&|\|\||[{};]")
ADMIN_LINES = re.compile(r"^\s*(?:copyright|author|authors|todo|fixme|run:|rlimit|http|license|licence)", re.I)
WORD = re.compile(r"[A-Za-z]+")
# A comment can be English and sit on the method and still not describe what
# the method computes: it addresses the student about the exercise, the
# course, the author, or the annotations to write. This list was written
# after reading every candidate the positional rule and the English test
# produced on 2026-09-25 (39 of 112 DafnyBench documents had a comment on the
# method; t/HEADS-2026-09-25.md lists each by name with its outcome). A
# candidate that names one of these is refused as meta-commentary and
# counted; the list is data about that corpus, not a claim about English.
META_COMMENTARY = re.compile(
    r"\b(?:exercise|exercises|assignment|assignments|homework|question|questions|points|annotate|annotation|"
    r"annotations|precondition|preconditions|postcondition|postconditions|pre-\s*and\s*post|invariant|"
    r"invariants|verify|verifies|verification|prove|provable|proof|dafny|lecture|course|tutorial|overheads|"
    r"student|fill\s+in|do\s+not\s+change|instead\s+of|line\s+\d|newly\s+created|method\s+body|test\s+method|"
    r"solution|solutions)\b", re.I)


def description_verdict(text: str) -> tuple[bool, str]:
    """(describes the method, reason): the English test first, then the
    meta-commentary refusal list above."""
    ok, why = english_verdict(text)
    if not ok:
        return False, why
    hit = META_COMMENTARY.search(text)
    if hit:
        return False, f"meta-commentary ({hit.group(0).lower()})"
    return True, why


def english_verdict(text: str) -> tuple[bool, str]:
    """(is English prose, reason). The reason names the rule that decided."""
    if not text or not text.strip():
        return False, "empty"
    if any(ord(c) > 127 and c.isalpha() for c in text):
        return False, "non-ascii letter"
    if CODE_OPERATORS.search(text):
        return False, "code operator"
    if ADMIN_LINES.match(text):
        return False, "administrative line"
    words = [w.lower() for w in WORD.findall(text)]
    if len(words) < 3:
        return False, f"{len(words)} word(s)"
    hits = [w for w in words if w in FUNCTION_WORDS or w in DESCRIPTION_VERBS]
    if not hits:
        return False, "no English function word"
    return True, f"{len(hits)} function word(s) of {len(words)}"


# ------------------------------------------------------------- Dafny src --
# The Dafny reference manual, section 2.5 (receipt 3ee2eb0f939f): a doc comment
# sits right before the definition, or between the declaration and its
# definition. Its extraction strips "/*", an optional "*" and one space on the
# first line, and the indentation with an optional star on the others.
DECL = r"^\s*(?:ghost\s+|static\s+|twostate\s+)*(?:lemma|method|function\s+method|function|predicate\s+method|predicate)\s+{name}\s*[(<]"


def strip_comment_markers(lines: list[str]) -> str:
    out = []
    for line in lines:
        s = line.strip()
        s = re.sub(r"^/\*+\s?", "", s)
        s = re.sub(r"\s*\*+/$", "", s)
        s = re.sub(r"^//+\s?", "", s)
        s = re.sub(r"^\*\s?", "", s)
        out.append(s.strip())
    return " ".join(w for w in " ".join(out).split())


def _block_above(lines: list[str], header: int) -> list[str] | None:
    """The comment block whose last line is the line right before the header,
    or None. A blank line between the block and the header breaks it."""
    j = header - 1
    if j < 0 or not lines[j].strip():
        return None
    last = lines[j].strip()
    if last.endswith("*/"):
        # walk up to the line that opens this block comment
        k = j
        while k >= 0 and "/*" not in lines[k]:
            k -= 1
        if k < 0:
            return None
        return lines[k:j + 1]
    if last.startswith("//"):
        k = j
        while k - 1 >= 0 and lines[k - 1].strip().startswith("//"):
            k -= 1
        return lines[k:j + 1]
    return None


def _between_header_and_body(lines: list[str], header: int) -> list[str] | None:
    """Comment lines from the header line to the body's opening brace (a
    trailing // on the header or a spec clause, or a whole comment line)."""
    found = []
    for i in range(header, min(header + 40, len(lines))):
        line = lines[i]
        code = re.sub(r"//.*$", "", line)
        if "//" in line:
            found.append(line[line.index("//"):])
        elif line.strip().startswith("/*"):
            found.append(line)
        if "{" in code:
            break
    return found or None


def dafnybench_comment(source: str, method: str) -> tuple[str | None, str]:
    """(comment text, reason) for the comment that sits directly on `method`
    in a Dafny source file; text is None when there is none."""
    lines = source.split("\n")
    pattern = re.compile(DECL.format(name=re.escape(method)))
    headers = [i for i, line in enumerate(lines) if pattern.match(line)]
    if not headers:
        return None, "method not found"
    header = headers[0]
    above = _block_above(lines, header)
    if above is not None:
        text = strip_comment_markers(above)
        if text:
            return text, "block above"
    between = _between_header_and_body(lines, header)
    if between is not None:
        text = strip_comment_markers(between)
        if text:
            return text, "between header and body"
    j = header - 1
    while j >= 0 and not lines[j].strip():
        j -= 1
    if j >= 0 and j < header - 1 and (lines[j].strip().startswith("//") or lines[j].strip().endswith("*/")):
        return None, "comment separated by a blank line"
    return None, "no comment"


# ------------------------------------------------------------- the lifts --
def family(stem: str) -> str:
    if stem.startswith("dafny-synthesis_task_id_"):
        return SOURCE_MBPP
    if stem.startswith("Clover_"):
        return SOURCE_CLOVER
    return SOURCE_DAFNYBENCH


def lifted_tasks(lifted_dir: Path) -> list[tuple[Path, str, str, dict]]:
    """(file, dfy stem, method, task) for every lifted task, from the file
    name the lifter wrote: <stem>.<method>.json (t/lifter.py lift_file)."""
    out = []
    files = sorted(f for f in lifted_dir.glob("*.json") if not f.name.endswith(".lift.json"))
    if not files:
        raise SystemExit(f"{lifted_dir} holds no lifted task; nothing to head")
    for f in files:
        if "." not in f.stem:
            raise SystemExit(f"{f.name}: not a <stem>.<method>.json lifted task")
        stem, method = f.stem.rsplit(".", 1)
        try:
            task = json.loads(f.read_text(encoding="utf-8"))
            task["name"], task["params"], task["returns"]
        except (OSError, ValueError, KeyError, TypeError) as e:
            raise SystemExit(f"{f.name}: not a lifted task: {e}")
        out.append((f, stem, method, task))
    return out


def example_lines(task: dict, points: list) -> list[str]:
    """The problem's discriminative pair, written for the task's own name."""
    lines = []
    for point in loop_locallm.discriminative(points, 2):
        try:
            args = ", ".join(json.dumps(value) for _kind, value in point["args"])
            lines.append(f"{task['name']}({args}) == {json.dumps(point['expected'][1])}")
        except (KeyError, IndexError, TypeError, ValueError):
            continue
    return lines


def mbpp_candidate(task: dict, pool: dict) -> tuple[dict | None, str]:
    task_id = loop_filter.problem_id(task["name"])
    if task_id is None:
        return None, "no MBPP id in the name"
    entry = pool.get(task_id)
    if entry is None:
        return None, "MBPP problem not in the pool"
    verdicts = [se.run_point(task, point)["verdict"] for point in entry["points"]]
    if not verdicts:
        return None, "MBPP problem has no points"
    if any(v != "pass" for v in verdicts):
        return None, "tests: " + ", ".join(sorted(set(verdicts)))
    return {"problem": " ".join(entry["rec"]["text"].split()), "examples": example_lines(task, entry["points"]),
            "task_id": task_id}, f"passes {len(verdicts)} point(s)"


def clover_candidate(stem: str, clover_dir: Path) -> dict:
    directory = stem[len("Clover_"):]
    spec = clover_dir / directory / f"{directory}_spec.txt"
    try:
        text = " ".join(spec.read_text(encoding="utf-8").split())
    except OSError as e:
        raise SystemExit(f"{stem}: the Clover dataset ships a docstring per program and {spec} cannot be read: {e}")
    if not text:
        raise SystemExit(f"{stem}: {spec} is empty")
    return {"problem": text, "examples": []}


def dafnybench_candidate(stem: str, method: str, ground_truth: Path) -> tuple[dict | None, str]:
    src = ground_truth / f"{stem}.dfy"
    try:
        source = src.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        raise SystemExit(f"{stem}: its DafnyBench source {src} cannot be read: {e}")
    text, reason = dafnybench_comment(source, method)
    if text is None:
        return None, reason
    ok, why = description_verdict(text)
    if not ok:
        return None, f"{reason}, not a description ({why})"
    return {"problem": text, "examples": []}, f"{reason}, English ({why})"


def build(lifted_dir: Path, table: Path, split: Path, pool: dict, clover_dir: Path,
          ground_truth: Path) -> tuple[list[dict], dict]:
    """The head rows and a report dict: counts per source, refusals by name."""
    evil = loop_locallm.held_out(str(split))
    dev = loop_filter.r12_dev_ids(split_path=split)
    gate = loop_filter.TrainingDataGate(frozenset(evil | dev))
    clean = loop_locallm.clean_rows(table)
    rows, log = [], {"sources": {}, "gated": [], "not_a_document": Counter()}
    for source in (SOURCE_MBPP, SOURCE_CLOVER, SOURCE_DAFNYBENCH):
        log["sources"][source] = {"tasks": 0, "documents": 0, "heads": 0, "reasons": Counter(), "refused": []}
    for _f, stem, method, task in lifted_tasks(lifted_dir):
        source = family(stem)
        entry = log["sources"][source]
        entry["tasks"] += 1
        name = task["name"]
        if name not in clean:
            log["not_a_document"][source] += 1
            continue
        entry["documents"] += 1
        if source == SOURCE_MBPP:
            candidate, reason = mbpp_candidate(task, pool)
        elif source == SOURCE_CLOVER:
            candidate, reason = clover_candidate(stem, clover_dir), "docstring"
        else:
            candidate, reason = dafnybench_candidate(stem, method, ground_truth)
        if candidate is None:
            entry["reasons"][reason] += 1
            entry["refused"].append(f"{name}: {reason}")
            continue
        task_ids = [candidate["task_id"]] if "task_id" in candidate else []
        if not gate.admit(candidate["problem"], [name], task_ids):
            entry["reasons"]["refused by the gates"] += 1
            log["gated"].append(name)
            continue
        entry["reasons"][reason.split(":")[0].split(",")[0]] += 1
        entry["heads"] += 1
        rows.append({"name": name, "problem": candidate["problem"], "examples": candidate["examples"],
                     "source": source, "curation": CURATION[source]})
    log["held"] = list(gate.held)
    log["decontaminated"] = list(gate.decontaminated)
    order = (SOURCE_MBPP, SOURCE_CLOVER, SOURCE_DAFNYBENCH)
    rows.sort(key=lambda r: (order.index(r["source"]), r["name"]))
    return rows, log


def report_text(rows: list[dict], log: dict, when: str) -> str:
    out = [f"# English heads for the lifted documents, {when}", "",
           "Built by `t/heads_from_sources.py` from sources that exist; nothing written by a model.",
           "Each source has its own curation, stated in every row's `curation` field. A task whose",
           "coverage row is not clean in all seven kernels is not a corpus document and gets no row.",
           "", "| source | lifted tasks | documents | heads | no head |", "|---|---:|---:|---:|---:|"]
    for source, entry in log["sources"].items():
        out.append(f"| {source} | {entry['tasks']} | {entry['documents']} | {entry['heads']} | "
                   f"{entry['documents'] - entry['heads']} |")
    out += ["", f"Heads written: {len(rows)}. Refused by the gates: {len(log['gated'])}"
            + (": " + ", ".join(log["gated"]) if log["gated"] else "") + ".",
            f"- held-out or dev-split ids ({len(log['held'])}): " + (", ".join(log["held"]) or "none"),
            f"- same-task exclusions, t/decontamination-2026-09-21.json ({len(log['decontaminated'])}): "
            + (", ".join(log["decontaminated"]) or "none"),
            "", "Tasks that are not corpus documents (coverage row not clean): "
            + (", ".join(f"{s} {n}" for s, n in sorted(log["not_a_document"].items())) or "none") + "."]
    for source, entry in log["sources"].items():
        out += ["", f"## {source}", "", f"Curation: {CURATION[source]}.", "", "Outcomes:", ""]
        for reason, n in sorted(entry["reasons"].items(), key=lambda kv: (-kv[1], kv[0])):
            out.append(f"- {reason}: {n}")
        examples = [r for r in rows if r["source"] == source][:10]
        if examples:
            out += ["", "Ten examples (the first ten by name):", ""]
            for r in examples:
                out.append(f"- `{r['name']}`: {r['problem']}")
                for e in r["examples"]:
                    out.append(f"  - Example: {e}")
        if entry["refused"]:
            out += ["", "No head, by name:", ""]
            out += [f"- {line}" for line in entry["refused"]]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--lifted-dir", type=Path, default=LIFTED_DIR)
    ap.add_argument("--table", type=Path, default=LIFTED_TABLE, help="the seven-kernel table whose clean rows are the documents")
    ap.add_argument("--split", type=Path, required=True, help="the split whose eval ids no head may name")
    ap.add_argument("--pool", default="v5")
    ap.add_argument("--clover-dir", type=Path, required=True,
                    help="a checkout of Clover's dataset/CloverBench/textbook_algo (<dir>/<dir>_spec.txt)")
    ap.add_argument("--dafnybench", type=Path, default=HERE.parent.joinpath(*GROUND_TRUTH),
                    help="DafnyBench's dataset/ground_truth directory (<stem>.dfy), read-only")
    ap.add_argument("--out", type=Path, required=True, help="heads.jsonl")
    ap.add_argument("--report", type=Path, required=True, help="the Markdown report")
    ap.add_argument("--date", default="2026-09-25")
    a = ap.parse_args(argv)
    for path, what in ((a.lifted_dir, "lifted tasks"), (a.clover_dir, "Clover dataset"), (a.dafnybench, "DafnyBench ground truth")):
        if not path.is_dir():
            raise SystemExit(f"{what} directory {path} does not exist")
    rows, log = build(a.lifted_dir, a.table, a.split, se.pool(a.pool), a.clover_dir, a.dafnybench)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(report_text(rows, log, a.date), encoding="utf-8")
    for source, entry in log["sources"].items():
        print(f"{source}: {entry['tasks']} lifted, {entry['documents']} documents, {entry['heads']} heads; "
              + ", ".join(f"{k} {n}" for k, n in sorted(entry["reasons"].items())))
    print(f"heads {a.out}: {len(rows)} rows; gated {len(log['gated'])}; report {a.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
