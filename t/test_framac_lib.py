#!/usr/bin/env python3
"""test_framac_lib.py: the library (v1) and max/min of one argument in the Frama-C lowering (PREDICT T11, 2026-10-06;
internal/RESEARCH-2026-10-06-landscape.md decision D1). Text-level checks only, no kernel runs: specification positions
use ACSL's own \\min/\\max/\\abs and the prelude's logic definitions, each recursive one with its termination lemma (the
adapter's structural backstop reads a missing one as vacuous); executable positions call the prelude's C helpers;
definedness is asserted where the SPEC owes it; the certificate replay evaluates the library and renders min, max and
abs branch-free; no ACSL axiom is emitted; the refusals are by name."""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import framac_lib  # noqa: E402
import harness  # noqa: E402
import lower_framac  # noqa: E402
import tasks_io  # noqa: E402

CHECKS = 0


def ok(cond, what):
    global CHECKS
    CHECKS += 1
    if not cond:
        print("FAIL:", what)
        sys.exit(1)


def framac(name: str) -> str:
    task = tasks_io.load_task(str(HERE / "tasks" / f"{name}.t"))
    return lower_framac.lower(task, task["body"])


def test_spec_and_code_positions():
    src = framac("clamp")
    ok("t_gcd" not in src and "? (" in src, "clamp is C conditionals, no prelude")
    src = framac("gcd_of")
    ok("ensures (\\result == t_gcd(a, b));" in src and "t_gcd_c(a, b)" in src, "gcd in the spec and the helper in code")
    src = framac("root_floor")
    ok("t_isqrt_c(n)" in src and "assert (n) >= 0" in src, "isqrt's helper, with its definedness asserted")
    src = framac("has_elem")
    ok("\\exists integer t_k; 0 <= t_k < s_n" in src and "t_memb_c(s, s_n, x)" in src,
       "membership is the existential in the spec and the helper in code")
    src = framac("sum_one")
    ok("((0 + (x)))" in src or "(0 + (x))" in src, "sum of a display is its definitional unfolding")
    src = framac("largest")
    ok("t_maxs_c(s, s_n)" in src and "assert s_n > 0" in src, "max of one argument, with its definedness asserted")


def test_every_recursive_definition_has_its_termination_lemma():
    text = framac_lib.prelude({"gcd", "pow", "isqrt", "sum", "maxs", "in"})
    found = 0
    for name, body in re.findall(r"logic integer (t_\w+?)(?:\{L\})?\([^)]*\)\s*=\s*(.*?);", text, re.S):
        if re.search(rf"\b{name}\b", body):           # recursive: its own name in its body
            found += 1
            ok(f"lemma {name}_terminates" in text, f"{name} carries its termination lemma")
    ok(found == 6, f"six recursive definitions (gcdn, pow, isqrt, sum, maxs, mins), found {found}")
    ok("axiom" not in text, "no ACSL axiom in the prelude")


def test_certificates():
    task = tasks_io.load_task(str(HERE / "tasks" / "clamp.t"))
    twin, _got, w = harness.twin_for(task)
    src = lower_framac.lower(task, twin, w)
    cert = src[src.find("t_certificate"):]
    ok("t_refutation_certificate" in cert and "?" not in cert,
       "clamp's certificate replays min/max branch-free (a live ?: arm is dead code at ground values)")
    task = tasks_io.load_task(str(HERE / "tasks" / "gcd_of.t"))
    twin, _got, w = harness.twin_for(task)
    ok("t_refutation_certificate" in lower_framac.lower(task, twin, w), "gcd_of's certificate is built")


def test_refusals_by_name():
    for name, word in (("palindrome", "rev"), ("first_sorted", "sort"), ("all_positive", "all")):
        task = tasks_io.load_task(str(HERE / "tasks" / f"{name}.t"))
        try:
            lower_framac.lower(task, task["body"])
            ok(False, f"{name} must refuse")
        except NotImplementedError as e:
            ok(word in str(e) and "not lowered yet" in str(e), f"{name} refuses by name: {e}")
    ok("in" not in lower_framac._SET_OPS_T, "a seq's `in` is not a set use")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: ok")
    print(f"{CHECKS} checks")
