#!/usr/bin/env python3
"""test_rocq_lib.py: the library (v1) and the reductions any/all/max/min of one argument in the Rocq lowering (PREDICT
T10, 2026-10-06; internal/RESEARCH-2026-10-06-landscape.md decision D1). Text-level checks only, no kernel runs: the
prelude carries only what a task uses, membership in a seq is the existential over indices with its bridge stated as a
fact, the facts the proof engine needs are posed before it runs, the certificate reads a witness seq as the
interpreter's tuple, and the refusals are by name."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import harness  # noqa: E402
import lower_rocq  # noqa: E402
import rocq_lib  # noqa: E402
import tasks_io  # noqa: E402

CHECKS = 0


def ok(cond, what):
    global CHECKS
    CHECKS += 1
    if not cond:
        print("FAIL:", what)
        sys.exit(1)


def rocq(name: str) -> str:
    task = tasks_io.load_task(str(HERE / "tasks" / f"{name}.t"))
    return lower_rocq.lower(task, task["body"])


def refusal(name: str) -> str:
    task = tasks_io.load_task(str(HERE / "tasks" / f"{name}.t"))
    try:
        lower_rocq.lower(task, task["body"])
    except NotImplementedError as e:
        return str(e)
    return ""


def test_prelude_only_what_is_used():
    src = rocq("clamp")
    ok("(Z.max lo (Z.min hi x))" in src and "t_sum_nat" not in src and "t_isort" not in src,
       "clamp is the stdlib's Z.min/Z.max, with no library prelude")
    src = rocq("sort_it")
    ok("Fixpoint t_isort" in src and "Lemma t_sortf_le" in src and "(t_sortf_le s s_len)" in src,
       "sort brings the insertion sort and poses its order lemma before the engine")
    ok(rocq_lib.prelude(set()) == "", "no piece, no prelude")


def test_membership_and_facts():
    src = rocq("has_elem")
    ok("(exists t_k : Z, 0 <= t_k < s_len /\\ s t_k = x)" in src, "membership in a seq is the existential")
    ok("t_memb_spec s s_len x" in src and "destruct (t_memb s s_len x); [t_dis | idtac]" in src,
       "the bridge is posed, rewritten into the goal and split")
    ok("S.In" not in src.split("Theorem has_elem_t_spec")[1], "no set membership in a seq task")
    ok("in" not in lower_rocq._SET_OPS_R, "a seq's `in` is not a set use")
    ok("(Z.sqrt_spec n ltac:(lia))" in rocq("root_floor"), "isqrt's bounds are posed")
    ok("(Z.gcd_nonneg a b)" in rocq("gcd_of"), "gcd's sign is posed")
    st = rocq("sum_tail")
    ok("t_sum_app s (t_upd (t_fill 0) 0 x) s_len 1" in st and "t_sum_one (t_upd (t_fill 0) 0 x)" in st,
       "a sum over a concatenation poses the append lemma and the one-element sum")
    hn = rocq("has_negative")
    ok("t_any_spec s_len" in hn and "setoid_rewrite" in hn, "any's bridge is carried to the Prop under the binder")


def test_certificates_read_the_interpreters_values():
    task = tasks_io.load_task(str(HERE / "tasks" / "sum_tail.t"))
    twin, _got, w = harness.twin_for(task)
    cert = lower_rocq._try_cert_v1(task, twin, w)
    ok(cert is not None, "sum_tail's twin certificate is built (a witness seq read as a list made `s + [x]` raise)")


def test_refusals_by_name():
    for name, word in (("members_upto", "toset"), ("weighted_sum", "fold"), ("longest_row", "max_by")):
        r = refusal(name)
        ok(word in r and "not lowered yet" in r, f"{name} refuses by name: {r!r}")
    ok("not lowered yet" in refusal("pad_right_len"), "the second string wave stays refused")


def test_seq_equality_has_one_orientation():
    # PREDICT T33: the code's `u == b` and the contract's `b == rev(a)` state one term, so the closer's congruence
    # between the contract's forall and the code's negated fact can close
    src = rocq("rev_equal")
    ok("&& t_seq_eqb a_len (t_rev a a_len) b)" in src, "the code's test, rev first")
    ok("(a_len = b_len /\\ (forall t_k : Z, 0 <= t_k < a_len -> (t_rev a a_len) t_k = b t_k))" in src,
       "and the contract's statement in the same order")
    ok(lower_rocq._seq_eq_order("b", "b_len", "(t_rev a a_len)", "a_len") == ("(t_rev a a_len)", "a_len", "b", "b_len"),
       "the operand whose function sorts first leads")
    ok(lower_rocq._seq_eq_order("a", "n", "b", "m") == ("a", "n", "b", "m"), "an ordered pair is left alone")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: ok")
    print(f"{CHECKS} checks")
