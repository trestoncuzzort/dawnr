#!/usr/bin/env python3
"""test_lower_spark_methods.py: the SPARK lowering of SPEC.md "Methods (v1)",
checked for shape on the fixtures in t/methods/ and t/methods_probe/. No
prover runs here; the kernel's verdicts are measured with run_par.

What the shape has to be (lower_spark.py, the note above _METHOD_HIDE):
  * each method is its own expression function with an explicit Pre and
    Post (and a Subprogram_Variant when it self-calls), declared before the
    task's F, its loop helpers before it;
  * its body is hidden from callers by default (GNATprove Hide_Info), so a
    caller reasons through the contract alone, as in Dafny;
  * a call statement renders as an Ada call, and its Pre is owed where the
    call executes even when the result is never read;
  * a twin's refutation certificate discloses the method bodies to itself
    alone (Unhide_Info), since it claims something about execution;
  * the shapes the lowering cannot state raise NotImplementedError by name.

Run: python3 t/test_lower_spark_methods.py   (or pytest)
"""

from __future__ import annotations

import copy
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import harness                                                 # noqa: E402
import lower_spark                                             # noqa: E402
import surface                                                 # noqa: E402

HIDE = 'Annotate => (GNATprove, Hide_Info, "Expression_Function_Body")'
FIXTURES = sorted(glob.glob(os.path.join(HERE, "methods", "*.t")))


def _load(path: str) -> dict:
    return surface.parse_file(os.path.join(HERE, path))


def _real(task: dict) -> str:
    return lower_spark.lower(task, task["body"])


def _decl(src: str, name: str) -> str:
    """The text of method `name`'s declaration, up to its closing `;`."""
    i = src.index(f"   function {name} (")
    return src[i:src.index(";\n", src.index(HIDE, i)) + 2]


def _raises(task: dict, needle: str) -> None:
    try:
        _real(task)
    except NotImplementedError as e:
        assert needle in str(e), str(e)
        return
    raise AssertionError(f"expected NotImplementedError containing {needle!r}")


def test_each_method_is_its_own_contracted_hidden_function() -> None:
    assert len(FIXTURES) >= 4, FIXTURES
    for f in FIXTURES + [os.path.join(HERE, "methods_probe",
                                      "opaque_callee.t")]:
        t = surface.parse_file(f)
        src = _real(t)
        f_at = src.index("   function F (")
        prev = -1
        for m in t["methods"]:
            name = lower_spark.cap(m["name"])
            d = _decl(src, name)
            at = src.index(d)
            assert prev < at < f_at, (f, name)       # declaration order
            prev = at
            assert "\n     Pre  => " in d, (f, name)
            assert f"\n     Post => " in d and f"{name}'Result" in d, (f, name)
            assert d.rstrip().endswith(HIDE + ";"), (f, name)
            assert ("Subprogram_Variant" in d) == ("decreases" in m), (f, name)


def test_calls_are_ada_calls() -> None:
    src = _real(_load("methods/max3.t"))
    assert "then Max2 (Max2 (A, B), C)" in src
    src = _real(_load("methods/clamp_sum.t"))
    assert "Add_clamped (A, B, Hi)" in src[src.index("   function F ("):]
    assert "Clamp ((Clamp (X, H) + Y), H)" in _decl(src, "Add_clamped")
    # a call inside a loop lands in the loop helper's recursive step
    src = _real(_load("methods/count_pos.t"))
    w = src[src.index("   function W_1 (S : Seq; R : Big_Integer; "
                      "I : Big_Integer) return W_1_State\n   is"):]
    assert "W_1 (S, Step (R, Elem (S, I)), (I + Big_Integer'(1)))" in w
    # a callee with a loop: its helper precedes it; seq in, seq out
    src = _real(_load("methods/rev_twice.t"))
    assert src.index("function W_1 (U : Seq") < src.index("function Rev (U : Seq)")
    assert "function Rev (U : Seq) return Seq is" in src
    assert "Rev (Rev (S))" in src[src.index("   function F ("):]


def test_opaque_callee_body_is_hidden() -> None:
    src = _real(_load("methods_probe/opaque_callee.t"))
    d = _decl(src, "Inc")
    assert "Post => (Inc'Result > A)" in d and d.rstrip().endswith(HIDE + ";")
    assert "Unhide_Info" not in src          # nothing discloses it to F


def test_unused_call_still_owes_its_requires() -> None:
    t = surface.parse(
        "t 1\n"
        "task dead_call(x: int) returns (r: int)\n"
        "  ensures r == 0\n"
        "method need_pos(a: int) returns (b: int)\n"
        "  requires a > 0\n"
        "  ensures b == a\n"
        "{\n  b := a;\n}\n"
        "{\n  var u: int := need_pos(x);\n"
        "  if x > 5 {\n    u := need_pos(x - 5);\n  } else {\n    u := 1;\n  }\n"
        "  r := 0;\n}\n")
    src = _real(t)
    body = src[src.rindex("   function F ("):]
    assert "(Need_pos (X) = Need_pos (X))" in body
    # the branch's call is owed only under its own guard
    assert ("(if ((X > Big_Integer'(5))) then Need_pos ((X - Big_Integer'(5)))"
            " = Need_pos ((X - Big_Integer'(5))) else True)") in body


def test_recursive_method_has_a_variant_and_names_itself() -> None:
    t = surface.parse(
        "t 1\n"
        "task rec_sum(n: int) returns (r: int)\n"
        "  requires n >= 0\n"
        "  ensures 2 * r == n * (n + 1)\n"
        "method tri(k: int) returns (s: int)\n"
        "  requires k >= 0\n"
        "  ensures 2 * s == k * (k + 1)\n"
        "  decreases k\n"
        "{\n  if k == 0 {\n    s := 0;\n  } else {\n"
        "    var p: int := tri(k - 1);\n    s := p + k;\n  }\n}\n"
        "{\n  r := tri(n);\n}\n")
    d = _decl(_real(t), "Tri")
    assert "Tri ((K - Big_Integer'(1)))" in d
    assert "Subprogram_Variant => (Decreases => (if K >= 0 then K else 0))" in d
    assert " F (" not in d


def test_twin_certificate_unhides_the_methods_for_itself() -> None:
    for name in ("max3", "clamp_sum", "rev_twice"):
        t = _load(f"methods/{name}.t")
        body, op, w = harness.twin_for(t)
        src = lower_spark.lower(t, body, w)
        cert = src.index("function T_Refutation_Certificate return Boolean is")
        for m in t["methods"]:
            line = (f'pragma Annotate (GNATprove, Unhide_Info, '
                    f'"Expression_Function_Body", {lower_spark.cap(m["name"])});')
            assert src.index(line) > cert, (name, m["name"])
        assert "Unhide_Info" not in _real(t), name


def test_tasks_without_methods_emit_no_method_machinery() -> None:
    for f in sorted(glob.glob(os.path.join(HERE, "tasks", "*.t"))):
        t = surface.parse_file(f)
        assert not t.get("methods"), f
        try:
            src = _real(t)
        except (NotImplementedError, ValueError):
            continue
        assert "Hide_Info" not in src and "Unhide_Info" not in src, f


def test_abstain_method_call_under_early_return() -> None:
    t = _load("methods/max3.t")
    call = {"call": {"fun": "max2", "args": [{"var": "a"}, {"var": "b"}]}}
    t["body"] = [{"var": {"name": "m1", "type": "int", "init": call}},
                 {"return": ["r", {"var": "m1"}]}]
    _raises(t, "method call in a body with an early `return`")


def test_abstain_pair_typed_method() -> None:
    t = _load("methods/max3.t")
    t["methods"][0]["params"][0]["type"] = {"pair": ["int", "int"]}
    _raises(t, "uses a pair type")


def test_abstain_method_name_the_package_generates() -> None:
    t = json.loads(json.dumps(_load("methods/max3.t")).replace('"max2"', '"w_1"'))
    _raises(t, "spells a name this package generates")
    # a method named like the task's own F is renamed by names.sanitize
    # (RESERVED holds "F"), never captured
    t = json.loads(json.dumps(_load("methods/max3.t")).replace('"max2"', '"f"'))
    src = _real(t)
    assert "function T_f (X : Big_Integer; Y : Big_Integer)" in src
    assert src.count("   function F (") == 2
    assert src.rstrip().endswith("-- t renames: f -> t_f")


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"{fn.__name__}: pass")
    print(f"test_lower_spark_methods: {len(tests)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
