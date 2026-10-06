"""Plain-python tests for the string library core (SPEC.md "The string
library (v1)", 2026-09-11): interp.py's 17 members against Python's own str
methods, and surface.py's notation round trip for every member form.

No corpus, no network, no model. Standard library plus interp and surface.

PARITY (2026-09-11, measured): 2,000 random code-point seqs per member,
drawn from ASCII (0-127; SPEC.md: "the corpus is ASCII"), evaluated through
`interp.ev` (so the op dispatch is exercised, not just the bare `_str_*`
helper) and compared against calling Python's real str method on the
`chr()`-joined string, converted back with `ord`. ASCII is the domain on
purpose: `lower`/`upper`/`isdigit`/`isalpha`/`isupper`/`islower` are
SPEC.md's own ASCII-only tables (65-90, 97-122, 48-57), not Python's
Unicode-aware casing/classification, which does MORE than SPEC.md
describes outside ASCII (e.g. Python's `'É'.lower()` gives an accented
lowercase letter no ASCII table has); inside ASCII the two coincide
exactly, so this is real parity evidence and not a test that quietly
narrows its own domain to dodge the discrepancy. `interp.py`'s own members
are int-tuple transcriptions (never `chr()`) so they stay total on any
int, a fact orthogonal to this file's own choice to fuzz ASCII: see
interp.py's module docstring.

Run as: cd <repo>/t && python3 test_strlib.py
"""
from __future__ import annotations

import random
import sys
import traceback

import interp
import surface

UNIT_TESTS = []


def test(fn):
    UNIT_TESTS.append(fn)
    return fn


# --------------------------------------------------------------- parity --

ST = interp.St
FUNS: dict = {}


def ev(op, *arg_values):
    """Evaluate {"op": op, "args": [...]} over `arg_values`, each an int, a
    seq (python tuple of ints), or a seq<seq> (a tuple of seq tuples), by
    building the matching literal AST node."""
    def node(v):
        if isinstance(v, tuple):
            return {"op": "seq", "args": [node(x) for x in v]}
        return {"int": v}
    e = {"op": op, "args": [node(v) for v in arg_values]}
    return interp.ev(e, {}, FUNS, ST())


def rand_seq(rng, n, alpha):
    return tuple(rng.choice(alpha) for _ in range(n))


def rand_len(rng):
    return rng.randint(0, 10)


N = 2000
ASCII = list(range(0, 128))


def _check(rng, name, want_fn, call_fn):
    for _ in range(N):
        args = call_fn(rng)
        got = args[0]
        want = args[1]
        assert got == want, (name, args)


def _run_parity(name, arity, build):
    """`build(rng)` returns (got, want) for one random sample; asserted N
    times. Factored so every member's test is one line of what differs."""
    rng = random.Random(f"strlib:{name}")
    for _ in range(N):
        got, want = build(rng)
        assert got == want, (name, got, want)


def _s(rng):
    return rand_seq(rng, rand_len(rng), ASCII)


def _to_str(s):
    return "".join(chr(c) for c in s)


def _from_str(st):
    return tuple(ord(c) for c in st)


@test
def test_split_no_sep():
    _run_parity("split()", 1, lambda rng: (
        ev("split", (s := _s(rng))),
        tuple(_from_str(w) for w in _to_str(s).split())))


@test
def test_split_sep():
    def one(rng):
        s = _s(rng)
        c = rng.choice(ASCII)
        got = ev("split", s, c)
        want = tuple(_from_str(w) for w in _to_str(s).split(chr(c)))
        return got, want
    _run_parity("split(s,c)", 2, one)


@test
def test_join():
    def one(rng):
        rows = tuple(_s(rng) for _ in range(rng.randint(0, 5)))
        sep = _s(rng)
        got = ev("join", rows, sep)
        want = _from_str(_to_str(sep).join(_to_str(r) for r in rows))
        return got, want
    _run_parity("join", 2, one)


@test
def test_tostr():
    rng = random.Random("strlib:tostr")
    for _ in range(N):
        n = rng.randint(-10 ** 9, 10 ** 9)
        got = ev("tostr", n)
        want = _from_str(str(n))
        assert got == want, (n, got, want)


@test
def test_count():
    def one(rng):
        s, t = _s(rng), _s(rng)
        return ev("count", s, t), _to_str(s).count(_to_str(t))
    _run_parity("count", 2, one)


@test
def test_find():
    def one(rng):
        s, t = _s(rng), _s(rng)
        return ev("find", s, t), _to_str(s).find(_to_str(t))
    _run_parity("find", 2, one)


@test
def test_strip():
    _run_parity("strip", 1, lambda rng: (
        ev("strip", (s := _s(rng))), _from_str(_to_str(s).strip())))


@test
def test_lstrip():
    _run_parity("lstrip", 1, lambda rng: (
        ev("lstrip", (s := _s(rng))), _from_str(_to_str(s).lstrip())))


@test
def test_rstrip():
    _run_parity("rstrip", 1, lambda rng: (
        ev("rstrip", (s := _s(rng))), _from_str(_to_str(s).rstrip())))


@test
def test_replace():
    def one(rng):
        s, t, u = _s(rng), _s(rng), _s(rng)
        got = ev("replace", s, t, u)
        want = _from_str(_to_str(s).replace(_to_str(t), _to_str(u)))
        return got, want
    _run_parity("replace", 3, one)


@test
def test_lower():
    _run_parity("lower", 1, lambda rng: (
        ev("lower", (s := _s(rng))), _from_str(_to_str(s).lower())))


@test
def test_upper():
    _run_parity("upper", 1, lambda rng: (
        ev("upper", (s := _s(rng))), _from_str(_to_str(s).upper())))


@test
def test_isdigit():
    _run_parity("isdigit", 1, lambda rng: (
        ev("isdigit", (s := _s(rng))), _to_str(s).isdigit()))


@test
def test_isalpha():
    _run_parity("isalpha", 1, lambda rng: (
        ev("isalpha", (s := _s(rng))), _to_str(s).isalpha()))


@test
def test_isupper():
    _run_parity("isupper", 1, lambda rng: (
        ev("isupper", (s := _s(rng))), _to_str(s).isupper()))


@test
def test_islower():
    _run_parity("islower", 1, lambda rng: (
        ev("islower", (s := _s(rng))), _to_str(s).islower()))


@test
def test_startswith():
    def one(rng):
        s, t = _s(rng), _s(rng)
        return ev("startswith", s, t), _to_str(s).startswith(_to_str(t))
    _run_parity("startswith", 2, one)


@test
def test_endswith():
    def one(rng):
        s, t = _s(rng), _s(rng)
        return ev("endswith", s, t), _to_str(s).endswith(_to_str(t))
    _run_parity("endswith", 2, one)


@test
def test_string_lib_properties():
    # SPEC.md's own stated identities, spot-checked over the same domain
    # rather than left to the member-by-member tests to imply.
    rng = random.Random("strlib:properties")
    for _ in range(500):
        s = _s(rng)
        c = rng.choice(ASCII)
        # len(split(s, c)) == count(s, [c]) + 1
        assert (ev("len", ev("split", s, c))
               == ev("count", s, (c,)) + 1)
        # join(split(s, c), [c]) == s
        assert ev("join", ev("split", s, c), (c,)) == s
        # count(s, []) == len(s) + 1
        assert ev("count", s, ()) == len(s) + 1
        # find(s, []) == 0
        assert ev("find", s, ()) == 0


# ------------------------------------------------ the second wave (v2) --
# SPEC.md "The string library (v2)" (2026-10-07): the same parity, member by member, against Python's own.

def _t1(rng):
    return rand_seq(rng, rng.randint(1, 2), ASCII)


@test
def test_split_str():
    def one(rng):
        s, u = _s(rng), _t1(rng)
        return ev("split", s, u), tuple(_from_str(w) for w in _to_str(s).split(_to_str(u)))
    _run_parity("split(s, u)", 2, one)


@test
def test_strip_chars():
    for op, py in (("strip", str.strip), ("lstrip", str.lstrip), ("rstrip", str.rstrip)):
        def one(rng, op=op, py=py):
            s, u = _s(rng), rand_seq(rng, rng.randint(0, 3), ASCII)
            return ev(op, s, u), _from_str(py(_to_str(s), _to_str(u)))
        _run_parity(op + "(s, u)", 2, one)


@test
def test_index_rfind():
    def one(rng):
        s, u = _s(rng), _t1(rng)
        got_r = ev("rfind", s, u)
        want_r = _to_str(s).rfind(_to_str(u))
        if want_r >= 0:
            assert ev("index", s, u) == _to_str(s).index(_to_str(u))
        else:
            try:
                ev("index", s, u)
                raise AssertionError("index of an absent part must be undefined")
            except interp.Undef:
                pass
        return got_r, want_r
    _run_parity("rfind/index", 2, one)


@test
def test_padding():
    def one(rng):
        s, w, f = _s(rng), rng.randint(0, 14), rng.choice(ASCII[33:127])
        got = (ev("zfill", s, w), ev("center", s, w), ev("ljust", s, w, f), ev("rjust", s, w, f), ev("center", s, w, f))
        st = _to_str(s)
        want = (_from_str(st.zfill(w)), _from_str(st.center(w)), _from_str(st.ljust(w, chr(f))),
                _from_str(st.rjust(w, chr(f))), _from_str(st.center(w, chr(f))))
        return got, want
    _run_parity("zfill/center/ljust/rjust", 2, one)


@test
def test_case_members():
    def one(rng):
        s = _s(rng)
        st = _to_str(s)
        return ((ev("capitalize", s), ev("swapcase", s), ev("title", s)),
                (_from_str(st.capitalize()), _from_str(st.swapcase()), _from_str(st.title())))
    _run_parity("capitalize/swapcase/title", 1, one)


@test
def test_isspace_isalnum_isint():
    import re
    def one(rng):
        s = rand_seq(rng, rand_len(rng), rng.choice([ASCII, list(range(48, 58)) + [43, 45], [9, 10, 32, 28]]))
        st = _to_str(s)
        return ((ev("isspace", s), ev("isalnum", s), ev("isint", s)),
                (st.isspace(), st.isalnum(), bool(re.fullmatch(r"[+-]?[0-9]+", st))))
    _run_parity("isspace/isalnum/isint", 1, one)


@test
def test_toint():
    def one(rng):
        n = rng.randint(-10 ** 6, 10 ** 6)
        s = _from_str((rng.choice(["", "+"]) if n >= 0 else "") + str(n))
        return ev("toint", s), int(_to_str(s))
    _run_parity("toint", 1, one)
    try:
        ev("toint", _from_str("12a"))
        raise AssertionError("toint of a non-integer must be undefined")
    except interp.Undef:
        pass


@test
def test_splitlines_partition():
    LB = [10, 13, 11, 12, 28, 29, 30, 133, 8232, 8233]
    def one(rng):
        s = rand_seq(rng, rand_len(rng), ASCII[32:127] + LB * 4)
        u = _t1(rng)
        st = _to_str(s)
        got_p = ev("partition", s, u)
        return ((ev("splitlines", s), tuple(got_p.items)),
                (tuple(_from_str(x) for x in st.splitlines()), tuple(_from_str(x) for x in st.partition(_to_str(u)))))
    _run_parity("splitlines/partition", 1, one)


@test
def test_padding_is_capped():
    # 2026-10-06: a width past MAX_SEQ decides nothing (Budget), as for fill and join; uncapped, the twin search's
    # width 2**31 built a 2-billion-element tuple and the OOM killer took the session down
    for op in ("zfill", "center", "ljust", "rjust"):
        try:
            ev(op, (49,), interp.MAX_SEQ + 1)
            raise AssertionError(op + " past MAX_SEQ must hit the length cap")
        except interp.Budget:
            pass


# --------------------------------------------------- notation round trip --

# SPEC.md "The string library": every member form, one line each (split at
# both its arities). Round-tripped through surface.parse_expr/pexpr.
NOTATION_FORMS = [
    # SPEC.md "The string library (v2)" (2026-10-07)
    "s.split(u)", "s.strip(u)", "s.lstrip(u)", "s.rstrip(u)", "s.index(u)", "s.rfind(u)", "s.zfill(w)",
    "s.center(w)", "s.center(w, c)", "s.ljust(w)", "s.rjust(w, c)", "s.capitalize()", "s.swapcase()", "s.title()",
    "s.isspace()", "s.isalnum()", "s.splitlines()", "s.partition(u)", "isint(s)", "toint(s)",
    "s.split()",
    "s.split(c)",
    "sep.join(rows)",
    "tostr(n)",
    "s.count(u)",
    "s.find(u)",
    "s.strip()",
    "s.lstrip()",
    "s.rstrip()",
    "s.replace(u, v)",
    "s.lower()",
    "s.upper()",
    "s.isdigit()",
    "s.isalpha()",
    "s.isupper()",
    "s.islower()",
    "s.startswith(u)",
    "s.endswith(u)",
    "s.split()[0]",             # postfix composes with indexing
    "s.strip().lower()",        # postfix chains
    "len(s.split(c))",
]


@test
def test_notation_round_trip():
    for src in NOTATION_FORMS:
        ast = surface.parse_expr(src)
        printed = surface.pexpr(ast)
        ast2 = surface.parse_expr(printed)
        assert ast == ast2, (src, ast, printed, ast2)


@test
def test_notation_canonical_text():
    # Every form above already IS the canonical print (no reparse needed to
    # see this): print(parse(text)) == text.
    for src in NOTATION_FORMS:
        assert surface.pexpr(surface.parse_expr(src)) == src, src


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
    print(f"test_strlib: all {len(UNIT_TESTS)} checks passed "
         f"({N} random code-point seqs per member)")


if __name__ == "__main__":
    try:
        run()
    except AssertionError as e:
        print(f"FAILED: {e}")
        sys.exit(1)
    sys.exit(0)
