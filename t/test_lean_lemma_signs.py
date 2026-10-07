#!/usr/bin/env python3
"""test_lean_lemma_signs.py: the nonlinear sign bridge for products inside a definition a lemma's ensures calls
(PREDICT T28, 2026-10-07). Text-level checks only, no kernel runs. AlgoVeri's integer_exponential was blocked in
Lean only by `0 <= b * spec_pow(b, e - 1)`, which grind's linear arithmetic does not derive from the two factors'
signs; the lemma closer now states it, instantiated at the call's arguments, after the inductive hypothesis."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import lower_lean  # noqa: E402
import tasks_io  # noqa: E402

CHECKS = 0


def ok(cond, what):
    global CHECKS
    CHECKS += 1
    if not cond:
        print("FAIL:", what)
        sys.exit(1)


def lean(path: Path) -> str:
    task = tasks_io.load_task(str(path))
    return lower_lean.lower(task, task["body"])


def test_definition_product_is_stated_after_the_hypothesis():
    src = lean(HERE / "algoveri" / "integer_exponential.t")
    lemma = src[src.index("theorem pow_nonneg_l"):src.index("termination_by", src.index("theorem pow_nonneg_l"))]
    fact = "try have _mpd0 : (0:Int) ≤ (b) * ((spec_pow_s b (e - (1 : Int)))) := Int.mul_nonneg (by omega) (by omega)"
    ok(fact in lemma, "the product inside spec_pow, at the call's arguments")
    ok(lemma.index("have _lm") < lemma.index("_mpd0"), "stated after the inductive hypothesis, so omega sees it")
    ok(lemma.count("_mpd0") == 2, "before each closer (both arms of the case split)")


def test_no_fact_without_a_definition_product():
    src = lean(HERE / "tasks" / "fib.t")
    ok("_mpd" not in src, "a task whose lemma-free definitions hold no product is unchanged")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: ok")
    print(f"{CHECKS} checks")
