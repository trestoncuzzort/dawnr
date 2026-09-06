"""Plain-python tests for `lift_check.py` (house rule: no pytest; run as
part of `python3 test_lifter.py test_lift_check [--slow]`, or standalone
via this file's own `if __name__` block).

Exposes `run(slow: bool = False) -> None` per `test_lifter.py`'s
implementer contract (its own docstring: "each `test_lift_*.py` must
expose `run(slow: bool = False) -> None`").

Fast checks (always run, no dafny): the 8 T7 mutation functions at the
JSON level (18.3), a handful of `_t_expr`/`_print_expr` atoms, and
`_param_overlay`'s handled-name precedence (the bug this file's own
development caught: a `record.rename_map` entry for a spec_fun's own
internal parameter name must never leak into the METHOD-level clause
translation -- see `lift_check._param_overlay`'s docstring).

Slow checks (`--slow`, each invokes dafny under a wall timeout): section
9/10/18.5's full `check()` over every seed pair in `test_lifter.SEEDS`
(acceptance a), the T7 mutation runner over at least two of those pairs
(acceptance b), and the 18.4 inverse test over the 11 committed
`t/tasks/*.json` plus a `fuzz_lower.build_corpus` sample (acceptance c).
The front end (`lift_resolve`/`lift_parse`/`lift_classify`/
`lift_rewrite`) is implemented as of this file's writing, so these run
the REAL pipeline, not a hand-built stand-in; a seed that a stub would
have blocked on is instead reported by whichever real stage refuses it.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

import fuzz_lower
import lift_check
import lift_classify
import lift_parse
import lift_resolve
import lift_rewrite
from lift_ast import LiftRecord, Refusal

import test_lifter

TASKS_DIR = Path(__file__).resolve().parent / "tasks"
OUT_DIR = Path(__file__).resolve().parent / "out" / "test_lift_check"


# ===========================================================================
# Shared fixture-building: the REAL front end, not a stand-in.
# ===========================================================================

def _lift_source(dfy_path: Path, method_name: str, timeout_s: float = 60.0) -> dict:
    """Runs resolve -> parse -> classify -> rewrite for one method of one
    corpus file. Returns a dict with `status` one of `"ok"` (plus `task`,
    `source`, `closure`, `record`) or `"refused"` (plus `stage`, `detail`)
    -- never raises, so a caller can report a per-seed status line instead
    of aborting the whole sweep on the first seed a stage legitimately
    refuses (a refusal upstream of `lift_check.check` is not this
    module's finding)."""
    try:
        rr = lift_resolve.resolve(dfy_path, timeout_s)
    except NotImplementedError:
        return {"status": "refused", "stage": "lift_resolve.resolve",
                "detail": "not implemented"}
    if rr.refusal is not None:
        return {"status": "refused", "stage": "resolve", "detail": str(rr.refusal)}

    try:
        module = lift_parse.parse(rr.rprint_text)
    except lift_parse.LiftParseError as e:
        return {"status": "refused", "stage": "parse", "detail": str(e)}
    except NotImplementedError:
        return {"status": "refused", "stage": "lift_parse.parse", "detail": "not implemented"}

    methods = lift_parse.gradable_methods(module)
    m = next((x for x in methods if x.name == method_name), None)
    if m is None:
        return {"status": "refused", "stage": "gradable_methods",
                "detail": f"{method_name!r} not among {[x.name for x in methods]}"}

    plan = lift_classify.classify(module, m)
    if isinstance(plan, Refusal):
        return {"status": "refused", "stage": "classify", "detail": str(plan)}

    rr2 = lift_rewrite.rewrite(module, plan, str(dfy_path), "0" * 64)
    return {"status": "ok", "task": rr2.task, "source": plan.method,
           "closure": plan.closure, "record": rr2.record}


# ===========================================================================
# Fast checks (no dafny).
# ===========================================================================

def _tiny_task(**over) -> dict:
    base = {
        "t": 1, "name": "demo",
        "params": [{"name": "n", "type": "int"}],
        "returns": [{"name": "r", "type": "int"}],
        "requires": [{"op": ">=", "args": [{"var": "n"}, {"int": 0}]}],
        "ensures": [{"op": "==", "args": [{"var": "r"}, {"var": "n"}]}],
        "body": [{"assign": ["r", {"var": "n"}]}],
    }
    base.update(over)
    return base


def test_t7_mutations_json_level() -> None:
    """Each of the 8 section-18.3 mutation functions, exercised at the
    JSON level (no dafny): applicable ones actually change the task in
    the documented way; inapplicable ones return `None` rather than
    raising or silently no-op'ing a copy."""
    plain = _tiny_task()
    assert lift_check.mut_iff_as_implies(plain)["ensures"][0]["op"] == "implies"
    assert lift_check.mut_ensures_conjunct_dropped(plain) is None  # only 1 ensures, not "and"
    assert lift_check.mut_negative_literal_flip(plain) is None     # no neg literal anywhere

    neg_task = _tiny_task(body=[{"assign": ["r", {"op": "neg", "args": [{"int": 3}]}]}])
    flipped = lift_check.mut_negative_literal_flip(neg_task)
    assert flipped["body"][0]["assign"][1] == {"int": 3}

    and_task = _tiny_task(ensures=[{"op": "and", "args": [
        {"op": ">=", "args": [{"var": "r"}, {"int": 0}]},
        {"op": "==", "args": [{"var": "r"}, {"var": "n"}]}]}])
    dropped = lift_check.mut_ensures_conjunct_dropped(and_task)
    assert len(dropped["ensures"][0]["args"]) == 1

    q_task = _tiny_task(ensures=[{"forall": {"var": "k", "lo": {"int": 0}, "hi": {"var": "n"},
                                             "body": {"op": ">=", "args": [{"var": "r"}, {"int": 0}]}}}])
    widened = lift_check.mut_quantifier_bound_widened(q_task)
    assert widened["ensures"][0]["forall"]["hi"] == {"op": "+", "args": [{"var": "n"}, {"int": 1}]}
    assert lift_check.mut_quantifier_bound_widened(plain) is None  # no quantifier

    loop_task = _tiny_task(body=[
        {"assign": ["r", {"int": 0}]},
        {"while": {"cond": {"op": "<", "args": [{"var": "r"}, {"var": "n"}]},
                  "invariants": [{"op": ">=", "args": [{"var": "r"}, {"int": 0}]}],
                  "decreases": {"op": "-", "args": [{"var": "n"}, {"var": "r"}]},
                  "body": [{"assign": ["r", {"op": "+", "args": [{"var": "r"}, {"int": 1}]}]}]}}])
    negated = lift_check.mut_loop_guard_negated(loop_task)
    assert negated["body"][1]["while"]["cond"]["op"] == "not"
    dropped_inv = lift_check.mut_invariant_dropped(loop_task)
    assert dropped_inv["body"][1]["while"]["invariants"] == []
    assert lift_check.mut_loop_guard_negated(plain) is None
    assert lift_check.mut_invariant_dropped(plain) is None

    tot_task = _tiny_task()
    tot_task["spec_funs"] = [{"name": "f", "params": [{"name": "x", "type": "int"}],
                             "result": "int", "decreases": {"var": "x"},
                             "body": {"ite": {"cond": {"op": ">=", "args": [{"var": "x"}, {"int": 0}]},
                                              "then": {"var": "x"}, "else": {"int": 0}}}}]
    swapped = lift_check.mut_totalisation_default_reached(tot_task)
    assert swapped["spec_funs"][0]["body"]["ite"]["then"] == {"int": 0}
    assert lift_check.mut_totalisation_default_reached(plain) is None

    seq_task = _tiny_task(body=[
        {"assign": ["r", {"var": "n"}]},
        {"assign": ["r", {"op": "+", "args": [{"var": "r"}, {"int": 1}]}]},
    ])
    swapped_seq = lift_check.mut_parallel_sequenced(seq_task)
    assert swapped_seq["body"][0]["assign"][0] == "r"
    assert swapped_seq["body"][1] == seq_task["body"][0]
    assert lift_check.mut_parallel_sequenced(plain) is None

    print("test_t7_mutations_json_level: 8/8 mutation functions exercised at JSON level")


def test_param_overlay_precedence() -> None:
    """The bug `lift_check.py`'s own development against the real front
    end caught (`_param_overlay`): a `record.rename_map` entry for a
    name ALREADY covered by positional param/return correspondence (or
    by the closure's own `_src` declaration renames) must never override
    that mapping -- only fill a gap (a true local with no positional
    counterpart)."""
    from lift_ast import Rename
    rec = LiftRecord(source_path="x", method="M", rprint_sha256="0" * 64)
    # A rename_map entry for "n" that has NOTHING to do with the method's
    # own param translation (e.g. a spec_fun's own internal binder
    # happening to share the source method's param name "n"), plus a
    # genuine local rename ("tmp" -> a sanitised name).
    rec.rename_map["n"] = Rename(t_name="n_v", reason="spec-fun-own-binder")
    rec.rename_map["tmp"] = Rename(t_name="tmp_1", reason="keyword-clash")
    overlay = lift_check._param_overlay(
        {"Fat": "Fat_src"}, rec, ["n"], ["n"], src_ret="f", task_ret="r")
    assert overlay["n"] == "n", overlay          # positional identity wins over rename_map
    assert overlay["f"] == "r", overlay          # positional return mapping intact
    assert overlay["Fat"] == "Fat_src", overlay  # closure decl rename intact
    assert overlay["tmp"] == "tmp_1", overlay    # true local: rename_map fills the gap
    print("test_param_overlay_precedence: rename_map cannot clobber a positional mapping")


def test_expr_printers_atoms() -> None:
    """A handful of `_t_expr`/`_print_expr` atoms and compounds, sanity
    only (the real coverage is the slow end-to-end checks, which compile
    and verify with dafny)."""
    assert lift_check._t_expr({"int": 5}) == "5"
    assert lift_check._t_expr({"op": "and", "args": [{"bool": True}, {"bool": False}]}) \
        == "(true && false)"
    assert lift_check._t_expr({"op": "neg", "args": [{"int": 3}]}) == "(-3)"
    assert lift_check._t_conj([]) == "true"
    from lift_ast import IntLit, Binary
    e = Binary(line=1, op="+", left=IntLit(line=1, value=1), right=IntLit(line=1, value=2))
    assert lift_check._print_expr(e, {}) == "(1 + 2)"
    print("test_expr_printers_atoms: t-expr and source-expr printer atoms check out")


FAST_TESTS = [test_t7_mutations_json_level, test_param_overlay_precedence,
             test_expr_printers_atoms]


# ===========================================================================
# Slow checks (dafny). Each --slow test prints a per-item measurement
# line -- the house rule ("every measurement you report comes from a
# command you actually ran") applies to this file's own output too.
# ===========================================================================

def _run_seeds() -> list:
    """One row per `test_lifter.SEEDS` entry: the real front end feeds
    `lift_check.check`, or reports which upstream stage refused first.
    Corpus files shared by two seeds (`05_a8q1`/`05b_a8q1_fix`) are re-run
    per seed (the method name can differ) rather than cached, since this
    is a correctness sweep, not a performance one."""
    rows = []
    for seed_json, corpus_path, method in test_lifter.SEEDS:
        t0 = time.monotonic()
        fx = _lift_source(corpus_path, method, timeout_s=90.0)
        if fx["status"] != "ok":
            rows.append({"seed": seed_json.name, "method": method,
                        "status": "refused-upstream", "stage": fx["stage"],
                        "detail": fx["detail"], "wall_s": round(time.monotonic() - t0, 2)})
            continue
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        dfy_path = OUT_DIR / f"{seed_json.stem}"
        out = lift_check.check(fx["task"], fx["source"], fx["closure"], fx["record"],
                              dfy_path, timeout_s=90.0)
        wall = round(time.monotonic() - t0, 2)
        rows.append({
            "seed": seed_json.name, "method": method,
            "status": "checked", "refusal": str(out.refusal) if out.refusal else None,
            "check_wf": (out.refusal is None or out.refusal.reason != "check-wf-failed"),
            "interp_points": out.interp_points,
            "twin_rung": fx["record"].twin_rung,
            "checker_verdicts": dict(fx["record"].checker_verdicts),
            "differential_verdict": fx["record"].differential_verdict,
            "wall_s": wall,
        })
    return rows


def test_seeds_check_end_to_end(slow: bool) -> None:
    """Acceptance (a): the full `check()` pipeline over every seed pair,
    reporting check_wf/points/twin rung/lemma verdicts/diff verdict/wall
    seconds per pair. Asserts only that `check` never raises and that
    `check-wf-failed` never fires on a task `lift_rewrite` itself
    produced (that would be a lifter bug this module is positioned to
    catch, per the module docstring's data-flow line) -- a
    `lift-check-failed`/`lift-diff-failed` row is reported, not asserted
    against, since it may legitimately mean the CORPUS FILE exposed a
    real lifter gap, which is exactly what this table is for."""
    if not slow:
        print("test_seeds_check_end_to_end: skipped (pass --slow)")
        return
    rows = _run_seeds()
    for r in rows:
        print(json.dumps(r))
    checked = [r for r in rows if r["status"] == "checked"]
    for r in checked:
        assert r["check_wf"], f"check-wf-failed on a rewrite-produced task: {r}"
    n_ok = sum(1 for r in checked if r["refusal"] is None)
    print(f"test_seeds_check_end_to_end: {len(rows)} seeds, {len(checked)} reached "
         f"lift_check.check, {n_ok} fully passed (spec+body+interp-arm), "
         f"{len(rows) - len(checked)} refused upstream of lift_check")


def test_t7_two_seed_pairs(slow: bool) -> None:
    """Acceptance (b): T7 caught/seeded over at least two seed pairs that
    actually reach `lift_check.check` (picks the first two `_run_seeds`
    finds, deterministically -- `test_lifter.SEEDS` is itself a fixed
    list, so this is reproducible)."""
    if not slow:
        print("test_t7_two_seed_pairs: skipped (pass --slow)")
        return
    picked = 0
    for seed_json, corpus_path, method in test_lifter.SEEDS:
        if picked >= 2:
            break
        fx = _lift_source(corpus_path, method, timeout_s=90.0)
        if fx["status"] != "ok":
            continue
        picked += 1
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        results = lift_check.run_t7(fx["task"], fx["source"], fx["closure"],
                                    OUT_DIR / f"t7_{seed_json.stem}", timeout_s=90.0)
        seeded = [r for r in results if r["seeded"]]
        caught = [r for r in seeded if r["caught"]]
        print(f"T7 on {seed_json.name} ({method}): {len(caught)}/{len(seeded)} caught "
             f"({len(results) - len(seeded)} not applicable to this task)")
        for r in results:
            print("  " + json.dumps(r))
    assert picked >= 2, "fewer than two seed pairs reached lift_check.check for T7"
    print(f"test_t7_two_seed_pairs: ran on {picked} seed pairs")


def test_inverse_committed_and_corpus(slow: bool) -> None:
    """Acceptance (c): the 18.4 inverse test over the 11 committed
    `t/tasks/*.json` and a `fuzz_lower.build_corpus` sample of 20+. Each
    task is reported by `inverse_test`'s own status; a `"mismatch"` for a
    v0-shaped committed task against `"t": 1` always (decision 16) is
    expected and normalised away by `_canon_task`'s "t"/"name" strip, so
    a residual mismatch there is a real finding, not decision 16 noise."""
    if not slow:
        print("test_inverse_committed_and_corpus: skipped (pass --slow)")
        return
    counts = {"match": 0, "mismatch": 0, "recursive": 0,
             "waits-for-integrator": 0, "error": 0}
    mismatches = []
    task_paths = sorted(TASKS_DIR.glob("*.json"))
    assert len(task_paths) == 11, f"expected 11 committed tasks, found {len(task_paths)}"
    for p in task_paths:
        task = json.loads(p.read_text(encoding="utf-8"))
        r = lift_check.inverse_test(task, timeout_s=60.0)
        counts[r["status"]] = counts.get(r["status"], 0) + 1
        print(f"inverse[{p.name}]: {r['status']}"
             + (f" ({r.get('stage')})" if r["status"] == "waits-for-integrator" else ""))
        if r["status"] == "mismatch":
            mismatches.append((p.name, r))

    corpus = fuzz_lower.build_corpus(20, seed=20260905)
    for i, task in enumerate(corpus):
        if "_wf_errors" in task:
            continue  # a deliberately-malformed generator finding, not a lift fixture
        r = lift_check.inverse_test(task, timeout_s=60.0)
        counts[r["status"]] = counts.get(r["status"], 0) + 1
        if r["status"] == "mismatch":
            mismatches.append((f"corpus[{i}]:{task['name']}", r))

    print(f"test_inverse_committed_and_corpus: {json.dumps(counts)}")
    if counts["waits-for-integrator"] == len(task_paths) + len(corpus):
        print("test_inverse_committed_and_corpus: every task waited on the same "
             "front-end stage -- the inverse test is wired but the round trip "
             "itself waits for the integrator")
    for name, r in mismatches[:5]:
        print(f"  MISMATCH {name}: {json.dumps(r)[:500]}")
    assert not mismatches, f"{len(mismatches)} inverse-test mismatch(es), see above"


SLOW_TESTS = [test_seeds_check_end_to_end, test_t7_two_seed_pairs,
             test_inverse_committed_and_corpus]


def run(slow: bool = False) -> None:
    failures = 0
    for fn in FAST_TESTS:
        try:
            fn()
        except AssertionError as e:
            failures += 1
            print(f"{fn.__name__}: FAILED: {e}")
    for fn in SLOW_TESTS:
        try:
            fn(slow)
        except AssertionError as e:
            failures += 1
            print(f"{fn.__name__}: FAILED: {e}")
    if failures:
        raise AssertionError(f"{failures} test_lift_check failure(s)")
    print("test_lift_check: all checks passed"
         + (" (fast only, pass --slow for the dafny-running checks)" if not slow else ""))


if __name__ == "__main__":
    import sys
    run(slow="--slow" in sys.argv)
