#!/usr/bin/env python3
"""test_spark_datatypes.py: datatypes in SPARK (SPEC.md "Datatypes (v1)", "(v2): fields", the SPARK note of
2026-10-07, PREDICT T36). Text-level checks only, no kernel runs:
- a datatype is a discriminated record, the discriminant its constructor, a component per constructor's field;
- a field read is a component selection (its discriminant check the definedness), `case` a case expression;
- a certificate binds a datatype parameter by name, never as a static aggregate under another variant;
- a recursive datatype and a seq field refuse by name."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import lower_spark  # noqa: E402
import tasks_io  # noqa: E402
import tlib  # noqa: E402

CHECKS = 0


def ok(cond, what):
    global CHECKS
    CHECKS += 1
    if not cond:
        print("FAIL:", what)
        sys.exit(1)


def load(name: str) -> dict:
    return tasks_io.load_task(str(HERE / "tasks" / f"{name}.t"))


def spark(name: str, twin: bool = False) -> str:
    return tlib.lower(load(name), "spark", twin_body=twin)


def test_declarations():
    src = spark("shape_area")
    ok("type Dt_Shape_Tag is (Dt_Shape_Circle, Dt_Shape_Rect, Dt_Shape_Dot);" in src, "the constructors' enumeration")
    ok("type Dt_Shape (Tag : Dt_Shape_Tag := Dt_Shape_Circle) is record\n      case Tag is\n" in src,
       "a discriminated record with a default, so the type is definite")
    ok("         when Dt_Shape_Rect =>\n            F_Rect_w : Big_Integer;\n            F_Rect_h : Big_Integer;\n" in src,
       "a component per constructor's field")
    ok("type Dt_" not in spark("clamp"), "nothing for a task without datatypes")


def test_expressions():
    src = spark("shape_area")
    ok("(case S.Tag is when Dt_Shape_Circle => ((Big_Integer'(3) * S.F_Circle_r) * S.F_Circle_r)," in src,
       "case is a case expression on the tag, a binder its component")
    ok("(S.F_Rect_w * S.F_Rect_h)" in spark("rect_area"), "a field read is the component selection")
    ok("(C = Dt_Color'(Tag => Dt_Color_Red))" in spark("color_code"), "== is the record's own equality on an aggregate")


def test_certificate_binds_parameters():
    src = spark("shape_area", twin=True)
    cert = src[src.index("   function T_Refutation_Certificate return Boolean is"):]
    ok("(declare T_W_S : constant Dt_Shape := Dt_Shape'(Tag => Dt_Shape_Circle, F_Circle_r => Big_Integer'(1)); begin"
       in cert, "the witness bound by name")
    ok("Dt_Shape'(Tag => Dt_Shape_Circle, F_Circle_r => Big_Integer'(1)).F_Rect_w" not in cert,
       "never a static aggregate selected under another variant")


def test_refused_by_name():
    for name, word in (("tree_sum", "recursive datatype"),):
        task = load(name)
        try:
            lower_spark.lower(task, task["body"])
            ok(False, f"{name} refuses")
        except NotImplementedError as e:
            ok(word in str(e), f"{name} refuses by name: {e}")


def test_seq_field():
    # PREDICT T42: a seq field is a `Seq` component, and the seq preamble is emitted for it
    src = spark("bag_size")
    ok("F_Bag_items : Seq;" in src and "subtype Seq is Seqs.Sequence;" in src, "a Seq component, its preamble")
    ok("Len (B.F_Bag_items)" in src, "its length")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: ok")
    print(f"{CHECKS} checks")
