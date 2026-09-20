#!/usr/bin/env python3
"""t/preflight.py -- everything that could make a round's numbers wrong, checked before the round (2026-09-18).

    python3 t/preflight.py [--split t/out/loop/split-v3.json] [--tokenizer NAME] [--quick] [--strict]

Each check below exists because something went wrong once. A round should not start while any of them fails,
and the ones that fail print what to do. `--strict` exits non-zero on a warning as well as a failure.

  1. The seven checkers are present, and at the versions t/AGREEMENT.md was measured with. A checker missing
     from PATH does not read as absent in every path: a hand-run grading on 2026-09-17 reported MALFORMED for
     every Verus cell because a non-login shell had no Rust toolchain.
  2. No held-out problem appears in the training set or the pairs. The split is the whole basis of every
     held-out number.
  3. Every answer counted clean agrees with its problem's own solution (t/spec_check.py). Five did not on
     2026-09-18, and all five had passed the tests, all seven proofs and a refuted twin.
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
 10. Every answer set that has a kernels.md also has a tests.json and an extract.json (2026-09-19).
     `clean_rows` reads a missing tests.json as "no answer passed its tests", so half a set does not announce
     itself: it quietly contributes nothing to a count that is then reported as if it had been counted.
 11. No answer set's kernels.md has fewer than the seven kernel columns (2026-09-19). A table graded with
     `--kernels lean` alone reports agreement among one column; the audit of that day made the cell say
     `(only N kernels)`, and this refuses to let such a table sit where a clean count is taken from it.
 12. The tokenizer of the base model the run names round-trips a line of t, and loop_generate.py still holds
     its own round-trip guard (2026-09-18). DeepSeek-Prover-V2-7B loads as LlamaTokenizer under transformers
     5.17 and drops every space on the way back: 122 answers came out as `t1tasksmall_nnum(s:seq,n:int)`.
     This one costs a few seconds where a tokenizer library is installed, like a kernel check does.
"""

from __future__ import annotations

import argparse
import json
import re
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


def check_split(split_path: Path) -> bool:
    try:
        split = json.loads(split_path.read_text())
    except OSError:
        return say(False, "split readable", str(split_path))
    ev = {int(i) for i in split["eval_ids"]}
    ok = True
    _ = ev
    # every pool and pair file there is, not a list that has to be edited each round: round 6's files existed
    # for a day without being leak-checked because they were not in the list (2026-09-19)
    files = sorted((OUT / "loop").glob("sft-*.jsonl")) + sorted((OUT / "loop").glob("pairs-*.jsonl"))
    if not files:
        ok = say(False, "a pool to check", "no sft-*.jsonl or pairs-*.jsonl under out/loop")
    for p in files:
        name = p.name
        leaked = set()
        for line in p.read_text(errors="replace").splitlines():
            for tid in re.findall(r"mbpp_(\d+)", line):
                if int(tid) in ev:
                    leaked.add(int(tid))
        ok = say(not leaked, f"{name} holds no held-out problem",
                 "" if not leaked else f"{len(leaked)} leaked: {sorted(leaked)[:5]}") and ok
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


def check_flakes() -> bool:
    ok_alone = rechecked()
    flaked, timeouts, total = [], [], 0
    for d in sorted(p for p in SE.glob("*") if (p / "kernels.md").exists()):
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


def check_spec_agreement() -> bool:
    """A disagreement in a POOL answer is a failure: it would be trained on. A disagreement in a held-out
    answer set cannot enter the pool, so it is reported, and score_heldout.py counts it in its own column."""
    j = OUT / "spec-disagree.json"
    if not j.exists():
        return say(False, "specifications checked against the problems", "run python3 t/spec_check.py")
    bad = json.loads(j.read_text()).get("disagree", [])
    pool_text = ""
    for name in ("sft-r4.jsonl", "pairs-r4.jsonl", "sft-r5.jsonl", "pairs-r5.jsonl"):
        f = OUT / "loop" / name
        if f.exists():
            pool_text += f.read_text(errors="replace")
    # compare the program, not the problem name: another model's answer to the same problem may be fine
    progs = json.loads(j.read_text()).get("programs", {})
    squash = lambda s: " ".join(s.split())                       # noqa: E731
    flat = squash(pool_text)
    in_pool = [x for x in bad if x in progs and squash(progs[x]) in flat]
    ok = say(not in_pool, f"no answer in the pool disagrees with its problem ({len(bad)} disagreements found)",
             "" if not in_pool else f"{in_pool}")
    if bad and not in_pool:
        print(f"  [note] {len(bad)} held-out answers disagree with their problems; score_heldout.py counts "
              f"them apart, see {j.name}")
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
        out = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", lab,
             "cd ~/tup && git rev-parse --short HEAD && git status --porcelain | wc -l"],
            capture_output=True, text=True, timeout=45)
        lines = [line.strip() for line in out.stdout.splitlines() if line.strip()]
        if len(lines) < 2:
            return warn("grading machine state unreadable", out.stderr.strip()[:60])
        head, dirty = lines[0], int(lines[1])
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return warn("grading machine state unreadable", str(error)[:60])
    mine = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                          text=True, cwd=HERE.parent).stdout.strip()
    if head == mine and dirty == 0:
        return say(True, f"the grading machine matches this tree at {head}")
    detail = f"it grades at {head} with {dirty} dirty entries; this tree is at {mine}"
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


def check_data(split_path: Path, lab: str | None) -> bool:
    """Check 9. The id lists, splits, grammars and adapters the run opens: here, tracked (t/out is gitignored,
    so a clone has only what was `git add -f`ed), and on the machine that will do the running."""
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
    need.setdefault(str(split_path.relative_to(ROOT) if split_path.is_relative_to(ROOT) else split_path),
                    "split")

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
        script = "; ".join(f'[ -e "{n}" ] || echo "{n}"' for n in names)
        try:
            r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", lab,
                                f"cd {LAB_DIR} 2>/dev/null || exit 9; {script}"],
                               capture_output=True, text=True, timeout=30)
            if r.returncode == 9:
                ok = say(False, f"the grading machine has a clone at ~/{LAB_DIR}") and ok
            else:
                absent = [x for x in r.stdout.split() if x]
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


def check_sets_complete() -> bool:
    """Check 10. A kernels.md with no tests.json beside it reads as a set where nothing passed its tests, and
    a scored row built from it is built from half a set."""
    half = []
    for d in tables():
        gone = [f for f in ("tests.json", "extract.json") if not (d / f).exists()]
        if gone:
            half.append(f"{d.name} (no {', '.join(gone)})")
    return say(not half, f"every graded answer set has its tests.json and extract.json ({len(tables())} sets)",
               "" if not half else f"{len(half)}: {half[:3]} -- run python3 t/spec_experiment.py extract "
                                   f"--model <tag> --pool <v> then ... tests --model <tag>, or move the "
                                   f"table aside; nothing downstream can tell half a set from an empty one")


def check_columns() -> bool:
    """Check 11. Seven columns or it is not a clean count."""
    import spec_experiment as se
    partial = []
    for d in tables():
        cols, _ = se.parse_kernel_table(d / "kernels.md")
        have = [c for c in cols if c in KERNELS]
        if len(have) < len(KERNELS):
            partial.append(f"{d.name} ({len(have)}: {', '.join(have) or 'none'})")
    return say(not partial, f"every kernels.md carries all seven kernel columns ({len(tables())} sets)",
               "" if not partial else f"{len(partial)}: {partial[:3]} -- finish the grading (bash "
                                      f"t/grade_lab.sh) or move the table aside; agreement among fewer than "
                                      f"seven columns is not this project's clean")


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
    ok = check_split(a.split) and ok
    print("what the run will open")
    ok = check_data(a.split, lab) and ok
    print("what is counted clean")
    ok = check_flakes() and ok
    ok = check_spec_agreement() and ok
    ok = check_sets_complete() and ok
    ok = check_columns() and ok
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
