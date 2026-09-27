#!/usr/bin/env python3
"""test_framac_seq_fun.py: SPEC.md "Seq-valued spec_funs (v1)", Frama-C's
\\list route (2026-09-27, t/FEATURES-SEQFUN-2026-09-27.md "Frama-C, the
\\list route"). lower_framac.py no longer abstains by name on a seq-
valued spec_fun: it states one as a recursive ACSL logic function
returning \\list<integer> (built-in \\Nil/\\Cons/\\concat, `spec_fun_acsl`'s
own new branch and `list_term`), and bridges a buffer-typed seq value to
one at every `==`/`len`/`at` site through ACSL's own built-in `\\length`/
`\\nth` (`_seq_len_render`/`_seq_at_render`/`defs`'s own new `call`
cases) -- no bridge PREDICATE symbol of its own is needed, since
`\\length`/`\\nth` already relate a `\\list` to whatever is compared
against it. What the route does not reach (a seq-typed spec_fun
PARAMETER passed through unchanged, `update`/`fill` inside a seq-valued
body, anything `list_term` does not name) still abstains by name.

This file is text-level and byte-identity by default (no prover needed);
`--slow` additionally runs the real prover on double_all, the four
`fz_p_sf_seq_*` probes and three faults seeded here into a seq-valued
spec_fun's own body (an off-by-one slice, a dropped element, a swapped
concatenation -- t/FEATURES-SEQFUN-2026-09-27.md's own three categories),
checking every twin refutes and every seeded fault reads refuted or
unproved, NEVER verified.

Run: python3 t/test_framac_seq_fun.py [--slow]   (or pytest)
"""
from __future__ import annotations

import copy
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import check_wf     # noqa: E402
import fuzz_lower   # noqa: E402
import harness      # noqa: E402
import lower_framac  # noqa: E402
import surface      # noqa: E402
import tlib         # noqa: E402

FIXTURES = ("fz_p_sf_seq_len", "fz_p_sf_seq_at", "fz_p_sf_seq_build",
            "fz_p_sf_seq_false", "fz_p_sf_seq_swap", "fz_p_sf_seq_slice_off")


def _committed() -> dict:
    return surface.parse_file(os.path.join(HERE, "tasks", "double_all.t"))


def _probes() -> dict:
    return {p["name"]: {k: v for k, v in p.items() if not k.startswith("_")}
            for p in fuzz_lower.probes() if p["name"] in FIXTURES}


def test_double_all_states_the_list_route() -> None:
    """The recursive \\list<integer> definition, the buffer<->list bridge
    at the loop invariant's `==` (elementwise over `\\nth`/`\\length`,
    no `predicate` symbol of its own), and the append lemmas
    (`T_SEQ_LIST_LEMMAS_ACSL`, provable in isolation from ACSL's own
    built-in list theory, Frama-C kernel_internals/typing/
    logic_builtin.ml / WP's Vlist.ml -- never an unproven axiom)."""
    task = _committed()
    real = tlib.lower(task, "framac", twin_body=False)
    assert ("logic \\list<integer> dbl{L}(int *s, integer s_n, integer n) ="
            in real), real
    assert "\\Nil" in real and "\\Cons(" in real and "\\concat(" in real
    assert ("\\length(dbl{Here}(s, s_n, i))" in real
            and "\\nth(dbl{Here}(s, s_n, i), __k)" in real), real
    assert "lemma t_list_append_length{L}:" in real
    assert "lemma t_list_append_nth{L}:" in real
    assert "lemma t_list_append_last{L}:" in real
    twin = tlib.lower(task, "framac", twin_body=True)
    assert "t_refutation_certificate" in twin
    print("test_double_all_states_the_list_route: ok")


def test_slice_bodied_spec_fun_gets_the_range_helper() -> None:
    """`tl`'s own body (`fz_p_sf_seq_len`/`_at`/`_build`/`_slice_off`)
    slices a real buffer parameter directly (`list_term`'s `slice`
    case): `T_SEQ_OF_RANGE_ACSL`, gated by `_has_seq_slice_sf`, appears;
    `double_all`'s own `dbl` never slices, so its file has no
    `t_seq_of_range` at all (`_has_seq_slice_sf` is False)."""
    probes = _probes()
    real = tlib.lower(probes["fz_p_sf_seq_at"], "framac", twin_body=False)
    assert "logic \\list<integer> t_seq_of_range{L}" in real, real
    assert "lemma t_seq_of_range_terminates:" in real
    dbl_real = tlib.lower(_committed(), "framac", twin_body=False)
    assert "t_seq_of_range" not in dbl_real, dbl_real
    print("test_slice_bodied_spec_fun_gets_the_range_helper: ok")


def test_probes_lower_in_framac() -> None:
    """Every fixture (real, and its twin where one exists) lowers to
    text -- the wholesale `NotImplementedError` this pass removes."""
    probes = _probes()
    for name, p in probes.items():
        real = tlib.lower(p, "framac", twin_body=False)
        assert isinstance(real, str) and real, (name, real)
        tb, _, _ = tlib.twin(p)
        if tb is not None:
            twin = tlib.lower(p, "framac", twin_body=True)
            assert isinstance(twin, str) and "t_refutation_certificate" in twin
    print("test_probes_lower_in_framac: ok")


def test_check_wf_and_committed_tasks_unaffected() -> None:
    """Byte identity, the in-tree half (the report's own sha256 sweep
    over t/tasks, t/lemmas, t/nested against r12-blockers is the number
    that matters; this checks the GATE that makes it true): every
    committed task other than double_all declares no seq-valued
    spec_fun, so every code path this pass adds (`_has_seq_result_sf`,
    `_has_seq_slice_sf`, the abstain removed in `lower()`, `spec_fun_acsl`'s
    seq branch, `_seq_len_render`/`_seq_at_render`/`defs`'s `call` cases,
    `_cev_call`'s seq branch) is gated on a spec_fun whose result is
    "seq", unreachable for any of them."""
    assert check_wf.check_wf(_committed()) == []
    n = 0
    for d in ("tasks", "lemmas", "nested"):
        for path in sorted(glob.glob(os.path.join(HERE, d, "*.t"))):
            task = surface.parse_file(path)
            seq_sf = [f["name"] for f in task.get("spec_funs", [])
                      if f["result"] == "seq"]
            if os.path.basename(path) != "double_all.t":
                assert not seq_sf, (path, seq_sf)
            for twin in (False, True):
                try:
                    tlib.lower(task, "framac", twin_body=twin)
                except (NotImplementedError, ValueError):
                    pass           # a named abstain, or a task with no twin
                n += 1
    assert n > 0
    print(f"test_check_wf_and_committed_tasks_unaffected: ok ({n} lowerings)")


def _seed_dropped_element() -> dict:
    """A seeded fault of our own, category "dropped element"
    (t/FEATURES-SEQFUN-2026-09-27.md "The review and the seeded faults"):
    `double_all`'s own `dbl`, with the recursive step's own appended
    element dropped -- `dbl(s, n) = dbl(s, n - 1)` alone, so `dbl`
    evaluates to `[]` for every `n`. check_wf still accepts it (the
    shape is well-typed; only its VALUE is wrong), and the loop's own
    body still appends `2 * s[i]` each iteration, so the real program's
    own `ensures r == dbl(s, len(s))` is false as soon as `s` is
    non-empty."""
    task = copy.deepcopy(_committed())
    task["name"] = "seed_dropped_element"
    sf = task["spec_funs"][0]
    dropped = sf["body"]["ite"]["else"]
    assert dropped["op"] == "+", dropped   # concat(rec-call, [2 * s[n-1]])
    sf["body"]["ite"]["else"] = dropped["args"][0]
    return task


def _seed_swapped_concat() -> dict:
    """Category "swapped concatenation": `dbl`'s recursive step prepends
    the new element instead of appending it (the shape
    `fz_p_sf_seq_swap`'s own `_SF_DBL_SWAPPED` already probes, built
    independently here from `double_all`'s own task)."""
    task = copy.deepcopy(_committed())
    task["name"] = "seed_swapped_concat"
    sf = task["spec_funs"][0]
    rec_call, singleton = sf["body"]["ite"]["else"]["args"]
    sf["body"]["ite"]["else"] = {"op": "+", "args": [singleton, rec_call]}
    return task


def _seed_offbyone_slice() -> dict:
    """Category "off-by-one slice": `fz_p_sf_seq_build`'s own `tl`,
    `slice(s, 1, len(s))` (drop the FIRST element) mutated to
    `slice(s, 0, len(s) - 1)` (drop the LAST instead) -- the same shape
    `fz_p_sf_seq_slice_off` already probes, built independently here."""
    task = copy.deepcopy(_probes()["fz_p_sf_seq_build"])
    task["name"] = "seed_offbyone_slice"
    sf = task["spec_funs"][0]
    then_branch = sf["body"]["ite"]["then"]
    assert then_branch["op"] == "slice", then_branch
    s_arg, _, hi = then_branch["args"]
    sf["body"]["ite"]["then"] = {
        "op": "slice", "args": [s_arg, {"int": 0},
                                {"op": "-", "args": [hi, {"int": 1}]}]}
    return task


SEEDED = {"seed_dropped_element": _seed_dropped_element,
          "seed_swapped_concat": _seed_swapped_concat,
          "seed_offbyone_slice": _seed_offbyone_slice}


def test_seeded_faults_lower_and_check_wf() -> None:
    """The three seeded faults (own-body bugs, not a task-side twin
    mutation) are well-formed and each has a real witness the
    interpreter itself finds against the task's OWN `ensures` (harness.
    real_witness, the conformance suite's no-twin path -- SPEC.md's twin
    never touches a spec_fun, so these faults need no twin at all)."""
    for name, build in SEEDED.items():
        task = build()
        assert check_wf.check_wf(task) == [], (name, check_wf.check_wf(task))
        w = harness.real_witness(task)
        assert w is not None and w.get("_ens") is True, (name, w)
        real = lower_framac.lower(task, task["body"], witness=w)
        assert isinstance(real, str) and "t_refutation_certificate" in real
        print(f"  {name}: witness {w}")
    print("test_seeded_faults_lower_and_check_wf: ok")


def _framac_verify(path):
    from pathlib import Path
    from verifiers import framac as framac_backend
    return framac_backend.verify(Path(path))


def test_kernels_verify_the_fixtures(slow: bool) -> None:
    """The real prover (frama-c 33 / alt-ergo, `t/verifiers/discover.py`'s
    own pinned pair): every twin here REFUTES -- the soundness property
    that matters most, no false `verified` anywhere -- and every real
    side either verifies or reads an honest `unproved`/`timeout`, never
    a wrong verdict. Measured 2026-09-27 (the desktop, CPU only): seven
    of seven tested twins (double_all + the four probes with one +
    itself has none, `fz_p_sf_seq_false`) refute; `fz_p_sf_seq_at`'s real
    side verifies outright; double_all's own real side and the other
    three probes' real sides read `timeout` (WP/alt-ergo's own
    automation gap for a loop-carried or slice-derived \\list fact under
    the task's other hypotheses, not a soundness gap -- "Frama-C, the
    \\list route" in t/FEATURES-SEQFUN-2026-09-27.md has the full
    account). The three seeded faults here each read `refuted` or
    `unproved` on their real side, never `verified`."""
    if not slow:
        print("test_kernels_verify_the_fixtures: skipped (pass --slow)")
        return
    import tempfile
    from verifiers import framac as framac_backend
    if not framac_backend.FRAMAC:
        print("test_kernels_verify_the_fixtures: skipped (frama-c absent)")
        return
    with tempfile.TemporaryDirectory() as d:
        results = {}
        task = _committed()
        for twin in (False, True):
            path = os.path.join(d, f"double_all_{'twin' if twin else 'real'}.c")
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(tlib.lower(task, "framac", twin_body=twin))
            r = _framac_verify(path)
            results[f"double_all/{'twin' if twin else 'real'}"] = r.outcome
        assert results["double_all/twin"] == "refuted", results
        probes = _probes()
        for name, p in probes.items():
            path = os.path.join(d, f"{name}_real.c")
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(tlib.lower(p, "framac", twin_body=False))
            r = _framac_verify(path)
            results[f"{name}/real"] = r.outcome
            tb, _, _ = tlib.twin(p)
            if tb is not None:
                tpath = os.path.join(d, f"{name}_twin.c")
                with open(tpath, "w", encoding="utf-8", newline="\n") as f:
                    f.write(tlib.lower(p, "framac", twin_body=True))
                rt = _framac_verify(tpath)
                results[f"{name}/twin"] = rt.outcome
                assert rt.outcome == "refuted", (name, rt.outcome, rt.error)
        assert results["fz_p_sf_seq_at/real"] == "verified", results
        for name, build in SEEDED.items():
            task = build()
            w = harness.real_witness(task)
            path = os.path.join(d, f"{name}.c")
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(lower_framac.lower(task, task["body"], witness=w))
            r = _framac_verify(path)
            results[name] = r.outcome
            assert r.outcome in ("refuted", "unproved", "timeout"), \
                (name, r.outcome, r.error)
            assert r.outcome != "verified", (name, "a seeded fault verified")
        print(json.dumps(results, indent=1, sort_keys=True))
    print("test_kernels_verify_the_fixtures: ok")


def run(slow: bool = False) -> None:
    test_double_all_states_the_list_route()
    test_slice_bodied_spec_fun_gets_the_range_helper()
    test_probes_lower_in_framac()
    test_check_wf_and_committed_tasks_unaffected()
    test_seeded_faults_lower_and_check_wf()
    test_kernels_verify_the_fixtures(slow)
    print("test_framac_seq_fun: ok")


if __name__ == "__main__":
    run("--slow" in sys.argv[1:])
