"""Plain-python tests for FRAMAC-NESTED, ROADMAP 13.4 item (a), 2026-09-12:
the extensional seq equality loop in EXECUTABLE position (`_seq_eq_top`/
`_seq_eq_loop`/`_seq_eq_value` in lower_framac.py, wired into `stmts()`'s
"assign"/"return"/"if" branches). Covers the three cells the design order
named -- `fz_p_nest_eq` (nested seq<seq> PARAMETERs), 576 IsSublist and 69
ContainsSequence (flat seq operands, a slice and a nested-seq row
respectively) -- plus the scalar re-declaration certificate bug this pass
found and fixed along the way (`_undef_certificate`'s `walk()`).

Run as: cd <repo>/t && python3 test_framac_nested.py

MEASURED 2026-09-12 by `python3 t/test_framac_nested.py`: see the printed
summary line for the exact pass/fail count this run produced. This file
checks LOWERING SHAPES ONLY (no frama-c invocation, matching
test_framac_seq4.py's own precedent) -- the actual kernel verdicts
(real=verified/twin=refuted for IsSublist, real=timeout/twin=timeout for
fz_p_nest_eq and ContainsSequence, none of them regressions) are measured
separately, by `python3 grade.py`, and recorded in this pass's own dated
docstring note in lower_framac.py, not reproduced here."""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import harness                       # noqa: E402
import fuzz_lower as fz              # noqa: E402
import lower_framac                  # noqa: E402

UNIT_TESTS = []


def test(fn):
    UNIT_TESTS.append(fn)
    return fn


def _probe(name):
    return next(t for t in fz.probes() if t["name"] == name)


def _lower_probe(name):
    task = _probe(name)
    w = harness.real_witness(task)
    return lower_framac.lower(task, task["body"], witness=w)


# The two lifted tasks named in this pass's own design order (ROADMAP
# 13.4 item (a): "576 isSublist and 69 containsSequence in the sweep"),
# embedded verbatim rather than read from t/out/lifted-tasks/ (generated
# data, not part of this repo's own checked-in tree, so a test depending
# on it being present on disk would be a test depending on something
# outside this pass's own control). Copied byte-for-byte from
# `t/out/lifted-tasks/dafny-synthesis_task_id_576.IsSublist.json` and
# `...task_id_69.ContainsSequence.json` at measurement time, 2026-09-12.
_ISSUBLIST_JSON = r'''{"body": [{"if": {"cond": {"args": [{"args": [{"var": "sub"}], "op": "len"}, {"args": [{"var": "main_v"}], "op": "len"}], "op": ">"}, "else": [], "then": [{"return": ["result", {"bool": false}]}]}}, {"var": {"init": {"args": [{"args": [{"args": [{"var": "main_v"}], "op": "len"}, {"args": [{"var": "sub"}], "op": "len"}], "op": "-"}, {"int": 1}], "op": "+"}, "name": "h", "type": "int"}}, {"var": {"init": {"int": 0}, "name": "i_v", "type": "int"}}, {"while": {"body": [{"if": {"cond": {"args": [{"var": "sub"}, {"args": [{"var": "main_v"}, {"var": "i_v"}, {"args": [{"var": "i_v"}, {"args": [{"var": "sub"}], "op": "len"}], "op": "+"}], "op": "slice"}], "op": "=="}, "else": [], "then": [{"assign": ["result", {"bool": true}]}]}}, {"assign": ["i_v", {"args": [{"var": "i_v"}, {"int": 1}], "op": "+"}]}], "cond": {"args": [{"var": "i_v"}, {"var": "h"}], "op": "<"}, "decreases": {"args": [{"var": "h"}, {"var": "i_v"}], "op": "-"}, "invariants": [{"args": [{"int": 0}, {"var": "i_v"}], "op": "<="}, {"args": [{"var": "i_v"}, {"var": "h"}], "op": "<="}, {"args": [{"args": [{"int": 0}, {"var": "i_v"}], "op": "<="}, {"args": [{"var": "i_v"}, {"args": [{"args": [{"args": [{"var": "main_v"}], "op": "len"}, {"args": [{"var": "sub"}], "op": "len"}], "op": "-"}, {"int": 1}], "op": "+"}], "op": "<="}], "op": "and"}, {"args": [{"exists": {"body": {"args": [{"var": "sub"}, {"args": [{"var": "main_v"}, {"var": "j"}, {"args": [{"var": "j"}, {"args": [{"var": "sub"}], "op": "len"}], "op": "+"}], "op": "slice"}], "op": "=="}, "hi": {"var": "i_v"}, "lo": {"int": 0}, "var": "j"}}, {"bool": true}], "op": "implies"}]}}, {"assign": ["result", {"bool": false}]}], "ensures": [{"args": [{"exists": {"body": {"args": [{"var": "sub"}, {"args": [{"var": "main_v"}, {"var": "i"}, {"args": [{"var": "i"}, {"args": [{"var": "sub"}], "op": "len"}], "op": "+"}], "op": "slice"}], "op": "=="}, "hi": {"args": [{"args": [{"args": [{"var": "main_v"}], "op": "len"}, {"args": [{"var": "sub"}], "op": "len"}], "op": "-"}, {"int": 1}], "op": "+"}, "lo": {"int": 0}, "var": "i"}}, {"bool": true}], "op": "implies"}], "gate": "loops", "name": "dafny_synthesis_task_id_576__isSublist", "params": [{"name": "sub", "type": "seq"}, {"name": "main_v", "type": "seq"}], "requires": [], "returns": [{"name": "result", "type": "bool"}], "t": 1}'''

_CONTAINSSEQ_JSON = r'''{"body": [{"assign": ["result", {"bool": false}]}, {"var": {"init": {"args": [{"var": "list"}], "op": "len"}, "name": "h", "type": "int"}}, {"var": {"init": {"int": 0}, "name": "i_v", "type": "int"}}, {"while": {"body": [{"if": {"cond": {"args": [{"var": "sub"}, {"args": [{"var": "list"}, {"var": "i_v"}], "op": "at"}], "op": "=="}, "else": [], "then": [{"assign": ["result", {"bool": true}]}, {"return": ["result", {"var": "result"}]}]}}, {"assign": ["i_v", {"args": [{"var": "i_v"}, {"int": 1}], "op": "+"}]}], "cond": {"args": [{"var": "i_v"}, {"var": "h"}], "op": "<"}, "decreases": {"args": [{"var": "h"}, {"var": "i_v"}], "op": "-"}, "invariants": [{"args": [{"int": 0}, {"var": "i_v"}], "op": "<="}, {"args": [{"var": "i_v"}, {"var": "h"}], "op": "<="}, {"args": [{"args": [{"int": 0}, {"var": "i_v"}], "op": "<="}, {"args": [{"var": "i_v"}, {"args": [{"var": "list"}], "op": "len"}], "op": "<="}], "op": "and"}, {"args": [{"var": "result"}, {"exists": {"body": {"args": [{"var": "sub"}, {"args": [{"var": "list"}, {"var": "k"}], "op": "at"}], "op": "=="}, "hi": {"var": "i_v"}, "lo": {"int": 0}, "var": "k"}}], "op": "=="}]}}], "ensures": [{"args": [{"var": "result"}, {"exists": {"body": {"args": [{"var": "sub"}, {"args": [{"var": "list"}, {"var": "i"}], "op": "at"}], "op": "=="}, "hi": {"args": [{"var": "list"}], "op": "len"}, "lo": {"int": 0}, "var": "i"}}], "op": "=="}], "gate": "loops", "name": "dafny_synthesis_task_id_69__containsSequence", "params": [{"name": "list", "type": {"seq": "seq"}}, {"name": "sub", "type": "seq"}], "requires": [], "returns": [{"name": "result", "type": "bool"}], "t": 1}'''


def _issublist_task():
    return json.loads(_ISSUBLIST_JSON)


def _containsseq_task():
    return json.loads(_CONTAINSSEQ_JSON)


@test
def nest_eq_lowers_to_a_two_level_loop():
    """`fz_p_nest_eq`'s BODY (`r := (m == n)`, both bare seq<seq>
    PARAMETER variables) used to raise `cexpr`'s own named
    NotImplementedError (SEQ VALUE, executable position, item 4); it now
    lowers cleanly to a fresh bool-int temp assigned from a two-level
    nested C loop (outer over row index, inner over each row's own
    cells), the shape `_seq_eq_loop`'s nested branch builds."""
    c = _lower_probe("fz_p_nest_eq")
    assert "__seq_eq0" in c, c
    assert c.count("while (") == 2, c
    assert "r = __seq_eq0;" in c, c


@test
def issublist_body_if_cond_lowers_to_a_flat_loop():
    """576 IsSublist's `if (sub == main_v[i_v .. i_v+len(sub)])` -- a bare
    seq extensional `==` reaching an `if` CONDITION directly, the same
    named refusal from a different call site (`stmts()`'s "if" branch,
    not "assign") -- lowers to a flat single-loop comparison (a slice
    operand via `_seq_eq_operand_c`'s "slice" case), no exception."""
    task = _issublist_task()
    c = lower_framac.lower(task, task["body"])
    assert "__seq_eq0" in c, c
    assert "if (__seq_eq0)" in c, c


@test
def containssequence_body_if_cond_lowers_via_nested_seq_row():
    """69 ContainsSequence's `if (sub == at(list, i_v))` -- `list` a
    seq<seq> parameter, so the comparison's second operand is a ROW,
    `_seq_eq_operand_c`'s "at" case (THE ENCODING's own
    `{m}_data + {m}_off[i]` / `{m}_off[i+1] - {m}_off[i]` pair) -- lowers
    with no exception, the row's own pointer/length pair appearing in
    the loop body rather than a materialized row buffer."""
    task = _containsseq_task()
    c = lower_framac.lower(task, task["body"])
    assert "__seq_eq0" in c, c
    assert "list_data + list_off[i_v]" in c or "list_data + (list_off[i_v])" in c or "list_data + list_off[" in c, c


@test
def seq_eq_counter_resets_per_lower_call():
    """`_SEQ_EQ_CTR` is module-global (temp names must be unique WITHIN
    one emitted file, `_seq_eq_loop`'s own docstring); `lower()` resets
    it at the top of every call, so two independent calls in the same
    process (real then twin, or two different tasks) both start their
    own temp naming at `__seq_eq0`, not accumulate across calls."""
    c1 = _lower_probe("fz_p_nest_eq")
    c2 = _lower_probe("fz_p_nest_eq")
    assert "__seq_eq0" in c1 and "__seq_eq0" in c2, (c1, c2)


@test
def flat_seq_literal_operand_still_named_refusal():
    """A shape genuinely out of this pass's own scope (a seq LITERAL or
    concatenation operand, not a bare variable/slice/nested-seq row)
    still raises `_seq_eq_operand_c`'s own named NotImplementedError, not
    a guess: built directly from fuzz_lower's own AST helpers rather than
    reusing a probe, since no committed/fuzzed task needs this shape."""
    task = {
        "t": 1, "name": "test_seq_eq_literal_operand",
        "params": [{"name": "s", "type": "seq"}],
        "returns": [{"name": "r", "type": "bool"}],
        "requires": [], "ensures": [],
        "body": [{"assign": ["r", {"op": "==", "args": [
            {"var": "s"}, {"op": "seq", "args": [{"int": 1}, {"int": 2}]}]}]}],
    }
    try:
        lower_framac.lower(task, task["body"])
    except NotImplementedError as ex:
        assert "only a bare seq variable" in str(ex), str(ex)
    else:
        raise AssertionError("expected a named NotImplementedError, "
                             "none raised")


@test
def undef_certificate_scalar_redeclaration_bug_is_fixed():
    """The certificate bug this pass found and fixed along the way
    (`_undef_certificate`'s `walk()`, unrelated in principle to the seq
    equality loop but only ever REACHED once IsSublist's own framac
    lowering stopped abstaining): a scalar name assigned more than once
    across a certificate's own unrolled loop iterations (`i_v`, or the
    task's RETURN name never declared by any "var" statement at all,
    `result`) used to either redeclare `int {name}` a second time (a
    frama-c parse error, "redefinition of '{name}' in the same scope")
    or skip its OWN first declaration entirely (an undeclared-identifier
    reference) depending on which statement kind assigned it first.
    Confirmed by grading 576 IsSublist end-to-end (`python3 grade.py`,
    this pass's own dated note): framac's compare-flip twin now reads
    MALFORMED->REFUTED, not the parse-error MALFORMED this bug caused.
    This test checks the emitted C directly rather than re-invoking
    frama-c, so it runs without the kernel installed."""
    task = _issublist_task()
    rungs = harness.ladder_rungs(task)
    hit = [(tag, twin, w) for tag, twin, w in rungs if tag == "compare-flip#1"]
    assert hit, [tag for tag, _, _ in rungs]
    _, twin, w = hit[0]
    assert w is not None and w.get("_kind") == "undefined", w
    c = lower_framac.lower(task, twin, witness=w)
    # No name is given a second `int` declaration inside t_certificate.
    cert = c[c.index("t_certificate"):]
    seen = set()
    for line in cert.splitlines():
        line = line.strip()
        if line.startswith("int ") and "[" not in line and "*" not in line:
            nm = line.split()[1].split("=")[0].strip()
            assert nm not in seen, (nm, cert)
            seen.add(nm)


def main() -> int:
    passed, failed = 0, 0
    for fn in UNIT_TESTS:
        try:
            fn()
        except AssertionError as e:
            failed += 1
            print(f"{fn.__name__}: FAIL: {e}")
        except Exception:                                    # noqa: BLE001
            failed += 1
            print(f"{fn.__name__}: ERROR")
            traceback.print_exc()
        else:
            passed += 1
            print(f"{fn.__name__}: pass")
    print(f"test_framac_nested: {passed} passed, {failed} failed "
          f"of {len(UNIT_TESTS)}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
