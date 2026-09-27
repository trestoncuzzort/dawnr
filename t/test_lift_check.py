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
import tasks_io
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

    # LIFTER-DECISIONS.md row 32: `lifter.py`'s own pipeline runs this
    # BEFORE classify, correcting `m` in place against dfy_path's own
    # text wherever rprint's print disagrees with it -- mirrored here so
    # this fixture-builder stays a faithful stand-in for the real
    # pipeline, not a copy that quietly skipped the newest stage.
    src_warnings, src_refusal = lift_resolve.check_against_source(dfy_path, m)
    if src_refusal is not None:
        return {"status": "refused", "stage": "check_against_source", "detail": str(src_refusal)}

    plan = lift_classify.classify(module, m)
    if isinstance(plan, Refusal):
        return {"status": "refused", "stage": "classify", "detail": str(plan)}

    rr2 = lift_rewrite.rewrite(module, plan, str(dfy_path), "0" * 64)
    rr2.record.warnings.extend(src_warnings)
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


def test_quantified_fun_call_scoping_and_array_bound() -> None:
    """2026-09-14 checker gap (ROADMAP 16.2's unbounded-quantifier row,
    the 20 `lift-check-failed` residuals it did not touch): a spec_fun
    call found by `_find_fun_calls` inside a source `forall`/`exists`
    uses that quantifier's OWN bound variable, not a lemma parameter --
    `L_fun_isEven(evenList[k]);` pasted as a bare top-level statement in
    the `L_inv_k` body is `unresolved identifier: k` (measured, dafny
    4.11.0, dafny-synthesis_task_id_412 RemoveOddNumbers and five
    siblings: 426, 436, 554, 594, 629). `_find_fun_calls` must report the
    call's innermost enclosing `Quantifier` so `build_checker` wraps the
    hint in a matching forall-statement instead; `_array_index_guards`
    must additionally bound an `array<T>` base's index (an `array`, unlike
    a `seq`, has no length fact free for the taking -- measured on the
    same six: fixing the scoping alone still left `index out of range`
    on `arr[k]` for `k` ranging only `0 <= k < i`, since `i <= arr.Length`
    is part of the very obligation the hint is helping prove, not yet an
    assumption inside the lemma body)."""
    from lift_ast import Quantifier, Call, Ident, Index, Binary, Param, Type

    k = Ident(line=1, name="k")
    idx = Index(line=1, base=Ident(line=1, name="arr"), index=k)
    call = Call(line=1, fn=Ident(line=1, name="IsEven"), args=(idx,))
    rng = Binary(line=1, op="<", left=k, right=Ident(line=1, name="n"))
    q = Quantifier(line=1, kind="forall",
                   binders=(Param(line=1, name="k", type=Type(line=1, kind="int")),),
                   attrs=(), range=rng, body=call)

    found = lift_check._find_fun_calls([q], {"IsEven"})
    assert len(found) == 1, found
    got_call, got_q = found[0]
    assert got_call is call, found
    assert got_q is q, ("a call under a quantifier must report THAT "
                        f"quantifier, not None: {found}")

    src_params = [Param(line=1, name="arr",
                        type=Type(line=1, kind="array", args=(Type(line=1, kind="int"),)))]
    bounds = lift_check._array_index_guards(call, src_params, {})
    assert bounds == ["0 <= k && k < arr.Length"], bounds

    # A plain lemma-parameter argument (no enclosing quantifier at all)
    # reports `None` -- the existing, unwrapped hint path stays unwrapped.
    plain_call = Call(line=1, fn=Ident(line=1, name="IsEven"), args=(Ident(line=1, name="n"),))
    found2 = lift_check._find_fun_calls([plain_call], {"IsEven"})
    assert len(found2) == 1 and found2[0][1] is None, found2

    # A seq base (no `array` kind) gets no `.Length` bound manufactured --
    # `|s|` is always defined, so nothing here is needed for it.
    seq_idx = Index(line=1, base=Ident(line=1, name="s"), index=k)
    seq_call = Call(line=1, fn=Ident(line=1, name="IsEven"), args=(seq_idx,))
    seq_params = [Param(line=1, name="s",
                        type=Type(line=1, kind="seq", args=(Type(line=1, kind="int"),)))]
    assert lift_check._array_index_guards(seq_call, seq_params, {}) == []
    print("test_quantified_fun_call_scoping_and_array_bound: ok")


FAST_TESTS = [test_t7_mutations_json_level, test_param_overlay_precedence,
             test_expr_printers_atoms, test_quantified_fun_call_scoping_and_array_bound]


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
    task_paths = tasks_io.load_dir(TASKS_DIR)
    # The docstring above dates from 11 committed tasks; the corpus has grown
    # since (26, measured here) and this asserts only that the directory
    # loader found some of them, not a number this file must be kept in sync
    # with by hand.
    assert task_paths, f"expected committed tasks in {TASKS_DIR}, found none"
    for p in task_paths:
        task = tasks_io.load_task(p)
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


def test_array_program_end_to_end(slow: bool) -> None:
    """Read-only `array<int>` parameter (decision 1, `array-readonly-as-
    seq`) end to end on a real corpus file: `Clover_min_array.dfy`'s
    `minArray` lifts `a: array<int>` to a task `seq<int>` of the same
    name, so the checker lemmas keep ONE lemma parameter per argument,
    typed to the SOURCE's `array<int>`, and every lifted-side reference to
    it must print as its sequence view `a[..]` rather than bare `a` (an
    `array<int>` has no `|.|`/seq-index operator) -- the bug this item
    fixed, measured directly against dafny before the fix ("size operator
    expects a collection argument (instead got array<int>)" on L_req,
    L_ens, L_inv_0 and L_dec_0, all four `tool_error`). Asserts every
    lemma verdict is `verified`, not merely that `check` ran."""
    if not slow:
        print("test_array_program_end_to_end: skipped (pass --slow)")
        return
    # Clover_MIN_array, not max. The max file does not parse: it carries a
    # hint-chain expression (a lemma call sequenced before the real result
    # inside a function arm), so the whole FILE refuses `let-expression`
    # (named `stmt-in-expression` since 2026-09-26, when lets began to lift)
    # before any method is reached. That is not a Mac artifact, it is what
    # this repository's own corpus report says: LIFTER-785.md row
    # "Clover_max_array.dfy | (file) | refused:let-expression". So the test
    # asserted a lift its own evidence rules out, and being --slow-gated it
    # had not been run. The min file is the same shape and the same decision
    # 1 rewrite, and it lifts with all four lemmas verified.
    dfy_path = test_lifter.CORPUS_DIR / "Clover_min_array.dfy"
    t0 = time.monotonic()
    fx = _lift_source(dfy_path, "minArray", timeout_s=90.0)
    assert fx["status"] == "ok", f"minArray lift refused upstream: {fx}"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = lift_check.check(fx["task"], fx["source"], fx["closure"], fx["record"],
                          OUT_DIR / "Clover_min_array", timeout_s=90.0)
    wall = round(time.monotonic() - t0, 2)
    verdicts = dict(fx["record"].checker_verdicts)
    print(f"test_array_program_end_to_end: minArray verdicts={json.dumps(verdicts)} "
         f"check_wf={out.refusal is None or out.refusal.reason != 'check-wf-failed'} "
         f"wall_s={wall}")
    assert verdicts, "no lemma verdicts recorded at all"
    non_verified = {k: v for k, v in verdicts.items() if v != "verified"}
    assert not non_verified, f"non-verified lemma verdict(s) on minArray: {non_verified}"
    for expected in ("L_req", "L_ens", "L_inv_0", "L_dec_0"):
        assert expected in verdicts, f"expected lemma {expected!r} missing: {verdicts}"


def test_kernel_unproved_not_folded_into_lift_check_failed(slow: bool) -> None:
    """Section 9 item 7 / decision 17: the checker file's lowered
    `<Method>` (item 2) is a SEPARATE column from the L_* lemma verdicts,
    because decision 8 drops hints (asserts, lemma calls, function
    ensures, nat-result facts) the kernel's own proof may need -- its
    body reading UNPROVED is then an expected consequence of that
    decision, not a wrong lift. Before this fix, `_verify_checker` folded
    ANY error attributable to the finish line's error count into
    `first_bad`/`lift-check-failed` when no lemma scan caught it,
    including the lowered method's own symbol (measured: a probe lifting
    `SumSeq(s: seq<nat>) ...` reported `lift-check-failed:
    Probe_seqnat__sumseq` -- the LOWERED METHOD's name, not a lemma --
    while every `L_*` verdict was `verified`). This constructs the same
    shape directly (a trivially-true lemma plus a kernel method whose own
    `ensures` is unprovable as written) and asserts the lemma verifies,
    `all_ok` stays true (no `lift-check-failed`), and the kernel's own
    verdict surfaces via `lowered_verdict`/`record.lowered_task_verdict`,
    never via `first_bad`."""
    if not slow:
        print("test_kernel_unproved_not_folded_into_lift_check_failed: skipped (pass --slow)")
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dfy = OUT_DIR / "unit_kernel_unproved.dfy"
    dfy.write_text(
        "lemma L_req(x: int)\n  ensures true\n{ }\n\n"
        "method Kernel(x: int) returns (r: int)\n  ensures r > x\n{\n  r := x;\n}\n",
        encoding="utf-8")
    verdicts, exit_code, all_ok, first_bad, warnings, lowered_verdict = (
        lift_check._verify_checker(dfy, ["L_req"], 60.0, "Kernel"))
    print(f"test_kernel_unproved_not_folded_into_lift_check_failed: "
         f"verdicts={verdicts} all_ok={all_ok} first_bad={first_bad!r} "
         f"lowered_verdict={lowered_verdict!r}")
    assert verdicts.get("L_req") == "verified", verdicts
    assert all_ok, f"a dropped-hint kernel failure must not fail the lift, got all_ok={all_ok}"
    assert first_bad is None, f"the kernel's own failure must not be named as first_bad, got {first_bad!r}"
    assert lowered_verdict == "unproved", f"expected the kernel verdict recorded separately, got {lowered_verdict!r}"


def test_for_desugared_extra_local_end_to_end(slow: bool) -> None:
    """2026-09-12, ROADMAP 16.2's `lift-check-failed` row: a `for`-
    desugared loop's own range-bound local (decision 15's `h_t := <hi>`)
    has no source-side declaration, so `_build_checker_parts` typed its
    L_inv_k/L_dec_k lemma parameter plain `int` with no fact tying its
    value to anything -- the <==> obligation then states a claim about
    an ARBITRARY `h`, not the one the lift's own construction produces,
    and is genuinely false for an `h` the real run never takes (confirmed
    by hand: `h == i_v` for an `i_v` past the array's length makes the
    lifted-side conjunction true while the source-side one, gated by
    `i_v <= a.Length` a few conjuncts earlier, is not). `_task_var_inits`
    fixes this by recovering `h`'s own init expr from the task body and
    requiring `h == <that expr>`. `SquareElements`
    (dafny-synthesis_task_id_8.dfy) is this shape's plainest member: one
    `for i := 0 to a.Length` loop, one quantified invariant, nothing
    else. Asserts every lemma verdict is `verified` and `L_inv_0`'s own
    text carries the new fact, not merely that the file lifts."""
    if not slow:
        print("test_for_desugared_extra_local_end_to_end: skipped (pass --slow)")
        return
    dfy_path = test_lifter.CORPUS_DIR / "dafny-synthesis_task_id_8.dfy"
    t0 = time.monotonic()
    fx = _lift_source(dfy_path, "SquareElements", timeout_s=90.0)
    assert fx["status"] == "ok", f"SquareElements lift refused upstream: {fx}"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = lift_check.check(fx["task"], fx["source"], fx["closure"], fx["record"],
                          OUT_DIR / "dafny-synthesis_task_id_8", timeout_s=90.0)
    wall = round(time.monotonic() - t0, 2)
    verdicts = dict(fx["record"].checker_verdicts)
    print(f"test_for_desugared_extra_local_end_to_end: SquareElements "
         f"verdicts={json.dumps(verdicts)} "
         f"check_wf={out.refusal is None or out.refusal.reason != 'check-wf-failed'} "
         f"wall_s={wall}")
    assert verdicts, "no lemma verdicts recorded at all"
    non_verified = {k: v for k, v in verdicts.items() if v != "verified"}
    assert not non_verified, f"non-verified lemma verdict(s) on SquareElements: {non_verified}"
    for expected in ("L_req", "L_ens", "L_inv_0"):
        assert expected in verdicts, f"expected lemma {expected!r} missing: {verdicts}"
    checker_path = OUT_DIR / "dafny-synthesis_task_id_8.check.dfy"
    checker_text = checker_path.read_text(encoding="utf-8")
    assert "h == " in checker_text, (
        "L_inv_0 should require h tied to its own init expr; "
        f"checker text: {checker_text}")


def test_task_var_inits_recovers_for_desugared_bound() -> None:
    """Fast, no-dafny unit for `_task_var_inits` itself: given a task
    body shaped like decision 15's for-desugaring (a `var h := <hi>`
    statement ahead of the `while`, exactly what `lift_rewrite.py`
    always emits for a `for` loop), the helper returns `h`'s init expr
    by name, pre-order through `if`/`while` nesting the same way
    `_task_loops` walks."""
    body = [
        {"var": {"name": "h", "type": "int", "init": {"op": "len", "args": [{"var": "a"}]}}},
        {"var": {"name": "i_v", "type": "int", "init": {"int": 0}}},
        {"while": {"cond": {"op": "<", "args": [{"var": "i_v"}, {"var": "h"}]},
                  "invariants": [], "body": [
            {"if": {"cond": {"bool": True}, "then": [
                {"var": {"name": "inner", "type": "int", "init": {"int": 1}}}], "else": []}}]}},
    ]
    inits = lift_check._task_var_inits(body)
    assert set(inits) == {"h", "i_v", "inner"}, inits
    assert inits["h"] == {"op": "len", "args": [{"var": "a"}]}, inits["h"]
    print("test_task_var_inits_recovers_for_desugared_bound: ok")


def test_for_desugared_bound_alignment_with_prior_local(slow: bool) -> None:
    """2026-09-14 fix (LIFTER-785-RESIDUALS.md, the 14-row `for`-shaped
    `lift-check-failed` group): when the source declares a REAL local
    before its `for` loop, `lift_rewrite`'s desugared bound (`h_t`) lands
    in the MIDDLE of the task's own declaration order, not at the front
    or back -- the old end-alignment guess in `_build_checker_parts`
    (`extra_names = rest_local_names[:extra]`) mis-took the source's
    real local as the "extra" one instead, mis-binding `L_inv_0`'s
    parameters (measured on this exact program: `h == ((2 * k) + 1)`
    where the source itself never relates `h` to anything -- the real
    fact belongs to `i`). `dafny-synthesis_task_id_267.dfy`
    (`SumOfSquaresOfFirstNOddNumbers`) is this shape's plainest member:
    `var i := 1;` then `for k := 0 to n`. Asserts `record.for_bound_locals`
    records exactly the desugared bound (not `i`), and that every lemma
    verdict is `verified` end to end."""
    if not slow:
        print("test_for_desugared_bound_alignment_with_prior_local: skipped (pass --slow)")
        return
    dfy_path = test_lifter.CORPUS_DIR / "dafny-synthesis_task_id_267.dfy"
    t0 = time.monotonic()
    fx = _lift_source(dfy_path, "SumOfSquaresOfFirstNOddNumbers", timeout_s=90.0)
    assert fx["status"] == "ok", f"SumOfSquaresOfFirstNOddNumbers lift refused upstream: {fx}"
    record = fx["record"]
    bound_names = {n for names in getattr(record, "for_bound_locals", {}).values() for n in names}
    assert len(bound_names) == 1, (
        f"expected exactly one desugared bound local, got {bound_names}")
    # The real source local `i` (declared before the for-loop) must NOT
    # be the one recorded as a desugaring-only extra.
    task_local_names = {s["var"]["name"] for s in fx["task"]["body"] if "var" in s}
    assert "i" not in bound_names, f"source's real local mis-recorded as extra: {bound_names}"
    assert bound_names <= task_local_names, (bound_names, task_local_names)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = lift_check.check(fx["task"], fx["source"], fx["closure"], record,
                          OUT_DIR / "dafny-synthesis_task_id_267", timeout_s=90.0)
    wall = round(time.monotonic() - t0, 2)
    verdicts = dict(record.checker_verdicts)
    print(f"test_for_desugared_bound_alignment_with_prior_local: "
         f"SumOfSquaresOfFirstNOddNumbers verdicts={json.dumps(verdicts)} "
         f"for_bound_locals={record.for_bound_locals} "
         f"check_wf={out.refusal is None or out.refusal.reason != 'check-wf-failed'} "
         f"wall_s={wall}")
    assert verdicts, "no lemma verdicts recorded at all"
    non_verified = {k: v for k, v in verdicts.items() if v != "verified"}
    assert not non_verified, f"non-verified lemma verdict(s): {non_verified}"


def test_array_view_forall_exists_end_to_end(slow: bool) -> None:
    """2026-09-14 fix (LIFTER-785-RESIDUALS.md, the 2 `while`-shaped
    `lift-check-failed` rows): an array-typed parameter read through
    both direct indexing (source syntax) and the seq VIEW `(a[..])`
    (decision 1) in the SAME `<==>` needs Dafny to connect `a[k]` and
    `(a[..])[k]` itself -- measured NOT automatic once the surrounding
    `<==>` combines a `forall`-guarded conjunct with an `exists`-guarded
    one (isolated single-guard copies of either half verify with no
    hint at all). `array_view_fact`, threaded into `L_ens`/`L_inv_k`'s
    own `requires`, states this always-true fact once.
    `dafny-synthesis_task_id_433.dfy` (`IsGreater`) is exactly this
    shape: `ensures result ==> forall ...` alongside
    `ensures !result ==> exists ...`. Asserts every lemma verdict is
    `verified` end to end."""
    if not slow:
        print("test_array_view_forall_exists_end_to_end: skipped (pass --slow)")
        return
    dfy_path = test_lifter.CORPUS_DIR / "dafny-synthesis_task_id_433.dfy"
    t0 = time.monotonic()
    fx = _lift_source(dfy_path, "IsGreater", timeout_s=90.0)
    assert fx["status"] == "ok", f"IsGreater lift refused upstream: {fx}"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = lift_check.check(fx["task"], fx["source"], fx["closure"], fx["record"],
                          OUT_DIR / "dafny-synthesis_task_id_433", timeout_s=90.0)
    wall = round(time.monotonic() - t0, 2)
    verdicts = dict(fx["record"].checker_verdicts)
    print(f"test_array_view_forall_exists_end_to_end: IsGreater "
         f"verdicts={json.dumps(verdicts)} "
         f"check_wf={out.refusal is None or out.refusal.reason != 'check-wf-failed'} "
         f"wall_s={wall}")
    assert verdicts, "no lemma verdicts recorded at all"
    non_verified = {k: v for k, v in verdicts.items() if v != "verified"}
    assert not non_verified, f"non-verified lemma verdict(s) on IsGreater: {non_verified}"
    for expected in ("L_req", "L_ens", "L_inv_0"):
        assert expected in verdicts, f"expected lemma {expected!r} missing: {verdicts}"
    checker_path = OUT_DIR / "dafny-synthesis_task_id_433.check.dfy"
    checker_text = checker_path.read_text(encoding="utf-8")
    assert "[..][k]" in checker_text, (
        "L_ens should carry the array-view index fact; "
        f"checker text: {checker_text}")


FAST_TESTS = FAST_TESTS + [test_task_var_inits_recovers_for_desugared_bound]


def test_quantified_call_hint_end_to_end(slow: bool) -> None:
    """2026-09-14, end-to-end companion to
    `test_quantified_fun_call_scoping_and_array_bound`: FindNegativeNumbers
    (dafny-synthesis_task_id_436.dfy) is one of the 22 ROADMAP 16.2's
    unbounded-quantifier row newly classifies, one of the 20 that still
    read `lift-check-failed` afterward -- an `IsNegative(arr[k])` call
    sits inside the loop invariant's own `forall k :: 0 <= k < i ==>
    IsNegative(arr[k]) ==> ...` and, pre-fix, made `build_checker` paste
    `L_fun_isNegative(arr[k_v]);` as a bare statement in `L_inv_0`'s body
    (`unresolved identifier: k_v`). Asserts every lemma verdict is
    `verified`, not merely that the file lifts."""
    if not slow:
        print("test_quantified_call_hint_end_to_end: skipped (pass --slow)")
        return
    dfy_path = test_lifter.CORPUS_DIR / "dafny-synthesis_task_id_436.dfy"
    t0 = time.monotonic()
    fx = _lift_source(dfy_path, "FindNegativeNumbers", timeout_s=90.0)
    assert fx["status"] == "ok", f"FindNegativeNumbers lift refused upstream: {fx}"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    lift_check.check(fx["task"], fx["source"], fx["closure"], fx["record"],
                     OUT_DIR / "dafny-synthesis_task_id_436", timeout_s=90.0)
    wall = round(time.monotonic() - t0, 2)
    verdicts = dict(fx["record"].checker_verdicts)
    print(f"test_quantified_call_hint_end_to_end: FindNegativeNumbers "
         f"verdicts={json.dumps(verdicts)} wall_s={wall}")
    assert verdicts, "no lemma verdicts recorded at all"
    non_verified = {k: v for k, v in verdicts.items() if v != "verified"}
    assert not non_verified, f"non-verified lemma verdict(s) on FindNegativeNumbers: {non_verified}"
    for expected in ("L_req", "L_ens", "L_inv_0"):
        assert expected in verdicts, f"expected lemma {expected!r} missing: {verdicts}"
    checker_text = (OUT_DIR / "dafny-synthesis_task_id_436.check.dfy").read_text(encoding="utf-8")
    assert "forall" in checker_text.split("lemma L_inv_0", 1)[1].split("lemma", 1)[0], (
        "L_inv_0's own body should re-quantify the IsNegative hint under a "
        f"forall-statement, not paste a bare call: {checker_text}")


def test_spec_fun_array_param_end_to_end(slow: bool) -> None:
    """2026-09-14 (LIFTER-785-RESIDUALS.md, wave O's own "four programs
    refused at the checker"): `_fn_param_views` (row 28's own char/string
    view map for a closure FUNCTION's params) never covered an
    array-typed one, so a spec_fun called with a source array argument
    got the raw `array<int>`-typed name where the lifted spec_fun's
    matching parameter is a `seq<int>` -- measured directly, before the
    fix: "incorrect argument type at index 0 for function parameter
    'a_v' (expected seq<int>, found array<int>)" on `inArray(a, x)` in
    both `L_fun_inArray`'s own `ensures` and `L_ens`'s forall hint call
    (SharedElements). RemoveElements and Intersection are the same
    `inArray`-shaped bug on a different task id; CubeElements has NO
    spec_fun at all -- its own failure is the sibling class fixed
    alongside this one (`loop_views` in the `L_inv_0` build: an
    "alloc-fill" array LOCAL in loop scope, not a param, needs the same
    view). All four are asserted end to end: every lemma verdict
    `verified`."""
    if not slow:
        print("test_spec_fun_array_param_end_to_end: skipped (pass --slow)")
        return
    cases = [
        ("dafny-synthesis_task_id_2", "SharedElements", ("L_req", "L_ens")),
        ("dafny-synthesis_task_id_161", "RemoveElements", ("L_req", "L_ens")),
        ("dafny-synthesis_task_id_249", "Intersection", ("L_req", "L_ens")),
        ("dafny-synthesis_task_id_447", "CubeElements", ("L_req", "L_ens", "L_inv_0")),
    ]
    failures = []
    for file_stem, method_name, expected_lemmas in cases:
        dfy_path = test_lifter.CORPUS_DIR / f"{file_stem}.dfy"
        t0 = time.monotonic()
        fx = _lift_source(dfy_path, method_name, timeout_s=90.0)
        if fx["status"] != "ok":
            failures.append(f"{method_name}: lift refused upstream: {fx}")
            continue
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        lift_check.check(fx["task"], fx["source"], fx["closure"], fx["record"],
                         OUT_DIR / file_stem, timeout_s=90.0)
        wall = round(time.monotonic() - t0, 2)
        verdicts = dict(fx["record"].checker_verdicts)
        print(f"test_spec_fun_array_param_end_to_end: {method_name} "
             f"verdicts={json.dumps(verdicts)} wall_s={wall}")
        if not verdicts:
            failures.append(f"{method_name}: no lemma verdicts recorded at all")
            continue
        non_verified = {k: v for k, v in verdicts.items() if v != "verified"}
        if non_verified:
            failures.append(f"{method_name}: non-verified lemma verdict(s): {non_verified}")
        for expected in expected_lemmas:
            if expected not in verdicts:
                failures.append(f"{method_name}: expected lemma {expected!r} missing: {verdicts}")
    assert not failures, "; ".join(failures)


SLOW_TESTS = [test_seeds_check_end_to_end, test_t7_two_seed_pairs,
             test_inverse_committed_and_corpus, test_array_program_end_to_end,
             test_kernel_unproved_not_folded_into_lift_check_failed,
             test_for_desugared_extra_local_end_to_end,
             test_for_desugared_bound_alignment_with_prior_local,
             test_array_view_forall_exists_end_to_end,
             test_quantified_call_hint_end_to_end,
             test_spec_fun_array_param_end_to_end]


# ===========================================================================
# 2026-09-26: renderer defects measured on the 2026-09-26 lift's check
# stage (154 methods refused `lift-check-failed`, 24 of them because the
# checker file itself did not parse or resolve). One fast test per defect
# class on the printer, and one slow test per class that lifts a minimal
# Dafny program reproducing the construct through the real pipeline and
# checks it.
# ===========================================================================

def _q(kind, binders, rng, body):
    from lift_ast import Quantifier, Param, Type
    return Quantifier(line=1, kind=kind,
                      binders=tuple(Param(line=1, name=b, type=Type(line=1, kind="int"))
                                    for b in binders),
                      attrs=(), range=rng, body=body)


def test_resolver_binder_printed_in_source_form() -> None:
    """rprint prints the trigger rewrite of Triggers/ExprSubstituter.cs:
    `forall i, _t#0 | _t#0 == i + 1 :: 0 <= i < |s| - 1 ==> s[i] <= s[_t#0]`.
    `_t#0` is not a legal identifier ("cannot declare identifier beginning
    with underscore"); the printer must substitute it back."""
    from lift_ast import Ident, Index, Binary, Chain, Implies, Cardinality, IntLit
    i, t0, s = Ident(1, "i"), Ident(1, "_t#0"), Ident(1, "s")
    rng = Chain(1, ("==",), (t0, Binary(1, "+", i, IntLit(1, 1))))
    ante = Chain(1, ("<=", "<"), (IntLit(1, 0), i,
                                  Binary(1, "-", Cardinality(1, s), IntLit(1, 1))))
    body = Implies(1, ante, Chain(1, ("<=",), (Index(1, s, i), Index(1, s, t0))))
    text = lift_check._print_expr(_q("forall", ["i", "_t#0"], rng, body), {})
    assert "_t#" not in text and "#" not in text, text
    assert text == "(forall i: int :: ((0 <= i < (|s| - 1)) ==> (s[i] <= s[(i + 1)])))", text
    # A binder the author wrote, pinned by an equation, is substituted the
    # same way since 2026-09-27 (t/FEATURES-TRACK.md feature 5): the one-point
    # rule is a logical identity, and the lifted side applies it too
    # (`lift_classify._eliminate_defined_binders`), so both sides of
    # L_req/L_ens read `P(E)`. Until then it was left alone.
    j = Ident(1, "j")
    kept = _q("forall", ["i", "j"], Chain(1, ("==",), (j, Binary(1, "+", i, IntLit(1, 1)))),
              Chain(1, ("<=",), (Index(1, s, i), Index(1, s, j))))
    assert lift_check._print_expr(kept, {}) == "(forall i: int :: (s[i] <= s[(i + 1)]))", \
        lift_check._print_expr(kept, {})
    # A quantifier all of whose binders are pinned is its body.
    from lift_ast import NaryBool
    alone = _q("exists", ["j"], None,
               NaryBool(1, "&&", (Chain(1, ("==",), (j, Binary(1, "+", i, IntLit(1, 1)))),
                                  Chain(1, ("<=",), (Index(1, s, i), Index(1, s, j))))))
    assert lift_check._print_expr(alone, {}) == "(s[i] <= s[(i + 1)])", lift_check._print_expr(alone, {})
    print("test_resolver_binder_printed_in_source_form: ok")


def test_split_quantifier_rejoined() -> None:
    """rprint prints Triggers/QuantifierSplitter.cs's split of `forall i ::
    0 <= i < |s| ==> 1 <= s[i] <= 100` as `(A ==> 1 <= s[i]) && (A ==>
    s[i] <= 100)`, which is not compilable in a compiled predicate. The
    printer rejoins parts that share one antecedent (forall) or one
    leading conjunct (exists); different antecedents stay split."""
    from lift_ast import Ident, Index, Chain, Implies, NaryBool, Cardinality, IntLit
    i, s = Ident(1, "i"), Ident(1, "s")
    ante = Chain(1, ("<=", "<"), (IntLit(1, 0), i, Cardinality(1, s)))
    b1 = Chain(1, ("<=",), (IntLit(1, 1), Index(1, s, i)))
    b2 = Chain(1, ("<=",), (Index(1, s, i), IntLit(1, 100)))
    split = NaryBool(1, "&&", (Implies(1, ante, b1), Implies(1, ante, b2)))
    text = lift_check._print_expr(_q("forall", ["i"], None, split), {})
    assert text == ("(forall i: int :: ((0 <= i < |s|) ==> "
                    "((1 <= s[i]) && (s[i] <= 100))))"), text
    ex = NaryBool(1, "||", (NaryBool(1, "&&", (ante, b1)), NaryBool(1, "&&", (ante, b2))))
    text = lift_check._print_expr(_q("exists", ["i"], None, ex), {})
    assert text == ("(exists i: int :: ((0 <= i < |s|) && "
                    "((1 <= s[i]) || (s[i] <= 100))))"), text
    other = Chain(1, ("<",), (i, IntLit(1, 3)))
    mixed = NaryBool(1, "&&", (Implies(1, ante, b1), Implies(1, other, b2)))
    text = lift_check._print_expr(_q("forall", ["i"], None, mixed), {})
    assert text.count("==>") == 2, text
    print("test_split_quantifier_rejoined: ok")


def test_call_guard_substitution_respects_binders() -> None:
    """`CalcBal(s, i, j, acc)` requires `forall i :: 0 <= i < |s| ==> ...`.
    Substituting the call `CalcBal(s1, 0, k, 0)` must leave the bound `i`
    alone (it printed `forall 0: int`, "invalid Ident", humaneval_dafny_119
    match_parens), and a bound variable that occurs free in an argument is
    renamed rather than capturing it."""
    from lift_ast import (FunctionDecl, Param, Type, RequiresClause, Ident, Index, Call,
                          Chain, Implies, Cardinality, IntLit)
    i, s = Ident(1, "i"), Ident(1, "s")
    q = _q("forall", ["i"], None,
           Implies(1, Chain(1, ("<=", "<"), (IntLit(1, 0), i, Cardinality(1, s))),
                   Chain(1, ("==",), (Index(1, s, i), IntLit(1, 40)))))
    t = Type(line=1, kind="int")
    fd = FunctionDecl(line=1, name="CalcBal", ghost=False,
                      params=(Param(1, "s", Type(line=1, kind="seq", args=(t,))),
                              Param(1, "i", t), Param(1, "j", t)),
                      ret_type=t, specs=(RequiresClause(1, q),), body=IntLit(1, 0))
    call = Call(1, Ident(1, "CalcBal"), (Ident(1, "s1"), IntLit(1, 0), Ident(1, "k")))
    g = lift_check._call_guard(fd, call, {})
    assert g == "((forall i: int :: ((0 <= i < |s1|) ==> (s1[i] == 40))))", g
    call2 = Call(1, Ident(1, "CalcBal"), (Index(1, Ident(1, "t"), Ident(1, "i")),
                                          IntLit(1, 0), IntLit(1, 1)))
    g2 = lift_check._call_guard(fd, call2, {})
    assert "forall i_b0: int" in g2 and "t[i][i_b0]" in g2, g2
    print("test_call_guard_substitution_respects_binders: ok")


def test_char_valued_function_result_viewed() -> None:
    """A closure function returning `char` is compared against the lifted
    spec_fun's `int` through `as int` (DafnyRef 5.2.6); a `seq<char>`
    parameter or return maps to the string view like `string` does."""
    from lift_ast import Type
    ch = Type(line=1, kind="char")
    assert lift_check._src_result_text("f_src(a)", ch) == "(f_src(a) as int)"
    assert lift_check._src_result_text("g_src(a)", Type(line=1, kind="int")) == "g_src(a)"
    seq_char = Type(line=1, kind="seq", args=(ch,))
    assert lift_check._view_kind_for_type(seq_char) == "string"
    txt = lift_check._src_result_text("h_src(a)", seq_char)
    assert txt.startswith("(var r_src := h_src(a); (seq(|r_src|,"), txt
    print("test_char_valued_function_result_viewed: ok")


def test_worst_block_is_the_lemma_verdict() -> None:
    """dafny prints a lemma's `(correctness)` and `(well-formedness)`
    blocks in completion order. The verdict is the worst block, and a
    failing symbol that is not a named lemma is recorded by name
    (humaneval_dafny_038 encode_cyclic: every lemma read `verified` in a
    file dafny finished with 2 errors)."""
    canned = "\n".join([
        "x.dfy(37,0): Error: a postcondition could not be proved on this return path",
        "Dafny program verifier finished with 8 verified, 2 errors",
        "Results for L_req (correctness)", "  Overall outcome: Correct",
        "Results for L_ens (correctness)", "  Overall outcome: Errors",
        "Results for L_ens (well-formedness)", "  Overall outcome: Correct",
        "Results for helper_src (well-formedness)", "  Overall outcome: Errors",
        "Results for Demo (correctness)", "  Overall outcome: Errors",
    ])
    saved = lift_check._run_dafny
    lift_check._run_dafny = lambda args, timeout_s: (4, canned)
    try:
        verdicts, code, ok, first_bad, _w, lowered = lift_check._verify_checker(
            Path("x.dfy"), ["L_req", "L_ens"], 10.0, "Demo")
    finally:
        lift_check._run_dafny = saved
    assert not ok and code == 4, (ok, code)
    assert verdicts["L_ens"] == "unproved", verdicts
    assert verdicts["L_req"] == "verified", verdicts
    assert verdicts.get("helper_src (well-formedness)") == "unproved", verdicts
    assert "Demo (correctness)" not in verdicts and lowered == "unproved", (verdicts, lowered)
    assert first_bad == "L_ens", first_bad
    print("test_worst_block_is_the_lemma_verdict: ok")


# Minimal Dafny programs, one per defect class, each reproducing the
# construct that made the 2026-09-26 checker file fail. Before the fix
# every one of them produced a checker file dafny refused to resolve
# (exit 2) or a lemma it could not prove.
MINIMAL_PROGRAMS = {
    "resolver_binder": ("Pick", """
predicate IsSorted(s: seq<int>)
{
  forall i :: 0 <= i < |s| - 1 ==> s[i] <= s[i + 1]
}
method Pick(s: seq<int>) returns (r: int)
  requires IsSorted(s)
  ensures r >= 0
{
  r := 0;
}
"""),
    "split_quantifier": ("Count", """
predicate Valid(s: seq<int>)
{
  forall i :: 0 <= i < |s| ==> 1 <= s[i] <= 100
}
method Count(s: seq<int>) returns (c: int)
  requires Valid(s)
  ensures c >= 0
{
  c := 0;
}
"""),
    "seq_char_param": ("FirstIsA", """
method FirstIsA(x: seq<char>) returns (r: bool)
  ensures r <==> (|x| > 0 && x[0] == 'a')
{
  r := |x| > 0 && x[0] == 'a';
}
"""),
    "char_result": ("Apply", """
function Flip(a: char): char
  requires a == '0' || a == '1'
{
  if a == '0' then '1' else '0'
}
method Apply(a: char) returns (r: char)
  requires a == '0' || a == '1'
  ensures r == Flip(a)
{
  r := Flip(a);
}
"""),
    "guard_binder": ("Total", """
function Sum(s: seq<int>, i: int, j: int): int
  requires forall i :: 0 <= i < |s| ==> s[i] >= 0
  requires 0 <= i <= j <= |s|
  decreases j - i
{
  if i == j then 0 else s[j - 1] + Sum(s, i, j - 1)
}
method Total(s: seq<int>) returns (b: int)
  requires forall k :: 0 <= k < |s| ==> s[k] >= 0
  ensures b == Sum(s, 0, |s|)
{
  b := 0;
  var j := 0;
  while j < |s|
    invariant 0 <= j <= |s|
    invariant b == Sum(s, 0, j)
  {
    b := b + s[j];
    j := j + 1;
  }
}
"""),
}


def test_minimal_programs_check(slow: bool) -> None:
    if not slow:
        print("test_minimal_programs_check: skipped (pass --slow)")
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    failures = []
    for tag, (method, text) in MINIMAL_PROGRAMS.items():
        src = OUT_DIR / f"minimal_{tag}.dfy"
        src.write_text(text.lstrip(), encoding="utf-8")
        fx = _lift_source(src, method, timeout_s=120.0)
        if fx["status"] != "ok":
            failures.append(f"{tag}: refused upstream {fx['stage']}: {fx['detail']}")
            continue
        out = lift_check.check(fx["task"], fx["source"], fx["closure"], fx["record"],
                               OUT_DIR / f"minimal_{tag}", timeout_s=300.0)
        rec = fx["record"]
        code = rec.dafny_exit_codes.get("verify-checker")
        print(f"  {tag}: verify-checker exit {code}, refusal {out.refusal}, "
              f"verdicts {rec.checker_verdicts}, diff {rec.differential_verdict}")
        if out.refusal is not None:
            failures.append(f"{tag}: {out.refusal} {rec.checker_verdicts}")
        elif not (rec.differential_verdict or "").startswith("agrees on"):
            failures.append(f"{tag}: differential {rec.differential_verdict}")
    assert not failures, "; ".join(failures)
    print("test_minimal_programs_check: ok")


FAST_TESTS += [test_resolver_binder_printed_in_source_form, test_split_quantifier_rejoined,
               test_call_guard_substitution_respects_binders,
               test_char_valued_function_result_viewed, test_worst_block_is_the_lemma_verdict]
SLOW_TESTS += [test_minimal_programs_check]


_CALLEE_SRC = """
method Helper(x: int) returns (h: int)
  requires x >= 0
  ensures h == x
{
  h := x;
}

method Caller(x: int) returns (r: int)
  requires x >= 0
  ensures r == x
{
  var t := Helper(x);
  r := t;
}
"""


def test_method_callees_checked_end_to_end() -> None:
    """Row 37 (methods as callees): `check` checks each callee method on
    its own before the caller -- its L_req/L_ens against the SOURCE
    callee's contract -- because a caller's proof uses only the callee's
    contract. (a) The honest lift passes, with `Helper/L_req` and
    `Helper/L_ens` verified on the caller's record. (b) A callee whose
    lifted ensures is wrong (`h == x + 1`, in both the callee task and the
    caller's `methods` entry) is caught: `lift-check-failed`, token
    `Helper:L_ens`. (c) A caller whose `methods` entry is not the checked
    callee is refused `method-entry-mismatch` before any dafny runs.
    Runs dafny when it is installed (two short verify runs and two
    `dafny run`s), else prints skipped."""
    import copy
    import dataclasses
    import tempfile
    from verifiers.dafny import DAFNY

    module = lift_parse.parse(_CALLEE_SRC)
    caller = next(m for m in lift_parse.gradable_methods(module) if m.name == "Caller")
    plan = lift_classify.classify(module, caller)
    assert not isinstance(plan, Refusal), plan
    rr = lift_rewrite.rewrite(module, plan, "unit.dfy", "0" * 64)
    assert rr.refusal is None and [c.name for c in rr.callees] == ["Helper"], rr

    # (c) needs no prover.
    bad_task = copy.deepcopy(rr.task)
    bad_task["methods"][0]["ensures"] = [{"bool": True}]
    with tempfile.TemporaryDirectory() as d:
        out = lift_check.check(bad_task, plan.method, plan.closure,
                               copy.deepcopy(rr.record), Path(d) / "c.dfy",
                               callees=rr.callees)
    assert out.refusal is not None and out.refusal.reason == "method-entry-mismatch", out.refusal

    if DAFNY is None:
        print("test_method_callees_checked_end_to_end: (a)/(b) skipped (no dafny)")
        return

    with tempfile.TemporaryDirectory() as d:
        out = lift_check.check(rr.task, plan.method, plan.closure, rr.record,
                               Path(d) / "a.dfy", callees=rr.callees)
    assert out.refusal is None, out.refusal
    v = out.record.checker_verdicts
    assert v.get("Helper/L_req") == "verified" and v.get("Helper/L_ens") == "verified", v
    assert v.get("L_ens") == "verified", v

    wrong = {"op": "==", "args": [{"var": "h"},
                                  {"op": "+", "args": [{"var": "x"}, {"int": 1}]}]}
    cl = rr.callees[0]
    assert cl.task["ensures"] and cl.task["returns"][0]["name"] == "h", cl.task
    bad_cl_task = copy.deepcopy(cl.task)
    bad_cl_task["ensures"] = [wrong]
    bad_cl = dataclasses.replace(cl, task=bad_cl_task, record=copy.deepcopy(cl.record))
    bad_task = copy.deepcopy(rr.task)
    bad_task["methods"] = [lift_rewrite._method_entry(bad_cl_task)]
    with tempfile.TemporaryDirectory() as d:
        out = lift_check.check(bad_task, plan.method, plan.closure,
                               copy.deepcopy(rr.record), Path(d) / "b.dfy",
                               callees=(bad_cl,))
    assert out.refusal is not None and out.refusal.reason == "lift-check-failed", out.refusal
    assert out.refusal.token == "Helper:L_ens", out.refusal
    print("test_method_callees_checked_end_to_end: honest lift checks (Helper/L_req, "
          "Helper/L_ens verified); a wrong callee ensures refuses lift-check-failed "
          "Helper:L_ens; a mismatched methods entry refuses method-entry-mismatch")


FAST_TESTS += [test_method_callees_checked_end_to_end]


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
