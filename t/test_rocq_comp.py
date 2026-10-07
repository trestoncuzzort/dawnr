#!/usr/bin/env python3
"""test_rocq_comp.py: comprehensions in the Rocq lowering (PREDICT T14, 2026-10-06; SPEC.md "Comprehensions (v1)").
Text-level checks only, no kernel runs. A map is its own (function, length) pair: over a seq `(fun k => body(s k))`
with the source's length; over a range `(fun k => body(lo + k))` with `Z.max 0 (hi - lo)`, the index alone when lo is
the literal 0. The body owes its definedness at every element. A filter, and a comprehension inside a spec_fun,
method or lemma, refuse by name. Every other kernel's refusal is unchanged."""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import lower_framac  # noqa: E402
import lower_rocq  # noqa: E402
import surface  # noqa: E402
import tasks_io  # noqa: E402

CHECKS = 0


def ok(cond, what):
    global CHECKS
    CHECKS += 1
    if not cond:
        print("FAIL:", what)
        sys.exit(1)


def load(name: str) -> dict:
    return tasks_io.load_task(str(HERE / "tasks" / f"{name}.t"))


def rocq(name: str) -> str:
    task = load(name)
    return lower_rocq.lower(task, task["body"])


def refusal(task: dict, mod=lower_rocq) -> str:
    try:
        mod.lower(task, task["body"])
    except NotImplementedError as e:
        return str(e)
    return ""


def test_maps_are_functions():
    src = rocq("doubled")
    ok(re.search(r"Definition doubled_t \(s : Z -> Z\) \(s_len : Z\) : Z -> Z := \(fun (t_ck\d+) : Z => "
                 r"\(2 \* \(s \1\)\)\)\.", src), "doubled is (fun k => 2 * s k)")
    ok("Definition doubled_t_len (s : Z -> Z) (s_len : Z) : Z := s_len." in src, "doubled has its source's length")
    src = rocq("squares")
    ok(re.search(r"Definition squares_t \(n : Z\) : Z -> Z := \(fun (t_ck\d+) : Z => \(\1 \* \1\)\)\.", src),
       "a range from 0 binds the index alone")
    ok("Definition squares_t_len (n : Z) : Z := (Z.max 0 (n - 0))." in src, "a range's length is Z.max 0 (hi - lo)")
    src = rocq("every_other")
    ok(re.search(r"\(fun (t_ck\d+) : Z => \(\(t_slice s 0\) \(2 \* \1\)\)\)", src),
       "a stepped slice is the range comprehension the parser expands it to")


def test_body_definedness_at_every_element():
    src = rocq("diffs")
    ok(re.search(r"\(0 <= i < \(s_len - 1\)\) ->\n  \(0 <= \(i \+ 1\) < s_len\)\.", src),
       "diffs' body owes s[i + 1] at every index of its range")
    ok(re.search(r"\(0 <= i < \(s_len - 1\)\) ->\n  \(0 <= i < s_len\)\.", src), "and s[i]")


def test_refusals_by_name():
    e = refusal(load("evens"))
    ok("comprehension" in e and "not lowered yet" in e, f"evens (a filter) refuses by name: {e}")  # PREDICT T55
    e = refusal(load("count_evens_skip"))
    ok("not lowered yet" in e, f"count_evens_skip refuses by name: {e}")
    task = surface.parse("""t 1
task twice_len(s: seq) returns (r: int)
  ensures r == dbl(s)
spec fun dbl(q: seq): int
  decreases 0
= len([2 * x for x in q])
{
  r := len(s);
}
""")
    e = refusal(task)
    ok("comprehension inside a spec_fun, method or lemma" in e, f"a spec_fun's comprehension refuses by name: {e}")


def test_other_kernels_refuse_a_filter_by_name():
    # every kernel carries maps since PREDICT T16, T18, T19; a filter is still refused by name in Frama-C
    e = refusal(load("evens"), lower_framac)
    ok("comprehension" in e and "not lowered yet" in e, f"lower_framac refuses evens by name: {e}")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: ok")
    print(f"{CHECKS} checks")
