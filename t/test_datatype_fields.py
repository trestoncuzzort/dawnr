#!/usr/bin/env python3
"""test_datatype_fields.py: datatypes with fields (SPEC.md "Datatypes (v2): fields", PREDICT T23, 2026-10-07).
Text-level checks only, no kernel runs: the notation (parse, print, the `X.y` rule), the interpreter (field values,
definedness, the witness ladder and its shown form), the three lowerings that state the construct (Dafny, Verus,
Lean), the four that refuse it by name, the name sanitizer, and the Python hand-back's refusal."""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import interp  # noqa: E402
import lower_dafny  # noqa: E402
import lower_framac  # noqa: E402
import lower_lean  # noqa: E402
import lower_verus  # noqa: E402
import names  # noqa: E402
import surface  # noqa: E402
import tasks_io  # noqa: E402
import to_python  # noqa: E402

CHECKS = 0

# a field named like a Lean and Verus keyword; committed tasks need no rename (test_names), so the probe lives here
OPEN_BAG = """datatype Bag = Bag(items: seq, open: bool)
t 1
task bag_open(b: Bag) returns (n: int)
  ensures b.open ==> n == len(b.items)
  ensures not b.open ==> n == 0
{
  if b.open {
    n := len(b.items);
  } else {
    n := 0;
  }
}
"""


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


def refusal(mod, task: dict) -> str:
    try:
        mod.lower(task, task["body"])
    except NotImplementedError as e:
        return str(e)
    return ""


def test_parse_and_print_round_trip():
    task = load("shape_area")
    ok(task["datatypes"][0]["ctors"][1] == {"name": "Rect", "fields": [{"name": "w", "type": "int"},
                                                                       {"name": "h", "type": "int"}]},
       "a constructor's fields are declared in order with their types")
    ok("fields" not in task["datatypes"][0]["ctors"][2], "a field-less constructor keeps v1's shape")
    for name in ("shape_area", "manhattan", "rect_area", "some_negative", "bag_size", "checked_tail"):
        t = load(name)
        again = surface.parse(surface.print_task(t))
        ok(again["datatypes"] == t["datatypes"] and again["body"] == t["body"]
           and again["ensures"] == t["ensures"] and again.get("requires") == t.get("requires"),
           f"{name}: printing and parsing again gives the same program")


def test_dot_rule():
    task = surface.parse("""datatype P = P(x: int)
t 1
task f(p: P) returns (r: int) ensures true
{
  r := p.x
}
""")
    ok(task["body"][0]["assign"][1] == {"field": {"of": {"var": "p"}, "name": "x"}},
       "x.f on a name that is not a declared datatype is field access")
    e = surface.parse_expr("Shape.Rect(2, 3)")
    ok(e == {"ctor": {"dtype": "Shape", "name": "Rect", "args": [{"int": 2}, {"int": 3}]}},
       "D.C(a, b) builds a constructor value")
    e = surface.parse_expr("Color.Red")
    ok("ctor" in e, "with no declarations in scope, Name.Name is a constructor, as on 2026-10-06")
    task = surface.parse("""datatype P = P(x: int)
t 1
task f(s: seq) returns (r: int) ensures true
{
  r := len(s.lower);
}
""")
    ok(task["body"][0]["assign"][1]["args"][0] == {"field": {"of": {"var": "s"}, "name": "lower"}},
       "a string-member name with no call is a field, so the grammar's one `.name` form is the parser's too")


def test_interp_fields_and_definedness():
    task = load("rect_area")
    funs = interp.funs_of(task, task["body"])
    ok(funs["$fields"]["Shape"] == {"Circle": ["r"], "Rect": ["w", "h"]}, "funs records each field list")
    rect = interp.Ctor("Shape", "Rect", (2, 3))
    circ = interp.Ctor("Shape", "Circle", (1,))
    w = {"field": {"of": {"var": "s"}, "name": "w"}}
    ok(interp.ev(w, {"s": rect}, funs, interp.St()) == 2, "s.w reads the field by position")
    try:
        interp.ev(w, {"s": circ}, funs, interp.St())
        ok(False, "s.w on a Circle is undefined")
    except interp.Undef:
        ok(True, "s.w on a Circle is undefined")
    lad = interp.ladders(task)["datatype:Shape"]
    rects = [v for v in lad if v.ctor == "Rect"]
    ok(0 < len(rects) <= interp.DT_CTOR_CAP and rects[0] == interp.Ctor("Shape", "Rect", (0, 0)),
       f"the witness ladder enumerates a constructor with fields, the near corner first: {rects[:3]}")
    ok(any(v.ctor == "Circle" for v in lad), "every constructor enters the ladder")
    shown = interp._j(interp.Ctor("Bag", "Bag", ((0,), False)))
    ok(shown == "Bag.Bag([0], false)", f"a shown value is t's notation, bools included: {shown}")
    back = interp.ev(surface.parse_expr(shown), {}, {}, interp.St())
    ok(back == interp.Ctor("Bag", "Bag", ((0,), False)), "and the parser reads it back to the same value")


def test_dafny():
    src = text(lower_dafny, "shape_area")
    ok("datatype Shape = Circle(r: int) | Rect(w: int, h: int) | Dot" in src, "dafny declares the named fields")
    src = text(lower_dafny, "rect_area")
    ok(re.search(r"\(s\)\.w", src), "dafny reads a field with its own destructor")


def test_verus():
    src = text(lower_verus, "manhattan")
    ok("enum Point { Point(int, int) }" in src, "verus declares tuple variants")
    ok("use Point::*;" not in src, "a variant named like its datatype is not glob-imported (E0659)")
    ok("Point::Point(" in src, "and is spelled qualified")
    src = text(lower_verus, "rect_area")
    ok("vstd::pervasive::arbitrary()" in src, "a field some constructor lacks reads arbitrary() there")
    ok("#[derive(PartialEq, Eq)]" in src, "an int-field enum keeps v1's derive")
    task = surface.parse(OPEN_BAG)
    src = lower_verus.lower(task, task["body"])
    ok("(match b { Bag::Bag(_, t_fv) => t_fv })" in src and "arbitrary()" not in src,
       "a renamed field still finds its constructor (the declarations are read after the rename)")
    src = text(lower_verus, "checked_tail")
    ok("#[derive(PartialEq, Eq)]" not in src and "enum Res { Ok(Seq<int>), Err(int) }" in src,
       "an enum with a seq field has no derive (vstd's Seq implements no PartialEq)")


def test_lean():
    src = text(lower_lean, "shape_area")
    ok("  | Rect (w : Int) (h : Int)\n" in src, "lean declares named binders")
    ok("mulsign" not in src, "no sign lemma over a match binder")
    ok("simp at hpre <;> simp_all" in src, "the case-split sign alternative is offered")
    src = text(lower_lean, "rect_area")
    ok("(match s with | .Rect t_fv _ => t_fv | _ => default)" in src, "a field read is Lean's own match")
    src = text(lower_lean, "manhattan")
    ok("| _ => default" not in src, "a record's field read has no default arm")
    src = text(lower_lean, "some_negative")
    ok(re.search(r"\| \.None => \(∀ \(k_\d+ : Int\)", src), "a quantified arm stays a Prop-valued match")
    ok("def some_negative_t_post (s : List Int) (r : Opt) : Prop :=" in src,
       "the loop lemma states the contract through a named predicate")
    task = surface.parse(OPEN_BAG)
    src = lower_lean.lower(task, task["body"])
    ok("(t_open : Bool)" in src and "(open : Bool)" not in src, "a field named like a Lean keyword is renamed")
    ok("| _ => default" not in text(lower_lean, "color_code"), "v1's enumeration reads no field")


def test_every_kernel_lowers_fields():
    # Rocq, F*, SPARK and Frama-C lower datatypes since PREDICT T34-T37 (test_rocq_datatypes.py,
    # test_fstar_datatypes.py, test_spark_datatypes.py, test_framac_datatypes.py)
    import lower_fstar
    import lower_rocq
    import lower_spark
    task = load("shape_area")
    for mod in (lower_dafny, lower_verus, lower_lean, lower_rocq, lower_fstar, lower_spark, lower_framac):
        ok(refusal(mod, task) == "", f"{mod.__name__} lowers shape_area")


def test_names_sanitize_fields_and_binders():
    task = surface.parse(OPEN_BAG)
    t2, ren = names.sanitize(task, names.KEYWORDS["lean"], uppercase_ok=True)
    ok(ren.get("open") == "t_open", "a field named open is renamed for lean")
    ok(t2["datatypes"][0]["ctors"][0]["fields"][1]["name"] == "t_open", "in its declaration")
    ok("t_open" in str(t2["ensures"]) and "'open'" not in str(t2["ensures"]), "and at every use")
    task = surface.parse("""datatype Opt = None | Some(v: int)
t 1
task f(r: Opt) returns (k: int) ensures true
{
  k := case r { None => 0, Some(have) => have };
}
""")
    t2, ren = names.sanitize(task, names.KEYWORDS["lean"], uppercase_ok=True)
    arm = t2["body"][0]["assign"][1]["match"]["arms"][1]
    ok(ren.get("have") and arm["binders"] == [ren["have"]] and arm["body"] == {"var": ren["have"]},
       "a match binder named like a keyword is renamed with its uses")


def test_python_hand_back_refuses():
    try:
        to_python.translate(load("manhattan"))
        ok(False, "to_python refuses datatypes")
    except to_python.Unsupported as e:
        ok("datatypes" in str(e), "to_python refuses datatypes by name")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: ok")
    print(f"{CHECKS} checks")
