"""
SCOPE, stated plainly after three review rounds (2026-09-27): this test runs the
cpu-torch job's shell in a sandbox with the test runners stubbed, so it catches a
suite that is named but never executed (a comment, a dead branch, a skipped step,
a heredoc, an uncalled function). It is NOT GitHub Actions: it does not parse YAML
the way Actions does (a tab-indented key Actions would reject is executed here),
it credits any argv token of a runner call (so `--ignore X` and `--collect-only X`
still read as wired), and a run: step could write the stub's log directly. The
guard that actually proves the suite runs is the CI job itself on GitHub
(.github/workflows/tests.yml, cpu-torch), whose real pytest output is the
evidence. This file is a cheap local tripwire, not that proof.
test_ci_workflow.py: a locallm suite that needs torch actually gets run by the workflow that
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
Six fixtures below (in WiredSuitesExecutionTests) covered one case each; all six failed against the
old `suite in job_block` check (run once, on purpose, before that rewrite -- see the commit message),
by way of a shlex.split(line, comments=True)-based tokenizer (the stdlib's own shell tokenizer,
'#'-comment stripping included, docs.python.org/3/library/shlex.html): a suite counted as wired only
when its filename was one of a physical line's tokens *exactly*, never a substring of anything, and
only on the one physical line that itself invoked the runner -- an echo or pip-install line elsewhere
in the same run: block could no longer contribute a stray word to the count.

Third gap, found on review of the second fix (the shlex-based one just described): shlex.split turns
a *line of text* into tokens; it has no idea whether bash would ever actually reach that line. A
reviewer produced five ways a suite's filename can sit in an argument position on a line that shlex
would tokenize as a pytest invocation, while the step never actually runs it: `exit 0` on an earlier
line of the same run: script (the shell exits before the invocation is reached); `if false; then
... fi` wrapped around it (the branch is never taken); a step-level `if: false` (GitHub Actions never
even starts the step's shell); the invocation written inside a heredoc (`cat <<'EOF' > run_it.sh` ...
`EOF` -- the line becomes the *content* of a file, never a command); and a shell function that wraps
the invocation but is defined and never called. Every one of these reads as "wired" to a check that
tokenizes lines without asking which of them the shell would execute, because token-level text is
still text -- the whole class of gap this file has now failed to close twice is "some property of
the text implies some property of the execution", and the only way to stop finding new members of
that class is to stop inferring execution from text and cause the execution instead.

So this file no longer parses the run: shell text. It extracts each step's run: text (still
block-scalar aware, now also dedented the way YAML's own `|` actually stores it -- a block scalar's
content is dedented by the indentation of its first non-blank line, yaml.org/spec/1.2.2/
#8111-block-scalar-headers -- which the shlex-based version never needed to get right, because
shlex does not care about a line's leading whitespace, and a heredoc's closing delimiter very much
does), reads that step's own `if:`, `working-directory:` and `env:`, and -- when the `if:` is absent
or a literal `true` -- actually runs the script with `bash -e`, in a throwaway sandbox, with a
recording stub standing in for `python`, `python3` and `pytest` on PATH. jasonkarns/bats-mock (a bats
mocking library extracted from ruby-build's own test suite) uses the same shape for the same reason:
a fake "binstub" placed in a directory prepended to PATH, with each invocation appended to a run file
the test inspects afterward -- a mock a test only reads is not proof of anything; a mock the code
under test had to actually call is. `exit 0` really does stop the script before the next line;
`if false` really does skip its branch; a heredoc really does just write a file; an uncalled
function's body really does never run -- none of these needed a special case in this file, because
none of them are special-cased: they are just what a real shell does with that text, which is the one
property a parser can never be talked out of by a cleverer input, because there is no parser left to
fool.

A step's `if:` gets the same treatment for the same reason this file already prefers a false failure
to a false pass: this is not a GitHub Actions expression evaluator (no success()/failure()/always()/
cancelled(), no matrix or secrets context), so a value that is not literally absent or `true`
(case-insensitively, optionally quoted) is read as "do not assume this step runs", and that step's
script is skipped -- with a warning saying so -- rather than guessed at either way. That can now make
this check miss a suite a real `if: runner.os == 'Linux'` would in fact have let run (a false
failure), but it can never credit a suite to a step a real `if: false` would have skipped (a false
pass), and a false pass is the one direction this file exists to rule out.

What this still cannot see, on purpose or otherwise: a step's `if:` written as anything other than a
bare literal always reads as "skip", even where GitHub Actions would actually run it -- undercounting,
the safe direction, but a real future conditional cpu-torch step would need a human to notice the
warning rather than a red CI check. Only `python`, `python3` and `pytest` are stubbed; a run: step
that shells out to anything else (curl, docker, apt-get, ...) executes for real in the sandbox, which
is fine for this job's two steps today (one is pip-install-that-is-actually-stubbed, twice; the other
is pytest) but is a real difference from the previous, inert, text-only check -- a future step that
reaches the network would now do so every time this test runs, and nothing here stops it. A command
invoked by its absolute path (/usr/bin/python3 ...) rather than its bare name never reaches PATH
resolution and so never reaches the stub; every invocation in this job today uses the bare name,
which is also the only form actions/setup-python ever produces. The stub's recording format is one
argument per line, terminated by a sentinel line: an argument that itself contained a newline would
desynchronize the log, and an argument equal to the sentinel text would be swallowed -- not a shape
any argument in this file's real content takes. And this check still only ever executes the
cpu-torch job; the standard-library job's own `FILES="test_a.py test_b.py"; pytest $FILES` pattern --
the false negative the second paragraph above already named on purpose -- would, if this same
executing design were ever pointed at that job too, actually resolve $FILES correctly, since bash
performs the expansion for real and a tokenizer never could. That gap is not closed here because it
was never this job's to close, but it is worth recording that executing rather than parsing would
close it for free.
"""
import functools
import os
import re
import shutil
import subprocess
import tempfile
import unittest
import warnings
from pathlib import Path
from typing import NamedTuple, Optional

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "tests.yml"

# Every locallm suite the cpu-torch job's own comment says it exists to run: the ones whose own
# module docstring says they need torch. Named explicitly, not discovered by scanning for "import
# torch", because a scan would need to run correctly to be trusted -- exactly the kind of
# self-referential check this file exists to avoid depending on.
CPU_TORCH_SUITES = ("test_dawnr_chat.py", "test_dawnr_api.py", "test_harness_chat.py", "test_fim.py",
                    "test_early_stop.py")

# A run: step invokes the test runner directly (`pytest ...`) or as a module (`python -m pytest ...`
# / `python3 -m unittest ...`). Matched against a real command's own argv, never raw text -- see
# _is_test_runner_invocation.
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


def _dedent_block_scalar(body_lines):
    """Undo the one YAML rule the previous (shlex-based) version of this file's run: extraction
    never needed to replicate: a `|` block scalar's content is stored dedented by the indentation
    of its first non-blank line (yaml.org/spec/1.2.2/#8111-block-scalar-headers). Feeding each
    line to shlex one at a time never cared about a line's leading whitespace; handing a whole
    multi-line body to bash as one script does, because a heredoc's closing delimiter has to sit
    at column 0 of the script a workflow author actually meant to write, not of the YAML file it
    happened to be indented inside of.
    """
    indents = [len(l) - len(l.lstrip(" \t")) for l in body_lines if l.strip() != ""]
    cut = min(indents) if indents else 0
    return "\n".join(l[cut:] if l.strip() != "" else "" for l in body_lines)


def _step_chunks(job_block: str):
    """Split a job block into one chunk per step, on the step-list `- ` marker's own indentation
    (the indentation of the first such marker found in the block). A `-` at any other indentation
    can never be mistaken for the start of the next step: shell content inside a run: body is
    always indented deeper than the run: key it belongs to, itself already deeper than any step
    marker. A block with no `- ` marker at all (every fixture from the second round predates this
    file needing per-step if:/working-directory:/env: context, and still writes a bare `run:` with
    nothing before it) is treated as one implicit step, so those fixtures are unchanged.
    """
    markers = list(re.finditer(r"(?m)^([ \t]*)-[ \t]", job_block))
    if not markers:
        return [job_block]
    indent = markers[0].group(1)
    starts = [m.start() for m in markers if m.group(1) == indent]
    return [job_block[s:e] for s, e in zip(starts, starts[1:] + [len(job_block)])]


class _Step(NamedTuple):
    run_text: Optional[str] = None
    if_value: Optional[str] = None
    working_directory: Optional[str] = None
    env: Optional[dict] = None


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _step_from_chunk(chunk: str) -> _Step:
    """One step's run: text (block-scalar aware, dedented) plus its `if:`, `working-directory:`
    and `env:` siblings -- found only outside the run: key's own lines (including its body), so a
    heredoc line that happens to read "if: something" can never be mistaken for this step's own
    condition. The step's own `- ` marker (only ever on the chunk's first line, since
    _step_chunks splits exactly there) is first replaced by equivalent spaces, so `- run: x` and
    `- name: x` line up at the same column as every other field this function looks for, instead
    of needing a separate rule for line zero.
    """
    lines = chunk.splitlines()
    if lines:
        lines[0] = re.sub(r"^([ \t]*)-([ \t]+)",
                           lambda m: " " * (len(m.group(1)) + 1 + len(m.group(2))), lines[0])

    run_text = None
    run_start = run_end = -1
    i = 0
    while i < len(lines):
        m = re.match(r"^(?P<indent>[ \t]*)run:[ \t]?(?P<value>.*)$", lines[i])
        if not m:
            i += 1
            continue
        indent, value = m.group("indent"), m.group("value")
        run_start = i
        if _BLOCK_SCALAR.match(value.strip()):
            body = []
            i += 1
            while i < len(lines) and (lines[i].strip() == ""
                                       or len(lines[i]) - len(lines[i].lstrip(" \t")) > len(indent)):
                body.append(lines[i])
                i += 1
            run_text = _dedent_block_scalar(body)
        else:
            run_text = value
            i += 1
        run_end = i
        break  # a step has at most one run: key

    if_value = None
    working_directory = None
    env = {}
    i = 0
    while i < len(lines):
        if run_start <= i < run_end:
            i += 1
            continue
        line = lines[i]
        m = re.match(r"^[ \t]*if:[ \t]?(.*)$", line)
        if m and if_value is None:
            if_value = m.group(1).strip()
            i += 1
            continue
        m = re.match(r"^[ \t]*working-directory:[ \t]?(.*)$", line)
        if m and working_directory is None:
            working_directory = m.group(1).strip()
            i += 1
            continue
        m = re.match(r"^([ \t]*)env:[ \t]*$", line)
        if m and not env:
            base_indent = len(m.group(1))
            i += 1
            while i < len(lines) and (lines[i].strip() == ""
                                       or len(lines[i]) - len(lines[i].lstrip(" \t")) > base_indent):
                em = re.match(r"^[ \t]+([A-Za-z_][A-Za-z0-9_]*):[ \t]?(.*)$", lines[i])
                if em:
                    env[em.group(1)] = _unquote(em.group(2).strip())
                i += 1
            continue
        i += 1

    return _Step(run_text=run_text, if_value=if_value, working_directory=working_directory,
                 env=env or None)


def _run_steps(job_block: str):
    """Every step in `job_block`, in document order, as a `_Step`."""
    return [_step_from_chunk(chunk) for chunk in _step_chunks(job_block)]


def _step_condition_is_true(if_value: Optional[str]) -> bool:
    """Whether this harness should run a step's script at all. This is not a GitHub Actions
    expression evaluator -- no success()/failure()/always()/cancelled(), no matrix or secrets
    context -- so the only conditions accepted as "runs" are the ones that do not need one: the
    key absent entirely, or a literal `true` (optionally quoted, in any case). Everything else,
    including a literal `false` and a real expression that would in fact evaluate true on
    GitHub's own runner, reads as "do not run this step's script" -- the safe direction, since it
    can only make this check miss a suite a real run would have covered, never credit one a real
    run would have skipped.
    """
    if if_value is None or if_value == "":
        return True
    return _unquote(if_value.strip()).lower() == "true"


_STUB_PROGRAMS = ("python", "python3", "pytest")
_STUB_END_MARKER = "@@ci-wiring-stub-call-end@@"
_STUB_TEMPLATE = (
    "#!/bin/sh\n"
    "{\n"
    "  printf '%s\\n' \"$0\"\n"
    "  for a in \"$@\"; do\n"
    "    printf '%s\\n' \"$a\"\n"
    "  done\n"
    "  printf '%s\\n' '" + _STUB_END_MARKER + "'\n"
    "} >> \"$CI_WIRING_STUB_LOG\"\n"
    "exit 0\n"
)


def _parse_invocations(log_text: str):
    """The stub log back into one argv list per call: `$0` followed by each `$@` entry, one per
    line, terminated by `_STUB_END_MARKER` -- the same shape jasonkarns/bats-mock calls a "stub
    run file", just written by a plain /bin/sh stub instead of a bats helper.
    """
    invocations = []
    current = []
    for line in log_text.split("\n"):
        if line == _STUB_END_MARKER:
            invocations.append(current)
            current = []
        else:
            current.append(line)
    return invocations


def _is_test_runner_invocation(argv) -> bool:
    """Mirrors the previous version's recognition rule (`pytest ...`, `python -m pytest ...`,
    `python3 -m unittest ...`) against what a command actually received instead of a statically
    tokenized line. `python -m pip install ... pytest` has argv = ["python", "-m", "pip", ...]:
    argv[2] is "pip", not "pytest" or "unittest", so this is still never mistaken for the
    invocation merely because the word "pytest" appears somewhere in it.
    """
    if not argv:
        return False
    prog = Path(argv[0]).name
    if prog in _RUNNER_MODULES:
        return True
    return (prog in ("python", "python3") and len(argv) >= 3
            and argv[1] == "-m" and argv[2] in _RUNNER_MODULES)


@functools.lru_cache(maxsize=None)
def _wired_suites(job_block: str) -> frozenset:
    """Every suite filename actually passed to a test runner when this job's run: steps are
    executed for real, once, in a throwaway sandbox -- see the module docstring's third section
    for why this replaced a text-level check. Cached on the job block's own text, since
    WiredSuitesExecutionTests below and CpuTorchJobCoverage's five subTests all call `_is_wired`
    against the same string repeatedly.
    """
    if shutil.which("bash") is None:
        raise unittest.SkipTest(
            "bash not found on PATH; the cpu-torch coverage check runs the job's own run: steps "
            "in a sandbox and needs a POSIX shell to do it -- this repository's own workflow "
            "already assumes one (tests.yml's standard-library job sets shell: bash, including "
            "for windows-latest)")

    invoked = []
    with tempfile.TemporaryDirectory(prefix="ci-wiring-") as tmp_name:
        tmp = Path(tmp_name)
        bin_dir = tmp / "bin"
        bin_dir.mkdir()
        for prog in _STUB_PROGRAMS:
            stub = bin_dir / prog
            stub.write_text(_STUB_TEMPLATE)
            stub.chmod(0o755)

        log_path = tmp / "invocations.log"
        log_path.write_text("")
        workspace = tmp / "workspace"
        workspace.mkdir()
        scripts_dir = tmp / "scripts"
        scripts_dir.mkdir()

        base_env = dict(os.environ)
        base_env["CI_WIRING_STUB_LOG"] = str(log_path)

        for n, step in enumerate(_run_steps(job_block)):
            if step.run_text is None:
                continue  # a `uses:` step (actions/checkout, actions/setup-python, ...): there is
                          # no shell script to run and nothing this check needs from it.
            if not _step_condition_is_true(step.if_value):
                warnings.warn(
                    f"cpu-torch coverage check: step {n} has if: {step.if_value!r}, which is not "
                    f"a literal true condition, so its run: script was not executed and none of "
                    f"its suites can count as wired here")
                continue

            cwd = workspace
            if step.working_directory:
                cwd = workspace / step.working_directory
                cwd.mkdir(parents=True, exist_ok=True)

            env = dict(base_env)
            if step.env:
                env.update(step.env)
            env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")

            script_path = scripts_dir / f"step-{n}.sh"
            script_path.write_text(step.run_text)
            result = subprocess.run(["bash", "-e", str(script_path)], cwd=str(cwd), env=env,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     timeout=30, text=True)
            if result.returncode != 0:
                warnings.warn(
                    f"cpu-torch coverage check: step {n}'s run: script exited "
                    f"{result.returncode} under bash -e; output: {result.stdout!r}. That step's "
                    f"suites may be undercounted rather than wrongly credited, which is this "
                    f"check's safe direction, but a nonzero exit here usually means the real "
                    f"workflow step would fail too")

        for argv in _parse_invocations(log_path.read_text()):
            if _is_test_runner_invocation(argv):
                invoked.extend(argv)
    return frozenset(invoked)


def _is_wired(suite: str, job_block: str) -> bool:
    """Whether `suite` is actually passed as an argument to a test runner when this job's run:
    steps are executed for real -- the only thing "this suite runs in CI" can honestly mean.
    """
    return suite in _wired_suites(job_block)


class CpuTorchJobCoverage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")
        cls.job = _job_block(cls.text, "cpu-torch")

    def test_every_cpu_torch_suite_is_named_in_the_jobs_run_command(self):
        wired = _wired_suites(self.job)
        for suite in CPU_TORCH_SUITES:
            with self.subTest(suite=suite):
                self.assertIn(
                    suite, wired,
                    f"{suite} needs torch but actually running the cpu-torch job's own run: "
                    f"steps (stubbed python/python3/pytest, real bash -e, real "
                    f"if:/working-directory:/env:) never invokes a test runner with it as an "
                    f"argument -- a mention in a comment, a disabled step, a branch that is "
                    f"never taken, a heredoc, or a function defined but never called doesn't "
                    f"count. Filenames this run actually did pass to a runner: "
                    f"{sorted(a for a in wired if a.endswith('.py'))}")


class WiredSuitesExecutionTests(unittest.TestCase):
    """_is_wired() against fixtures, not the real workflow file, so these run the same whether or
    not tests.yml is ever edited. The six `test_a_suite_...`-style cases below are the fixtures
    this file grew for the second-round gap -- six ways a filename could sit in a job's raw text
    without the job ever passing it to a test runner; every one of them still has to pass, now by
    way of actually running the fixture's run: text in the same sandbox the real check uses,
    rather than shlex-tokenizing it.

    The rest are the third round: five fixtures reproducing a reviewer's own list, each a way to
    make a token-level read of the text say "wired" while a real shell never reaches the
    invocation, plus three narrower ones this rewrite's own design commits to and would otherwise
    ship untested (an `if: true`/absent step still runs; a non-literal `if:` reads as "skip", not
    "run"; a step's own `env:` reaches its script).
    """

    # --- second round: a mention that is not a wiring (unchanged fixtures, now executed) ---

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

    # --- third round: token-level text says "wired"; a real shell never reaches it ---

    def test_an_exit_before_the_invocation_means_the_shell_never_reaches_it(self):
        job = (
            "      - name: locallm CPU-torch suites\n"
            "        working-directory: locallm\n"
            "        run: |\n"
            "          exit 0\n"
            "          python -m pytest -v test_dawnr_api.py\n"
        )
        self.assertFalse(_is_wired("test_dawnr_api.py", job))

    def test_an_invocation_inside_an_if_false_branch_never_runs(self):
        job = (
            "      - name: locallm CPU-torch suites\n"
            "        working-directory: locallm\n"
            "        run: |\n"
            "          if false; then\n"
            "            python -m pytest -v test_dawnr_api.py\n"
            "          fi\n"
        )
        self.assertFalse(_is_wired("test_dawnr_api.py", job))

    def test_a_step_whose_own_if_is_false_never_runs_its_script(self):
        job = (
            "      - name: locallm CPU-torch suites (disabled)\n"
            "        if: false\n"
            "        working-directory: locallm\n"
            "        run: python -m pytest -v test_dawnr_api.py\n"
        )
        self.assertFalse(_is_wired("test_dawnr_api.py", job))

    def test_an_invocation_written_into_a_heredoc_file_is_never_executed(self):
        # The line is real, well-formed shell -- it just writes a file instead of running a
        # command. A block-scalar-aware line scan (this file's second-round design) cannot tell
        # this from a real invocation; a real shell writes run_it.sh and calls nothing.
        job = (
            "      - name: locallm CPU-torch suites\n"
            "        working-directory: locallm\n"
            "        run: |\n"
            "          cat <<'RUNNER' > run_it.sh\n"
            "          python -m pytest -v test_dawnr_api.py\n"
            "          RUNNER\n"
        )
        self.assertFalse(_is_wired("test_dawnr_api.py", job))

    def test_a_shell_function_that_wraps_the_invocation_but_is_never_called_never_runs_it(self):
        job = (
            "      - name: locallm CPU-torch suites\n"
            "        working-directory: locallm\n"
            "        run: |\n"
            "          run_cpu_torch_suite() {\n"
            "            python -m pytest -v test_dawnr_api.py\n"
            "          }\n"
        )
        self.assertFalse(_is_wired("test_dawnr_api.py", job))

    # --- narrower cases this rewrite's own design commits to ---

    def test_a_step_whose_own_if_is_literally_true_still_runs_its_script(self):
        # The other half of the if: false fixture above: an if: key being *present* must not by
        # itself be read as "skip", only a present-and-not-true value should be.
        job = (
            "      - name: locallm CPU-torch suites\n"
            "        if: true\n"
            "        working-directory: locallm\n"
            "        run: python -m pytest -v test_dawnr_api.py\n"
        )
        self.assertTrue(_is_wired("test_dawnr_api.py", job))

    def test_a_steps_if_that_is_a_github_expression_is_treated_as_not_a_literal_true(self):
        # This is not an expression evaluator: ${{ success() }} would genuinely run on GitHub's
        # own runner, but reading it as "skip" is the safe direction (see the module docstring).
        job = (
            "      - name: locallm CPU-torch suites\n"
            "        if: ${{ success() }}\n"
            "        working-directory: locallm\n"
            "        run: python -m pytest -v test_dawnr_api.py\n"
        )
        self.assertFalse(_is_wired("test_dawnr_api.py", job))

    def test_a_steps_declared_env_reaches_its_script(self):
        # Not one of the five reviewer inputs, but the design explicitly calls for honoring a
        # step's env: the same way as its working-directory: and if:, so a step that only decides
        # which suite to run by reading its own env var is exercised at least once. This also
        # demonstrates a capability the old shlex-based design structurally could not have, even
        # in principle: real variable expansion (the same reason the standard-library job's own
        # $FILES-driven suites, named in the module docstring, are a known false negative there).
        job = (
            "      - name: locallm CPU-torch suites\n"
            "        env:\n"
            "          SUITE: test_dawnr_api.py\n"
            "        run: python -m pytest -v \"$SUITE\"\n"
        )
        self.assertTrue(_is_wired("test_dawnr_api.py", job))


if __name__ == "__main__":
    unittest.main()
