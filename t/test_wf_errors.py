#!/usr/bin/env python3
"""test_wf_errors.py: the well-formedness half of ROADMAP 14.2, "Errors
with a position" (the parse half -- a bad TOKEN's file/line/col, and the
corpus in t/malformed/*.t with t/malformed/EXPECTED.tsv -- is separate,
already in the tree, and not read by this file).

t/malformed/EXPECTED-WF.tsv holds one row (file, line, col, rule) per key
in check_wf.RULES that a malformed but PARSEABLE .t file can trigger; the
matching t/malformed/wf-<rule>.t is a minimal task built by hand so that
`surface.check_file` on it reports a check_wf.WfError with exactly that
rule, at exactly that line and column. Not every RULES key has a row: some
are structural guards check_wf keeps for a hand-built (non-notation) task
dict -- the AST the surface grammar itself can produce already satisfies
them, so no .t file can ever reach them. UNREACHABLE below is that list,
with the reason for each; test_coverage_matches_rules asserts
len(EXPECTED-WF rows) + len(UNREACHABLE) == len(check_wf.RULES), so a new
rule added to RULES with no matching .t file and no stated reason fails
this test rather than going unnoticed.

Ported 2026-09-11 onto this tree from a wf-positions patch built
independently on an older base (see the ROADMAP 14.2 note in check_wf.py's
own docstring): the malformed corpus and this test file are that patch's,
with seven of EXPECTED-WF.tsv's (line, col) pairs corrected to match what
THIS tree's surface.py positions map actually records for the offending
node (arith-int, at-types, op-unknown, proj-nonpair, slice-types,
strlib-types, update-types -- each an operator or postfix-index node,
where this tree's parser marks the position at the operator/bracket token
that introduces the construct, not the left operand's start; the operator
is the thing the rule text says is at fault, so that is the token these
rows now name).

Run: python3 t/test_wf_errors.py
"""

from __future__ import annotations

import csv
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
MALFORMED = os.path.join(HERE, "malformed")

import check_wf                                                # noqa: E402
import surface                                                 # noqa: E402
import tasks_io                                                # noqa: E402

# Mirrors the generator the malformed corpus and EXPECTED-WF.tsv were built
# with: a RULES key with no .t file because the surface grammar cannot
# build an AST that would trip it.
UNREACHABLE = {
    "name": "the lexer's identifier regex (_ID) is exactly NAME_RE; no "
            "token the lexer can produce for a task name ever fails it.",
    "one-return": "SYNTAX.md's `returns` production has notation for "
                  "exactly one `(name: Type)`; there is no way to write a "
                  "second return in the surface syntax (program() eats "
                  "exactly one Id ':' Type between the parens).",
    "valid-type": "ptype()'s pair branch reads T1/T2 with vtype() (base "
                  "types only, not recursive), and its seq<seq> branch "
                  "accepts only the literal keyword pair 'seq' '<' 'seq' "
                  "'>', so the parser cannot build a pair of pairs or a "
                  ">1-level seq<seq>; every Type the grammar accepts is "
                  "already _valid_type()-valid.",
    "op-arity": "every operator's AST arity is fixed by which grammar rule "
               "built it (p_add/p_mul/p_cmp always build 2 args, unary "
               "prefixes always 1, `and`/`or` fold to a chain of >=2 "
               "operands, ternary forms (update/slice/replace) and "
               "string-library forms are arity-checked by the parser "
               "itself, one .err() per member, before the AST node is "
               "built); no notation reaches check_wf with a wrong-arity "
               "op node.",
    "strlib-arity": "the parser itself raises SurfaceError for a "
                    "string-library call with the wrong argument count "
                    "before an AST node is ever built (p_postfix's "
                    ".split/.join/.replace/.count/.find/... arms each "
                    "check len(margs) and self.err() on mismatch), so "
                    "check_wf's own arity check on that node can never "
                    "see a bad count.",
    "unknown-stmt": "stmt() raises SurfaceError itself for anything that "
                    "is not return/assign/var/if/while; check_wf's `else` "
                    "branch in _check_stmts has no AST shape a parse can "
                    "produce to reach it.",
    "return-name": "the parser fills a `return` node's name from "
                   "self.ret_name (the task's own declared return name) "
                   "at parse time (stmt()'s `return` arm); there is no "
                   "notation for a `return` naming any other variable.",
}


def load_expected():
    path = os.path.join(MALFORMED, "EXPECTED-WF.tsv")
    rows = []
    with open(path, encoding="utf-8", newline="") as fh:
        for row in csv.reader(fh, delimiter="\t"):
            if not row or row[0].startswith("#"):
                continue
            fname, line, col, rule = row
            rows.append((fname, int(line), int(col), rule))
    return rows


def test_coverage_matches_rules():
    """Every check_wf.RULES key is either covered by a row in
    EXPECTED-WF.tsv or named in UNREACHABLE, and not both."""
    rows = load_expected()
    covered = {r[3] for r in rows}
    assert covered <= set(check_wf.RULES), covered - set(check_wf.RULES)
    assert set(UNREACHABLE) <= set(check_wf.RULES), \
        set(UNREACHABLE) - set(check_wf.RULES)
    overlap = covered & set(UNREACHABLE)
    assert not overlap, f"in both EXPECTED-WF.tsv and UNREACHABLE: {overlap}"
    missing = set(check_wf.RULES) - covered - set(UNREACHABLE)
    assert not missing, f"RULES key with no .t file and no stated reason: {missing}"
    assert len(covered) + len(UNREACHABLE) == len(check_wf.RULES)
    print(f"test_coverage_matches_rules: {len(covered)} covered by a .t "
          f"file, {len(UNREACHABLE)} unreachable, {len(check_wf.RULES)} "
          f"RULES keys total")
    return len(covered)


def test_each_row():
    """Every row of EXPECTED-WF.tsv: surface.check_file on the named
    t/malformed/ file reports a check_wf.WfError at exactly that rule,
    line and column."""
    rows = load_expected()
    assert rows, "EXPECTED-WF.tsv has no rows"
    ok = 0
    for fname, line, col, rule in rows:
        path = os.path.join(MALFORMED, fname)
        assert os.path.exists(path), f"{fname} named in EXPECTED-WF.tsv, missing on disk"
        errs = surface.check_file(path)
        hit = [e for e in errs
              if getattr(e, "rule", None) == rule
              and getattr(e, "line", None) == line
              and getattr(e, "col", None) == col]
        seen = [(getattr(e, "rule", None), getattr(e, "line", None),
                getattr(e, "col", None)) for e in errs]
        assert hit, (
            f"{fname}: expected rule={rule!r} line={line} col={col}, "
            f"got {seen}")
        assert str(hit[0]).startswith(f"{path}:{line}:{col}: "), str(hit[0])
        assert hit[0].rule in check_wf.RULES
        ok += 1
    print(f"test_each_row: {ok} of {len(rows)} rows of EXPECTED-WF.tsv "
          f"reproduce their expected file:line:col and rule")
    return ok


def test_no_position_falls_back():
    """check_wf(task) with no positions argument returns exactly what it
    always did -- a list[str], each "message [SPEC: rule]" -- so any
    existing caller (fuzz_lower.py, grade.py, test_check_wf.py) is
    unaffected by check_wf growing position-awareness."""
    task = surface.parse(
        "t 1 task f(x: int) returns (r: int) ensures true { r := true }")
    errs = check_wf.check_wf(task)
    assert errs, "expected at least the assign-type error"
    assert all(isinstance(e, str) for e in errs), errs
    assert all(" [SPEC: " in e and not e.startswith("<string>:")
              for e in errs), errs
    print(f"test_no_position_falls_back: {len(errs)} error(s), "
          f"plain strings, no position on any of them")


def test_well_formed_tasks_clean():
    """Every committed task in t/tasks/*.t is well-formed under
    check_wf.py's own logic (not just fuzz_lower.py's re-export): zero
    errors on all of them, read through tasks_io as the rest of the tree
    does (ROADMAP 14.1: tasks live as .t files, the JSON derived)."""
    paths = sorted(glob.glob(os.path.join(HERE, "tasks", "*.t")))
    assert paths
    bad = []
    for p in paths:
        task = tasks_io.load_task(p)
        errs = check_wf.check_wf(task)
        if errs:
            bad.append((p, errs))
    assert not bad, bad
    print(f"test_well_formed_tasks_clean: {len(paths)} committed tasks, 0 check_wf errors")


def main():
    n_rows = test_coverage_matches_rules()
    n_each = test_each_row()
    test_no_position_falls_back()
    test_well_formed_tasks_clean()
    print(f"OK: {n_rows} rules covered by {n_each} malformed .t files, "
          f"{len(UNREACHABLE)} rules unreachable through valid syntax")


if __name__ == "__main__":
    main()
