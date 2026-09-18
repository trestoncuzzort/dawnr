"""Plain-python tests for ROADMAP 13.4, framac-axiom (2026-09-11):
lower_framac.py withholds the definition of a spec function a "measure"
witness names (harness.real_witness/interp.MeasureViolation), emitting a
bare ACSL declaration instead of the recursive `logic ... = ...` WP would
otherwise assume as an inconsistent axiom (`g(n) = g(n) + 1` at
`decreases 0` has no solution). See lower_framac.py's `spec_fun_acsl`
docstring and the module docstring's "THE WITHHELD-DEFINITION
CERTIFICATE" note for the full argument; this file measures it through
the real pipeline (fuzz_lower.py's committed probes and t/tasks), not a
reimplementation of any of it.

Run as: cd <repo>/t && python3 test_framac_measure_axiom.py

MEASURED 2026-09-11 by `python3 t/test_framac_measure_axiom.py`: see the
printed summary line for the exact pass/fail count this run produced.
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import harness                       # noqa: E402
import fuzz_lower as fz              # noqa: E402
import lower_framac                  # noqa: E402
import tasks_io                      # noqa: E402

UNIT_TESTS = []


def test(fn):
    UNIT_TESTS.append(fn)
    return fn


def _probe(name):
    p = next(t for t in fz.probes() if t["name"] == name)
    return {k: v for k, v in p.items() if not k.startswith("_")}


@test
def declares_g_without_a_body_for_badrec():
    """fz_p_badrec's `g` gets a bare declaration (no `=`, no `g`-terminates
    lemma) in the real lowering; the task's own function (`fz_p_badrec_t`)
    and its `requires`/`ensures` are unaffected."""
    task = _probe("fz_p_badrec")
    w = harness.real_witness(task)
    assert w is not None and w.get("_kind") == "measure", w
    src = lower_framac.lower(task, task["body"], witness=w)
    assert "logic integer g(integer n);" in src, src
    assert "logic integer g(integer n) =" not in src, src
    assert "g_terminates" not in src, src
    assert "ensures (\\result == g(n));" in src, src


@test
def declares_g_without_a_body_for_badrec2():
    """Same shape, badrec2's increasing-measure variant."""
    task = _probe("fz_p_badrec2")
    w = harness.real_witness(task)
    assert w is not None and w.get("_kind") == "measure", w
    src = lower_framac.lower(task, task["body"], witness=w)
    assert "logic integer g(integer n);" in src, src
    assert "logic integer g(integer n) =" not in src, src
    assert "g_terminates" not in src, src


@test
def badvariant_has_no_spec_fun_to_withhold():
    """fz_p_badvariant's measure witness names a LOOP (`_site` becomes an
    int index, not a spec_fun name, in harness.py before this file ever
    sees it), so nothing here withholds anything for it -- confirmed by
    running the actual lowering rather than assumed from the shape."""
    task = _probe("fz_p_badvariant")
    w = harness.real_witness(task)
    assert w is not None and w.get("_kind") == "measure", w
    assert not isinstance(w.get("_site"), str), w
    src = lower_framac.lower(task, task["body"], witness=w)
    assert "logic" not in src        # no spec_funs on this task at all


@test
def certificate_still_refutes_with_the_definition_withheld():
    """The certificate function (the ground `caller_measure`/
    `callee_measure` comparison) is still emitted after the definition is
    withheld -- withholding the axiom does not withhold the proof
    obligation the witness itself grounds."""
    task = _probe("fz_p_badrec")
    w = harness.real_witness(task)
    src = lower_framac.lower(task, task["body"], witness=w)
    assert "t_refutation_certificate" in src, src
    assert "!((0 >= 0) && (0 < 0))" in src, src


@test
def committed_recursive_tasks_are_byte_identical():
    """Every committed task in t/tasks with a spec_fun (none of them has a
    measure witness: each is a correct, verified program) lowers to the
    EXACT same source as `lower()` with no witness at all -- the
    withholding path is reached only through a "measure"-kind witness,
    never merely through having a spec_fun."""
    taskdir = HERE / "tasks"
    names = sorted(p.stem for p in taskdir.glob("*.t"))
    # 35 since 2026-09-18: has_duplicate.t, the nested-`while` task
    # (ROADMAP WS-20 move 1), joined the committed set. The count is
    # pinned so a task appearing without this test seeing it is a
    # failure, not a silent shrink of what "every committed task" means.
    assert len(names) == 35, len(names)
    checked_a_spec_fun_task = False
    for name in names:
        task = tasks_io.load_task(taskdir / f"{name}.t")
        try:
            w = harness.real_witness(task)
        except Exception:
            w = None
        assert w is None, f"{name}: unexpected witness on a committed task: {w}"
        if task.get("spec_funs"):
            checked_a_spec_fun_task = True
        try:
            with_witness_arg = lower_framac.lower(task, task["body"], witness=w)
        except NotImplementedError:
            continue                 # this file's own named abstains (unrelated)
        without_witness_arg = lower_framac.lower(task, task["body"])
        assert with_witness_arg == without_witness_arg, name
    assert checked_a_spec_fun_task, "no committed task with a spec_fun was checked"


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
    print(f"test_framac_measure_axiom: {passed} passed, {failed} failed "
          f"of {len(UNIT_TESTS)}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
