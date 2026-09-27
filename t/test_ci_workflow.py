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

Second gap, found on review of the first fix: the check above originally read
`assertIn(suite, self.job)` -- true whenever the suite's filename appears *anywhere* in the cpu-torch
job's raw text. A reviewer showed this with one instance (a step-level comment, "# TODO: add
test_dawnr_api.py", next to a run: line that never names the file) but the instance is not the whole
bug: "the filename occurs somewhere in the job's text" was standing in for "the job passes it to a
test runner" everywhere in this file, and every way those two can come apart is the same silent gap
this file exists to catch, just one level up. Besides a comment, the filename can occur in: a
trailing `# ...` on the run: line itself; a step's `name:` field; as a substring of a longer
argument (`--ignore=test_x.py`, `test_x.py.bak`); or on an unrelated line of a multi-line `run: |`
block (an echo, a different command) that is not the line actually invoking the test runner.
WiredSuitesParsingTests below has one fixture per case; all six failed against the old
`suite in job_block` check (run once, on purpose, before this rewrite -- see the commit message).

The fix parses the job's run: step(s) as shell text instead of grepping the job's YAML text:
shlex.split(line, comments=True) -- the stdlib's own shell tokenizer, '#'-comment stripping included
(docs.python.org/3/library/shlex.html) -- turns the one physical line that actually invokes the test
runner into its argument list, and a suite counts as wired only when its filename is one of those
arguments *exactly*, never a substring of anything. Scoping to that single line (not the whole run:
block) is what rules out the "different line in the same block" case: an echo or a pip-install line
elsewhere in the same step can no longer contribute a stray word to the count.

What this still cannot see, on purpose rather than by oversight: a filename built at runtime from a
shell variable, e.g. `FILES="test_a.py test_b.py"; python -m pytest -v $FILES` -- the exact pattern
the standard-library job above already uses for its own suites. `$FILES` is one opaque token to a
tokenizer that does not run the shell, so a suite wired only that way now reads as *not* wired: a
false failure, not a false pass. That is the class of input that could still get through in the other
direction, and it is the safe direction to fail in -- this file's job is to make a silently-uncovered
suite loud, and "loud when it actually is covered" is a bug report waiting for a human, not a
regression that ships quietly. A second, narrower gap in the same direction: two commands chained on
one physical line with `&&`/`;`/`|` after the test-runner invocation are not split apart, so a
filename-shaped word placed there would still be read as one of the runner's own arguments -- neither
job in this workflow does that today, and closing it would mean hand-rolling shell-grammar command
splitting for a one-line run: command that has never needed it.
"""
import re
import shlex
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

# A run: step invokes the test runner directly (`pytest ...`) or as a module (`python -m pytest ...`
# / `python3 -m unittest ...`). Matched against shell tokens, never raw text, so a mention inside an
# already-stripped comment can't reach this at all.
_RUNNER_MODULES = ("pytest", "unittest")
_BLOCK_SCALAR = re.compile(r"^[|>][+-]?\d*$")


def _job_block(text: str, job_name: str) -> str:
    """The raw text of one top-level job, from its own `  <job_name>:` line to the next top-level
    job key (2-space indent) or end of file. Written as a bounded regex anyway so it stays correct
    if a job is ever added after this one.
    """
    m = re.search(rf"(?m)^  {re.escape(job_name)}:\n(.*?)(?=^  [A-Za-z0-9_-]+:\n|\Z)", text, re.S)
    assert m, f"no {job_name!r} job found"
    return m.group(1)


def _run_step_texts(job_block: str):
    """Every step's `run:` shell text within a job block, kept separate from the step's other keys
    (`name:`, `if:`, `working-directory:`, a comment at the step level, ...) -- which is what makes
    it safe to search only this text for the files a step actually runs. Handles both `run:` forms
    this repository's workflow uses: inline (`run: <command>`) and block scalar (`run: |`, every
    following line indented deeper than the `run:` key itself, same rule YAML itself uses). Not a
    YAML parser: a `run:` form outside these two is a workflow-authoring change this test should be
    re-taught about, not something to guess at.
    """
    lines = job_block.splitlines()
    i = 0
    while i < len(lines):
        m = re.match(r"^(?P<indent>[ \t]*)run:[ \t]?(?P<value>.*)$", lines[i])
        if not m:
            i += 1
            continue
        indent, value = m.group("indent"), m.group("value")
        if _BLOCK_SCALAR.match(value.strip()):
            body = []
            i += 1
            while i < len(lines) and (lines[i].strip() == ""
                                       or len(lines[i]) - len(lines[i].lstrip(" \t")) > len(indent)):
                body.append(lines[i])
                i += 1
            yield "\n".join(body)
        else:
            yield value
            i += 1


def _pytest_argv(shell_text: str):
    """The argv of the one physical line in `shell_text` that invokes the test runner (`pytest ...`,
    `python -m pytest ...`, `python3 -m unittest ...`), or None if no line does.

    shlex.split(line, comments=True) is the stdlib's own shell tokenizer with '#'-comment stripping
    built in (docs.python.org/3/library/shlex.html): a name that lives only in a comment -- a whole
    commented-out line, or a trailing `# ...` after the real command -- never becomes a token, and a
    name that is merely a *substring* of a real token (`--ignore=test_x.py`, `test_x.py.bak`) never
    equals a bare filename either, because list membership on the returned argv is exact, not
    substring.

    Scoped to a single physical line, and to a line that *starts* with the invocation, on purpose: a
    run: step can hold more than one shell command (the standard-library job's own install step above
    runs two `pip install` lines in one block), and only the line that is itself the test invocation
    should count as evidence a suite runs -- an unrelated `echo` or `pip install` line elsewhere in
    the same block must not be able to smuggle a filename through as a stray word, and a bare mention
    of the word "pytest" as someone else's argument (`pip install ... pytest ...`) must not be
    mistaken for the invocation itself.
    """
    for line in shell_text.splitlines():
        tokens = shlex.split(line, comments=True)
        if not tokens:
            continue
        if tokens[0] in _RUNNER_MODULES:
            return tokens
        if tokens[0] in ("python", "python3") and len(tokens) >= 3 \
                and tokens[1] == "-m" and tokens[2] in _RUNNER_MODULES:
            return tokens
    return None


def _is_wired(suite: str, job_block: str) -> bool:
    """Whether `suite` is actually passed as an argument to a test runner somewhere in this job --
    the only thing "this suite runs in CI" can honestly mean. Not `suite in job_block`: that reads a
    mention anywhere in the job's raw YAML/shell text as proof the suite runs, which is the class of
    false pass described at the top of this file.
    """
    for step_text in _run_step_texts(job_block):
        argv = _pytest_argv(step_text)
        if argv and suite in argv:
            return True
    return False


class CpuTorchJobCoverage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")
        cls.job = _job_block(cls.text, "cpu-torch")

    def test_every_cpu_torch_suite_is_named_in_the_jobs_run_command(self):
        for suite in CPU_TORCH_SUITES:
            with self.subTest(suite=suite):
                self.assertTrue(_is_wired(suite, self.job),
                                 f"{suite} needs torch but the cpu-torch job's run command never "
                                 f"passes it as an argument to pytest/unittest (a mention in a "
                                 f"comment, a step name, or as part of a longer argument doesn't "
                                 f"count), so it never runs in CI")


class WiredSuitesParsingTests(unittest.TestCase):
    """_is_wired() against fixtures, not the real workflow file, so these run the same whether or
    not tests.yml is ever edited. Every "not_wired" fixture is a different way a suite's filename can
    appear in a job's raw text without the job ever passing it to a test runner -- the class the
    reviewer's one example (a comment) belongs to. Each one failed against this file's original
    `suite in job_block` check; each passes here.
    """

    def test_a_suite_named_only_in_a_comment_above_the_run_line_is_not_wired(self):
        # The reviewer's own case: a step-level comment, not shell text at all, sitting next to a
        # run: line that never mentions the file.
        job = (
            "      - name: locallm CPU-torch suites\n"
            "        working-directory: locallm\n"
            "        # TODO: add test_dawnr_api.py\n"
            "        run: python -m pytest -v test_dawnr_chat.py test_harness_chat.py\n"
        )
        self.assertFalse(_is_wired("test_dawnr_api.py", job))
        self.assertTrue(_is_wired("test_dawnr_chat.py", job))

    def test_a_suite_named_only_in_a_trailing_comment_on_the_run_line_is_not_wired(self):
        job = "        run: python -m pytest -v test_dawnr_chat.py  # still need test_dawnr_api.py\n"
        self.assertFalse(_is_wired("test_dawnr_api.py", job))

    def test_a_suite_named_only_as_part_of_a_longer_argument_is_not_wired(self):
        for job in (
            "        run: python -m pytest -v test_dawnr_chat.py --ignore=test_dawnr_api.py\n",
            "        run: python -m pytest -v test_dawnr_chat.py test_dawnr_api.py.bak\n",
        ):
            with self.subTest(job=job):
                self.assertFalse(_is_wired("test_dawnr_api.py", job))

    def test_a_suite_named_only_in_an_unrelated_steps_field_is_not_wired(self):
        job = (
            "      - name: covers test_dawnr_api.py too\n"
            "        run: python -m pytest -v test_dawnr_chat.py\n"
        )
        self.assertFalse(_is_wired("test_dawnr_api.py", job))

    def test_a_suite_named_on_an_unrelated_line_in_the_same_block_scalar_is_not_wired(self):
        # Same run: step, same multi-line block -- but the filename sits on an echo line, not the
        # pytest line, in the same block.
        job = (
            "        run: |\n"
            "          echo about to add test_dawnr_api.py\n"
            "          python -m pytest -v test_dawnr_chat.py\n"
        )
        self.assertFalse(_is_wired("test_dawnr_api.py", job))

    def test_a_bare_mention_of_the_word_pytest_is_not_mistaken_for_the_invocation(self):
        # "pytest" as someone else's argument (installing it) is not a line that invokes it.
        job = "        run: python -m pip install --upgrade pip pytest numpy\n"
        self.assertFalse(_is_wired("pytest", job))
        self.assertFalse(_is_wired("numpy", job))

    def test_a_suite_genuinely_passed_as_an_argument_is_wired(self):
        # The control: this file must not simply fail everything.
        job = "        run: python -m pytest -v test_dawnr_chat.py test_dawnr_api.py\n"
        self.assertTrue(_is_wired("test_dawnr_api.py", job))

    def test_a_suite_passed_in_a_multiline_block_scalar_is_wired(self):
        job = (
            "        run: |\n"
            "          # five suites need torch\n"
            "          python -m pytest -v test_dawnr_chat.py test_dawnr_api.py\n"
        )
        self.assertTrue(_is_wired("test_dawnr_api.py", job))


if __name__ == "__main__":
    unittest.main()
