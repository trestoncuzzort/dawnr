#!/usr/bin/env python3
"""test_collection_quant.py: quantifiers over a collection (SPEC.md "Quantifiers over a collection", PREDICT T26,
2026-10-07). Text-level checks only, no kernel runs:
- the notation (the range forms, and the field-access reading the separator must not take);
- the rule `quant-range`, and the interpreter over a set and a seq;
- the seq rewrite (index form, fresh names, identity elsewhere);
- Dafny's and Verus's set forms, and the five refusals by name;
- the Python hand-back."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import check_wf  # noqa: E402
import interp  # noqa: E402
import lower_dafny  # noqa: E402
import lower_framac  # noqa: E402
import lower_fstar  # noqa: E402
import lower_lean  # noqa: E402
import lower_rocq  # noqa: E402
import lower_spark  # noqa: E402
import lower_verus  # noqa: E402
import surface  # noqa: E402
import tasks_io  # noqa: E402
import to_python  # noqa: E402
import tshape  # noqa: E402

CHECKS = 0


def ok(cond, what):
    global CHECKS
    CHECKS += 1
    if not cond:
        print("FAIL:", what)
        sys.exit(1)


def load(name: str) -> dict:
    return tasks_io.load_task(str(HERE / "tasks" / f"{name}.t"))


def text(mod, name: str) -> str:
    task = load(name)
    return mod.lower(task, task["body"])


def test_notation():
    e = surface.parse_expr("forall x in view(l) . x < v")
    ok(e == {"forall": {"var": "x", "in": {"call": {"fun": "view", "args": [{"var": "l"}]}},
                        "body": {"op": "<", "args": [{"var": "x"}, {"var": "v"}]}}},
       "a call range, the `.` read as the separator and not a field")
    ok(surface.parse_expr("exists y in s . y == 0")["exists"]["in"] == {"var": "s"}, "a name range")
    e = surface.parse_expr("forall z in (union(a, b)) . z >= 0")
    ok(e["forall"]["in"]["op"] == "union", "a parenthesized range")
    ok("lo" in surface.parse_expr("forall k in [0, n) . k >= 0")["forall"], "the int range is unchanged")
    for src in ("forall x in view(l) . x < v", "exists y in s . y == 0", "forall z in (union(a, b)) . z >= 0"):
        ok(surface.parse_expr(surface.pexpr(surface.parse_expr(src))) == surface.parse_expr(src), f"{src} prints back")


def test_rule_and_interpreter():
    pos: dict = {}
    bad = surface.parse((HERE / "malformed" / "wf-quant-range.t").read_text(), positions=pos)
    ok({e.rule for e in check_wf.check_wf(bad, pos)} == {"quant-range"}, "an int range is refused by name")
    e = surface.parse_expr("forall x in s . x > 0")
    ok(interp.ev(e, {"s": frozenset({1, 2})}, {}, interp.St()) is True, "over a set")
    ok(interp.ev(e, {"s": frozenset({0, 2})}, {}, interp.St()) is False, "a set element fails")
    ok(interp.ev(e, {"s": (3, 4)}, {}, interp.St()) is True, "over a seq")
    ok(interp.ev(surface.parse_expr("exists x in s . x > 3"), {"s": ()}, {}, interp.St()) is False,
       "an empty collection decides without the body")


def test_seq_rewrite():
    task = load("none_neg")
    t2, b2 = tshape.desugar_seq_quants(task, task["body"])
    q = t2["ensures"][0]["args"][1]["forall"]
    ok(q["var"] == "qi1" and q["lo"] == {"int": 0} and q["hi"] == {"op": "len", "args": [{"var": "s"}]},
       "a seq range becomes [0, len(s))")
    ok(q["body"] == {"op": ">=", "args": [{"op": "at", "args": [{"var": "s"}, {"var": "qi1"}]}, {"int": 0}]},
       "with the element read by index")
    ok(b2 is t2["body"], "the real body keeps its identity")
    task = load("all_pos_set")
    t3, _ = tshape.desugar_seq_quants(task, task["body"])
    ok("in" in t3["ensures"][0]["args"][1]["forall"], "a set range is left as it is")
    task = load("clamp")
    ok(tshape.desugar_seq_quants(task, task["body"])[0] is task, "identity for a task with no such quantifier")
    for mod in (lower_dafny, lower_verus, lower_lean, lower_rocq, lower_fstar, lower_spark, lower_framac):
        src = text(mod, "none_neg")
        ok("t renames" not in src, f"{mod.__name__}: the fresh index name needs no rename")


def test_set_range_in_dafny_and_verus():
    ok("(forall x :: x in s ==> (x > 0))" in text(lower_dafny, "all_pos_set"), "Dafny's membership range")
    ok("forall|x: int| #![trigger s.contains(x)] s.contains(x) ==> (x > (0int))" in text(lower_verus, "all_pos_set"),
       "Verus's contains, as range and trigger")
    task = load("all_pos_set")
    for mod in (lower_lean, lower_rocq, lower_fstar, lower_spark, lower_framac):
        try:
            mod.lower(task, task["body"])
            ok(False, f"{mod.__name__} refuses a set range")
        except NotImplementedError as e:
            ok("Quantifiers over a collection" in str(e), f"{mod.__name__} refuses a set range by name")


def test_python_hand_back():
    src, _ = to_python.translate(load("all_pos_set"))
    ok("all((x > 0) for x in s)" in src or "for x in s)" in src, f"Python iterates the collection: {src[:200]}")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: ok")
    print(f"{CHECKS} checks")
