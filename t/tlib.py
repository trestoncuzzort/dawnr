"""t/tlib.py: the harness as a library (ROADMAP 15.1).

`run_par.py` and `run_all.py` are drivers: they own a task directory, a
table file, and an out/ a whole suite run writes into. An editor owns
neither -- it has one task at a time, changing under a human's hands, and
it needs an answer in-process, not a subprocess and a markdown table.

    verify(task, kernels=None, flake=3, budget=None) -> {kernel: {...}}
    twin(task) -> (twin_body, operator, witness)
    lower(task, kernel, twin=False) -> source text
    explain(verdict) -> one sentence per kernel

Caching: every verdict is looked up in t/cache.py before any kernel runs,
keyed by the lowered source's sha256, the kernel's own version string, and
the budget, so an unchanged task, unchanged kernel, unchanged budget costs
no kernel run on the second call, in this process or the next one. A cache
entry is written only after a full flake_check agreement (n=`flake` runs
agree) -- SPEC.md's flake discipline is not relaxed for the cache: nothing
provisional is ever cached, and nothing provisional is ever what a cache
hit reports back, because a cache hit is never provisional (see `_side`).

Isolation from run_par.py: a table run's out/ (harness.OUT, or run_par's
--out) is a lock-protected directory (verifiers.acquire_run_lock) that one
suite run owns for its duration. The library never touches it. Lowered
sources for a verify() call go under out/lib/<source_sha>/, named by the
content that produced them, so two callers computing the same source write
the same bytes to the same path (idempotent, not a race) and no caller
ever needs the run lock: table runs and library calls write to disjoint
directories by construction, which is the "run lock relaxed" ROADMAP 15.1
asks for -- relaxed by not being shared, not by being removed.
"""
from __future__ import annotations

import hashlib
import importlib
from pathlib import Path

import cache
import harness
from verifiers import Outcome, flake_check

HERE = Path(__file__).resolve().parent

# Mirrors run_par.py's BACKENDS list (name, lowering module, file suffix).
# Duplicated rather than imported: run_par.py owns its own task-loading and
# argparse main(), and importing it here for one tuple would couple tlib.py
# to a module built to be run, not imported.
BACKENDS = (
    ("dafny", "lower_dafny", "dfy"),
    ("verus", "lower_verus", "rs"),
    ("spark", "lower_spark", "ads"),
    ("framac", "lower_framac", "c"),
    ("lean", "lower_lean", "lean"),
    ("rocq", "lower_rocq", "v"),
    ("fstar", "lower_fstar", "fst"),
)
_LOWER_MOD = {b: (l, s) for b, l, s in BACKENDS}

_VERSIONS: dict[str, str] = {}     # kernel -> version string, once per process


def kernel_version(kernel: str) -> str:
    """The kernel's own --version output, read once per process (per
    ROADMAP 15.1: "kernel version read once per process from each
    verifier's version command"). Raises SystemExit, exactly as the
    backend's version() does, when the kernel is absent -- callers here
    catch it and report the kernel as refused, never crash the whole
    verify() call over one missing kernel."""
    if kernel not in _VERSIONS:
        backend = importlib.import_module(f"verifiers.{kernel}")
        _VERSIONS[kernel] = backend.version()
    return _VERSIONS[kernel]


def twin(task: dict) -> tuple[list | None, str | None, dict | None]:
    """(twin_body, operator, witness), or (None, reason, None) when no rung
    of the ladder produced a witness. harness.twin_cached, so the ladder
    search itself still runs once per task regardless of how many kernels
    or callers ask."""
    return harness.twin_cached(task)


def lower(task: dict, kernel: str, twin_body: bool = False) -> str:
    """The lowered source for `kernel`: the real body by default, or the
    task's twin when `twin_body` is True. Raises ValueError when the task
    has no twin (harness.REFUSALS names why); a caller that wants that
    reason without an exception should call `twin()` first."""
    if kernel not in _LOWER_MOD:
        raise ValueError(f"tlib.lower: unknown kernel {kernel!r}, "
                         f"known: {sorted(_LOWER_MOD)}")
    lmod, _suffix = _LOWER_MOD[kernel]
    lower_fn = importlib.import_module(lmod).lower
    if not twin_body:
        return lower_fn(task, task["body"])
    tb, op, w = twin(task)
    if tb is None:
        raise ValueError(f"{task.get('name', '?')}: no twin "
                         f"({harness.REFUSALS.get(op, op)})")
    return lower_fn(task, tb, witness=w)


def _side(backend, kernel: str, path: Path, key: str, version: str,
          budget, flake: int, cache_dir):
    """One (real- or twin-) source's verdict: a cache hit costs no kernel
    run and is never provisional (only a completed n-of-3 agreement is
    ever written to the cache -- see cache.write's one call site below).
    A miss runs flake_check(n=flake); on agreement the result is cached
    and reported final, on disagreement it is reported provisional and
    NOT cached, so the next call tries again rather than trusting a flake.
    Returns (outcome, was_cached, provisional)."""
    hit = cache.read(kernel, key, cache_dir)
    if hit is not None:
        return hit["outcome"], True, False
    verify_fn = backend.verify if budget is None else (
        lambda p, _b=budget: backend.verify(p, _b))
    result, agreed = flake_check(verify_fn, path, flake)
    if agreed:
        cache.write(kernel, key, {"outcome": result.outcome,
                                  "backend_version": version}, cache_dir)
        return result.outcome, False, False
    return result.outcome, False, True


def _verify_one(task: dict, kernel: str, flake: int, budget,
                out_dir, cache_dir) -> dict:
    entry = {"real": None, "twin": None, "twin_op": None, "witness": "none",
             "provisional": False, "source_sha": None, "kernel_version": None,
             "cached": False}
    try:
        version = kernel_version(kernel)
    except SystemExit as e:
        entry["refused"] = f"kernel absent: {e}"
        return entry
    entry["kernel_version"] = version

    tb, op, w = twin(task)
    entry["twin_op"] = op
    entry["witness"] = harness.witness(w)
    if tb is None:
        entry["refused"] = harness.REFUSALS[op]
        return entry

    lmod, suffix = _LOWER_MOD[kernel]
    lower_fn = importlib.import_module(lmod).lower
    real_src = lower_fn(task, task["body"])
    twin_src = lower_fn(task, tb, witness=w)
    real_sha = hashlib.sha256(real_src.encode("utf-8")).hexdigest()
    entry["source_sha"] = real_sha

    lib_dir = Path(out_dir) if out_dir is not None else (
        HERE / "out" / "lib" / real_sha)
    lib_dir.mkdir(parents=True, exist_ok=True)
    real_path = lib_dir / f"{task['name']}.{suffix}"
    twin_path = lib_dir / f"{task['name']}_twin.{suffix}"
    real_path.write_text(real_src, encoding="utf-8", newline="\n")
    twin_path.write_text(twin_src, encoding="utf-8", newline="\n")

    backend = importlib.import_module(f"verifiers.{kernel}")
    real_key = cache.key_for(real_src, kernel, version, budget)
    twin_key = cache.key_for(twin_src, kernel, version, budget)
    r_outcome, r_cached, r_prov = _side(
        backend, kernel, real_path, real_key, version, budget, flake, cache_dir)
    t_outcome, t_cached, t_prov = _side(
        backend, kernel, twin_path, twin_key, version, budget, flake, cache_dir)

    entry["real"] = r_outcome
    entry["twin"] = t_outcome
    entry["provisional"] = r_prov or t_prov
    entry["cached"] = r_cached and t_cached
    return entry


def verify(task: dict, kernels: list[str] | None = None, flake: int = 3,
          budget=None, out_dir=None, cache_dir=None) -> dict[str, dict]:
    """The library entry point: {kernel: {real, twin, twin_op, witness,
    provisional, source_sha, kernel_version, cached}}, one entry per
    kernel in `kernels` (default: every kernel in BACKENDS, in order,
    each reporting itself absent rather than raising when its binary is
    not on this box).

    `provisional` is True exactly when the flake_check for the real
    source, the twin source, or both ran but its n=`flake` runs did not
    all agree -- the editor's signal (ROADMAP 15.1) to show the verdict as
    unconfirmed rather than write it anywhere a table reads from.
    `cached` is True exactly when BOTH sides came from t/cache.py, i.e.
    this call ran no kernel at all.

    `budget` is passed through to every backend's verify(path, budget) when
    given; left at each backend's own default (None) otherwise, matching
    run_par.py and run_all.py, which never pass one either."""
    names = kernels if kernels is not None else [b for b, _, _ in BACKENDS]
    return {k: _verify_one(task, k, flake, budget, out_dir, cache_dir
                           if cache_dir is not None else cache.DEFAULT_CACHE_DIR)
           for k in names}


_OUTCOME_SENTENCE = {
    Outcome.VERIFIED: "a real proof",
    Outcome.VACUOUS: "accepted, but for the wrong reason",
    Outcome.REFUTED: "refuted, the kernel found this wrong",
    Outcome.MALFORMED: "does not parse or resolve, not a proof failure",
    Outcome.TIMEOUT: "timed out, budget exhausted, not known wrong",
    Outcome.UNPROVED: "the solver gave up without exhausting its budget or "
                      "finding a countermodel",
    Outcome.TOOL_ERROR: "a tool error, never evidence of anything",
}


def _sentence(entry: dict) -> str:
    if entry.get("real") is None:
        return f"no twin, {entry.get('refused', 'refused')}"
    r, t = entry["real"], entry["twin"]
    flip = r == Outcome.VERIFIED and t == Outcome.REFUTED
    verdict = "COUNTS" if flip else "REFUSED"
    tail = "; provisional, n has not yet agreed" if entry.get("provisional") else ""
    return (f"{verdict}, real is {_OUTCOME_SENTENCE.get(r, r)}; "
           f"{entry.get('twin_op')} twin is {_OUTCOME_SENTENCE.get(t, t)}{tail}")


def explain(verdict: dict) -> dict[str, str] | str:
    """One sentence per kernel, from the verifiers' own Outcome vocabulary
    (verifiers.Outcome, not a second taxonomy invented here). `verdict` is
    either the {kernel: entry} dict verify() returns, or a single entry
    (has a "real" or "refused" key) -- the latter returns one bare
    sentence, the former a dict of `kernel: "<kernel>: <sentence>"`."""
    if "real" in verdict or "refused" in verdict:
        return _sentence(verdict)
    return {k: f"{k}: {_sentence(e)}" for k, e in verdict.items()}
