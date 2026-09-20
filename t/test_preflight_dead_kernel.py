"""A kernel that never started must not be read as a kernel that disagreed.

Measured 2026-09-20: two seed arms were graded with Verus reading
`malformed / malformed` on 114 of 114 and 87 of 88 rows, because the driver ran
in a non-login shell and Verus needs rustup on PATH. preflight's column check
passed them, since all seven columns were present. Scored as they stood both
read 0 clean, which would have been reported as the recipe failing to reproduce
its headline across seeds.
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import preflight

HEAD = ("| task | dafny | verus | spark | framac | lean | rocq | fstar |\n"
        "|---|---|---|---|---|---|---|---|\n")
OK = "verified / refuted"


def make(rows, verus_cell):
    d = Path(tempfile.mkdtemp()) / "tag"
    d.mkdir()
    body = "".join(
        f"| mbpp_{i}__f | {OK} | {verus_cell} | {OK} | {OK} | {OK} | {OK} | {OK} |\n"
        for i in range(rows))
    (d / "kernels.md").write_text(HEAD + body, encoding="utf-8")
    return d


class DeadKernelTests(unittest.TestCase):
    def run_check(self, d):
        with mock.patch.object(preflight, "tables", lambda: [d]):
            return preflight.check_kernel_ran()

    def test_a_kernel_malformed_on_every_row_fails(self):
        self.assertFalse(self.run_check(make(20, "malformed / malformed")))

    def test_a_healthy_table_passes(self):
        self.assertTrue(self.run_check(make(20, OK)))

    def test_a_few_malformed_cells_are_ordinary_and_pass(self):
        """One bad lowering is a fact about that lowering, not about the toolchain."""
        d = make(20, OK)
        text = (d / "kernels.md").read_text().replace(OK, "malformed / malformed", 2)
        (d / "kernels.md").write_text(text, encoding="utf-8")
        self.assertTrue(self.run_check(d))

    def test_a_tiny_table_is_not_judged(self):
        """Under ten rows, 'nearly every row' has no meaning."""
        self.assertTrue(self.run_check(make(5, "malformed / malformed")))


if __name__ == "__main__":
    unittest.main()
