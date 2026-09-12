"""Plain-python tests for `lift_resolve.py` and `lift_parse.py`
(LIFTER-DESIGN.md sections 1, 3, 18.1, and 10(b)). Owned solely by the
front-end implementer per LIFTER-DESIGN.md's header table; imported and run
by `test_lifter.py`'s `main`, house rule: no pytest, no unittest.

    cd <repo>/t && python3 test_lifter.py test_lift_front
    cd <repo>/t && python3 test_lifter.py test_lift_front --slow

Fast tests (default, always run, no dafny invocation) exercise the parser
directly against the banked rprints under
`t-corpora/lifter-design-2026-09-05/dpn/corpus_rprint` and cross-reference
`test_lifter.SEEDS`. Slow tests (`--slow` only) are the two corpus-scale
acceptance checks that need either all 785 files or a fresh `dafny
--rprint` call per file: acceptance (a) (parse-or-refuse over all 785) and
acceptance (c) (the section 10(b)/12 fixpoint over the 77), run with at
most 4 concurrent dafny processes (house rule for this shared box).
"""

from __future__ import annotations

import re
import tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import corpora
import lift_ast
import lift_parse as lp
import lift_resolve as lr
from test_lifter import SEEDS

RPRINT_DIR = corpora.CORPUS_RPRINT
INFRAGMENT_FILE = corpora.INFRAGMENT_TXT
CORPUS_DIR = corpora.CORPUS_DIR


def infragment_names() -> list[str]:
    """The in-fragment file names, read on demand.

    This was a module-level `read_text()`, which made `import
    test_lift_front` raise FileNotFoundError on any machine without the
    corpus. `test_lifter.py`'s dispatcher catches ImportError but not
    OSError, so that one line took the whole suite down instead of skipping
    the modules that need a corpus. Read it inside the tests that use it."""
    return [ln.strip() for ln in
            INFRAGMENT_FILE.read_text(encoding="utf-8").splitlines()
            if ln.strip()]


MAX_DAFNY_WORKERS = 4  # house rule: at most 4 concurrent dafny processes on this box


def _rprint_for(corpus_filename: str) -> Path:
    """The banked rprint for a corpus source file's plain name (e.g.
    "Clover_abs.dfy" -> ".../corpus_rprint/Clover_abs.dfy.rprint.dfy"),
    matching how the 785 rprints were named when they were banked."""
    return RPRINT_DIR / f"{corpus_filename}.rprint.dfy"


def _normalize_rprint(text: str) -> str:
    """Acceptance (c)'s comparison rule: drop the `module _System { ... }`
    preamble block (everything up to and including the `/* CALL GRAPH for
    module _module: ... */` comment) and collapse whitespace, so the
    fixpoint check compares only the real declarations' canonical text."""
    marker = "/* CALL GRAPH for module _module:"
    idx = text.find(marker)
    if idx == -1:
        body = text
    else:
        end = text.find("*/", idx)
        body = text[end + 2:] if end != -1 else text[idx:]
    return re.sub(r"\s+", " ", body).strip()


# ---------------------------------------------------------------------------
# Fast tests (default; no dafny invocation).
# ---------------------------------------------------------------------------

def test_ast_shape_on_abs() -> None:
    """A hand-checked shape assertion on the smallest in-fragment program
    (Clover_abs.dfy: one param, one return, two ensures, one decreases, an
    if/else body), using its banked rprint directly."""
    text = _rprint_for("Clover_abs.dfy").read_text(encoding="utf-8")
    module = lp.parse(text)
    assert len(module.call_graph) == 1, module.call_graph
    assert module.call_graph[0].names == ("Abs",)
    gm = lp.gradable_methods(module)
    assert [m.name for m in gm] == ["Abs"]
    m = gm[0]
    assert len(m.params) == 1 and m.params[0].name == "x"
    assert len(m.returns) == 1 and m.returns[0].name == "y"
    ensures = [s for s in m.specs if isinstance(s, lift_ast.EnsuresClause)]
    assert len(ensures) == 2
    decreases = [s for s in m.specs if isinstance(s, lift_ast.DecreasesClause)]
    assert len(decreases) == 1
    assert m.body is not None and len(m.body) == 1
    assert isinstance(m.body[0], lift_ast.IfStmt)
    print("test_ast_shape_on_abs: Abs's parsed shape matches the source")


def test_77_infragment_parse_clean() -> None:
    """Acceptance (b): all 77 in-fragment banked rprints parse with zero
    refusals. Pure parsing, no dafny invocation -- fast enough by default."""
    names = infragment_names()
    ok = 0
    fails = []
    for name in names:
        text = _rprint_for(name).read_text(encoding="utf-8", errors="replace")
        try:
            lp.parse(text)
            ok += 1
        except lp.LiftParseError as e:
            fails.append((name, e.token, e.line))
    assert not fails, f"{len(fails)} of the 77 in-fragment files failed to parse: {fails[:5]}"
    assert ok == len(names) == 77, ok
    print(f"test_77_infragment_parse_clean: {ok}/77 in-fragment files parse with zero refusals")


def test_seeds_front_end() -> None:
    """Every SEEDS corpus source's banked rprint parses, and the seed's
    named method is among the parsed module's gradable methods -- the
    front end's half of `test_lifter.SEEDS` being a usable fixture. Uses
    the banked rprint (no live dafny call), so this stays fast."""
    checked = 0
    for seed_json, corpus_path, method in SEEDS:
        text = _rprint_for(corpus_path.name).read_text(encoding="utf-8", errors="replace")
        module = lp.parse(text)
        gradable_names = {m.name for m in lp.gradable_methods(module)}
        assert method in gradable_names, (
            f"{corpus_path.name}: {method!r} not gradable (found {gradable_names})")
        checked += 1
    print(f"test_seeds_front_end: {checked}/{len(SEEDS)} seed methods are gradable "
          f"in their parsed source")


def test_resolve_18_1_small() -> None:
    """A fast slice of acceptance (d): one clean file (exit 0, refusal
    None, verify_exit populated, rprint/print text present) and the two
    corpus_pass.json exit-2 files (resolve-failure, rprint/print/verify
    all None, the diagnostic's own first Error: line named as the refusal
    token). The full 10-file version is `test_resolve_18_1_full`,
    --slow-gated only because it is the slower of the two, not because it
    is required to be."""
    cases = [
        ("Clover_abs.dfy", 0),
        ("groupTheory_tmp_tmppmmxvu8h_assignment1.dfy", 2),
        ("Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_from dafny main "
         "repo_dafny4_ACL2-extractor.dfy", 2),
    ]
    with ThreadPoolExecutor(max_workers=MAX_DAFNY_WORKERS) as ex:
        futs = {ex.submit(lr.resolve, CORPUS_DIR / name, 60.0): (name, exp)
                for name, exp in cases}
        for fut in as_completed(futs):
            name, exp_exit = futs[fut]
            r = fut.result()
            assert r.resolve_exit == exp_exit, f"{name}: exit {r.resolve_exit}, expected {exp_exit}"
            if exp_exit == 0:
                assert r.refusal is None
                assert r.rprint_text is not None
                assert r.verify_exit is not None
            else:
                assert r.refusal is not None and r.refusal.reason == "resolve-failure"
                assert r.rprint_text is None
                assert r.print_text is None
                assert r.verify_exit is None
                assert "Error:" in r.refusal.token
    print("test_resolve_18_1_small: 18.1 exit-code discipline holds on 1 clean + 2 exit-2 files")


def test_source_disagreement_598() -> None:
    """LIFTER-DECISIONS.md row 32 ("do not trust a lossy print of the
    source"), the measured case that motivated it:
    `dafny-synthesis_task_id_598` IsArmstrong's own ensures reads `(n /
    100) * (n / 100) * (n / 100) + ...`; dafny's `--rprint:-` drops the
    parens around a divided operand of `*` and prints `n / 100 * n / 100
    * n / 100 + ...`, which parses to a DIFFERENT tree. `lift_resolve
    .check_against_source` must (1) find exactly one disagreement, on
    `ensures#0`, (2) correct `method.specs` in place to the SOURCE's own
    tree, never rprint's, and (3) leave `requires` (which the two texts
    agree on) untouched."""
    path = CORPUS_DIR / "dafny-synthesis_task_id_598.dfy"
    r = lr.resolve(path, 60.0)
    assert r.refusal is None, r.refusal
    module = lp.parse(r.rprint_text)
    methods = lp.gradable_methods(module)
    assert len(methods) == 1 and methods[0].name == "IsArmstrong"
    method = methods[0]
    rprint_ensures_before = method.specs[1]
    assert isinstance(rprint_ensures_before, lift_ast.EnsuresClause)

    warnings, refusal = lr.check_against_source(path, method)
    assert refusal is None, refusal
    assert len(warnings) == 1, warnings
    assert warnings[0].startswith("rprint-source-disagreement: IsArmstrong ensures#0:")

    # requires is untouched (structurally unchanged, same object even).
    assert method.specs[0] is not None
    assert isinstance(method.specs[0], lift_ast.RequiresClause)
    assert lr._struct_eq(method.specs[0], lift_ast.RequiresClause(
        line=method.specs[0].line, expr=method.specs[0].expr))

    # ensures now parses like the SOURCE's own `(n/100)*(n/100)*(n/100)`:
    # three INDEPENDENT `n / 100` sub-trees multiplied together, not one
    # `n / 100` multiplied by `n` and divided by 100 again the way
    # rprint's dropped parens gave it (measured before this row:
    # `((n div 100) * n) div 100`). Built and compared structurally
    # (`_struct_eq`, line-blind) rather than poked at by field path, so a
    # harmless AST shape change elsewhere cannot make this assertion lie.
    def lit(n):
        return lift_ast.IntLit(line=1, value=n)

    def ident(name):
        return lift_ast.Ident(line=1, name=name)

    def bin_(op, l, r):
        return lift_ast.Binary(line=1, op=op, left=l, right=r)

    da = bin_("/", ident("n"), lit(100))
    term_a = bin_("*", bin_("*", da, da), da)
    mb = bin_("%", bin_("/", ident("n"), lit(10)), lit(10))
    term_b = bin_("*", bin_("*", mb, mb), mb)
    mc = bin_("%", ident("n"), lit(10))
    term_c = bin_("*", bin_("*", mc, mc), mc)
    expected_ens = lift_ast.EnsuresClause(
        line=1, expr=lift_ast.Iff(
            line=1, left=ident("result"),
            right=lift_ast.Chain(
                line=1, ops=("==",),
                operands=(ident("n"), bin_("+", bin_("+", term_a, term_b), term_c)))))

    ens = method.specs[1]
    assert isinstance(ens, lift_ast.EnsuresClause)
    assert not lr._struct_eq(ens, rprint_ensures_before), \
        "ensures was not corrected away from rprint's own (wrong) tree"
    assert lr._struct_eq(ens, expected_ens), \
        "corrected ensures does not match the source's own (n/100)*(n/100)*(n/100) grouping"
    print("test_source_disagreement_598: rprint's dropped-parens ensures is "
          "corrected to the source's own tree, requires is untouched")


def test_align_and_correct_unit() -> None:
    """A dafny-free unit test of `_align_and_correct`/`_struct_eq`
    (LIFTER-DECISIONS.md row 32): (1) a genuine disagreement is corrected
    and logged; (2) an agreeing pair is left alone and logs nothing; (3)
    a requires/ensures COUNT mismatch refuses `source-unparseable` naming
    both counts, never guesses an alignment; (4) a `decreases` count
    mismatch (dafny's own inference, never authored) is logged, never
    refused."""
    def lit(n, line=1):
        return lift_ast.IntLit(line=line, value=n)

    def ident(name, line=1):
        return lift_ast.Ident(line=line, name=name)

    def bin_(op, l, r, line=1):
        return lift_ast.Binary(line=line, op=op, left=l, right=r)

    # (1) + (2): one ensures that disagrees (rprint dropped grouping,
    # `(a * a) * b` printed and reparsed as `a * (a * b)`), one requires
    # that agrees.
    rp_req = lift_ast.RequiresClause(line=10, expr=ident("n"))
    src_req = lift_ast.RequiresClause(line=1, expr=ident("n"))
    rp_ens = lift_ast.EnsuresClause(
        line=20, expr=bin_("*", ident("a", 20), bin_("*", ident("a", 20), ident("b", 20), 20), 20))
    src_ens = lift_ast.EnsuresClause(
        line=2, expr=bin_("*", bin_("*", ident("a", 2), ident("a", 2), 2), ident("b", 2), 2))
    rprint_specs = (rp_req, rp_ens)
    raw_specs = [src_req, src_ens]
    warnings: list[str] = []
    new_specs, refusal = lr._align_and_correct(rprint_specs, raw_specs, "Unit", warnings)
    assert refusal is None
    assert new_specs[0] is rp_req, "an agreeing requires must not be replaced"
    assert new_specs[1] is src_ens, "a disagreeing ensures must be replaced by the source's tree"
    assert len(warnings) == 1 and "ensures#0" in warnings[0]

    # (3): two source ensures where rprint only has one -- refused, not guessed.
    warnings2: list[str] = []
    _, refusal2 = lr._align_and_correct((rp_ens,), [src_ens, src_ens], "Unit2", warnings2)
    assert refusal2 is not None and refusal2.reason == "source-unparseable"
    assert "1 rprint ensures" in refusal2.token and "2 parsed from the source" in refusal2.token

    # (4): rprint carries an inferred `decreases` the source never wrote
    # -- logged as a mismatch note only if it disagrees on the overlap
    # (here there IS no overlap, 0 source decreases), never refused.
    rp_dec = lift_ast.DecreasesClause(line=30, exprs=(ident("n", 30),))
    warnings3: list[str] = []
    new_specs3, refusal3 = lr._align_and_correct((rp_dec,), [], "Unit3", warnings3)
    assert refusal3 is None
    assert new_specs3[0] is rp_dec
    assert warnings3 == []
    print("test_align_and_correct_unit: disagreement correction, agreement "
          "pass-through, strict-count refusal, and lenient decreases all hold")


FAST_TESTS = [
    test_ast_shape_on_abs,
    test_77_infragment_parse_clean,
    test_seeds_front_end,
    test_resolve_18_1_small,
    test_source_disagreement_598,
    test_align_and_correct_unit,
]


# ---------------------------------------------------------------------------
# Slow tests (--slow only): full-785 and dafny-round-trip corpus checks.
# ---------------------------------------------------------------------------


# Acceptance (a): the 154 files the 785 run refused at parse time with a
# bare `parse-failure` reason. Named tokens that survive as a genuine
# residual (the parser recognises the shape but section 3's grammar has
# no way to admit it AND no census-vocabulary name fits precisely enough
# to assign one without guessing) are listed here with their one example
# each, so a bare-token reason never appears silently.
KNOWN_BARE_TOKEN_RESIDUALS = {
    # `(n << d as bv6) | (n >> (32 - d) as bv6)`: a bare infix "|" is
    # Dafny's bitvector bitwise-or, but "|" is also how every cardinality
    # atom opens ("|s|") -- a naive recursive-descent parser cannot tell
    # "close this cardinality" from "start a new infix operator" without
    # unbounded lookahead, and mis-guessing would silently break every
    # `|s|` use in the corpus. Left refused rather than risk that.
    "|": "dafny-synthesis_task_id_799.dfy.rprint.dfy",
}


def test_785_parse_or_refuse() -> None:
    """Acceptance (a) and (c): every one of the 785 banked rprints either
    parses cleanly or raises `LiftParseError` naming a token, a line, and
    a construct-named reason (section 5, section 18.2) -- never any other
    exception, and never a bare `parse-failure` reason outside the named
    residual list above."""
    files = sorted(RPRINT_DIR.glob("*.rprint.dfy"))
    assert len(files) == 785, len(files)
    parsed = refused = 0
    tokens: Counter = Counter()
    reasons: Counter = Counter()
    bare_failures: list[tuple[str, str, int]] = []
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        try:
            lp.parse(text)
            parsed += 1
        except lp.LiftParseError as e:
            refused += 1
            tokens[e.token] += 1
            reasons[e.reason] += 1
            if e.reason == "parse-failure":
                bare_failures.append((f.name, e.token, e.line))
    assert parsed + refused == 785
    unexpected = [(name, tok, line) for name, tok, line in bare_failures
                  if tok not in KNOWN_BARE_TOKEN_RESIDUALS]
    assert not unexpected, f"unnamed bare-token parse-failure(s): {unexpected}"
    for name, tok, _line in bare_failures:
        assert KNOWN_BARE_TOKEN_RESIDUALS[tok] == name, (name, tok)
    top = tokens.most_common(15)
    print(f"test_785_parse_or_refuse: {parsed} parsed, {refused} refused "
          f"(0 crashes) / 785; refusal reasons: {reasons.most_common()}; "
          f"top refusal tokens: {top}; bare-token residuals: {bare_failures}")


def test_77_fixpoint() -> None:
    """Acceptance (c): `rprint(print(parse(rprint(f)))) == rprint(f)`
    (after dropping the `_System` preamble and normalising whitespace) on
    all 77 in-fragment files, each checked with a fresh `dafny --rprint`
    call (at most 4 concurrent, house rule)."""
    def check_one(name: str):
        orig_text = _rprint_for(name).read_text(encoding="utf-8")
        module = lp.parse(orig_text)
        printed = lp.print_dafny(module)
        with tempfile.TemporaryDirectory(prefix="fixpoint_") as tmp:
            tmp_dfy = Path(tmp) / "roundtrip.dfy"
            tmp_dfy.write_text(printed, encoding="utf-8", newline="\n")
            result = lr.resolve(tmp_dfy, timeout_s=60.0)
        if result.refusal is not None:
            return (name, False, f"re-resolve failed: {result.refusal.token}")
        match = _normalize_rprint(orig_text) == _normalize_rprint(result.rprint_text)
        return (name, match, None if match else "canonical text differs")

    results = []
    with ThreadPoolExecutor(max_workers=MAX_DAFNY_WORKERS) as ex:
        futs = [ex.submit(check_one, name) for name in infragment_names()]
        for fut in as_completed(futs):
            results.append(fut.result())

    fails = [r for r in results if not r[1]]
    assert not fails, f"fixpoint failed on {len(fails)}/77; first={fails[0]}"
    assert len(results) == 77
    print(f"test_77_fixpoint: fixpoint holds on {len(results)}/77 in-fragment files")


def test_resolve_18_1_full() -> None:
    """Acceptance (d) in full: 10 corpus files, including the 2 that exit
    2 in corpus_pass.json, showing section 18.1's exit-code discipline."""
    cases = [
        ("Clover_abs.dfy", 0),
        ("Clover_triple.dfy", 0),
        ("Clover_min_of_two.dfy", 0),
        ("Clover_return_seven.dfy", 0),
        ("Clover_integer_square_root.dfy", 0),
        ("dafny-synthesis_task_id_266.dfy", 0),
        ("dafny-synthesis_task_id_458.dfy", 0),
        ("dafny-synthesis_task_id_86.dfy", 0),
        ("groupTheory_tmp_tmppmmxvu8h_assignment1.dfy", 2),
        ("Program-Verification-Dataset_tmp_tmpgbdrlnu__Dafny_from dafny main "
         "repo_dafny4_ACL2-extractor.dfy", 2),
    ]
    with ThreadPoolExecutor(max_workers=MAX_DAFNY_WORKERS) as ex:
        futs = {ex.submit(lr.resolve, CORPUS_DIR / name, 60.0): (name, exp)
                for name, exp in cases}
        for fut in as_completed(futs):
            name, exp_exit = futs[fut]
            r = fut.result()
            assert r.resolve_exit == exp_exit, f"{name}: exit {r.resolve_exit}, expected {exp_exit}"
            if exp_exit == 0:
                assert r.refusal is None and r.rprint_text is not None and r.verify_exit is not None
            else:
                assert r.refusal is not None and r.refusal.reason == "resolve-failure"
                assert r.rprint_text is None and r.print_text is None and r.verify_exit is None
    print(f"test_resolve_18_1_full: 18.1 exit-code discipline holds on {len(cases)} files "
          f"(8 clean + 2 exit-2)")


SLOW_TESTS = [test_785_parse_or_refuse, test_77_fixpoint, test_resolve_18_1_full]


def run(slow: bool = False) -> None:
    if not corpora.available(RPRINT_DIR, INFRAGMENT_FILE, CORPUS_DIR):
        print("test_lift_front: skipped, " + corpora.why_missing(
            RPRINT_DIR, INFRAGMENT_FILE, CORPUS_DIR))
        return
    tests = list(FAST_TESTS)
    if slow:
        tests += SLOW_TESTS
    for t in tests:
        t()
    suffix = " (including --slow corpus-scale checks)" if slow else ""
    print(f"test_lift_front: {len(tests)} check(s) passed{suffix}")


if __name__ == "__main__":
    import sys
    run(slow="--slow" in sys.argv)
