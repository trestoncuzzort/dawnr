"""Invalid tasks must not reach the witness ladder or proof kernels."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cli
import surface
import tlib


VALID = "t 1\ntask probe(x: int) returns (r: int)\nensures r == x\n{ r := x; }\n"
INVALID = VALID.replace("r := x;", "assert true; r := x;")


class ValidationGateTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.source = self.root / "probe.t"
        self.source.write_text(INVALID)

    def call_cli(self, args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = cli.main(args + ["--json"])
        return rc, [json.loads(line) for line in out.getvalue().splitlines()], err.getvalue()

    def test_check_lower_twin_and_verify_share_semantic_diagnostics(self):
        for args in (["check", str(self.source)],
                     ["lower", str(self.source), "--kernel", "dafny", "--out", str(self.root / "out")],
                     ["twin", str(self.source)],
                     ["verify", str(self.source), "--kernels", "dafny"],
                     ["verify", str(self.root), "--kernels", "dafny", "--table", str(self.root / "table.md")]):
            with self.subTest(command=args[0], target=args[1]), \
                 patch("harness.twin_cached", side_effect=AssertionError("invalid task reached twin search")), \
                 patch("run_par.probe_backends", side_effect=AssertionError("invalid task reached kernel probe")), \
                 patch("tlib.kernel_version", side_effect=AssertionError("invalid task reached kernel probe")):
                rc, records, stderr = self.call_cli(args)
                self.assertEqual(rc, 1)
                self.assertTrue(records)
                self.assertTrue(all(r["severity"] == "error" and r["kernel"] == "" for r in records))
                self.assertTrue(all(r["file"] == str(self.source) for r in records))
                self.assertTrue(all(r["line"] is not None for r in records))
                self.assertNotIn("Traceback", stderr)
        self.assertFalse((self.root / "out").exists())
        self.assertFalse((self.root / "table.md").exists())

    def test_library_refuses_before_twin_lowering_or_kernel(self):
        task = surface.parse(INVALID)
        for call in (lambda: tlib.twin(task), lambda: tlib.lower(task, "dafny"),
                     lambda: tlib.verify(task, kernels=["dafny"])):
            with self.subTest(call=call), \
                 patch("harness.twin_cached", side_effect=AssertionError("twin search")), \
                 patch("tlib.kernel_version", side_effect=AssertionError("kernel probe")), \
                 patch("lower_dafny.lower", side_effect=AssertionError("lowering")):
                with self.assertRaisesRegex(ValueError, "ill-formed"):
                    call()

    def test_directory_syntax_error_is_diagnostic(self):
        self.source.write_text("t 1\ntask broken(")
        rc, records, stderr = self.call_cli(["verify", str(self.root), "--table", str(self.root / "table.md")])
        self.assertEqual(rc, 1)
        self.assertEqual(records[0]["severity"], "error")
        self.assertEqual(records[0]["file"], str(self.source))
        self.assertNotIn("Traceback", stderr)

    def test_invalid_json_shapes_refuse_without_kernel_work(self):
        self.source.unlink()
        path = self.root / "probe.json"
        for task in ([], None, {}, {"t": 8}, {"t": 1, "name": "probe"}):
            with self.subTest(task=task), patch("run_par.probe_backends") as probe:
                path.write_text(json.dumps(task))
                rc, records, stderr = self.call_cli(["verify", str(self.root), "--table", str(self.root / "table.md")])
                self.assertEqual(rc, 1)
                self.assertEqual(records[0]["severity"], "error")
                self.assertNotIn("Traceback", stderr)
                probe.assert_not_called()
            with self.subTest(library_task=task), patch("tlib.kernel_version") as version:
                with self.assertRaisesRegex(ValueError, "ill-formed"):
                    tlib.verify(task)
                version.assert_not_called()

    def test_valid_task_still_lowers(self):
        self.source.write_text(VALID)
        rc, records, stderr = self.call_cli(["lower", str(self.source), "--kernel", "dafny",
                                            "--out", str(self.root / "out")])
        self.assertEqual((rc, records, stderr), (0, [], ""))
        self.assertIn("method Probe", (self.root / "out" / "probe.dfy").read_text())

    def test_existing_semantic_error_corpus_never_reaches_kernels(self):
        fixtures = sorted((Path(__file__).resolve().parent / "malformed").glob("wf-*.t"))
        self.assertTrue(fixtures)
        with patch("tlib.kernel_version") as version, patch("harness.twin_cached") as twin:
            for path in fixtures:
                with self.subTest(fixture=path.name):
                    with self.assertRaisesRegex(ValueError, "ill-formed"):
                        tlib.verify(surface.parse_file(path), kernels=["dafny"])
            version.assert_not_called()
            twin.assert_not_called()


if __name__ == "__main__":
    unittest.main()
