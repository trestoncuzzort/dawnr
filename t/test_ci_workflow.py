"""test_ci_workflow.py: a locallm suite that needs torch actually gets run by the workflow that
installs it.

The exact gap this file exists to catch: locallm/test_dawnr_api.py (30 tests, including every
client-tool-poisoning regression test) was written, passed locally, and was cited as "no regressions"
in two commit messages, while .github/workflows/tests.yml's cpu-torch job's own run line still read
test_dawnr_chat.py test_harness_chat.py test_fim.py test_early_stop.py -- four files, unchanged since
before dawnr_api.py existed. A suite that never runs in CI is indistinguishable, from CI's own output,
from a suite that does not exist. This reads the workflow file as text (no PyYAML anywhere in this
repository; confirmed by grep before adding a dependency for one job's one line, stackoverflow.com/
q/8344357 confirms the bind-port-0-then-read-it-back pattern the suites under test already use is the
standard one, so nothing about their own design needed to change for this) and fails the way a
reviewer reading the file by eye would notice the gap: by name, not by count.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "tests.yml"

# Every locallm suite the cpu-torch job's own comment says it exists to run: the ones whose own
# module docstring says they need torch. Named explicitly, not discovered by scanning for "import
# torch", because a scan would need to run correctly to be trusted -- exactly the kind of
# self-referential check this file exists to avoid depending on.
CPU_TORCH_SUITES = ("test_dawnr_chat.py", "test_dawnr_api.py", "test_harness_chat.py", "test_fim.py",
                    "test_early_stop.py")


class CpuTorchJobCoverage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")
        # A top-level job key sits at 2-space indentation; the next one (or end of file) ends the
        # block. There are only two jobs here and cpu-torch is the last, so this only ever needs to
        # find where the block starts and take the rest of the file -- written as a bounded regex
        # anyway so it stays correct if a job is ever added after this one.
        m = re.search(r"(?m)^  cpu-torch:\n(.*?)(?=^  [A-Za-z0-9_-]+:\n|\Z)", cls.text, re.S)
        assert m, f"no 'cpu-torch:' job found in {WORKFLOW}"
        cls.job = m.group(1)

    def test_every_cpu_torch_suite_is_named_in_the_jobs_run_command(self):
        for suite in CPU_TORCH_SUITES:
            with self.subTest(suite=suite):
                self.assertIn(suite, self.job,
                              f"{suite} needs torch but the cpu-torch job's run command never "
                              f"names it, so it never runs in CI")


if __name__ == "__main__":
    unittest.main()
