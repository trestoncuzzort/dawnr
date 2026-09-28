#!/usr/bin/env python3
"""test_lower_lean_datatypes.py: the case-split alternative for datatype-typed
parameters in the Lean lowering's contract proof (2026-09-28, fz_p_dt_eq).

grind does not split an enumerated type's parameter on its own, so a
contract stated through `=`/`≠` on constructors (fz_p_dt_eq: `c ≠ Blue`
against a body deciding `c = Red ∨ c = Green`) read unproved under every
alternative of the ladder while Dafny and Verus verified it. `cases p <;>
grind [f]` (Theorem Proving in Lean 4 ch. 7 "Inductive Types": the
recursor of an enumerated type, one goal per constructor) is one more
`first` alternative, offered only when a parameter has a datatype type, so
no other task's text changes. This file runs no prover; the kernel verdict
is t/CONFORMANCE.md's fz_p_dt_eq row (verified from 2026-09-28).

Run: python3 t/test_lower_lean_datatypes.py   (or pytest)
"""

from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import fuzz_lower as fz                                        # noqa: E402
import surface                                                 # noqa: E402
from lower_lean import lower                                   # noqa: E402


def _probe(name: str) -> dict:
    p = next(x for x in fz.probes() if x["name"] == name)
    return {k: v for k, v in p.items() if not k.startswith("_")}


def _committed(name: str) -> dict:
    return surface.parse_file(os.path.join(HERE, "tasks", name + ".t"))


def test_datatype_parameter_gets_the_case_split_alternative() -> None:
    task = _probe("fz_p_dt_eq")
    src = lower(task, task["body"])
    assert "  | (cases c <;> grind [fz_p_dt_eq_t])\n" in src, src
    assert src.index("| grind [fz_p_dt_eq_t]") < src.index("| (cases c"), \
        "the case split is offered after the plain grind, not before it"


def test_committed_color_code_gets_it_too() -> None:
    task = _committed("color_code")
    src = lower(task, task["body"])
    assert "  | (cases c <;> grind [color_code_t])\n" in src, src


def test_two_datatype_parameters_nest_the_split() -> None:
    task = json.loads(json.dumps(_probe("fz_p_dt_eq")))
    task["params"].append({"name": "d", "type": {"datatype": "Color"}})
    src = lower(task, task["body"])
    assert "  | (cases c <;> cases d <;> grind [fz_p_dt_eq_t])\n" in src, src


def test_no_datatype_parameter_no_case_split() -> None:
    for name in ("abs", "double_all"):
        task = _committed(name)
        src = lower(task, task["body"])
        assert "| (cases " not in src, (name, src)


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"{t.__name__}: pass")
    print(f"test_lower_lean_datatypes: all {len(tests)} checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
