"""Fault injection for verdict orchestration; fake backends prove nothing."""
import contextlib
import io
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import cache
import cli
import surface
import tlib
from verifiers import Outcome, Result, flake_check


SOURCE = "t 1\ntask cacheprobe(x: int) returns (r: int)\nensures r == x\n{ r := x; }\n"


def fake_verify(path):
    outcome = Outcome.REFUTED if path.stem.endswith("_twin") else Outcome.VERIFIED
    return Result("dafny", "fake-v1", "fake-source", outcome, ok=outcome == Outcome.VERIFIED)


class VerdictCacheTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.source = self.root / "probe.t"
        self.source.write_text(SOURCE)
        self.task = surface.parse(SOURCE)

    def verify(self, **kw):
        return tlib.verify(self.task, kernels=["dafny"], out_dir=self.root / "out",
                           cache_dir=self.root / "cache", **kw)["dafny"]

    def test_stronger_repetition_request_runs_again(self):
        with patch("tlib.kernel_version", return_value="fake-v1"), \
             patch("verifiers.dafny.verify", side_effect=fake_verify) as verifier:
            self.assertFalse(self.verify(flake=1)["cached"])
            self.assertEqual(verifier.call_count, 2)
            self.assertFalse(self.verify(flake=3)["cached"])
            self.assertEqual(verifier.call_count, 8)
            self.assertTrue(self.verify(flake=3)["cached"])
            self.assertEqual(verifier.call_count, 8)

    def test_adapter_change_invalidates_library_cache(self):
        with patch("tlib.kernel_version", return_value="fake-v1"), \
             patch("verifiers.dafny.verify", side_effect=fake_verify) as verifier, \
             patch("cache.adapter_fingerprint", create=True, return_value="before") as fingerprint:
            self.assertFalse(self.verify()["cached"])
            fingerprint.return_value = "after"
            self.assertFalse(self.verify()["cached"])
            self.assertEqual(verifier.call_count, 12)

    def test_source_version_budget_and_repeat_count_change_the_key(self):
        base = cache.verdict_key("source", "dafny", "v1", None, 3)
        for source, version, budget, repeats in (("new source", "v1", None, 3),
                                                ("source", "v2", None, 3),
                                                ("source", "v1", 123, 3),
                                                ("source", "v1", None, 1)):
            with self.subTest(source=source, version=version, budget=budget, repeats=repeats):
                self.assertNotEqual(base, cache.verdict_key(source, "dafny", version, budget, repeats))

    def test_unwritable_cache_does_not_discard_measured_result(self):
        backend = SimpleNamespace(verify=lambda p: Result("fake", "v1", "x", Outcome.VERIFIED))
        with patch("cache.write", side_effect=OSError("read only")):
            self.assertEqual(tlib._side(backend, "fake", self.source, "key", "v1", None, 3, self.root),
                             (Outcome.VERIFIED, False, False))

    def test_malformed_cache_entries_are_misses(self):
        path = cache.path_for("dafny", "probe", self.root)
        path.parent.mkdir(parents=True)
        for raw in (b'null', b'[]', b'"verified"', b'{}', b'{"outcome": []}',
                    b'{"outcome":"made-up","backend_version":"v1"}', b'\xff'):
            with self.subTest(raw=raw):
                path.write_bytes(raw)
                self.assertIsNone(cache.read("dafny", "probe", self.root))

    def test_transient_outcomes_are_not_cached(self):
        for outcome in (Outcome.TIMEOUT, Outcome.TOOL_ERROR):
            with self.subTest(outcome=outcome):
                backend = SimpleNamespace(verify=lambda p: Result("fake", "v1", "x", outcome))
                result = tlib._side(backend, "fake", self.source, outcome, "v1", None, 3, self.root)
                self.assertEqual(result, (outcome, False, False))
                self.assertIsNone(cache.read("fake", outcome, self.root))
                self.assertFalse(cache.path_for("fake", outcome, self.root).exists())

    def test_provisional_flip_does_not_count_or_exit_successfully(self):
        entry = {"real": Outcome.VERIFIED, "twin": Outcome.REFUTED,
                 "twin_op": "fake", "provisional": True}
        self.assertNotIn("COUNTS", tlib.explain(entry))
        with patch("tlib.verify", return_value={"dafny": entry}), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["verify", str(self.source), "--kernels", "dafny"]), 1)
        entry["provisional"] = False
        self.assertIn("COUNTS", tlib.explain(entry))
        with patch("tlib.verify", return_value={"dafny": entry}), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["verify", str(self.source), "--kernels", "dafny"]), 0)

    def test_invalid_repetition_counts_refused_before_verification(self):
        for value in (0, -1, True, 1.5):
            with self.subTest(value=value), patch("tlib.kernel_version") as version:
                with self.assertRaises(ValueError):
                    self.verify(flake=value)
                version.assert_not_called()
            with self.subTest(low_level=value):
                with self.assertRaises(ValueError):
                    flake_check(lambda p: self.fail("invalid repetitions launched a verifier"), self.source, value)

    def test_cli_refuses_non_positive_repetition_count(self):
        for target in (self.source, self.root):
            with self.subTest(target=target), patch("tlib.verify") as verify, \
                 patch("run_par.probe_backends") as probe, contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(cli.main(["verify", str(target), "--flake", "0"]), 2)
                verify.assert_not_called()
                probe.assert_not_called()


if __name__ == "__main__":
    unittest.main()
