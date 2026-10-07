#!/usr/bin/env python3
"""test_rocq_datatypes.py: datatypes in Rocq (SPEC.md "Datatypes (v1)", "(v2): fields", "(v3): recursion", the Rocq
note of 2026-10-07, PREDICT T34). Text-level checks only, no kernel runs:
- a datatype is an Inductive, with a `decide equality` decider and a projection per field;
- `case` is Rocq's match, a field read owes its constructor, `==` is Leibniz in a Prop and decided in a bool;
- recursion on a datatype parameter is a structural Fixpoint, proved by induction;
- a certificate grounds a constructor witness;
- what is not lowered refuses by name."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import lower_rocq  # noqa: E402
import surface  # noqa: E402
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


def rocq(name: str, twin: bool = False) -> str:
    return tlib.lower(load(name), "rocq", twin_body=twin)


def test_declarations():
    src = rocq("shape_area")
    ok("Inductive dt_Shape : Type :=\n  | dt_Shape_Circle (f_r : Z)\n  | dt_Shape_Rect (f_w : Z) (f_h : Z)\n"
       "  | dt_Shape_Dot." in src, "an Inductive, one constructor per |, a field its argument")
    ok("Definition dt_Shape_eq_dec (t_a t_b : dt_Shape) : {t_a = t_b} + {t_a <> t_b}." in src
       and "decide equality" in src, "a decider by decide equality")
    ok("Definition dt_Shape_f_w (t_x : dt_Shape) : Z :=\n  match t_x with dt_Shape_Rect t_p0 t_p1 => t_p0 | _ => 0 end."
       in src, "a projection per field, a placeholder elsewhere")
    ok("Ltac t_dt_cases :=" in src and "destruct (dt_Shape_eq_dec a b)" in src, "the per-file case tactic")
    ok("Inductive dt_" not in rocq("clamp"), "nothing for a task without datatypes")


def test_expressions():
    src = rocq("shape_area")
    ok("(match s with dt_Shape_Circle r => ((3 * r) * r) | dt_Shape_Rect w h => (w * h) | dt_Shape_Dot => 0 end)"
       in src, "case is Rocq's match")
    ok("(match s with dt_Shape_Circle r => (r >= 0) | dt_Shape_Rect w h => ((w >= 0) /\\ (h >= 0))" in src,
       "and a Prop-valued one in a contract")
    ok("t_dt_cases.\n  all: t_dis." in src, "the straight-line proof splits first")
    src = rocq("rect_area")
    ok("(match s with dt_Shape_Rect _ _ => True | _ => False end)" in src and "t_dt_cases; t_dis" in src,
       "a field read owes its constructor, discharged by cases")
    ok("((c = dt_Color_Red) -> ((color_code_t c) = 0))" in rocq("color_code"), "== in a Prop is Leibniz equality")
    task = surface.parse("datatype Color = Red | Green\nt 1\ntask f(c: Color) returns (r: bool)\n"
                         "  ensures r == (c == Color.Red)\n{\n  r := c == Color.Red;\n}\n")
    ok("(if dt_Color_eq_dec c dt_Color_Red then true else false)" in lower_rocq.lower(task, task["body"]),
       "and decided in a bool")


def test_structural_recursion():
    src = rocq("tree_sum")
    ok("Fixpoint sf_total (q : dt_Tree) {struct q} : Z :=" in src, "a spec fun recursing on a datatype")
    ok("Fixpoint tree_sum_t (tr : dt_Tree) {struct tr} : Z :=" in src and "sf_total_fuel" not in src,
       "and the task, both structural, no fuel")
    ok("induction tr; cbn [tree_sum_t sf_total] in *." in src, "proved by induction")
    src = rocq("tree_insert")
    ok("destruct c eqn:?" in src and "H : _ /\\ _ |- _ => destruct H" in src,
       "an undecided if destructed, the hypotheses' conjuncts split")


def test_certificate_grounds_constructors():
    src = rocq("tree_mirror", twin=True)
    ok("Theorem t_refutation_certificate" in src, "the twin is certified")
    ok("(tree_mirror_t (dt_Tree_Node 0 dt_Tree_Leaf (dt_Tree_Node 0 dt_Tree_Leaf dt_Tree_Leaf)))" in src,
       "at the witness's constructor term")
    lower_rocq._DTS.update({d["name"]: d for d in load("tree_mirror")["datatypes"]})
    try:
        ok(lower_rocq._glit("Tree.Node(-1, Tree.Leaf, Tree.Leaf)", {"datatype": "Tree"})
           == "(dt_Tree_Node (-1) dt_Tree_Leaf dt_Tree_Leaf)", "a negative field in a ground term")
        ok(lower_rocq._dt_default("Tree") == "dt_Tree_Leaf", "the default value is the first buildable constructor")
    finally:
        lower_rocq._DTS.clear()


def test_refused_by_name():
    # PREDICT T42: a seq field lowers (bag_size); `==` on a datatype holding one refuses by name (checked_tail)
    task = load("checked_tail")
    try:
        lower_rocq.lower(task, task["body"])
        ok(False, "checked_tail refuses")
    except NotImplementedError as e:
        ok("on a datatype holding a seq" in str(e), f"checked_tail refuses by name: {e}")


def test_seq_field():
    src = rocq("bag_size")
    ok("| dt_Bag_Bag (f_items : ((Z -> Z) * Z)) (f_active : bool)." in src, "a seq field is one (function, length)")
    ok("(snd (dt_Bag_f_items b))" in src, "its length read by snd")
    ok("dt_Bag_eq_dec" not in src, "no decider for a datatype holding a function")


def test_loop_state_alternative():
    # PREDICT T41: a datatype task's t_dis and t_side split matched variables as their last alternative
    src = rocq("some_negative")
    ok("| solve [ t_dt_cases; t_vc0 ] ]" in src, "t_dis's last alternative")
    ok(src.count("solve [ t_dt_cases; t_vc0 ]") >= 2, "and t_side's")
    ok("t_dt_cases; t_vc0" not in rocq("clamp"), "not for a task without datatypes")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: ok")
    print(f"{CHECKS} checks")
