"""Plain-python tests for mbpp_dfy.py's `strings` parameter (SPEC.md
"Strings as sequences of code points (v1)"; the pool's version 2).

The one thing worth a regression test here is the one thing the task asked
for twice: `strings=False` (the default) must stay byte-for-byte what
`parse_assertion`/`_literal` always returned, and `strings=True` must turn a
Python string literal into a t character (a length-1 string) or a t `seq`
of Unicode code points (any other length), handling escapes and non-ASCII
by code point, not by byte, exactly as SPEC.md's char/string sugar does at
the notation level (`'a'` is `{"int": 97}`, `"abc"` is the seq literal).

No corpus, no network, no model. Standard library plus mbpp_dfy itself.

Run as: cd <repo>/t && python3 test_mbpp_dfy.py
"""
from __future__ import annotations

import sys
import traceback

import mbpp_dfy


UNIT_TESTS = []


def test(fn):
    UNIT_TESTS.append(fn)
    return fn


# --------------------------------------------------- strings=False (v1) --

@test
def test_v1_default_refuses_string_arg():
    r = mbpp_dfy.parse_assertion('assert f("abc") == 1')
    assert r == {"ok": False, "why": "arg:str"}, r


@test
def test_v1_default_refuses_string_expected():
    r = mbpp_dfy.parse_assertion('assert f(1) == "abc"')
    assert r == {"ok": False, "why": "expected:str"}, r


@test
def test_v1_default_refuses_single_char_too():
    # A length-1 Python string is still a `str` node; strings=False must not
    # special-case it just because strings=True would treat it as a char.
    r = mbpp_dfy.parse_assertion('assert f("a") == True')
    assert r == {"ok": False, "why": "arg:str"}, r


@test
def test_v1_default_unchanged_for_every_other_kind():
    # The kinds strings=False already handled must be byte-for-byte
    # unchanged: int, bool, negative int, seq of int, tuple, dict, set, call.
    cases = [
        ('assert f(3) == 4', {"ok": True, "fn": "f", "args": [("int", 3)],
                               "expected": ("int", 4)}),
        ('assert f(True) == False', {"ok": True, "fn": "f",
                                      "args": [("bool", True)],
                                      "expected": ("bool", False)}),
        ('assert f(-3) == 4', {"ok": True, "fn": "f", "args": [("int", -3)],
                                "expected": ("int", 4)}),
        ('assert f([1, 2, 3]) == 4', {"ok": True, "fn": "f",
                                       "args": [("seq", [1, 2, 3])],
                                       "expected": ("int", 4)}),
        ('assert f((1, 2)) == 4', {"ok": False, "why": "arg:tuple"}),
        ('assert f({1: 2}) == 4', {"ok": False, "why": "arg:dict"}),
        ('assert f({1, 2}) == 4', {"ok": False, "why": "arg:set"}),
        ('assert f(g(1)) == 4', {"ok": False, "why": "arg:call:g"}),
        ('assert not f(1)', {"ok": True, "fn": "f", "args": [("int", 1)],
                              "expected": ("bool", False)}),
    ]
    for src, want in cases:
        got = mbpp_dfy.parse_assertion(src)
        assert got == want, (src, got, want)


# ---------------------------------------------------- strings=True (v2) --

@test
def test_v2_single_char_is_an_int_codepoint():
    r = mbpp_dfy.parse_assertion('assert f("a") == True', strings=True)
    assert r == {"ok": True, "fn": "f", "args": [("int", 97)],
                 "expected": ("bool", True)}, r


@test
def test_v2_multichar_string_is_a_seq_of_codepoints():
    r = mbpp_dfy.parse_assertion('assert f("abc") == "xy"', strings=True)
    assert r == {"ok": True, "fn": "f", "args": [("seq", [97, 98, 99])],
                 "expected": ("seq", [120, 121])}, r


@test
def test_v2_empty_string_is_the_empty_seq():
    r = mbpp_dfy.parse_assertion('assert f("") == 0', strings=True)
    assert r == {"ok": True, "fn": "f", "args": [("seq", [])],
                 "expected": ("int", 0)}, r


@test
def test_v2_escapes_resolve_to_codepoints_not_source_bytes():
    # \n \t are single characters once ast.parse has resolved them; the
    # escape resolution happens before _literal ever sees the string.
    r = mbpp_dfy.parse_assertion(r'assert f("\n\tX") == 1', strings=True)
    assert r == {"ok": True, "fn": "f",
                 "args": [("seq", [10, 9, 88])],
                 "expected": ("int", 1)}, r
    # a single escaped character is a t CHARACTER (int), same rule as any
    # other length-1 string.
    r2 = mbpp_dfy.parse_assertion(r'assert f("\n") == 1', strings=True)
    assert r2 == {"ok": True, "fn": "f", "args": [("int", 10)],
                  "expected": ("int", 1)}, r2


@test
def test_v2_non_ascii_is_code_points_not_bytes():
    # 'e' + combining accent would be two code points; a precomposed e-acute
    # (U+00E9) is one. UTF-8 bytes for it are 0xC3 0xA9 (195, 169); its own
    # code point is 233. A wrong (byte-wise) implementation would produce
    # the former; SPEC.md requires the latter.
    r = mbpp_dfy.parse_assertion('assert f("café") == 1', strings=True)
    assert r == {"ok": True, "fn": "f",
                 "args": [("seq", [99, 97, 102, 233])],
                 "expected": ("int", 1)}, r


@test
def test_v2_astral_codepoint_beyond_the_bmp():
    # U+1F600 GRINNING FACE. A UTF-16-code-unit view (surrogate pairs) would
    # split this into two units; a t/Python code-point view keeps it as one
    # int, and it is one Python str character.
    r = mbpp_dfy.parse_assertion('assert f("\U0001F600") == 1', strings=True)
    assert r == {"ok": True, "fn": "f", "args": [("int", 0x1F600)],
                 "expected": ("int", 1)}, r


@test
def test_v2_list_of_single_char_strings_is_a_plain_seq():
    # A Python list of one-character strings ["a", "b", "a"] is exactly how
    # some MBPP tests spell a string as a list of chars; since each element
    # is a t character (an int), the whole list is a legitimate seq<int>,
    # not a nested seq.
    r = mbpp_dfy.parse_assertion('assert f(["a", "b", "a"]) == 1',
                                  strings=True)
    assert r == {"ok": True, "fn": "f", "args": [("seq", [97, 98, 97])],
                 "expected": ("int", 1)}, r


@test
def test_v2_list_of_multichar_strings_is_refused_as_nested():
    # Each element is itself a seq (multi-char), so the outer list is a seq
    # of seqs: still not in t (SPEC.md: "What is still not in v1: nested
    # seqs"), named with the existing "seq-of-" convention, not invented.
    r = mbpp_dfy.parse_assertion('assert f(["ab", "cd"]) == 1',
                                  strings=True)
    assert r == {"ok": False, "why": "arg:seq-of-seq"}, r


@test
def test_v2_mixed_length_list_is_refused_as_nested_too():
    r = mbpp_dfy.parse_assertion('assert f(["a", "bc"]) == 1',
                                  strings=True)
    assert r == {"ok": False, "why": "arg:seq-of-seq"}, r


@test
def test_v2_tuple_of_strings_still_refused_as_tuple():
    # Tuples are refused before their elements are ever inspected, in both
    # versions; strings=True must not change that.
    r = mbpp_dfy.parse_assertion('assert f(("a", "b")) == 1', strings=True)
    assert r == {"ok": False, "why": "arg:tuple"}, r


@test
def test_v2_still_refuses_everything_strings_never_touched():
    cases = [
        ('assert f(1.5) == 1', {"ok": False, "why": "arg:float"}),
        ('assert f({1: 2}) == 1', {"ok": False, "why": "arg:dict"}),
        ('assert f({1, 2}) == 1', {"ok": False, "why": "arg:set"}),
        ('assert f(g(1)) == 1', {"ok": False, "why": "arg:call:g"}),
    ]
    for src, want in cases:
        got = mbpp_dfy.parse_assertion(src, strings=True)
        assert got == want, (src, got, want)


@test
def test_v1_and_v2_agree_when_there_is_no_string_anywhere():
    # strings only changes the str branch of _literal; every assertion that
    # never mentions a Python string must parse identically either way.
    srcs = [
        'assert f(1, 2) == 3',
        'assert f([1, 2], -3) == [4, 5]',
        'assert f(True) == False',
        'assert f((1, 2)) == 1',
        'assert f({1: 2}) == 1',
    ]
    for src in srcs:
        a = mbpp_dfy.parse_assertion(src, strings=False)
        b = mbpp_dfy.parse_assertion(src, strings=True)
        assert a == b, (src, a, b)


# --------------------------------------------- pool v1 regression guard --

@test
def test_pool_v1_is_still_368():
    # The frozen baseline this whole task must not disturb (SPEC-EXPERIMENT-
    # pool-v2.md; spec_experiment.pool_report()). Imported lazily: this is
    # the one test that touches nl/'s data files, which test_mbpp_dfy.py's
    # other tests do not need.
    import spec_experiment as se
    rep = se.pool_report("v1")
    assert rep["problems"] == 974, rep
    assert rep["in_pool"] == 368, rep


def run() -> None:
    failures = 0
    for fn in UNIT_TESTS:
        try:
            fn()
            print(f"{fn.__name__}: pass")
        except AssertionError as e:
            failures += 1
            print(f"{fn.__name__}: FAILED: {e}")
        except Exception as e:                                  # noqa: BLE001
            failures += 1
            traceback.print_exc()
            print(f"{fn.__name__}: FAILED (exception): {e}")
    if failures:
        raise AssertionError(f"{failures} of {len(UNIT_TESTS)} test(s) failed")
    print(f"test_mbpp_dfy: all {len(UNIT_TESTS)} checks passed")


if __name__ == "__main__":
    try:
        run()
    except AssertionError as e:
        print(f"FAILED: {e}")
        sys.exit(1)
    sys.exit(0)
