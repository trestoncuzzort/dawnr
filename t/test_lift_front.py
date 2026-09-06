"""Plain-python tests for `lift_resolve.py` and `lift_parse.py`
(LIFTER-DESIGN.md sections 1, 3, 18.1, and 10(b)). Owned solely by the
front-end implementer per LIFTER-DESIGN.md's header table; imported and run
by `test_lifter.py`'s `main`, house rule: no pytest, no unittest.

    cd /home/tmcuzzort/tup/t && python3 test_lifter.py test_lift_front
    cd /home/tmcuzzort/tup/t && python3 test_lifter.py test_lift_front --slow

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

import lift_ast
import lift_parse as lp
import lift_resolve as lr
from test_lifter import SEEDS

RPRINT_DIR = Path("/home/tmcuzzort/t-corpora/lifter-design-2026-09-05/dpn/corpus_rprint")
INFRAGMENT_FILE = Path("/home/tmcuzzort/t-corpora/lifter-design-2026-09-05/infragment.txt")
CORPUS_DIR = Path("/home/tmcuzzort/t-corpora/DafnyBench/DafnyBench/dataset/ground_truth")

INFRAGMENT_NAMES = [ln.strip() for ln in INFRAGMENT_FILE.read_text(encoding="utf-8").splitlines()
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
    ok = 0
    fails = []
    for name in INFRAGMENT_NAMES:
        text = _rprint_for(name).read_text(encoding="utf-8", errors="replace")
        try:
            lp.parse(text)
            ok += 1
        except lp.LiftParseError as e:
            fails.append((name, e.token, e.line))
    assert not fails, f"{len(fails)} of the 77 in-fragment files failed to parse: {fails[:5]}"
    assert ok == len(INFRAGMENT_NAMES) == 77, ok
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


FAST_TESTS = [
    test_ast_shape_on_abs,
    test_77_infragment_parse_clean,
    test_seeds_front_end,
    test_resolve_18_1_small,
]


# ---------------------------------------------------------------------------
# Slow tests (--slow only): full-785 and dafny-round-trip corpus checks.
# ---------------------------------------------------------------------------

def test_785_parse_or_refuse() -> None:
    """Acceptance (a): every one of the 785 banked rprints either parses
    cleanly or raises `LiftParseError` naming a token and a line -- never
    any other exception."""
    files = sorted(RPRINT_DIR.glob("*.rprint.dfy"))
    assert len(files) == 785, len(files)
    parsed = refused = 0
    tokens: Counter = Counter()
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        try:
            lp.parse(text)
            parsed += 1
        except lp.LiftParseError as e:
            refused += 1
            tokens[e.token] += 1
    assert parsed + refused == 785
    top = tokens.most_common(15)
    print(f"test_785_parse_or_refuse: {parsed} parsed, {refused} refused "
          f"(0 crashes) / 785; top refusal tokens: {top}")


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
        futs = [ex.submit(check_one, name) for name in INFRAGMENT_NAMES]
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
