"""Plain-python tests for ROADMAP 13.4 (2026-09-11): a `requires` that is
UNDEFINED (raises, e.g. a `div`/`mod` by zero) at every type-correct input
tried is DEFECTIVE per SPEC.md's "Undefined requires (normative)", the same
defect CLASS as a well-defined but unsatisfiable `requires`
(fz_p_vac_unsat/fz_p_vac_range), and must be told apart from it and from a
body that is merely undefined on every requires-satisfying input.

Measured here, through the real pipeline, not a reimplementation of any of
it:

  1. `interp.Reference` on an fz_p_divreq0-shaped task: `n_req == 0`,
     `req_undef == n_domain > 0`, `points == []` -- the interpreter can
     tell "requires raised" from "requires evaluated False" apart.
  2. `harness.twin_for` on the same task returns `(None,
     "vacuous-requires-undefined", None)`, a NAMED refusal distinct from
     "no-input" (fz_p_vac_unsat/fz_p_vac_range's op, still measured here to
     confirm the distinction is preserved, not merely asserted).
  3. `run_par.lower_and_dispatch` refuses the whole cell before any kernel
     lowering happens: the row reads `("no-twin", "no-twin", True)` and no
     `.c`/`.dfy`/... file for the task is ever written under `out_dir`.
  4. `lower_framac.lower()` on the real body emits the `requires`
     clause's own definedness obligation as a companion `requires` (the
     divisor-nonzero side condition), which was previously omitted.
  5. `verifiers.framac.verify()` on that lowered source reads VACUOUS, not
     VERIFIED (requires frama-c on PATH; skipped, not failed, if absent --
     the same convention test_twin_rule.py uses for dafny).

Run as: cd <repo>/t && python3 test_vacuous_requires.py

MEASURED 2026-09-11 by `python3 t/test_vacuous_requires.py`: see the
printed summary line for the exact pass/fail count this run produced.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import json

import harness                       # noqa: E402
import interp                        # noqa: E402
import lower_framac                  # noqa: E402
import run_par                       # noqa: E402

UNIT_TESTS = []


def test(fn):
    UNIT_TESTS.append(fn)
    return fn


def OP(op, *args):
    return {"op": op, "args": list(args)}


def V(n):
    return {"var": n}


def I(n):
    return {"int": n}


# `requires x / 0 == 0`: `x / 0` has no value at any x, so this task's
# `requires` raises Undef at every type-correct input, never merely
# evaluating False -- the fz_p_divreq0 shape, restated here rather than
# imported, so this file stays independent of fuzz_lower.py's own probe
# list changing shape later.
DIVREQ0 = {
    "t": 1,
    "name": "test_divreq0",
    "params": [{"name": "x", "type": "int"}],
    "returns": [{"name": "r", "type": "int"}],
    "requires": [OP("==", OP("div", V("x"), I(0)), I(0))],
    "ensures": [OP("==", V("r"), I(0))],
    "body": [{"assign": ["r", I(0)]}],
}

# `requires x > 0 and x < 0`: well-defined at every x, satisfied by none --
# the fz_p_vac_range shape. The contrast case: this must still read
# "no-input", never the new "vacuous-requires-undefined" op.
VAC_RANGE = {
    "t": 0,
    "name": "test_vac_range",
    "params": [{"name": "x", "type": "int"}],
    "returns": [{"name": "r", "type": "int"}],
    "requires": [OP(">", V("x"), I(0)), OP("<", V("x"), I(0))],
    "ensures": [OP("==", V("r"), I(5))],
    "body": [{"assign": ["r", I(5)]}],
}


@test
def test_reference_tells_undef_from_false():
    ref = interp.Reference(DIVREQ0)
    assert ref.n_req == 0, f"expected n_req == 0, got {ref.n_req}"
    assert ref.n_domain > 0, "domain() produced no points to test on"
    assert ref.req_undef == ref.n_domain, (
        f"expected requires to raise Undef at EVERY point tried "
        f"({ref.n_domain}), only {ref.req_undef} did")
    assert ref.points == []


@test
def test_reference_well_defined_unsat_is_not_undef():
    ref = interp.Reference(VAC_RANGE)
    assert ref.n_req == 0
    assert ref.req_undef == 0, (
        f"a well-defined but unsatisfiable requires must never raise "
        f"Undef; got req_undef={ref.req_undef}")
    assert ref.points == []


@test
def test_twin_for_names_the_undefined_requires_refusal():
    twin, op, w = harness.twin_for(DIVREQ0)
    assert twin is None and w is None
    assert op == "vacuous-requires-undefined", op
    assert op in harness.REFUSALS
    assert "undefined" in harness.REFUSALS[op].lower()


@test
def test_twin_for_still_says_no_input_for_well_defined_unsat():
    twin, op, w = harness.twin_for(VAC_RANGE)
    assert twin is None and w is None
    assert op == "no-input", op


@test
def test_harness_cache_and_run_par_refuse_before_any_kernel():
    twin_body, op, w = harness.twin_cached(DIVREQ0)
    assert twin_body is None and op == "vacuous-requires-undefined"
    tmp = Path(tempfile.mkdtemp(prefix="t_vacreq_"))
    try:
        tpath = tmp / f"{DIVREQ0['name']}.json"
        tpath.write_text(json.dumps(DIVREQ0), encoding="utf-8")
        out_dir = tmp / "out"
        old_out = harness.OUT
        harness.OUT = out_dir
        try:
            present = [("framac", lower_framac.lower, "c")]
            rows, wits, all_ok = run_par.lower_and_dispatch(
                [tpath], present, jobs_arg=1, flake_n=3)
        finally:
            harness.OUT = old_out
        assert all_ok is False
        assert rows[DIVREQ0["name"]]["framac"] == ("no-twin", "no-twin", True)
        written = list(out_dir.glob("*")) if out_dir.exists() else []
        assert written == [], (
            f"the real must never be lowered for a refused cell; found "
            f"{[p.name for p in written]}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@test
def test_framac_lowering_emits_the_definedness_companion_requires():
    src = lower_framac.lower(DIVREQ0, DIVREQ0["body"])
    # The divisor is the literal 0, so its definedness obligation renders
    # as `(0) != 0`, an explicit contradictory companion to `requires
    # t_div(x, 0) == 0`; either spelling (with or without the outer
    # parens this backend uses elsewhere) is accepted, the CONTENT is
    # what matters.
    assert "requires" in src and "!= 0" in src, (
        "expected an explicit definedness requires clause for the "
        "requires-position div; got:\n" + src)


@test
def test_framac_reads_vacuous_not_verified():
    try:
        from verifiers import framac as fr
    except Exception:                                       # noqa: BLE001
        print("  (frama-c import failed, skipping)")
        return
    try:
        fr.version()
    except (Exception, SystemExit):                          # noqa: BLE001
        print("  (frama-c not on PATH, skipping)")
        return
    src = lower_framac.lower(DIVREQ0, DIVREQ0["body"])
    tmp = Path(tempfile.mkdtemp(prefix="t_vacreq_framac_"))
    try:
        p = tmp / "test_divreq0.c"
        p.write_text(src, encoding="utf-8", newline="\n")
        r = fr.verify(p)
        from verifiers import Outcome
        assert r.outcome == Outcome.VACUOUS, (
            f"expected VACUOUS (the same reading fz_p_vac_unsat/"
            f"fz_p_vac_range already get), got {r.outcome}: "
            f"{(r.error or '')[:300]}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    passed, failed = 0, 0
    for fn in UNIT_TESTS:
        try:
            fn()
        except AssertionError as e:
            failed += 1
            print(f"{fn.__name__}: FAIL: {e}")
        except Exception:                                    # noqa: BLE001
            failed += 1
            print(f"{fn.__name__}: ERROR")
            traceback.print_exc()
        else:
            passed += 1
            print(f"{fn.__name__}: pass")
    print(f"test_vacuous_requires: {passed} passed, {failed} failed "
          f"of {len(UNIT_TESTS)}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
