#!/usr/bin/env python3
"""test_framac_datatypes.py: datatypes in Frama-C (SPEC.md "Datatypes (v1)", "(v2): fields", the Frama-C note of
2026-10-07, PREDICT T37). Text-level checks only, no kernel runs:
- a datatype is a struct passed by value, a tag and a field per constructor's field, its predicates `ok` and `eq`;
- a match is a conditional on the tag (`\\let` in ACSL, the field substituted in C), a field read owes its tag;
- `==` with a constructor expands field by field;
- the certificate declares the witness as a compound literal and decides each match at the ground tag;
- a single-constructor datatype with a seq field is a flattened parameter, one C parameter per field (PREDICT T43);
- a recursive datatype, a seq field in a datatype of several constructors, any other use of a flattened one refuse by
  name."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import lower_framac  # noqa: E402
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


def framac(name: str, twin: bool = False) -> str:
    return tlib.lower(load(name), "framac", twin_body=twin)


def test_declarations():
    src = framac("shape_area")
    ok("enum dt_Shape_tag { dt_Shape_Circle, dt_Shape_Rect, dt_Shape_Dot };" in src, "the tags")
    ok("struct dt_Shape { int tag; int f_Circle_r; int f_Rect_w; int f_Rect_h; };" in src, "every variant's storage")
    ok("predicate dt_Shape_ok(struct dt_Shape x)" in src and "requires dt_Shape_ok(s);" in src,
       "a parameter is built by one of its constructors")
    ok("int shape_area_t(struct dt_Shape s)" in src, "passed by value")
    ok("enum dt_" not in framac("clamp"), "nothing for a task without datatypes")


def test_match_and_fields():
    src = framac("shape_area")
    ok("(\\let r = (s).f_Circle_r; (\\result == ((3 * r) * r)))" in src, "an ACSL match arm binds by \\let")
    ok("a = ((s).tag == dt_Shape_Circle ? ((3 * (s).f_Circle_r) * (s).f_Circle_r)" in src,
       "in C the binder is its field")
    src = framac("rect_area")
    ok("/*@ assert ((s).tag == dt_Shape_Circle ? \\false : \\true); */" in src, "a field read asserts its tag first")
    ok("(((c).tag == dt_Color_Red) ==> (\\result == 0))" in framac("color_code"),
       "== with a constructor is its tag and fields")


def test_certificate():
    src = framac("shape_area", twin=True)
    cert = src[src.index("void t_certificate(void)"):]
    ok("struct dt_Shape s = ((struct dt_Shape){.tag = dt_Shape_Circle, .f_Circle_r = 1});" in cert,
       "the witness as its compound literal")
    ok("/*@ assert (s).tag == dt_Shape_Circle; */" in cert and "a = ((4 * (s).f_Circle_r) * (s).f_Circle_r);" in cert,
       "the match decided at the ground tag, only the taken arm")
    cert = framac("manhattan", twin=True)
    ok("?" not in cert[cert.index("void t_certificate(void)"):], "a nested abs is decided too, no live ?:")


def test_refused_by_name():
    for name, word in (("tree_sum", "recursive datatype"), ("checked_tail", "a seq field in a datatype with several")):
        task = load(name)
        try:
            lower_framac.lower(task, task["body"])
            ok(False, f"{name} refuses")
        except NotImplementedError as e:
            ok(word in str(e), f"{name} refuses by name: {e}")


def test_flattened_parameter():
    # PREDICT T43: Bag(items: seq, active: bool) as a parameter is its fields, the seq one a buffer and a length
    src = framac("bag_size")
    ok("int bag_size_t(int *b_items, int b_items_n, int b_active)" in src, "one C parameter per field")
    ok("requires b_items_n >= 0;" in src and "requires \\valid_read(b_items + (0 .. b_items_n - 1));" in src,
       "the seq field owes what a seq parameter owes")
    ok("ensures ((b_active != 0) ==> (\\result == b_items_n));" in src and "n = b_items_n;" in src,
       "a field read is the bare name, a bool one compared with 0")
    ok("struct dt_Bag" not in src and "dt_Bag_ok" not in src, "no struct and no ok predicate")
    cert = framac("bag_size", twin=True)
    cert = cert[cert.index("void t_certificate(void)"):]
    ok("int t_cert_b_items[1] = {0};" in cert and "int *b_items = t_cert_b_items;" in cert
       and "int b_items_n = 1;" in cert and "int b_active = 0;" in cert, "the witness declared field by field")


def test_flattened_parameter_other_uses_refused():
    head = "datatype Bag = Bag(items: seq, active: bool)\nt 1\n"
    for src, what in (
            ("task f(b: Bag) returns (r: Bag)\n  ensures true\n{\n  r := b;\n}\n", "a return"),
            ("task f(b: Bag, c: Bag) returns (r: bool)\n  ensures true\n{\n  r := b == c;\n}\n", "an equality"),
            ("task f(s: seq) returns (r: int)\n  ensures true\n{\n  var b: Bag := Bag.Bag(s, true);\n"
             "  r := len(b.items);\n}\n", "a local and a constructor"),
            ("task f(b: Bag) returns (r: int)\n  ensures true\n{\n  r := case b { Bag(xs, a) => len(xs) };\n}\n",
             "a match")):
        task = surface.parse(head + src)
        try:
            lower_framac.lower(task, task["body"])
            ok(False, f"{what} refuses")
        except NotImplementedError as e:
            ok("flattened task parameter" in str(e), f"{what} refuses by name: {e}")


def test_datatype_return_and_local():
    # PREDICT T40: a datatype return is the struct by value, the loop frame havocs it by name
    src = framac("some_negative")
    ok("struct dt_Opt some_negative_t(int *s, int s_n)" in src and "  struct dt_Opt r;" in src, "the struct return")
    ok("r = ((struct dt_Opt){.tag = dt_Opt_Some, .f_Some_v = s[i]});" in src, "a constructor assigned")
    ok("loop assigns r, i;" in src, "framed by name")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: ok")
    print(f"{CHECKS} checks")
