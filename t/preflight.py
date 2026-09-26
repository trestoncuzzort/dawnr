#!/usr/bin/env python3
"""t/preflight.py -- everything that could make a round's numbers wrong, checked before the round (2026-09-18).

    python3 t/preflight.py --split t/out/loop/split-v5.json --pool t/out/loop/sft-r12.jsonl \
        --corpus t/out/loop/corpus-r12.txt [--answer-set TAG] [--audit-history] \
        [--tokenizer NAME] [--quick] [--strict]

Each check below exists because something went wrong once. A round should not start while any of them fails,
and the ones that fail print what to do. `--strict` exits non-zero on a warning as well as a failure.

  1. The seven checkers are present, and at the versions t/AGREEMENT.md was measured with. A checker missing
     from PATH does not read as absent in every path: a hand-run grading on 2026-09-17 reported MALFORMED for
     every Verus cell because a non-login shell had no Rust toolchain.
  2. No held-out problem appears in the training set or the pairs. The split is the whole basis of every
     held-out number.
  3. No selected training input contains a program recorded as disagreeing with its problem's own solution
     (t/spec_check.py). Five did on 2026-09-18, and all five had passed the tests, all seven proofs and a
     refuted twin.
  4. No cell counted clean is marked FLAKED, and none of a clean answer's cells is a timeout. A timeout is not
     a verdict, and grading at 64 jobs on a shared machine produces them.
  5. The copy check's keys are unique, so no answer entered the pool twice under two tags.
  6. There is room to write: this machine's disk and the grading machine's.
  7. Every prompt version builds, the versions the run asks for exist, and no prompt in use contradicts the
     parser about the notation (2026-09-19). Prompt v1, v2 and v3 told every model for eleven days that t has
     "no division, no modulo"; division has existed since 2026-09-08, and prompt v4 -- which is built by
     replacement into v3's own text, so an edit to v3 makes v4's asserts fire on import -- was worth 3 clean
     answers to 5 on the same 232 problems. A wrong sentence costs a round; it should not cost eleven days.
  8. Every grammar the run decodes against parses: each rule it names is defined, each rule it defines is
     reachable from `root`, the generated identifier rules still agree with surface.KEYWORDS, and, where
     xgrammar is installed, the backend itself loads the file (2026-09-19). A grammar that does not load does
     not stop the run; it silently decodes unconstrained, and the constrained arm of
     t/PREREG-2026-09-18-constrained.md is then the unconstrained arm under another name. The related trap is
     recorded: `--grammar` reached three call sites and missed the one that ran, and the tell was 158 parse
     failures against 159.
  9. The data files the run opens are here, tracked, and on the grading machine (2026-09-19). `t/out/` is
     gitignored, so anything a clone needs -- the id lists, the splits, the pool files -- is only there if it
     was `git add -f`ed; the audit of 2026-09-19 found round 6's whole pool missing from the repository. A run
     that dies in its first seconds with FileNotFoundError is almost always one of these.
 10. Every selected answer set has a kernels.md, tests.json and an extract.json (2026-09-19).
     `clean_rows` reads a missing tests.json as "no answer passed its tests", so half a set does not announce
     itself: it quietly contributes nothing to a count that is then reported as if it had been counted.
 11. No selected answer set's kernels.md has fewer than the seven kernel columns (2026-09-19). A table graded with
     `--kernels lean` alone reports agreement among one column; the audit of that day made the cell say
     `(only N kernels)`, and this refuses to let such a table sit where a clean count is taken from it.
 12. The tokenizer of the base model the run names round-trips a line of t, and loop_generate.py still holds
     its own round-trip guard (2026-09-18). DeepSeek-Prover-V2-7B loads as LlamaTokenizer under transformers
     5.17 and drops every space on the way back: 122 answers came out as `t1tasksmall_nnum(s:seq,n:int)`.
     This one costs a few seconds where a tokenizer library is installed, like a kernel check does.
 13. t/AGREEMENT.md has a row for every committed task (2026-09-25). A one-task run_par.py sweep overwrote
     the table on 2026-09-20, and the corpus builder then kept 1 of 35 committed tasks without a word.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

KERNELS = ["dafny", "verus", "spark", "framac", "lean", "rocq", "fstar"]
ROOT = HERE.parent
OUT = HERE / "out"
SE = OUT / "spec-experiment"

# The files that say what a round will actually run, so checks 7 to 9 read the run rather than a list kept by
# hand: the leak check fell a round behind exactly that way (2026-09-19).
RUN_SCRIPTS = ("steps.json", "lab_gpu.sh", "grade_lab.sh", "overnight.py")
# loop_generate.py's own probe, so this checks the line that file checks
PROBE = "t 1 task f(x: int) returns (r: int)"
# the clone on the grading machine, as t/lab_gpu.sh's own rsync writes it ("$LAB:tup/...")
LAB_DIR = "tup"

WARNED: list[str] = []


def say(ok: bool, name: str, detail: str = "") -> bool:
    print(f"  [{'ok  ' if ok else 'FAIL'}] {name}" + (f": {detail}" if detail else ""))
    return ok


def warn(name: str, detail: str = "") -> bool:
    """Something that will not make this round's numbers wrong but will make the next one's. `--strict` fails
    on these, so a round that is about to be reported can be held to them."""
    WARNED.append(name)
    print(f"  [warn] {name}" + (f": {detail}" if detail else ""))
    return True


def run_text() -> str:
    """Every command this project runs, concatenated, for the flag scans below."""
    out = []
    for name in RUN_SCRIPTS:
        p = HERE / name
        if p.exists():
            out.append(p.read_text(errors="replace"))
    return "\n".join(out)


def flag(text: str, name: str) -> list[str]:
    """Every value given to `--name` anywhere in `text`, JSON quoting and trailing commas stripped."""
    return [v for v in re.findall(rf"--{name}[=\s]+([^\s\"',]+)", text) if v]


def tables() -> list[Path]:
    """The answer sets that have been graded: every directory under out/spec-experiment with a kernels.md."""
    return sorted(p for p in SE.glob("*") if (p / "kernels.md").exists())


def versions_from_agreement() -> dict:
    out = {}
    try:
        for line in (HERE / "AGREEMENT.md").read_text(errors="replace").splitlines():
            m = re.match(r"- (\w+): (.+)", line.strip())
            if m and m.group(1) in KERNELS:
                out[m.group(1)] = m.group(2).strip()
    except OSError:
        pass
    return out


def check_kernels() -> bool:
    ok = True
    want = versions_from_agreement()
    for k in KERNELS:
        try:
            mod = __import__(f"verifiers.{k}", fromlist=["version"])
            have = mod.version()
        except (Exception, SystemExit) as e:                    # noqa: BLE001
            ok = say(False, f"{k} present", str(e).split("\n")[0][:80]) and ok
            continue
        w = want.get(k, "")
        if "?" in have or not have.strip():
            # the 2026-09-17 trap: the binary answers but its toolchain is missing, so the adapter cannot even
            # read a version and every cell would read MALFORMED
            ok = say(False, f"{k} version readable", f"reported {have!r}") and ok
            continue
        same = (not w) or w.split()[0] in have or have.split()[0] in w
        ok = say(same, f"{k} {have[:40]}", "" if same else f"AGREEMENT.md measured with {w[:40]}") and ok
    return ok



def _decoded_strings(value):
    """Yield JSON strings after decoding so task declarations are real newlines."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _decoded_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _decoded_strings(child)


def _pool_metadata(text: str) -> tuple[str, list[str | None], list[object]]:
    """Extract explicit producer metadata without trusting a display-name alias."""
    decoded, names, task_ids = [text], [], []
    for line in text.splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        decoded.extend(_decoded_strings(row))
        if isinstance(row, dict):
            names.append(row.get("task"))
            task_ids.append(row.get("task_id"))
    return "\n".join(decoded), names, task_ids


def _check_training_validation(path: Path, validation, verb: str) -> bool:
    """Print the two independent training-data guarantees from the shared gate."""
    import loop_filter

    held = say(not validation.held_out, f"{path.name} {verb} no held-out problem",
               "" if not validation.held_out else loop_filter.held_out_detail(validation.held_out))
    same = say(not (validation.same_task_names or validation.same_task_ids),
               f"{path.name} {verb} no same-task training source",
               "" if not (validation.same_task_names or validation.same_task_ids)
               else loop_filter.same_task_detail(validation))
    return held and same


def check_pool_files(eval_ids: set[int], files: list[Path]) -> bool:
    """Check selected JSONL training rows through the shared data validator."""
    import loop_filter

    ok = True
    for path in files:
        try:
            text = path.read_text(errors="replace")
        except OSError as error:
            ok = say(False, f"{path.name} readable", str(error)[:80]) and ok
            continue
        payload, names, task_ids = _pool_metadata(text)
        validation = loop_filter.validate_training_data(payload, eval_ids, names=names, task_ids=task_ids)
        ok = _check_training_validation(path, validation, "holds") and ok
    return ok


def check_corpora(eval_ids: set[int], corpora: list[Path]) -> bool:
    """Check selected text corpora through the shared data validator."""
    import loop_filter

    ok = True
    for path in corpora:
        try:
            text = path.read_text(errors="replace")
        except OSError as error:
            ok = say(False, f"{path.name} readable", str(error)[:80]) and ok
            continue
        validation = loop_filter.validate_training_data(text, eval_ids)
        ok = _check_training_validation(path, validation, "trains on") and ok
    return ok


def _unique_paths(paths) -> list[Path]:
    """Keep caller order while making one current file produce one verdict."""
    result, seen = [], set()
    for path in paths:
        path = Path(path)
        key = path.resolve(strict=False)
        if key not in seen:
            seen.add(key)
            result.append(path)
    return result


def _repository_relative(path: Path) -> str | None:
    """A selected input's stable repository-relative name, or None if it cannot be reproduced from the tree."""
    candidate = Path(path)
    absolute = candidate if candidate.is_absolute() else ROOT / candidate
    try:
        return str(absolute.resolve(strict=False).relative_to(ROOT.resolve()))
    except ValueError:
        return None


def _historical_training_inputs() -> tuple[list[Path], list[Path]]:
    """The opt-in audit of legacy artifacts, never the default run boundary."""
    pools = sorted((OUT / "loop").glob("sft-*.jsonl")) + sorted((OUT / "loop").glob("pairs-*.jsonl"))
    corpora = (sorted((OUT / "loop").glob("corpus-*.txt"))
               + sorted((OUT / "loop-locallm").glob("corpus*.txt")))
    return pools, corpora


def selected_training_inputs(pool_files: list[Path] = (), corpora: list[Path] = (),
                             audit_history: bool = False) -> tuple[list[Path], list[Path]]:
    """Current training inputs, plus legacy files only under an explicit history audit."""
    pools, texts = _unique_paths(pool_files), _unique_paths(corpora)
    if audit_history:
        old_pools, old_corpora = _historical_training_inputs()
        pools = _unique_paths([*pools, *old_pools])
        texts = _unique_paths([*texts, *old_corpora])
    return pools, texts


def _valid_answer_set_tag(tag: str) -> bool:
    """Tags name direct children of spec-experiment, never arbitrary filesystem paths."""
    return bool(isinstance(tag, str) and tag and tag not in {".", ".."} and "/" not in tag and "\\" not in tag
                and not Path(tag).is_absolute())


def select_answer_sets(tags: list[str], audit_history: bool = False) -> tuple[bool, list[Path]]:
    """Resolve the result sets that this preflight is allowed to judge.

    Cargo distinguishes explicit package selection from an explicit workspace-wide
    operation: https://doc.rust-lang.org/cargo/reference/workspaces.html#package-selection .
    We use the same boundary here. Unlike Cargo there is no meaningful implicit
    "current" answer set before generation, so no tag defers result-quality checks;
    ``--audit-history`` is the deliberate all-set audit. This preserves the old
    result provenance rather than making it an accidental input, following the
    workflow-provenance distinction in https://arxiv.org/abs/1406.0905 .
    """
    selected, ok = [], True
    for tag in tags:
        if not _valid_answer_set_tag(tag):
            ok = say(False, "answer-set tag is a direct child of out/spec-experiment", repr(tag)) and ok
            continue
        directory = SE / tag
        if not directory.is_dir() or not (directory / "kernels.md").is_file():
            ok = say(False, f"selected answer set {tag} has kernels.md",
                     f"expected {directory / 'kernels.md'}") and ok
            continue
        selected.append(directory)
    if audit_history:
        selected = _unique_paths([*selected, *tables()])
        print(f"  [note] auditing {len(selected)} answer set(s), including history")
    else:
        selected = _unique_paths(selected)
        if selected:
            print(f"  [note] checking {len(selected)} selected answer set(s)")
    return ok, selected


def check_split(split_path: Path, pool_files: list[Path] = (), corpora: list[Path] = (),
                audit_history: bool = False) -> bool:
    """Validate only the training inputs selected for this run.

    Historical artifacts are evidence, not implicit inputs to a new run. Use
    audit_history when reviewing them deliberately; otherwise an old corpus
    cannot make a new preflight fail or pass by accident.
    """
    try:
        split = json.loads(split_path.read_text())
        eval_ids = {int(task_id) for task_id in split["eval_ids"]}
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        return say(False, "split readable", f"{split_path}: {error}")
    pools, corpora = selected_training_inputs(pool_files, corpora, audit_history)
    if audit_history:
        print(f"  [note] auditing {len(pools)} historical pool file(s) and {len(corpora)} corpus file(s)")
    elif not pools and not corpora:
        return say(False, "current training input selected",
                   "pass --pool and/or --corpus; use --audit-history only for a deliberate legacy audit")
    else:
        print(f"  [note] checking {len(pools)} selected pool file(s) and {len(corpora)} selected corpus file(s)")
    if not pools and not corpora:
        return say(True, "historical training inputs", "none found")
    ok = True
    if pools:
        ok = check_pool_files(eval_ids, pools) and ok
    if corpora:
        ok = check_corpora(eval_ids, corpora) and ok
    return ok


def clean_rows(tag_dir: Path) -> dict:
    """task -> its row, for answers counted clean (tests pass and all seven verified with the twin refuted)."""
    import spec_experiment as se
    cols, cells = se.parse_kernel_table(tag_dir / "kernels.md")
    try:
        tests = {v.get("name"): v.get("overall") for v in json.loads((tag_dir / "tests.json").read_text()).values()}
    except (OSError, ValueError):
        tests = {}
    return {n: r for n, r in cells.items()
            if tests.get(n) == "pass" and all(r.get(k, "").startswith("verified / refuted") for k in KERNELS)}


def rechecked() -> set:
    """Cells re-verified alone and recorded in t/out/recheck.json. A FLAKED mark means the sweep disagreed with
    itself under load, not that the cell is unstable: lower_spark.py's own notes call a spark cell graded at
    high concurrency provisional until it is re-run alone. A re-check is only worth anything if it is written
    down with how it was run, so this reads that file rather than letting anyone edit a verdict by hand."""
    try:
        rows = json.loads((OUT / "recheck.json").read_text()).get("rechecked", [])
    except (OSError, ValueError):
        return set()
    return {(r["tag"], r["task"], r["kernel"]) for r in rows
            if r.get("alone", "").startswith("verified / refuted")}


def check_flakes(answer_sets: list[Path]) -> bool:
    """Check only the explicitly selected result sets for flaky clean rows."""
    ok_alone = rechecked()
    flaked, timeouts, total = [], [], 0
    for d in _unique_paths(answer_sets):
        for name, row in clean_rows(d).items():
            total += 1
            for k in KERNELS:
                cell = row.get(k, "")
                if "FLAKED" in cell and (d.name, name, k) not in ok_alone:
                    flaked.append(f"{d.name}/{name} {k}")
                if "timeout" in cell:
                    timeouts.append(f"{d.name}/{name} {k}")
    if ok_alone:
        print(f"  [note] {len(ok_alone)} cell(s) re-verified alone, recorded in out/recheck.json")
    ok = say(not flaked, f"no clean answer rests on a flaked cell ({total} clean)",
             "" if not flaked else f"{len(flaked)}: {flaked[:3]}")
    return say(not timeouts, "no clean answer rests on a timeout",
               "" if not timeouts else f"{len(timeouts)}: {timeouts[:3]}") and ok


def check_spec_agreement(pool_files: list[Path], corpora: list[Path]) -> bool:
    """Reject a recorded disagreement only when its program occurs in this run's selected training inputs."""
    pool_files, corpora = _unique_paths(pool_files), _unique_paths(corpora)
    inputs = _unique_paths([*pool_files, *corpora])
    if not inputs:
        return say(True, "selected training inputs checked against specifications", "none selected")
    j = OUT / "spec-disagree.json"
    if not j.exists():
        return say(False, "specifications checked against the problems", "run python3 t/spec_check.py")
    try:
        report = json.loads(j.read_text())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return say(False, "specification disagreement report readable", str(error)[:80])
    if not isinstance(report, dict):
        return say(False, "specification disagreement report is an object")
    bad, progs = report.get("disagree", []), report.get("programs", {})
    if not isinstance(bad, list) or not isinstance(progs, dict):
        return say(False, "specification disagreement report has list and program map")
    unmapped = [key for key in bad if not isinstance(key, str) or not isinstance(progs.get(key), str)]
    if unmapped:
        return say(False, "specification disagreement report maps every disagreement to program text",
                   f"{len(unmapped)} missing or invalid: {unmapped[:3]!r}")
    texts = []
    for path in pool_files:
        try:
            payload, _names, _task_ids = _pool_metadata(path.read_text(errors="replace"))
        except OSError as error:
            return say(False, f"{path.name} readable for specification check", str(error)[:80])
        texts.append(payload)
    for path in corpora:
        try:
            texts.append(path.read_text(errors="replace"))
        except OSError as error:
            return say(False, f"{path.name} readable for specification check", str(error)[:80])
    # compare the program, not the problem name: another model's answer to the same problem may be fine
    squash = lambda s: " ".join(s.split())                       # noqa: E731
    flat = squash("\n".join(texts))
    in_inputs = [x for x in bad if isinstance(x, str) and isinstance(progs.get(x), str)
                 and squash(progs[x]) in flat]
    ok = say(not in_inputs,
             f"no answer in selected training inputs disagrees with its problem ({len(bad)} disagreements found)",
             "" if not in_inputs else f"{in_inputs}")
    if bad and not in_inputs:
        print(f"  [note] {len(bad)} recorded disagreement(s) are outside the selected training inputs; "
              f"score_heldout.py counts held-out ones apart, see {j.name}")
    return ok


def check_keys() -> bool:
    p = OUT / "pool-keys.txt"
    if not p.exists():
        return say(True, "copy-check keys (none yet)")
    keys = p.read_text(errors="replace").splitlines()
    dup = len(keys) - len(set(keys))
    return say(dup == 0, f"copy-check keys unique ({len(keys)})", "" if not dup else f"{dup} duplicates")


def check_space(lab: str | None) -> bool:
    free = shutil.disk_usage(HERE).free / 1e9
    ok = say(free > 20, f"this machine has {free:.0f} GB free")
    if lab:
        try:
            out = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", lab,
                                  "df -B1 --output=avail / | tail -1"], capture_output=True, text=True, timeout=30)
            gb = int(out.stdout.strip() or 0) / 1e9
            ok = say(gb > 20, f"the grading machine has {gb:.0f} GB free") and ok
        except (OSError, ValueError, subprocess.SubprocessError) as e:
            ok = say(False, "grading machine reachable", str(e)[:60]) and ok
    return ok


def check_evaluator(lab: str | None) -> bool:
    """The machine that runs the kernels runs its own tree, and that tree drifts.

    On 2026-09-19 it was 19 commits behind origin with 109 dirty entries while
    every log line looked normal, because grade_lab.sh ran `git pull --ff-only
    || true`. Two answer sets graded by different evaluators cannot be compared,
    and nothing anywhere said so. This warns rather than fails: those dirty
    files are other agents' unverified work and must be preserved, and a round
    graded by a known-stale evaluator is fine as long as its baseline is
    regraded beside it.
    """
    if not lab:
        return True
    try:
        # Tracked modifications and untracked files are counted apart on purpose.
        # A modified tracked file IS a different evaluator. An untracked file is
        # not: nothing imports it. Counting them together made this warn "the
        # grading machine is not this tree: it grades at 07ab406 ... this tree is
        # at 07ab406" over three stray files on 2026-09-20, which reads as a
        # contradiction and trains the reader to skip the line. A check that
        # cries wolf every round is worse than no check, because this is the one
        # that catches a genuinely stale evaluator.
        out = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", lab,
             "cd ~/tup && git rev-parse --short HEAD"
             " && git status --porcelain --untracked-files=no | wc -l"
             " && git ls-files --others --exclude-standard | wc -l"],
            capture_output=True, text=True, timeout=45)
        lines = [line.strip() for line in out.stdout.splitlines() if line.strip()]
        if len(lines) < 3:
            return warn("grading machine state unreadable", out.stderr.strip()[:60])
        head, modified, untracked = lines[0], int(lines[1]), int(lines[2])
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return warn("grading machine state unreadable", str(error)[:60])
    mine = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                          text=True, cwd=HERE.parent).stdout.strip()
    if head == mine and modified == 0:
        if untracked:
            return say(True, f"the grading machine matches this tree at {head} "
                             f"({untracked} untracked file(s), which change no evaluator)")
        return say(True, f"the grading machine matches this tree at {head}")
    if head == mine:
        detail = f"same commit {head}, but {modified} tracked file(s) modified there"
    else:
        detail = (f"it grades at {head}, this tree is at {mine}"
                  + (f", and {modified} tracked file(s) are modified there" if modified else ""))
    warn("the grading machine is not this tree", detail)
    print("         regrade a baseline beside any new answer set, or the comparison "
          "spans two evaluators")
    return True


def check_prompt() -> bool:
    """Check 7. Every prompt version builds, the ones the run names exist, and no prompt in use tells the
    model something about the notation that this repository's own parser contradicts."""
    text = run_text()
    try:
        import spec_experiment as se
        import surface
    except Exception as e:                                      # noqa: BLE001
        # prompt v4 is built by replacing strings in v3's own text and asserts it found each one, so an edit to
        # v3 fails this import rather than shipping two prompts that have quietly drifted apart
        return say(False, "the prompt module imports", f"{type(e).__name__}: {e}".split("\n")[0][:90])

    named = sorted(set(flag(text, "prompt")))
    unknown = [v for v in named if v not in se.PROMPT_VERSIONS]
    ok = say(not unknown, f"prompt versions the run asks for exist ({', '.join(named) or 'none named'})",
             "" if not unknown else f"{unknown} is not one of {list(se.PROMPT_VERSIONS)}; add it to "
                                    f"spec_experiment.PROMPT_VERSIONS or fix the step that names it")

    entry = {"rec": {"text": "a problem", "test_list": ["assert f(1) == 1"]}, "fn": "f",
             "points": [{"args": [("int", 1)], "expected": [("int", 1)]}]}
    built = {}
    for v in se.PROMPT_VERSIONS:
        try:
            built[v] = se.build_prompt(entry, v)[0]["content"]
        except Exception as e:                                  # noqa: BLE001
            ok = say(False, f"prompt {v} builds", f"{type(e).__name__}: {e}".split("\n")[0][:90]) and ok
    ok = say(len(built) == len(se.PROMPT_VERSIONS),
             f"{len(built)} of {len(se.PROMPT_VERSIONS)} prompt versions build "
             f"({min((len(t) for t in built.values()), default=0)}-"
             f"{max((len(t) for t in built.values()), default=0)} chars)") and ok

    # what the prompt claims about the notation, against what the parser does with it: the eleven-day sentence
    divides = "t 0\ntask q(a: int, b: int) returns (r: int)\n  requires b > 0\n{\n  r := a / b;\n}\n"
    try:
        surface.parse(divides)
        has_div = True
    except Exception:                                           # noqa: BLE001
        has_div = False
    squash = lambda s: " ".join(s.split())                      # noqa: E731
    lying = [v for v in (named or list(se.PROMPT_VERSIONS))
             if v in built and has_div and "no division" in squash(built[v])]
    if lying:
        warn(f"a prompt in use says t has no division, and surface.py parses `a / b` ({', '.join(lying)})",
             "v4 corrects it (3 clean to 5 on the same 232 problems); run the round with --prompt v4, or say "
             "in the log why this one is generating under the old sentence")
    else:
        say(True, f"no prompt in use contradicts the parser about division "
                  f"(parser accepts `a / b`: {has_div})")
    return ok


def gbnf_rules(src: str) -> dict:
    """rule name -> the rule names its right-hand side uses. Quoted strings and character classes go first, so
    a `#` inside either is not read as a comment and `int` inside `"int"` is not read as a rule."""
    rules: dict[str, str] = {}
    cur = None
    for line in src.splitlines():
        s = re.sub(r'"(\\.|[^"\\])*"', " ", line)
        s = re.sub(r"\[(\\.|[^\]\\])*\]", " ", s)
        s = s.split("#")[0]
        m = re.match(r"\s*([A-Za-z][A-Za-z0-9_-]*)\s*::=(.*)", s)
        if m:
            cur = m.group(1)
            rules[cur] = rules.get(cur, "") + " " + m.group(2)
        elif cur and s.strip():
            rules[cur] += " " + s
    return {k: set(re.findall(r"[A-Za-z][A-Za-z0-9_-]*", v)) for k, v in rules.items()}


def check_grammar() -> bool:
    """Check 8. Every grammar the run decodes against is a grammar: defined, connected, in step with the
    lexer's keywords, and loadable by the backend where the backend is installed."""
    text = run_text()
    paths = {(ROOT / p).resolve() for p in flag(text, "grammar")}
    if (HERE / "t.gbnf").exists():
        paths.add((HERE / "t.gbnf").resolve())
    if not paths:
        return say(True, "no grammar named by any step (nothing to check)")
    ok = True
    for p in sorted(paths):
        rel = p.relative_to(ROOT) if p.is_relative_to(ROOT) else p
        if not p.exists():
            ok = say(False, f"{rel} exists",
                     "the step that passes --grammar will decode unconstrained without it") and ok
            continue
        src = p.read_text(errors="replace")
        rules = gbnf_rules(src)
        undefined = sorted({r for used in rules.values() for r in used} - set(rules))
        seen, stack = set(), ["root"]
        while stack:
            n = stack.pop()
            if n in seen or n not in rules:
                continue
            seen.add(n)
            stack += sorted(rules[n])
        orphans = sorted(set(rules) - seen)
        ok = say("root" in rules and not undefined,
                 f"{rel} parses: {len(rules)} rules, root present, none undefined",
                 "" if "root" in rules else "no `root` rule" if not undefined
                 else f"{len(undefined)} used and never defined: {undefined[:5]}") and ok
        if orphans:
            warn(f"{rel} has {len(orphans)} rule(s) unreachable from root", f"{orphans[:5]}")
        try:
            import make_grammar
            import surface
            body = make_grammar.rules(set(surface.KEYWORDS))
            fresh = src.partition(make_grammar.BEGIN)[0] + body + src.partition(make_grammar.END + "\n")[2] \
                if make_grammar.BEGIN in src else src
            ok = say(fresh == src, f"{rel} identifier rules match surface.KEYWORDS "
                                   f"({len(surface.KEYWORDS)} keywords)",
                     "" if fresh == src else "out of date: run python3 t/make_grammar.py, then "
                                             "grammar_check.py where xgrammar is") and ok
        except Exception as e:                                  # noqa: BLE001
            ok = say(False, f"{rel} identifier rules checkable", str(e).split("\n")[0][:80]) and ok
        try:
            from xgrammar import Grammar
            Grammar.from_ebnf(src)
            say(True, f"{rel} loads in xgrammar, the backend vLLM decodes with")
        except ImportError:
            print(f"  [note] xgrammar is not installed here, so {rel} was checked structurally and not "
                  f"loaded; t/grammar_check.py runs it where vLLM is")
        except Exception as e:                                  # noqa: BLE001
            ok = say(False, f"{rel} loads in xgrammar", str(e).split("\n")[0][:80]) and ok
    return ok


def check_agreement_covers_tasks() -> bool:
    """Check 13. t/AGREEMENT.md has a row for every committed task before the corpus builder reads it.

    A derived table has to cover every row of its source (Deequ's hasSize and
    isComplete, github.com/awslabs/deequ). On 2026-09-20 a one-task run_par.py
    sweep overwrote the table, and `loop_locallm.py corpus --lifted` then kept
    1 of 35 committed tasks without a word (blocker A3).
    """
    import loop_locallm
    try:
        rows, missing = loop_locallm.agreement_gap()
    except SystemExit as e:
        return say(False, "committed tasks readable", str(e))
    total = len(rows) + len(missing)
    return say(not missing, f"AGREEMENT.md covers the {total} committed tasks",
               "" if not missing else f"{len(rows)} row(s) for {total} tasks; no row for {missing[:5]}"
               + (" ..." if len(missing) > 5 else "")
               + " (regrade: bash t/grade_lab.sh matrix, then copy t/out/AGREEMENT-lab.md over it)")


def check_data(split_path: Path, lab: str | None, pool_files: list[Path] = (),
               corpora: list[Path] = ()) -> bool:
    """Check current inputs plus recipe files: here, tracked, and on the machine that will run them."""
    text = run_text()
    # a file some step writes before another reads it (lab_gpu.sh builds apps-left.txt) is missing in a
    # different way from one nothing here can rebuild, so the two are told apart rather than filtered out
    written = (set(re.findall(r'Path\(["\']([^"\']+)["\']\)\.write_text', text)) | set(flag(text, "out"))
               | set(re.findall(r">\s*(t/\S+)", text)))
    need: dict[str, str] = {}                                   # path -> the flag that names it
    for f in ("ids-file", "split", "grammar", "adapter"):
        for v in flag(text, f):
            if v in ("none", "") or "$" in v or not v.startswith("t/"):
                continue                                        # `none` is a real value for --adapter
            need.setdefault(v, f)
    current = [(split_path, "split"), *[(path, "pool") for path in pool_files],
               *[(path, "corpus") for path in corpora]]
    outside = []
    for path, kind in current:
        rel = _repository_relative(path)
        if rel is None:
            outside.append(f"{kind}={path}")
        else:
            need.setdefault(rel, kind)
    if outside:
        return say(False, "current run inputs are inside this repository",
                   f"cannot check/reproduce {outside[:3]}")

    tracked = set()
    try:
        r = subprocess.run(["git", "-C", str(ROOT), "ls-files"], capture_output=True, text=True, timeout=20)
        tracked = set(r.stdout.split())
    except (OSError, subprocess.SubprocessError):
        print("  [note] git did not answer, so nothing was checked for being tracked")

    missing = [p for p in sorted(need) if not (ROOT / p).exists()]
    gone = [p for p in missing if p not in written]              # nothing in this project writes it
    later = [p for p in missing if p in written]                 # a step writes it, and has not run yet
    ok = say(not gone, f"the {len(need)} data file(s) the run opens are here"
                       + (f" ({len(later)} still to be written by a step)" if later else ""),
             "" if not gone else f"missing, and no step here writes them: {gone} -- rsync them from the "
                                 f"machine that has them, or git pull if they are tracked")
    if later:
        print(f"  [note] {len(later)} of them is written by a step of the run itself and is not here yet "
              f"({', '.join(later[:4])}); that is a FileNotFoundError only if its step does not run first")
    # a directory of weights is deliberately untracked (the handoff: weights follow from the pool and the
    # commands); a text file a clone needs and cannot rebuild is the failure the audit found
    untracked = [p for p in sorted(need) if (ROOT / p).exists() and (ROOT / p).is_file() and p not in tracked]
    if tracked and untracked:
        warn(f"{len(untracked)} file(s) the run opens are not in the repository",
             f"{untracked[:4]} -- t/out is gitignored, so a fresh clone cannot run this: git add -f them")
    elif tracked:
        say(True, f"every data file the run opens is tracked, so a clone has it "
                  f"({len([p for p in need if (ROOT / p).is_file()])} files)")
    if lab:
        names = [p for p in sorted(need) if p not in later]      # nothing has written the others yet
        script = "; ".join(f"[ -e {shlex.quote(n)} ] || printf '%s\\n' {shlex.quote(n)}" for n in names)
        try:
            r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", lab,
                                f"cd {shlex.quote(LAB_DIR)} 2>/dev/null || exit 9; {script}"],
                               capture_output=True, text=True, timeout=30)
            if r.returncode == 9:
                ok = say(False, f"the grading machine has a clone at ~/{LAB_DIR}") and ok
            else:
                absent = [x for x in r.stdout.splitlines() if x]
                # an id list, a split or the grammar is read by every round, so its absence there stops the
                # next run; an adapter belongs to one round, and an old one not being there is not a fault
                adapters = sorted((p for p, f in need.items() if f == "adapter"),
                                  key=lambda p: [int(n) for n in re.findall(r"\d+", p)] or [0])
                current = adapters[-1] if adapters else None     # the round about to run loads this one
                hard = [x for x in absent if need.get(x) != "adapter" or x == current]
                soft = [x for x in absent if x not in hard]
                ok = say(not hard, f"the grading machine has the {len(names) - len(soft)} file(s) every round "
                                   f"reads, under ~/{LAB_DIR}",
                         "" if not hard else f"{hard[:4]}: rsync -a <file> {lab}:{LAB_DIR}/<dir>/ "
                                             f"(or git pull there, for the tracked ones)") and ok
                if soft:
                    print(f"  [note] {len(soft)} earlier round's adapter(s) are not on the grading machine "
                          f"({', '.join(soft[:3])}); the newest, {current}, is what the next round loads")
        except (OSError, subprocess.SubprocessError) as e:
            ok = say(False, "grading machine answered about its data files", str(e)[:60]) and ok
    return ok


def check_sets_complete(answer_sets: list[Path]) -> bool:
    """Check 10. A kernels.md with no tests.json beside it reads as a set where nothing passed its tests, and
    a scored row built from it is built from half a set."""
    answer_sets = _unique_paths(answer_sets)
    half = []
    for d in answer_sets:
        gone = [f for f in ("tests.json", "extract.json") if not (d / f).exists()]
        if gone:
            half.append(f"{d.name} (no {', '.join(gone)})")
    return say(not half, f"every selected answer set has its tests.json and extract.json ({len(answer_sets)} sets)",
               "" if not half else f"{len(half)}: {half[:3]} -- run python3 t/spec_experiment.py extract "
                                   f"--model <tag> --pool <v> then ... tests --model <tag>, or move the "
                                   f"table aside; nothing downstream can tell half a set from an empty one")


def check_columns(answer_sets: list[Path]) -> bool:
    """Check 11. Seven columns or it is not a clean count."""
    import spec_experiment as se
    answer_sets = _unique_paths(answer_sets)
    partial = []
    for d in answer_sets:
        cols, _ = se.parse_kernel_table(d / "kernels.md")
        have = [c for c in cols if c in KERNELS]
        if len(have) < len(KERNELS):
            partial.append(f"{d.name} ({len(have)}: {', '.join(have) or 'none'})")
    return say(not partial, f"every selected kernels.md carries all seven kernel columns ({len(answer_sets)} sets)",
               "" if not partial else f"{len(partial)}: {partial[:3]} -- finish the grading (bash "
                                      f"t/grade_lab.sh) or move the table aside; agreement among fewer than "
                                      f"seven columns is not this project's clean")


def check_kernel_ran(answer_sets: list[Path]) -> bool:
    """Check 11b. A column of seven is not seven columns that ran.

    A kernel that cannot START is recorded as `malformed`, which is the same
    word used for a lowering that really is malformed. Measured 2026-09-20: two
    seed arms were graded with Verus reading `malformed / malformed` on 114 of
    114 and 87 of 88 rows, because the driver ran in a non-login shell and Verus
    needs rustup on PATH. Check 11 passed them, since all seven columns were
    present. Scored as they stood, both read **0 clean**, which would have been
    reported as the recipe failing to reproduce its headline across seeds.

    A single malformed cell is ordinary and says something about one lowering. A
    column that is malformed on nearly every row of a set says the toolchain
    never started, and no verdict in that column means anything.
    """
    import spec_experiment as se
    answer_sets = _unique_paths(answer_sets)
    dead = []
    for d in answer_sets:
        cols, rows = se.parse_kernel_table(d / "kernels.md")
        if not rows:
            continue
        # parse_kernel_table returns {task: {kernel: "real / twin"}}
        for name in cols:
            if name not in KERNELS:
                continue
            bad = sum(1 for cells in rows.values()
                      if str(cells.get(name, "")).strip().startswith("malformed"))
            if len(rows) >= 10 and bad >= 0.9 * len(rows):
                dead.append(f"{d.name}/{name} ({bad} of {len(rows)})")
    return say(not dead,
               f"no kernel is malformed on nearly every row of a selected set ({len(answer_sets)} sets)",
               "" if not dead else
               f"{len(dead)}: {dead[:3]} -- that kernel did not RUN, it did not disagree. "
               f"Verus needs rustup on PATH and a non-login shell does not provide it; "
               f"t/grade_lab.sh uses bash -lc for exactly this. Regrade or move the table "
               f"aside, because every clean count over it is wrong")


def check_result_quality(answer_sets: list[Path]) -> bool:
    """Run result-only checks over a declared set, never a directory discovery side effect."""
    if not answer_sets:
        print("  [note] no answer set selected; result-quality checks are deferred until grading")
        return True
    ok = check_flakes(answer_sets)
    ok = check_sets_complete(answer_sets) and ok
    ok = check_columns(answer_sets) and ok
    return check_kernel_ran(answer_sets) and ok


def hf_cached(model: str) -> Path | None:
    """The local Hugging Face snapshot for `model`, or None. Nothing here downloads anything."""
    import os
    hub = Path(os.environ.get("HF_HUB_CACHE") or
               Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")) / "hub")
    d = hub / ("models--" + model.replace("/", "--"))
    snaps = sorted((d / "snapshots").glob("*")) if (d / "snapshots").exists() else []
    return snaps[-1] if snaps else None


def roundtrip(model: str) -> tuple[str, str]:
    """(verdict, detail) for one tokenizer, using whatever tokenizer library is here and nothing else."""
    snap = hf_cached(model)
    if snap is None:
        return "skip", "not in this machine's Hugging Face cache"
    code = ("import sys\n"
            "m, probe = sys.argv[1], sys.argv[2]\n"
            "try:\n"
            "    from transformers import AutoTokenizer\n"
            "    t = AutoTokenizer.from_pretrained(m, local_files_only=True)\n"
            "    back = t.decode(t(probe)['input_ids'], skip_special_tokens=True)\n"
            "    print(type(t).__name__ + '\\t' + back)\n"
            "except ImportError:\n"
            "    from tokenizers import Tokenizer\n"
            "    t = Tokenizer.from_file(sys.argv[3])\n"
            "    print('Tokenizer\\t' + t.decode(t.encode(probe).ids))\n")
    pys = [sys.executable] + [str(p) for p in (Path.home() / ".venv-vllm" / "bin" / "python",
                                               Path.home() / ".venv-t" / "bin" / "python") if p.exists()]
    last = "no tokenizer library here (transformers, tokenizers)"
    for py in pys:
        t0 = time.time()
        try:
            r = subprocess.run([py, "-c", code, model, PROBE, str(snap / "tokenizer.json")],
                               capture_output=True, text=True, timeout=120)
        except (OSError, subprocess.SubprocessError) as e:
            last = str(e)[:70]
            continue
        if r.returncode == 0 and "\t" in r.stdout:
            klass, back = r.stdout.rstrip("\n").split("\t", 1)
            took = f"{klass}, {time.time() - t0:.0f}s"
            if back == PROBE:
                return "ok", f"{took}, returned it unchanged"
            return "fail", f"{took}, returned {back!r}"
        last = (r.stderr.strip().split("\n")[-1] if r.stderr.strip() else "no output")[:70]
    return "skip", last


def check_tokenizer(named: str | None, quick: bool = False) -> bool:
    """Check 12. The base model's tokenizer gives back the line of t it was given, and loop_generate.py still
    guards this itself where the generation happens."""
    src = (HERE / "loop_generate.py").read_text(errors="replace")
    guarded = "skip_special_tokens=True) != probe" in src and "probe = " in src
    ok = say(guarded, "loop_generate.py still round-trips a line of t before it trusts a tokenizer",
             "" if guarded else "the 2026-09-18 guard is gone: 122 answers once came back with every space "
                                "dropped, and nothing downstream could tell")
    if quick:
        print("  [note] --quick, so no tokenizer was loaded here; this is the one check that costs seconds")
        return ok
    # the model a step gets when it names none, read from the file rather than restated here
    m = re.search(r'^DEFAULT_BASE\s*=\s*["\']([^"\']+)', src, re.M)
    models = [named] if named else sorted(set(flag(run_text(), "base")) | ({m.group(1)} if m else set()))
    for m in [m for m in models if "/" in m and not m.startswith("t/")]:
        verdict, detail = roundtrip(m)
        if verdict == "skip":
            print(f"  [note] {m}: tokenizer not round-tripped here ({detail}); loop_generate.py runs this "
                  f"check on the machine that generates")
        else:
            ok = say(verdict == "ok", f"{m} round-trips a line of t", detail if verdict == "fail" else
                     detail) and ok
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--split", type=Path, default=OUT / "loop" / "split-v3.json")
    ap.add_argument("--tokenizer", help="round-trip this base model's tokenizer rather than the ones the "
                                        "run scripts name")
    ap.add_argument("--pool", type=Path, action="append", default=[], metavar="JSONL",
                    help="current JSONL training input; repeat for paired inputs")
    ap.add_argument("--corpus", type=Path, action="append", default=[], metavar="TEXT",
                    help="current text training corpus; repeat for each direct input")
    ap.add_argument("--answer-set", action="append", default=[], metavar="TAG",
                    help="graded answer-set tag to quality-check; repeat for a paired comparison")
    ap.add_argument("--audit-history", action="store_true",
                    help="also audit legacy pools, corpora, and answer sets; none are selected by default")
    ap.add_argument("--quick", action="store_true",
                    help="skip the one check that costs seconds (the tokenizer round-trip)")
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()
    lab = None
    conf = HERE / "lab-workstation.conf"
    if conf.exists():
        m = re.search(r"^T_LAB=(\S+)", conf.read_text(), re.M)
        lab = m.group(1) if m else None

    print("checkers")
    ok = check_kernels()
    print("the generator")
    ok = check_prompt() and ok
    ok = check_grammar() and ok
    ok = check_tokenizer(a.tokenizer, a.quick) and ok
    print("the split")
    pools, corpora = selected_training_inputs(a.pool, a.corpus, a.audit_history)
    ok = check_split(a.split, a.pool, a.corpus, a.audit_history) and ok
    print("what the run will open")
    ok = check_data(a.split, lab, pools, corpora) and ok
    ok = check_agreement_covers_tasks() and ok
    print("what is counted clean")
    answer_sets_ok, answer_sets = select_answer_sets(a.answer_set, a.audit_history)
    ok = answer_sets_ok and ok
    if answer_sets_ok:
        ok = check_result_quality(answer_sets) and ok
    else:
        print("  [note] result-quality checks skipped because answer-set selection failed")
    ok = check_spec_agreement(pools, corpora) and ok
    print("housekeeping")
    ok = check_keys() and ok
    ok = check_space(lab) and ok
    ok = check_evaluator(lab) and ok
    if WARNED and ok:
        print("\n" + (f"not ready: {len(WARNED)} warning(s) above, and --strict was asked for" if a.strict else
                      f"ready, with {len(WARNED)} warning(s) above: nothing here makes this round's numbers "
                      f"wrong, and each one is how a later round's go wrong"))
        return 1 if a.strict else 0
    print("\n" + ("ready: nothing left to doubt in this list" if ok else
                  "not ready: fix what reads FAIL above, then run this again"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
