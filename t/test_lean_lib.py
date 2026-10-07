#!/usr/bin/env python3
"""test_lean_lib.py: the library (v1), the reductions any/all/max/min of one argument, and fold/max_by/min_by in the
Lean lowering (PREDICT T9, 2026-10-06; internal/RESEARCH-2026-10-06-landscape.md decision D1). Text-level checks only,
no kernel runs: the prelude is emitted only for what a task uses, every definition is structurally recursive (no
`termination_by`, so the kernel's `decide` evaluates ground values), grind is handed the lemmas the call needs, and the
refusals are by name (sets, the string library's second wave, sort_by)."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import lower_lean  # noqa: E402
import surface  # noqa: E402
import tasks_io  # noqa: E402
import tshape  # noqa: E402

CHECKS = 0


def ok(cond, what):
    global CHECKS
    CHECKS += 1
    if not cond:
        print("FAIL:", what)
        sys.exit(1)


def lean(name: str) -> str:
    task = tasks_io.load_task(str(HERE / "tasks" / f"{name}.t"))
    return lower_lean.lower(task, task["body"])


def refusal(name: str) -> str:
    task = tasks_io.load_task(str(HERE / "tasks" / f"{name}.t"))
    try:
        lower_lean.lower(task, task["body"])
    except NotImplementedError as e:
        return str(e)
    return ""


def test_prelude_only_what_is_used():
    src = lean("clamp")
    ok("def t_min" in src and "def t_max" in src and "def t_sort" not in src and "t_isqrt" not in src,
       "clamp's file carries min and max only")
    ok("grind [t_max, t_min]" in src, "grind is handed the two definitions")
    src = lean("sort_it")
    ok("def t_ins" in src and "theorem t_sort_le" in src and "#print axioms t_sort_le" in src,
       "sort brings the insertion sort and its lemmas, each audited")


def test_definitions_are_structural():
    for name in ("cube", "root_floor", "sort_it", "largest", "sum_tail", "weighted_sum", "longest_row"):
        src = lean(name)
        prelude = src[:src.find(f"def {name}_t")]
        ok("termination_by" not in prelude, f"{name}: no well-founded definition in the library prelude")


def test_grind_hints_and_patterns():
    ok("grind_pattern t_isqrt_spec => t_isqrt n" in lean("root_floor"), "isqrt's bounds reach grind by a pattern")
    def proof(name):
        return lean(name).split(f"theorem {name}_t_spec")[1].split("#print axioms")[0]
    ok("t_sum_append" not in proof("sum_one"),
       "the append lemma is not handed to grind without a concatenation (it timed sum_one's twin out)")
    ok("t_sum_append" in proof("sum_tail"), "nor withheld where `+` concatenates")
    ws = lean("weighted_sum")
    ok("def t_fold1" in ws and "theorem t_fold1_step" in ws and "t_fold1 s (0 : Int) w (s).length" in ws and "t_fold1 s (0 : Int) w (i).toNat" in ws,
       "fold in prefix form, the whole sequence's call with its length")
    lr = lean("longest_row")
    ok("def t_maxbyi1" in lr and "theorem t_maxby1_mem" in lr and "theorem t_maxby1_bound" in lr,
       "max_by through the chosen index, with membership and the key bound")
    ap = lean("all_positive")
    ok("List.all s" in ap and "t_all_iff" in ap, "all over a comprehension is List.all over a predicate")


def test_refusals_by_name():
    # since PREDICT T29 (2026-10-07) Lean carries finite sets of ints, toset included (ExtTreeSet.ofList)
    ok(refusal("members_upto") == "", "toset is lowered since T29: %r" % refusal("members_upto"))
    ok("second wave" in refusal("pad_right_len") or "not lowered yet" in refusal("pad_right_len"),
       "the second string wave stays refused: %r" % refusal("pad_right_len"))
    task = surface.parse("t 1\ntask f(s: seq) returns (r: seq)\n  ensures len(r) == len(s)\n{ r := sort_by(s, x => x); }\n")
    try:
        lower_lean.lower(task, task["body"])
        ok(False, "sort_by must be refused in Lean")
    except NotImplementedError as e:
        ok("sort_by" in str(e), "sort_by is refused by name: %s" % e)


def test_shared_rules():
    ok("in" not in lower_lean._SET_OPS_T, "membership in a seq is not read as a set use")
    task = surface.parse("t 1\ntask f(s: seq) returns (r: bool)\n  ensures true\n{ r := all([x > 0 for x in s]); }\n")
    ok(tshape.has_comprehension(task, task["body"]) is True, "the comprehension is seen by default")
    ok(tshape.has_comprehension(task, task["body"], under_reduction_ok=True) is False,
       "a comprehension directly under all is carried by a kernel that says so")
    task = surface.parse("t 1\ntask f(s: seq) returns (r: bool)\n  ensures true\n"
                         "{ var u: seq := [y + 1 for y in s]; r := all([x > 0 for x in u]); }\n")
    ok(tshape.has_comprehension(task, task["body"], under_reduction_ok=True) is True,
       "a comprehension anywhere else is still seen")


def test_comprehensions():
    # SPEC.md "Comprehensions (v1)" in Lean (PREDICT T12)
    src = lean("doubled")
    ok("def t_comp1 (t_s : List Int) : Nat → List Int" in src and "theorem t_comp1_get" in src
       and "(t_comp1 s (s).length)" in src, "a map over a seq: prefix form, the whole seq by its length")
    src = lean("squares")
    ok("def t_compr1 (t_a : Int) : Nat → List Int" in src and "theorem t_compr1_get0" in src,
       "a range: its own function and the zero-offset element corollary")
    src = lean("evens")
    ok("theorem t_comp1_all" in src and "theorem t_comp1_length" in src, "a filter: its length bound and its property")
    src = lean("diffs")
    ok("∀ (t_dk" in src or "(∀ (t_dk" in src, "a partial body owes its definedness at every index of the range")
    prelude = src[:src.find("def diffs_t")]
    ok("termination_by" not in prelude, "the comprehension's function is structurally recursive")
    # PREDICT T44: an early exit is rewritten away (tshape.desugar_exits), so the filter's task lowers
    ok(refusal("count_evens_skip") == "", "a comprehension task with an early exit lowers: %r" % refusal("count_evens_skip"))


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: ok")
    print(f"{CHECKS} checks")
