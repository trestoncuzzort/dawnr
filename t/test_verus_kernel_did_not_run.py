"""t/verifiers/verus.py (2026-09-30): a verus that could not launch is TOOL_ERROR, never MALFORMED.

verus's launcher (github.com/verus-lang/verus, source/verus/src/main.rs) prints "verus: rustup
not found, or not executable" and "verus needs a rustup installation" when rustup is off the
PATH, then "error: failed to execute rust_verify ..." and exits 128. That is the tool failing to
run, which the Outcome vocabulary says is never evidence of anything; until this test it read
MALFORMED, and one grade launched from a shell without ~/.cargo/bin wrote "malformed" into a whole
column. A file rustc rejects (no JSON, a plain rustc error, exit 1) still reads MALFORMED. Both
cases run a stub in place of the kernel, so no verus is needed. No kernel."""
from __future__ import annotations

import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from verifiers import verus  # noqa: E402
from verifiers import Outcome  # noqa: E402

SOURCE = """use vstd::prelude::*;
verus! {
proof fn t_lp_x(a: int) -> (r: int)
    ensures r == a,
{ a }
}
fn main() {}
"""

LAUNCHER_FAILURE = ("#!/bin/sh\n"
                    "printf '\\033[31mverus: rustup not found, or not executable\\033[0m\\n' >&2\n"
                    "printf 'verus needs a rustup installation\\n' >&2\n"
                    "printf 'error: failed to execute rust_verify Os { code: 2, kind: NotFound }\\n' >&2\n"
                    "exit 128\n")
RUSTC_REJECTION = ("#!/bin/sh\n"
                   "printf 'error[E0425]: cannot find value `b` in this scope\\n' >&2\n"
                   "exit 1\n")


def _stub(directory: Path, name: str, body: str) -> Path:
    path = directory / name
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


@unittest.skipIf(sys.platform == "win32", "the stubs are shell scripts")
class KernelDidNotRun(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.src = self.dir / "x.rs"
        self.src.write_text(SOURCE, encoding="utf-8")

    def test_a_launcher_that_cannot_find_rustup_is_a_tool_error_that_names_the_cause(self):
        stub = _stub(self.dir, "verus", LAUNCHER_FAILURE)
        with patch.object(verus, "VERUS", str(stub)):
            result = verus.verify(self.src, budget=1000)
        self.assertEqual(result.outcome, Outcome.TOOL_ERROR)
        self.assertIn("rustup not found", result.error)
        self.assertEqual(result.exit_code, 128)
        self.assertFalse(result.ok)

    def test_a_file_rustc_rejects_still_reads_malformed(self):
        stub = _stub(self.dir, "verus", RUSTC_REJECTION)
        with patch.object(verus, "VERUS", str(stub)):
            result = verus.verify(self.src, budget=1000)
        self.assertEqual(result.outcome, Outcome.MALFORMED)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
