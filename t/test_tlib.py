"""Plain-python tests for t/tlib.py and t/cache.py (ROADMAP 15.1, "The
harness as a library, with a cache", 2026-09-11).

Runs dafny only (the one kernel every t/tasks/*.json task lowers to, and
the DONE WHEN's own measurement: "verify(abs) twice ... the second call
runs no kernel"), over a private cache/out directory pair under a
TemporaryDirectory so this test never reads or writes the real
t/out/cache or t/out/lib, and never races run_par.py or another run of
itself over shared state.

Two things pinned here as regression tests:
  (a) verify(task) called twice in one process: the first call is
      uncached and runs dafny (verifiers.LAUNCHES advances); the second
      call, same task, same private cache dir, is cached=True,
      provisional=False, and launches nothing (verifiers.LAUNCHES is
      unchanged).
  (b) the SAME private cache dir read fresh in a second process (a
      subprocess.run of a small script) sees the cache the first process
      wrote: cached=True there too, no dafny launch in that process
      either (its own LAUNCHES counter, printed, is 0).
  (c) a flaked (disagreeing) flake_check is never cached and is reported
      provisional=True -- exercised directly against t/cache.py plus a
      stub backend, no kernel involved, so this check is fast and
      deterministic.

Requires dafny on PATH (export PATH per t/README.md before running this
file, exactly as every other kernel-touching test in t/).

Run as: cd <repo>/t && python3 test_tlib.py
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

import harness
import tasks_io
import tlib
import verifiers
from verifiers import Result, Outcome

HERE = Path(__file__).resolve().parent

UNIT_TESTS = []


def test(fn):
    UNIT_TESTS.append(fn)
    return fn


@test
def test_second_call_same_process_runs_no_kernel():
    task = harness.load(tasks_io.find(HERE / "tasks", "abs"))
    with tempfile.TemporaryDirectory(prefix="t-tlib-test-") as td:
        cache_dir = Path(td) / "cache"
        out_dir = Path(td) / "lib"
        verifiers.reset_launch_count()
        v1 = tlib.verify(task, kernels=["dafny"],
                         cache_dir=cache_dir, out_dir=out_dir)
        launches_first = verifiers.LAUNCHES
        assert launches_first > 0, "first call must run dafny"
        e1 = v1["dafny"]
        assert e1["real"] == Outcome.VERIFIED, e1
        assert e1["twin"] == Outcome.REFUTED, e1
        assert e1["cached"] is False, e1
        assert e1["provisional"] is False, e1
        assert e1["kernel_version"], e1

        v2 = tlib.verify(task, kernels=["dafny"],
                         cache_dir=cache_dir, out_dir=out_dir)
        launches_second = verifiers.LAUNCHES
        assert launches_second == launches_first, (
            f"second call launched dafny: {launches_first} -> {launches_second}")
        e2 = v2["dafny"]
        assert e2["real"] == e1["real"], e2
        assert e2["twin"] == e1["twin"], e2
        assert e2["cached"] is True, e2
        assert e2["provisional"] is False, e2
        assert e2["source_sha"] == e1["source_sha"], (e1, e2)


@test
def test_second_process_reads_the_same_cache():
    task_path = tasks_io.find(HERE / "tasks", "abs")
    with tempfile.TemporaryDirectory(prefix="t-tlib-test-") as td:
        cache_dir = Path(td) / "cache"
        out_dir = Path(td) / "lib"
        task = harness.load(task_path)
        tlib.verify(task, kernels=["dafny"], cache_dir=cache_dir, out_dir=out_dir)

        script = (
            "import sys; sys.path.insert(0, %r)\n"
            "from pathlib import Path\n"
            "import harness, tlib, verifiers\n"
            "task = harness.load(Path(%r))\n"
            "verifiers.reset_launch_count()\n"
            "v = tlib.verify(task, kernels=['dafny'], cache_dir=%r, out_dir=%r)\n"
            "e = v['dafny']\n"
            "print('cached', e['cached'])\n"
            "print('provisional', e['provisional'])\n"
            "print('launches', verifiers.LAUNCHES)\n"
        ) % (str(HERE), str(task_path), str(cache_dir), str(out_dir))
        p = subprocess.run([sys.executable, "-c", script],
                           cwd=str(HERE), capture_output=True, text=True,
                           timeout=120)
        assert p.returncode == 0, (p.stdout, p.stderr)
        out = dict(line.split(" ", 1) for line in p.stdout.strip().splitlines())
        assert out["cached"] == "True", p.stdout
        assert out["provisional"] == "False", p.stdout
        assert out["launches"] == "0", p.stdout


@test
def test_flaked_result_is_provisional_and_uncached():
    # No kernel: a stub backend whose verify() alternates outcomes, so
    # flake_check's own n=3 disagreement path is exercised directly, and
    # cache.read after a flaked _side call must still be a miss.
    calls = {"n": 0}

    def flaky_verify(path):
        calls["n"] += 1
        outcome = Outcome.VERIFIED if calls["n"] % 2 else Outcome.REFUTED
        return Result(backend="stub", backend_version="stub-1", source_sha256="x",
                     outcome=outcome, ok=(outcome == Outcome.VERIFIED))

    class _Backend:
        verify = staticmethod(flaky_verify)

    with tempfile.TemporaryDirectory(prefix="t-tlib-test-") as td:
        cache_dir = Path(td) / "cache"
        src_path = Path(td) / "stub.src"
        src_path.write_text("stub source", encoding="utf-8")
        key = __import__("cache").key_for("stub source", "stub", "stub-1", None)
        outcome, was_cached, provisional = tlib._side(
            _Backend, "stub", src_path, key, "stub-1", None, 3, cache_dir)
        assert was_cached is False
        assert provisional is True, "disagreeing flake_check must be provisional"
        import cache as cache_mod
        assert cache_mod.read("stub", key, cache_dir) is None, (
            "a flaked result must never be cached")


@test
def test_explain_uses_outcome_vocabulary():
    task = harness.load(tasks_io.find(HERE / "tasks", "abs"))
    entry = {"real": Outcome.VERIFIED, "twin": Outcome.REFUTED,
             "twin_op": "collapse-if", "witness": "x=0 -> real 0, twin 1",
             "provisional": False, "source_sha": "deadbeef",
             "kernel_version": "dafny 4.11.0", "cached": True}
    sentence = tlib.explain(entry)
    assert isinstance(sentence, str), sentence
    assert "COUNTS" in sentence, sentence
    assert "real proof" in sentence, sentence

    full = tlib.explain({"dafny": entry})
    assert set(full) == {"dafny"}, full
    assert full["dafny"] == f"dafny: {sentence}", full
    del task  # unused beyond documenting the entry's shape


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
    print(f"test_tlib: all {len(UNIT_TESTS)} checks passed")


if __name__ == "__main__":
    try:
        run()
    except AssertionError as e:
        print(f"FAILED: {e}")
        sys.exit(1)
    sys.exit(0)
