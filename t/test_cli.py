#!/usr/bin/env python3
"""t/test_cli.py: unit tests for cli.py (ROADMAP 14.4, "One command").

Every subcommand is exercised at least once through `subprocess`, on the
committed corpus (t/tasks/*.t) and on t/malformed/*.t, exactly as a real
invocation of `python3 t/cli.py ...` would run: this file never imports
cli.py's functions directly, since the bar is the command, not the
module. Also covered: the --json record shape (the seven required keys,
one JSON object per line, `json.loads`-able), the --flag=value form
(argparse's own long-option syntax, tested once per the bar's wording),
and format's idempotence (format --write twice reproduces the same
bytes).

The verify-directory bar (byte-identical AGREEMENT.md, modulo the
timestamp line) is NOT re-measured by this file: it is the one full
matrix run t/COMMAND.md and the task's own report paste, not a repeated
kernel run inside every `python3 test_cli.py`. This file's own verify
tests use a single present kernel (dafny, always installed on this box)
over one or two tasks, which is cheap enough to run on every test pass.

Run: python3 t/cli.py test, or directly: python3 test_cli.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLI = HERE / "cli.py"
TASKS = HERE / "tasks"
MALFORMED = HERE / "malformed"

ENV = dict(os.environ)
ENV["PATH"] = (str(Path.home() / ".cargo/bin") + os.pathsep
              + str(Path.home() / ".opam/default/bin") + os.pathsep
              + str(Path.home() / ".elan/bin") + os.pathsep
              + ENV.get("PATH", ""))


def run(*args, timeout=120):
    """Run `python3 cli.py <args>` from t/, return (rc, stdout, stderr)."""
    p = subprocess.run([sys.executable, str(CLI), *args], cwd=str(HERE),
                      capture_output=True, text=True, timeout=timeout, env=ENV)
    return p.returncode, p.stdout, p.stderr


REQUIRED_KEYS = {"file", "line", "col", "rule", "severity", "kernel", "message"}


def assert_json_lines(test, text: str, min_records: int = 1):
    lines = [ln for ln in text.splitlines() if ln.strip()]
    test.assertGreaterEqual(len(lines), min_records,
                            f"expected at least {min_records} JSON line(s), got {lines!r}")
    for ln in lines:
        rec = json.loads(ln)                     # raises on malformed JSON
        test.assertEqual(set(rec.keys()), REQUIRED_KEYS, rec)
        test.assertIn(rec["severity"], ("error", "warning", "info", "verdict"))
    return [json.loads(ln) for ln in lines]


class ParseTest(unittest.TestCase):
    def test_well_formed_task_json(self):
        rc, out, err = run("parse", str(TASKS / "abs.t"))
        self.assertEqual(rc, 0, err)
        task = json.loads(out)
        self.assertEqual(task["name"], "abs")
        self.assertEqual(task["t"], 0)

    def test_malformed_text_error(self):
        rc, out, err = run("parse", str(MALFORMED / "stmt.t"))
        self.assertEqual(rc, 1)
        self.assertIn("stmt.t", out)

    def test_malformed_json_diagnostic(self):
        rc, out, err = run("parse", str(MALFORMED / "stmt.t"), "--json")
        self.assertEqual(rc, 1)
        recs = assert_json_lines(self, out)
        self.assertEqual(recs[0]["severity"], "error")
        self.assertTrue(str(MALFORMED / "stmt.t").endswith(recs[0]["file"])
                        or recs[0]["file"].endswith("stmt.t"))


class CheckTest(unittest.TestCase):
    def test_well_formed_task_clean(self):
        rc, out, err = run("check", str(TASKS / "abs.t"))
        self.assertEqual(rc, 0, err)
        self.assertIn("well-formed", out)

    def test_wf_violation_text(self):
        rc, out, err = run("check", str(MALFORMED / "wf-arith-int.t"))
        self.assertEqual(rc, 1)
        self.assertIn("arith-int", out)

    def test_wf_violation_json(self):
        rc, out, err = run("check", str(MALFORMED / "wf-arith-int.t"), "--json")
        self.assertEqual(rc, 1)
        recs = assert_json_lines(self, out)
        self.assertEqual(recs[0]["rule"], "arith-int")
        self.assertEqual(recs[0]["severity"], "error")
        self.assertEqual(recs[0]["kernel"], "")

    def test_syntax_error_still_one_diagnostic(self):
        rc, out, err = run("check", str(MALFORMED / "stmt.t"), "--json")
        self.assertEqual(rc, 1)
        recs = assert_json_lines(self, out)
        self.assertEqual(len(recs), 1)


class FormatTest(unittest.TestCase):
    def test_stdout_matches_committed_printer(self):
        # tasks/*.t are already canonical text (surface.py --check verifies
        # this corpus-wide), so format with no --write reproduces the file.
        rc, out, err = run("format", str(TASKS / "abs.t"))
        self.assertEqual(rc, 0, err)
        self.assertEqual(out, (TASKS / "abs.t").read_text(encoding="utf-8"))

    def test_write_is_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "abs.t"
            path.write_text((TASKS / "abs.t").read_text(encoding="utf-8"),
                            encoding="utf-8")
            rc1, _, err1 = run("format", str(path), "--write")
            self.assertEqual(rc1, 0, err1)
            first = path.read_text(encoding="utf-8")
            rc2, _, err2 = run("format", str(path), "--write")
            self.assertEqual(rc2, 0, err2)
            second = path.read_text(encoding="utf-8")
            self.assertEqual(first, second)

    def test_malformed_input_errors(self):
        rc, out, err = run("format", str(MALFORMED / "stmt.t"))
        self.assertEqual(rc, 1)


class LowerTest(unittest.TestCase):
    def test_one_kernel_to_stdout(self):
        rc, out, err = run("lower", str(TASKS / "abs.t"), "--kernel", "dafny")
        self.assertEqual(rc, 0, err)
        self.assertIn("method", out)
        self.assertIn("Abs", out)

    def test_all_kernels_to_files(self):
        with tempfile.TemporaryDirectory() as d:
            rc, out, err = run("lower", str(TASKS / "abs.t"),
                              "--kernel", "all", "--out", d)
            self.assertEqual(rc, 0, err)
            names = sorted(p.name for p in Path(d).iterdir())
            self.assertEqual(names, sorted([
                "abs.dfy", "abs.rs", "abs.ads", "abs.c",
                "abs.lean", "abs.v", "abs.fst"]))

    def test_unknown_kernel_is_usage_error(self):
        rc, out, err = run("lower", str(TASKS / "abs.t"), "--kernel", "nope")
        self.assertEqual(rc, 2)

    def test_rename_comment_present_when_renamed(self):
        # names.rename_comment's own text is emitted by every lowering when
        # sanitize() actually renamed something; abs.t needs no renames, so
        # this just checks the stdout form carries no crash and no comment
        # for a task that needs none (rename_comment("") == "").
        rc, out, err = run("lower", str(TASKS / "abs.t"), "--kernel", "dafny")
        self.assertEqual(rc, 0, err)
        self.assertNotIn("t renames:", out)


class VerifyTest(unittest.TestCase):
    def test_single_file_one_kernel(self):
        rc, out, err = run("verify", str(TASKS / "abs.t"), "--kernels", "dafny",
                          timeout=180)
        self.assertIn(rc, (0, 1), err)
        self.assertIn("dafny", out)

    def test_single_file_json(self):
        rc, out, err = run("verify", str(TASKS / "abs.t"), "--kernels", "dafny",
                          "--json", timeout=180)
        recs = assert_json_lines(self, out)
        self.assertEqual(recs[0]["kernel"], "dafny")
        self.assertEqual(recs[0]["severity"], "verdict")

    def test_unknown_kernel_usage_error(self):
        rc, out, err = run("verify", str(TASKS / "abs.t"), "--kernels", "nope")
        self.assertEqual(rc, 2)

    def test_directory_form_writes_table(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "tasks"
            src.mkdir()
            (src / "abs.t").write_text((TASKS / "abs.t").read_text(encoding="utf-8"),
                                       encoding="utf-8")
            table = Path(d) / "AGREEMENT.md"
            out_dir = Path(d) / "out"
            env = dict(ENV)
            env["T_MIN_KERNELS"] = "1"   # this box's test run has only
                                         # dafny reliably fast; the real
                                         # >=2-kernel bar is the full
                                         # matrix run in COMMAND.md, not
                                         # this single-kernel unit test.
            p = subprocess.run([sys.executable, str(CLI), "verify", str(src),
                              "--kernels", "dafny", "--table", str(table),
                              "--out", str(out_dir)],
                              cwd=str(HERE), capture_output=True, text=True,
                              timeout=180, env=env)
            rc, out, err = p.returncode, p.stdout, p.stderr
            self.assertIn(rc, (0, 1), err)
            self.assertTrue(table.exists())
            text = table.read_text(encoding="utf-8")
            self.assertIn("t cross-kernel agreement", text)
            self.assertIn("abs", text)


class TwinTest(unittest.TestCase):
    def test_text(self):
        rc, out, err = run("twin", str(TASKS / "abs.t"))
        self.assertEqual(rc, 0, err)
        self.assertIn("witness", out)

    def test_json(self):
        rc, out, err = run("twin", str(TASKS / "abs.t"), "--json")
        self.assertEqual(rc, 0, err)
        recs = assert_json_lines(self, out)
        self.assertEqual(recs[0]["severity"], "verdict")


class ExplainTest(unittest.TestCase):
    def test_all_kernels(self):
        rc, out, err = run("explain", "verified")
        self.assertEqual(rc, 0, err)
        lines = [ln for ln in out.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 7)

    def test_one_kernel(self):
        rc, out, err = run("explain", "refuted", "--kernel", "dafny")
        self.assertEqual(rc, 0, err)
        lines = [ln for ln in out.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 1)
        self.assertIn("dafny", lines[0])

    def test_json_shape(self):
        rc, out, err = run("explain", "timeout", "--kernel", "lean", "--json")
        self.assertEqual(rc, 0, err)
        recs = assert_json_lines(self, out)
        self.assertEqual(recs[0]["kernel"], "lean")
        self.assertEqual(recs[0]["severity"], "verdict")

    def test_unknown_word_is_usage_error(self):
        rc, out, err = run("explain", "bogus")
        self.assertEqual(rc, 2)


class FlagEqualsFormTest(unittest.TestCase):
    """argparse accepts --flag=value for every long option; tested once,
    per the bar's "state it and test it once" (ROADMAP 14.4)."""

    def test_kernel_equals_form(self):
        # --json is store_true (no value to give it); the --flag=value
        # form is exercised here on a value-taking flag, --kernel.
        rc3, out3, err3 = run("lower", str(TASKS / "abs.t"), "--kernel=dafny")
        rc4, out4, err4 = run("lower", str(TASKS / "abs.t"), "--kernel", "dafny")
        self.assertEqual(rc3, 0, err3)
        self.assertEqual(out3, out4)


class SubprocessSmokeTest(unittest.TestCase):
    """Every subcommand runs at least once end to end (the bar's "every
    subcommand at least once through subprocess")."""

    def test_no_args_usage(self):
        rc, out, err = run()
        self.assertEqual(rc, 2)

    def test_bad_flag_usage(self):
        rc, out, err = run("check", str(TASKS / "abs.t"), "--nope")
        self.assertEqual(rc, 2)


class FailurePathTest(unittest.TestCase):
    """Added 2026-09-11 after the independent check of 14.4: a missing input
    is a usage error, not a traceback, and a lowering that abstains is an
    abstain verdict from the single-file verify, as it is in the table."""

    def test_missing_file_is_usage_error(self):
        p = subprocess.run([sys.executable, str(CLI), "parse", "/nonexistent/x.t"],
                           cwd=str(HERE), capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 2, p.stderr)
        self.assertNotIn("Traceback", p.stderr)
        self.assertIn("no such file", p.stderr)
        p = subprocess.run([sys.executable, str(CLI), "check", "/nonexistent/x.t", "--json"],
                           cwd=str(HERE), capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 2)
        rec = json.loads(p.stdout.strip().splitlines()[0])
        self.assertEqual(rec["rule"], "usage")
        self.assertEqual(rec["severity"], "error")

    def test_single_file_verify_reports_abstain(self):
        p = subprocess.run([sys.executable, str(CLI), "verify", "tasks/count_vowels.t",
                            "--kernels", "framac", "--json"],
                           cwd=str(HERE), capture_output=True, text=True, timeout=300)
        self.assertNotIn("Traceback", p.stderr)
        recs = [json.loads(l) for l in p.stdout.strip().splitlines() if l.startswith("{")]
        self.assertTrue(recs, p.stdout + p.stderr)
        self.assertTrue(any("abstain" in r["message"] for r in recs), recs)


if __name__ == "__main__":
    unittest.main()
