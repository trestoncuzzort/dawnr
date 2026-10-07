#!/usr/bin/env python3
"""test_framac_comp.py: comprehensions in the Frama-C lowering (PREDICT T19, 2026-10-07; SPEC.md "Comprehensions
(v1)"). Text-level checks only, no kernel runs. A map that is the whole right-hand side of an assignment to a seq is
one write loop over the buffer: the count asserted equal to the buffer's length as an ACSL term (never cexpr's
branch-free C, which Frama-C rejects inside an annotation), each step asserting the body's definedness, the
invariant stating every element written. `s[a..b][i]` in the body is read as `s[a + i]` with the slice's
definedness asserted. The return's length is a map's closed form, so the buffer is EXACT, not capacity-tracked. A
filter, and a comprehension anywhere but an assignment's right-hand side, refuse by name."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import lower_framac  # noqa: E402
import surface  # noqa: E402
import tasks_io  # noqa: E402


def load(name: str) -> dict:
    return tasks_io.load_task(str(HERE / "tasks" / f"{name}.t"))


def framac(name: str) -> str:
    task = load(name)
    return lower_framac.lower(task, task["body"])


def refusal(task: dict) -> str:
    try:
        lower_framac.lower(task, task["body"])
    except NotImplementedError as e:
        return str(e)
    return ""


def test_a_map_is_one_write_loop_over_an_exact_buffer():
    src = framac("doubled")
    assert "requires r_n == s_n;" in src
    assert "loop invariant \\forall integer __t; 0 <= __t < __k ==> r[__t] == (2 * s[__t]);" in src
    assert "r[__k] = (2 * s[__k]);" in src


def test_definedness_per_element_and_the_count_as_an_acsl_term():
    src = framac("diffs")
    assert "/*@ assert 0 <= (((0 + __k) + 1)) && (((0 + __k) + 1)) < s_n; */" in src
    src = framac("every_other")
    count = [l for l in src.splitlines() if "== r_n; */" in l][0]
    assert "t_div" in count and " < 0)" not in count, f"the count is an ACSL term: {count}"


def test_a_slice_index_in_the_body_reads_the_base_buffer():
    src = framac("odd_positions")
    assert "r[__k] = s[(1 + (2 * (0 + __k)))];" in src
    assert "/*@ assert ((2 * (0 + __k)) < (s_n - 1)); */" in src


def test_refusals_by_name():
  # PREDICT T55: evens' spec now states the comprehension too, so the refusal can name it in a spec position
    e = refusal(load("evens"))
    assert "comprehension" in e and "not lowered yet" in e, e
    task = surface.parse("""t 1
task same_len(s: seq) returns (r: int)
  ensures r == len([2 * x for x in s])
{
  r := len(s);
}
""")
    assert "comprehension in a spec position" in refusal(task)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: ok")
