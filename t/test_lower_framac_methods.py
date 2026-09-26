#!/usr/bin/env python3
"""test_lower_framac_methods.py: SPEC.md "Methods (v1)" in the Frama-C
lowering -- the shape of what `lower_framac.lower` emits for the fixtures
in t/methods/ and t/methods_probe/, and the shapes it refuses by name.
Kernel verdicts are measured by run_par; this file runs no prover.

Each method is its own C function `{m}_t` with its own ACSL contract,
emitted before the task's function; a call is a plain C call, which WP
proves through the callee's contract only (ACSL reference manual, "Simple
function contracts"). A seq local set by a method call is a caller-provided
workspace buffer of the enclosing function.

Run: python3 t/test_lower_framac_methods.py   (or pytest)
"""

from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import check_wf                                                # noqa: E402
import harness                                                 # noqa: E402
import lower_framac                                            # noqa: E402
import surface                                                 # noqa: E402


def _load(rel: str) -> dict:
    return surface.parse_file(os.path.join(HERE, rel))


def _real(rel: str) -> str:
    t = _load(rel)
    return lower_framac.lower(t, t["body"])


def _contract_of(src: str, fn: str) -> str:
    """The ACSL block immediately before C function `fn`'s definition."""
    i = src.index(f" {fn}(")
    j = src.rindex("/*@", 0, i)
    return src[j:i]


def _abstains(src: str, reason: str) -> None:
    t = surface.parse(src)
    assert check_wf.check_wf(t) == [], check_wf.check_wf(t)
    try:
        lower_framac.lower(t, t["body"])
    except NotImplementedError as e:
        assert reason in str(e), (reason, str(e))
        return
    raise AssertionError(f"expected an abstain naming {reason!r}")


def test_each_method_is_its_own_function_before_the_task() -> None:
    src = _real("methods/clamp_sum.t")
    assert "int clamp_t(int x, int h) {" in src
    assert "int add_clamped_t(int x, int y, int h) {" in src
    assert (src.index("int clamp_t(") < src.index("int add_clamped_t(")
            < src.index("int clamp_sum_t("))
    c = _contract_of(src, "clamp_t")
    assert "requires (h >= 0);" in c and "assigns \\nothing;" in c
    assert "ensures ((x < 0) ==> (\\result == 0));" in c
    a = _contract_of(src, "add_clamped_t")
    assert "ensures ((0 <= \\result) && (\\result <= h));" in a


def test_call_is_a_c_call_never_the_callee_body() -> None:
    src = _real("methods/max3.t")
    body = src[src.index("int max3_t("):]
    assert "int m1 = max2_t(a, b);" in body
    assert "r = max2_t(m1, c);" in body
    assert "x >= y" not in body                    # not inlined
    src = _real("methods/clamp_sum.t")
    assert "int u = clamp_t(x, h);" in src
    assert "s = clamp_t((u + y), h);" in src
    assert "r = add_clamped_t(a, b, hi);" in src


def test_opaque_callee_is_not_inlined() -> None:
    src = _real("methods_probe/opaque_callee.t")
    task = src[src.index("int opaque_callee_t("):]
    assert "r = inc_t(x);" in task and "+ 1" not in task
    assert "ensures (\\result > a);" in _contract_of(src, "inc_t")


def test_call_inside_a_loop_keeps_its_definedness_assert() -> None:
    src = _real("methods/count_pos.t")
    task = src[src.index("int count_pos_t("):]
    loop = task[task.index("while"):]
    assert "/*@ assert 0 <= (i) && (i) < s_n; */" in loop
    assert "r = step_t(r, s[i]);" in loop
    assert "requires (k >= 0);" in _contract_of(src, "step_t")


def test_seq_result_goes_to_a_workspace_and_the_return_buffer() -> None:
    src = _real("methods/rev_twice.t")
    assert "int rev_t(int *u, int u_n, int *v, int v_n) {" in src
    rc = _contract_of(src, "rev_t")
    assert "requires v_n == u_n;" in rc and "assigns v[0 .. v_n - 1];" in rc
    assert ("int rev_twice_t(int *s, int s_n, int *r, int r_n, "
            "int *w, int w_n) {") in src
    tc = _contract_of(src, "rev_twice_t")
    assert "requires \\valid(w + (0 .. w_n - 1));" in tc
    assert "requires w_n == s_n;" in tc
    assert "requires \\separated(r + (0 .. r_n - 1), w + (0 .. w_n - 1));" in tc
    assert "assigns r[0 .. r_n - 1], w[0 .. w_n - 1];" in tc
    task = src[src.index("int rev_twice_t("):]
    # the workspace's length is w_n only because the callee's ensures says
    # so: an assert WP must prove, never an assumption
    assert re.search(r"int (__mlen\d+) = rev_t\(s, s_n, w, w_n\);\n"
                     r"\s*/\*@ assert \1 == w_n; \*/", task), task
    assert "r_len = rev_t(w, w_n, r, r_n);" in task


def test_twin_certificate_replays_the_callee_by_value() -> None:
    t = _load("methods/max3.t")
    body, _op, w = harness.twin_for(t)
    src = lower_framac.lower(t, body, w)
    cert = src[src.index("void t_certificate(void)"):]
    assert "t_cert_call0_x = b;" in cert and "m1 = t_cert_call0_m;" in cert
    assert "max2_t(" not in cert
    # the real functions themselves are the same as the real lowering's
    real = _real("methods/max3.t")
    assert src[:src.index("int max3_t(")] == real[:real.index("int max3_t(")]


def test_recursive_method_carries_its_decreases() -> None:
    src = ("t 1 task f(x: int) returns (r: int) requires x >= 0 ensures r >= 1\n"
           "method p(n: int) returns (b: int) requires n >= 0 ensures b >= 1 "
           "decreases n\n{ if n == 0 { b := 1 } else { var c: int := p(n - 1); "
           "b := 2 * c } }\n{ r := p(x) }")
    t = surface.parse(src)
    out = lower_framac.lower(t, t["body"])
    assert "decreases (n);" in _contract_of(out, "p_t")
    assert "int c = p_t((n - 1));" in out


HEAD = "t 1 task f(s: seq) returns (r: int) ensures true\n"
REV = ("method rev(u: seq) returns (v: seq) ensures len(v) == len(u)\n"
       "{ v := seq(len(u), 0); var i: int := 0;\n"
       "  while i < len(u) invariant len(v) == len(u) invariant 0 <= i and i <= len(u)"
       " decreases len(u) - i { v := v[i := u[i]]; i := i + 1; } }\n")


def test_abstain_seq_local_from_a_call_inside_a_loop() -> None:
    _abstains(HEAD + REV + "{ r := 0; var i: int := 0;\n"
              "  while i < 2 invariant 0 <= i and i <= 2 decreases 2 - i\n"
              "  { var w: seq := rev(s); i := i + 1; } }",
              "inside a loop")


def test_abstain_workspace_reassigned() -> None:
    _abstains(HEAD + REV + "{ var w: seq := rev(s); w := rev(s); r := 0; }",
              "is assigned again")


def test_abstain_workspace_size_not_from_params() -> None:
    mk = ("method mk(n: int) returns (v: seq) requires n >= 0 ensures len(v) == n\n"
          "{ v := seq(n, 0); }\n")
    _abstains(HEAD + mk + "{ var k: int := len(s); var w: seq := mk(k); r := 0; }",
              "not a function of the params")


def test_abstain_exact_seq_callee_without_a_length_ensures() -> None:
    cp = "method cp(u: seq) returns (v: seq) ensures true { v := seq(len(u), 0); }\n"
    _abstains(HEAD + cp + "{ var w: seq := cp(s); r := 0; }",
              "does not state its result's length")


def test_abstain_callee_that_needs_a_workspace() -> None:
    twice = ("method twice(u: seq) returns (z: int) ensures true\n"
             "{ var w: seq := rev(u); z := 0; }\n")
    _abstains(HEAD + REV + twice + "{ r := twice(s); }",
              "itself needs a workspace buffer")


def test_abstain_pair_typed_method() -> None:
    _abstains("t 1 task f(x: int) returns (r: int) ensures true\n"
              "method g(a: (int, int)) returns (b: int) ensures true { b := a.0 }\n"
              "{ r := g((x, x)) }",
              "is not implemented for methods")


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"{fn.__name__}: pass")
    print(f"test_lower_framac_methods: {len(tests)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
