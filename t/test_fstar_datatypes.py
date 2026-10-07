#!/usr/bin/env python3
"""test_fstar_datatypes.py: datatypes in F* (SPEC.md "Datatypes (v1)", "(v2): fields", "(v3): recursion", the F* note
of 2026-10-07, PREDICT T35). Text-level checks only, no kernel runs:
- a datatype is F*'s own inductive type, a field read a function refined to the constructors that declare it;
- `case` is F*'s match, `==` is `=` in a bool and `==` in a Prop;
- recursion on a datatype parameter decreases by the subterm ordering;
- a certificate names the file's own (renamed) functions;
- a seq field refuses by name."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import lower_fstar  # noqa: E402
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


def fstar(name: str, twin: bool = False) -> str:
    return tlib.lower(load(name), "fstar", twin_body=twin)


def test_declarations():
    src = fstar("shape_area")
    ok("type dt_Shape =\n  | Dt_Shape_Circle : f_r:int -> dt_Shape\n  | Dt_Shape_Rect : f_w:int -> f_h:int -> dt_Shape\n"
       "  | Dt_Shape_Dot : dt_Shape" in src, "an inductive type, lower-case type and upper-case constructors")
    ok("let dt_Shape_f_w (t_x:dt_Shape{Dt_Shape_Rect? t_x}) : int =" in src,
       "a field read refined to its constructor, which F* proves at every read")
    ok("type dt_" not in fstar("clamp"), "nothing for a task without datatypes")


def test_expressions():
    src = fstar("shape_area")
    ok("(match s with | Dt_Shape_Circle r -> ((3 * r) * r) | Dt_Shape_Rect w h -> (w * h) | Dt_Shape_Dot -> 0)" in src,
       "case is F*'s match")
    ok("((c == Dt_Color_Red) ==> (r == 0))" in fstar("color_code"), "== in a Prop")
    task = surface.parse("datatype Color = Red | Green\nt 1\ntask f(c: Color) returns (r: bool)\n"
                         "  ensures r == (c == Color.Red)\n{\n  r := c == Color.Red;\n}\n")
    ok("(c = Dt_Color_Red)" in lower_fstar.lower(task, task["body"]), "and = in a bool")


def test_recursion():
    src = fstar("tree_sum")
    ok("let rec t_total (q:dt_Tree)\n  : Tot int (decreases q)" in src, "a spec fun decreasing on the tree")
    ok("(decreases tr)" in src, "and the task")


def test_certificate_uses_the_files_names():
    src = fstar("tree_sum", twin=True)
    cert = src[src.index("let t_refutation_certificate"):]
    ok("(t_total Dt_Tree_Leaf)" in cert and "(total " not in cert, "the renamed spec fun, at the ground witness")


def test_seq_fields():
    # PREDICT T42: a seq field is `Seq.seq int`; such a type is no eqtype, so `==` is propositional only
    src = fstar("bag_size")
    ok("| Dt_Bag_Bag : f_items:Seq.seq int -> f_active:bool -> dt_Bag" in src, "a seq field")
    ok("(Seq.length (dt_Bag_f_items b))" in src, "its length")
    src = fstar("checked_tail")
    ok("(r == (Dt_Res_Ok (Seq.slice s 1 (Seq.length s))))" in src, "== in a Prop on a datatype holding a seq")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: ok")
    print(f"{CHECKS} checks")
