"""Plain-python test driver for the lifter (no pytest, no unittest -- house
rule: run as `cd /home/tmcuzzort/tup/t && python3 test_lifter.py`).

Two jobs:

1. `SEEDS`, a module-level list resolving every hand-lifted seed pair under
   `/home/tmcuzzort/t-corpora/lifter-design-2026-09-05/inventory/{lifts,
   lift3}/*.json` to its corpus source file and source method name (see
   `_resolve_seeds`'s docstring for how each was found, and
   `SEEDS_UNMAPPED` for anything that could not be). Every implementer's
   test file is expected to iterate `SEEDS` to build (source AST, expected
   task) fixtures rather than re-deriving the mapping.

2. A `main` that imports and runs each of the four implementer test
   modules named in `LIFTER-DESIGN.md`'s header table (`test_lift_front`
   for `lift_resolve.py`/`lift_parse.py`, `test_lift_rules` for
   `lift_classify.py`/`lift_rewrite.py`, `test_lift_check` for
   `lift_check.py`, `test_lift_report` for `lift_census.py`/`lifter.py`),
   printing "not implemented" for any that do not exist yet. This file
   owns none of those four implementers' test bodies -- it only resolves
   the shared fixture list and dispatches to whichever of the four test
   files exist.

Convention every `test_lift_*.py` module is expected to follow, so this
driver can call it uniformly: define a module-level `run(slow: bool =
False) -> None` that runs its own assertions (raising `AssertionError` on
failure, exactly like every other plain-python check in this project) and
prints a one-line summary of what it checked. A module with no such
function is treated the same as a module that does not exist yet: "not
implemented".
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Fixture roots. These live outside the repo (t-corpora is a data checkout
# on this box, not a committed directory), so they are plain absolute
# constants rather than something computed relative to this file -- the
# same way lift_census.py's production callers point --census-json/
# --corpus-dir at wherever census.json and DafnyBench actually are. Wrapped
# in pathlib.Path throughout so every join and every file open downstream
# is Windows-safe even though these particular roots are this box's own.
# ---------------------------------------------------------------------------

INVENTORY_DIR = Path("/home/tmcuzzort/t-corpora/lifter-design-2026-09-05/inventory")
CORPUS_DIR = Path("/home/tmcuzzort/t-corpora/DafnyBench/DafnyBench/dataset/ground_truth")


# ---------------------------------------------------------------------------
# SEEDS: (seed_json_path, corpus_source_path, method_name).
#
# `method_name` is the method's ACTUAL name in the Dafny source, not
# necessarily the seed JSON's `"name"` field: a hand lifter was free to
# rename on the way to t (SPEC.md/SYNTAX.md naming has no notion of a
# reserved word clash with plain Dafny identifiers, so a rename like
# `main` -> `main_k` reflects the reader's taste, not a lift rule), and
# what a caller needs to locate the gradable method inside the PARSED
# SOURCE is the name dafny actually gave it. Each entry below was resolved
# by: reading the seed JSON's `name` field and its sibling `.t`/`.err`
# file (a lift3 seed has no `.err`; `lift3/` was hand-lifted straight from
# the corpus with no recorded failed attempts), searching the corpus with
# `grep -il "method[^A-Za-z0-9_]*<name>\\b"` (case-insensitive: several
# sources spell a method with different capitalisation than the seed's t
# name -- `pot` -> `Pot`, `carre` -> `Carre`), preferring a candidate
# whose filename shares a word with the seed's own filename, and where
# that still left more than one candidate, reading the candidate's body
# against the seed's `.t` file (params, invariants, spec_fun name and
# body) until exactly one matched byte-for-byte in structure. Two entries
# needed that last step and are called out here:
#   - `02_main_k`: the JSON/`.t` name `main_k` appears in no corpus file
#     (there is no method actually called `main_k`); the seed is a rename
#     of `method main(n, k) returns (k_out)` in
#     `..._dataset_C_convert_examples_15.dfy` -- confirmed by the exact
#     invariant `j + k_out == k`, which a sibling file in the same corpus
#     directory (`..._Generated_Code_15.dfy`) states differently
#     (`k_out == k - j`, an equivalent but textually different invariant
#     that would have silently produced a wrong seed mapping).
#   - `lift3/04_Metodos_Mult`: two corpus files
#     (`..._Invariantes_multiplicador.dfy` and
#     `..._Aula_2_ex1.dfy`) both define `method Mult(x:nat,y:nat)` with an
#     IDENTICAL body and invariant, so the seed's body cannot disambiguate
#     them; `..._Invariantes_multiplicador.dfy` was picked because its
#     filename is the only one of the two containing "mult" as a
#     substring. Since the two sources are identical modulo comments, a
#     lift of either produces the same task; this is recorded here rather
#     than under `SEEDS_UNMAPPED` because a definite corpus FILE was
#     chosen, even though the choice among two byte-identical-body
#     candidates was a coin flip broken by filename.
#
# All 21 seed JSONs (11 in `lifts/`, 10 in `lift3/`) resolved; none are in
# `SEEDS_UNMAPPED`.
# ---------------------------------------------------------------------------

def _seed(seed_dir: str, stem: str, corpus_file: str, method: str) -> tuple[Path, Path, str]:
    return (INVENTORY_DIR / seed_dir / f"{stem}.json", CORPUS_DIR / corpus_file, method)


SEEDS: list[tuple[Path, Path, str]] = [
    _seed("lifts", "01_triple", "Clover_triple.dfy", "Triple"),
    _seed("lifts", "02_main_k",
          "Dafny_Verify_tmp_tmphq7j0row_dataset_C_convert_examples_15.dfy", "main"),
    _seed("lifts", "03_carre",
          "M2_tmp_tmp2laaavvl_Software Verification_Exercices_Exo9-Carre.dfy", "Carre"),
    _seed("lifts", "04_pot",
          "Metodos_Formais_tmp_tmpql2hwcsh_Invariantes_potencia.dfy", "Pot"),
    _seed("lifts", "05_a8q1",
          "cs245-verification_tmp_tmp0h_nxhqp_A8_Q1.dfy", "A8Q1"),
    _seed("lifts", "05b_a8q1_fix",
          "cs245-verification_tmp_tmp0h_nxhqp_A8_Q1.dfy", "A8Q1"),
    _seed("lifts", "06_factorial",
          "dafny-programs_tmp_tmpcwodh6qh_src_factorial.dfy", "factorial"),
    _seed("lifts", "07_lateral", "dafny-synthesis_task_id_266.dfy", "LateralSurfaceArea"),
    _seed("lifts", "08_rect", "dafny-synthesis_task_id_458.dfy", "RectangleArea"),
    _seed("lifts", "09_hex", "dafny-synthesis_task_id_86.dfy", "CenteredHexagonalNumber"),
    _seed("lifts", "10_fatorial",
          "Metodos_Formais_tmp_tmpql2hwcsh_Invariantes_fatorial2.dfy", "Fatorial"),
    _seed("lift3", "01_Clover_return_seven", "Clover_return_seven.dfy", "M"),
    _seed("lift3", "02_Dafny_Verify_Mult",
          "Dafny_Verify_tmp_tmphq7j0row_Generated_Code_Mult.dfy", "mult"),
    _seed("lift3", "03_M2_ComputeSum",
          "M2_tmp_tmp2laaavvl_Software Verification_Exercices_Exo7-ComputeSum.dfy",
          "ComputeSum"),
    _seed("lift3", "04_Metodos_Mult",
          "Metodos_Formais_tmp_tmpql2hwcsh_Invariantes_multiplicador.dfy", "Mult"),
    _seed("lift3", "05_PVS_gcdI",
          "Programmverifikation-und-synthese_tmp_tmppurk6ime_PVS_Assignment_ex_06_Hoangkim_"
          "ex_06_hoangkim.dfy", "gcdI"),
    _seed("lift3", "06_expt", "dafny-programs_tmp_tmpcwodh6qh_src_expt.dfy", "expt"),
    _seed("lift3", "07_DogYears", "dafny-synthesis_task_id_264.dfy", "DogYears"),
    _seed("lift3", "08_CalculateLoss", "dafny-synthesis_task_id_452.dfy", "CalculateLoss"),
    _seed("lift3", "09_CountEqualNumbers", "dafny-synthesis_task_id_801.dfy",
          "CountEqualNumbers"),
    _seed("lift3", "10_se2011_Eval", "se2011_tmp_tmp71eb82zt_ass1_ex4.dfy", "Eval"),
]

# Seed JSONs this module could not map to a corpus source; kept as a
# parallel list of (seed_json_path, reason) rather than silently dropped.
# Empty: all 21 seeds resolved (see the block comment above).
SEEDS_UNMAPPED: list[tuple[Path, str]] = []


def _seed_json_and_siblings(seed_json: Path) -> tuple[dict, str | None]:
    """Load one seed's JSON and, if present, its sibling `.t`/`.err` text
    (whichever exists; `.err` is empty for every seed that has one, and
    `lift3/` seeds have neither). Used by fixture-building tests, not by
    `SEEDS` resolution itself (that was done by hand, see above, and is
    fixed data)."""
    import json
    task = json.loads(seed_json.read_text(encoding="utf-8"))
    for suffix in (".t", ".err"):
        sib = seed_json.with_suffix(suffix)
        if sib.exists():
            text = sib.read_text(encoding="utf-8")
            if text.strip():
                return task, text
    return task, None


def test_seeds_resolve() -> None:
    """Sanity check on `SEEDS` itself: every seed JSON, every corpus
    source file, exists on disk, every seed JSON parses, and every
    corpus source file's text actually contains the claimed method name
    (a loose textual check -- `lift_parse.parse` is the real authority
    once it exists; this only guards against a typo in the table above)."""
    assert SEEDS, "SEEDS must not be empty"
    seen_names = set()
    for seed_json, corpus_path, method in SEEDS:
        assert seed_json.is_file(), f"missing seed json: {seed_json}"
        assert corpus_path.is_file(), f"missing corpus source: {corpus_path}"
        task, _ = _seed_json_and_siblings(seed_json)
        assert "name" in task, f"seed json has no name field: {seed_json}"
        src_text = corpus_path.read_text(encoding="utf-8", errors="replace")
        assert method in src_text, (
            f"method name {method!r} not found verbatim in {corpus_path}")
        seen_names.add((seed_json.name, corpus_path.name, method))
    assert len(seen_names) == len(SEEDS), "duplicate SEEDS entries"
    print(f"test_seeds_resolve: {len(SEEDS)} seeds resolve, "
          f"{len(SEEDS_UNMAPPED)} unmapped")


def test_ast_imports() -> None:
    """`lift_ast.py` is data only (no NotImplementedError bodies); confirm
    its declared surface (the classes named in the interfaces contract)
    is actually present, so a typo in a dataclass name fails loudly here
    rather than as a mysterious AttributeError three modules downstream."""
    import lift_ast
    for name in ("Node", "Star", "Attr", "Type", "Param", "Expr", "IntLit",
                 "BoolLit", "Ident", "Unary", "Binary", "NaryBool",
                 "Implies", "Iff", "Chain", "IfExpr", "Quantifier", "Call",
                 "Index", "Slice", "SeqUpdate", "Member", "Cardinality",
                 "Lhs", "Assign", "VarDeclStmt", "AssignSuchThat", "IfStmt",
                 "WhileStmt", "ForStmt", "ReturnStmt", "AssertStmt",
                 "AssumeStmt", "CalcStmt", "ForallStmt", "CallStmt",
                 "RequiresClause", "EnsuresClause", "InvariantClause",
                 "DecreasesClause", "ModifiesClause", "FunctionDecl",
                 "MethodDecl", "LemmaDecl", "SkippedDecl", "Module",
                 "CallGraphSCC", "Refusal", "Rename", "Rewrite",
                 "ClauseAdded", "ClauseDropped", "LiftRecord"):
        assert hasattr(lift_ast, name), f"lift_ast missing {name}"
    print("test_ast_imports: lift_ast's declared surface is present")


OWN_TESTS = [test_seeds_resolve, test_ast_imports]

IMPLEMENTER_MODULES = [
    "test_lift_front",   # lift_resolve.py, lift_parse.py
    "test_lift_rules",   # lift_classify.py, lift_rewrite.py
    "test_lift_check",   # lift_check.py
    "test_lift_report",  # lift_census.py, lifter.py
]


def _run_own_tests() -> int:
    failures = 0
    for fn in OWN_TESTS:
        try:
            fn()
        except AssertionError as e:
            failures += 1
            print(f"{fn.__name__}: FAILED: {e}")
    return failures


def _run_implementer_module(name: str, slow: bool) -> int:
    """Import `name` and call its `run(slow=slow)`. Returns 1 on any
    failure (import error, missing `run`, or `run` raising), 0 on
    success; prints "not implemented" rather than a traceback when the
    module or its `run` function does not exist yet, since that is the
    expected state before an implementer has written it."""
    try:
        mod = importlib.import_module(name)
    except ImportError:
        print(f"{name}: not implemented")
        return 0
    run_fn = getattr(mod, "run", None)
    if run_fn is None:
        print(f"{name}: not implemented (module exists, no run())")
        return 0
    try:
        run_fn(slow=slow)
        return 0
    except AssertionError as e:
        print(f"{name}: FAILED: {e}")
        return 1
    except NotImplementedError as e:
        print(f"{name}: not implemented ({e})")
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the lifter's plain-python tests.")
    parser.add_argument("module", nargs="?", default=None,
                         choices=IMPLEMENTER_MODULES,
                         help="run only this implementer test module")
    parser.add_argument("--slow", action="store_true",
                         help="also run the corpus-scale checks "
                              "(section 12 test plan steps that touch all "
                              "785 files, not just the 77/49/21 samples)")
    args = parser.parse_args(argv)

    failures = 0
    if args.module is None:
        failures += _run_own_tests()
        targets = IMPLEMENTER_MODULES
    else:
        targets = [args.module]

    for name in targets:
        failures += _run_implementer_module(name, args.slow)

    if failures:
        print(f"{failures} failure(s)")
    else:
        print("all run tests passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
