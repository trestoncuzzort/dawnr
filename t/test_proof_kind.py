"""t/proof_kind.py: whether a proved answer is an algorithm held to a separate statement or a program that is its
specification written again (CLEVER's leak, arXiv:2505.13938), read from the answer's text by rule."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import proof_kind as pk                                         # noqa: E402
import surface                                                  # noqa: E402


def task(text: str) -> dict:
    return surface.parse("t 1\n" + text)


ONE_LINE = "task area(d1: int, d2: int) returns (r: int)\n  ensures r == d1 * d2 / 2\n{\n  r := d1 * d2 / 2;\n}\n"
BY_CASES = ("task sign(n: int) returns (r: int)\n  ensures n > 0 ==> r == 1\n  ensures n <= 0 ==> r == 0\n"
            "{\n  if n > 0 {\n    r := 1;\n  } else {\n    r := 0;\n  }\n}\n")
LUCAS = "spec fun lucas(n: int): int\n  decreases n\n= if n <= 0 then 2 else if n == 1 then 1 else lucas(n - 1) + lucas(n - 2)\n"
MIRROR = ("gate recursion\ntask find_lucas(n: int) returns (r: int)\n  requires n >= 0\n  ensures r == lucas(n)\n  decreases n\n" + LUCAS
          + "{\n  if n <= 0 {\n    r := 2;\n  } else {\n    if n == 1 {\n      r := 1;\n    } else {\n"
            "      r := find_lucas(n - 1) + find_lucas(n - 2);\n    }\n  }\n}\n")
SUM = "spec fun total(k: int): int\n  decreases k\n= if k <= 0 then 0 else total(k - 1) + k\n"
LOOP = ("gate loops\ntask series(n: int) returns (r: int)\n  requires n >= 0\n  ensures r == total(n)\n" + SUM
        + "{\n  r := 0;\n  var i: int := 1;\n  while i <= n\n    invariant r == total(i - 1)\n    invariant i >= 1 and i <= n + 1\n"
          "    decreases n - i + 1\n  {\n    r := r + i;\n    i := i + 1;\n  }\n}\n")
OTHER_RECURSION = ("gate recursion\ntask series(n: int) returns (r: int)\n  requires n >= 0\n  ensures r == total(n)\n  decreases n\n" + SUM
                   + "{\n  if n <= 1 {\n    r := n;\n  } else {\n    r := series(n - 2) + n + n - 1;\n  }\n}\n")
PROPERTY = ("task max_of_three(a: int, b: int, c: int) returns (r: int)\n  ensures r >= a\n  ensures r >= b\n  ensures r >= c\n"
            "  ensures r == a or r == b or r == c\n{\n  if a >= b and a >= c {\n    r := a;\n  } else {\n    if b >= c {\n      r := b;\n"
            "    } else {\n      r := c;\n    }\n  }\n}\n")
POW = "spec fun pow(base: int, exp: int): int\n  decreases exp\n= if exp <= 0 then 1 else base * pow(base, exp - 1)\n"
THROUGH = ("gate loops\ntask powers(s: seq, n: int) returns (r: seq)\n  requires n >= 0\n  ensures len(r) == len(s)\n"
           "  ensures forall i in [0, len(r)) . r[i] == pow(s[i], n)\n" + POW
           + "{\n  r := [];\n  var i: int := 0;\n  while i < len(s)\n    invariant 0 <= i\n    invariant i <= len(s)\n    invariant len(r) == i\n"
             "    invariant forall j in [0, i) . r[j] == pow(s[j], n)\n    decreases len(s) - i\n  {\n    r := r + [pow(s[i], n)];\n    i := i + 1;\n  }\n}\n")


@pytest.mark.parametrize("text, kind, spec, word", [
    (ONE_LINE, pk.RESTATEMENT, "a formula", "no loop"),
    (BY_CASES, pk.RESTATEMENT, "a formula", "by cases"),
    (MIRROR, pk.RESTATEMENT, "a formula", "recurses exactly as the specification function"),
    (LOOP, pk.ALGORITHM, "a formula", "a loop is proved"),
    (OTHER_RECURSION, pk.ALGORITHM, "a formula", "a recursion other than the specification's own"),
    (PROPERTY, pk.ALGORITHM, "a property", "constrains the result without giving it"),
    (THROUGH, pk.ALGORITHM, "a property", "constrains the result"),
])
def test_what_a_proof_is_of(text, kind, spec, word):
    k = pk.kind(task(text))
    assert k["kind"] == kind and k["specification"] == spec and word in k["why"]


def test_a_program_that_computes_through_its_specification_function_is_noted_and_an_invariant_is_not_a_computation():
    assert pk.kind(task(THROUGH))["through its specification function"] is True
    assert pk.kind(task(LOOP))["through its specification function"] is False          # `total` appears only in the invariant
    assert pk.kind(task(MIRROR))["through its specification function"] is False


def test_a_formula_is_a_clause_that_gives_the_result_outright_or_as_the_conclusion_of_a_case():
    assert pk.formula(task(ONE_LINE)) is not None and len(pk.formula(task(BY_CASES))) == 2
    # cases under two conditions, beside a clause that only lists the allowed values: still read off the specification
    nested = task("task verdict(s: seq, b: int) returns (r: int)\n  ensures r == 1 or r == 0\n"
                  "  ensures len(s) >= 2 ==> b == 0 ==> r == 1\n  ensures b != 0 ==> r == 0\n"
                  "{\n  if b == 0 {\n    r := 1;\n  } else {\n    r := 0;\n  }\n}\n")
    assert len(pk.formula(nested)) == 2 and pk.kind(nested)["kind"] == pk.RESTATEMENT
    assert pk.formula(task(PROPERTY)) is None and pk.formula(task(THROUGH)) is None
    # `r == r + 0` does not give r; a bound beside a formula does not make it a property
    assert pk.formula(task("task f(n: int) returns (r: int)\n  ensures r == r + 0\n{\n  r := n;\n}\n")) is None
    both = task("task f(n: int) returns (r: int)\n  ensures r >= 0\n  ensures n * n == r\n{\n  r := n * n;\n}\n")
    assert pk.formula(both) is not None and pk.kind(both)["kind"] == pk.RESTATEMENT


def test_the_person_is_told_which_it_is():
    assert pk.sentence(task(LOOP)) == "What the proof is of: a loop is proved to reach what the specification defines."
    said = pk.sentence(task(ONE_LINE))
    assert said.startswith("What the proof is of: the program has no loop and the specification gives its result as a formula or by cases.")
    assert said.endswith("what this answer rests on is the specification, which was held to an independent solution on drawn inputs and is printed to be read.")
    assert pk.sentence(task(ONE_LINE), "prove").endswith("the specification, which is the one you wrote.")
    assert pk.sentence(task(ONE_LINE), "verify").endswith("which was held to your own function's answers on drawn inputs and is printed to be read.")
    assert pk.said("t 1\n" + LOOP).startswith("What the proof is of: a loop") and pk.said("not a program") is None
