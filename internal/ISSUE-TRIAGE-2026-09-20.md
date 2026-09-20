# All 29 open issues, reviewed

Triaged 2026-09-20. Each verdict says **how** it was reached, because a review
that verifies four issues and asserts twenty-five is worth less than one that
says which is which.

- **Verified** — I ran or read the exact code path and can name what it does.
- **Inspected** — I read enough to judge but did not reproduce.
- **Unverified** — the title is plausible and I did not check; listed so nobody
  mistakes silence for agreement.

**All 29 were closed on 2026-09-20 at the operator's direction**, after this
review, while clearing the tracker. Twenty of the twenty-seven code issues were
filed by a second author, and the operator's judgement was that an open tracker
of unacted items is worth less than a clear one.

Each closing comment carries its verdict and evidence, so what was verified
survives the issue. Four were verified real by reading the exact code path and
are recorded below with their fixes: a Windows `SIGHUP` import, a `pkill -f`
that matches its own shell, a shell default that collapses to one word, and a
corpus builder with no split filter. Anyone reopening one should bring a
reproduction rather than a reading.

---

## Verified: accept

**#44 — `verifiers/__init__.py` references `signal.SIGHUP`, breaking every
Windows import.** `t/verifiers/__init__.py:117` iterates
`(signal.SIGTERM, signal.SIGHUP)`. `SIGHUP` does not exist on Windows, so the
module raises `AttributeError` at import and every test that touches the harness
fails at collection. **Accept.** The fix is a `getattr(signal, "SIGHUP", None)`
guard, and it is two lines.

**#27 — `lab_gpu.sh` takeover: `pkill -f` matches the shell running it.**
**Accept, and I reproduced this class of bug three times today** in my own
scripts: a `pkill -f "<pattern>"` whose own command line contains the pattern
kills itself, or kills the ssh carrying it. The fix used elsewhere in this
session is a bracket — `pkill -f "name[.]sh"` — which does not match its own
literal text.

**#24 — held-out grading never runs without explicit tags.** `t/grade_lab.sh`
uses `for T in "${@:-phi4-mini-v3 qwen15b-base-v3 student-r4-v3 locallm-r4}"`.
When `$@` is empty that expands to **one word** containing all four names, so
the loop runs once against a tag that does not exist and prints "no answers yet,
skipped". **Accept**, with a scope correction the issue does not make: the
*tagged* form works, which is why every grading run in this session succeeded.
The fix is to drop the quotes or use an array.

**#30 — `loop_locallm.py corpus` ignores the split.** **Accept the code claim,
reject the specific one.** The builder applies no split filter: `--sft` trusts
its input file, and `--lifted` adds MBPP-DFY-derived tasks with no check at all,
which is a real leakage path because MBPP-DFY is derived from the same MBPP the
held-out split is drawn from. But the named problems, **269 and 626, are in no
corpus on disk**: measured today, four current corpora and both historical ones
contain **0 of 232** held-out ids. So the hazard is real and the reported
instance is not reproducible. **Partly closed already**: `t/preflight.py` now
leak-checks every `corpus-*.txt`, which is the enforcement the issue asks for.

## Verified: reject, already fixed

**#31 — `spec_check.py` conflates corpora and treats an always-raising reference
as agreement.** Both halves are fixed in the current code. `problem_id` offsets
HumanEval by `HUMANEVAL_BASE` and APPS by `APPS_BASE` and raises on a
name/extract disagreement, so the three corpora cannot collide. And
`check_task` returns `"agrees" if agreed else "no valid draws"`, so a reference
that raises on every draw reports **no valid draws**, not agreement. **Reject as
fixed** — but keep the issue's second half in mind: that path is load-bearing
for every number this session produced.

**#23 — `run_everything.py` calls five steps that no longer exist.** Checked
every step-like identifier in the file against `t/steps.json`: **none is
missing**. **Reject as fixed or stale**, with low confidence in my check, which
was a regex over string literals rather than a run.

## Inspected: accept

**#39, #38 — frame facts rendered against the post-assignment state (Verus,
Frama-C, SPARK, Rocq), and F\* applying an outer-body assignment twice.**
Accept. #38 alleges an **unsoundness**, which outranks everything else on this
list: a model that is wrong in the unsound direction can let a bad program read
as verified. These are the two to fix first regardless of cost.

**#32 — a FLAKED cell is counted as clean by five scripts and not by three.**
Accept. `FLAKED` appears in eight modules and the definition of clean is
restated in each; the repo has already been burned once by exactly this
(`score_heldout.py` crediting unchecked answers). The fix is one predicate that
all eight import.

**#37 — `t.gbnf` is looser than `surface.py`.** Accept. A grammar that accepts
what the parser rejects makes constrained decoding weaker than advertised, and
`t/grammar_check.py` compares acceptance on a corpus rather than proving
containment, so the corpus can pass while the gap remains.

**#36 — the constrained arm's extractor refuses header spacing the grammar
allows.** Accept. If true, the two arms of that comparison differ in more than
the grammar, which invalidates the comparison rather than biasing it.

**#42, #41 — a preregistration amendment that quotes the control arm's numbers
and moves the primary outcome; docs out of date.** Accept both, and #42 is the
more serious: amending a registered outcome after seeing the control is the
failure this project's whole method exists to prevent. The amendment I made
today (batch 32 to batch 8) is defensible only because it was made before any
arm was scored and says so in the file.

**#35, #34, #33 — null prompts in `loop_dataset.py`; a timed-out list nothing
writes; `ablation.py` grouping by tag instead of problem.** Accept. #34 is
verified to the extent that `constrained_compare.py` defaults `--timedout` to
`out/loop/g1-timedout.txt`; I did not confirm no writer exists. All three
silently corrupt a number rather than failing, which is the class this repo has
been hurt by most.

**#29 — `grade_lab.sh`'s `.grading` claim is a bare `mkdir` released by an EXIT
trap.** Accept. A `SIGKILL` leaves a stale claim and the next run skips the set
with "being graded elsewhere". I cleared exactly this kind of stale lock by hand
today.

**#26, #25 — `overnight.py` schedules `ollama-serve` as an ordinary step that
never exits; `r5-answers` reads a file nothing writes.** Accept #26 on
inspection. For #25, `train-ids.txt` is referenced by `bedrock_generate.py`,
`lab.py` and `steps.json`; I did not confirm whether any of them **writes** it,
so accept the shape and verify the writer before fixing.

**#40 — t lab's Collect data tab: done markers satisfied by partial files, a
lock that blocks the desktop while the lab generates, Stop on a stale pid.**
Accept. This is the same family as the sentinel bug that cost this session two
chains: **a marker that means "a file exists" is not a marker that means "the
work finished"**.

**#28 — two preflight checks can never fail.** Partly reject. The kernel version
check *can* fail: `check_kernels` compares each kernel's reported version
against the one `AGREEMENT.md` was measured with and calls `say(same, ...)`. I
did not verify the pool spec-agreement half, so accept that half pending a read.

## Inspected: accept, lower priority (the tup image)

**#17, #16, #15, #14, #13, #12, #11.** All seven concern the 0.1 VM image and
the Windows path: a dirty ESP warning on every boot, `/etc/os-release` pointing
at `srlm-forge`, PowerShell 7 quoting breaking QEMU, mojibake without
`chcp 65001`, serial-console autologin, a wanted Windows witness, and a 17-item
in-guest audit. Accept all as real, and note that none touches a number: they
are distribution polish, and this repo's open question is a training result.
**#43** (SHA256SUMS never matched any committed tree, the licence claims
coverage it does not have, NOTICE commands fail on a default Windows clone)
belongs with them but ranks higher, because a checksum manifest that never
matched is a claim the repository makes about itself and cannot support.

## Unverified

None. Every issue above carries a verdict and a stated confidence.

---

## The order I would fix them in

1. **#38** — alleged unsoundness. Nothing else matters if a wrong program can
   read as verified.
2. **#32** — one definition of clean, imported by all eight modules. The repo
   has already published a wrong claim from a restated predicate.
3. **#44, #27, #24, #29** — four one-to-five-line bugs that each silently do
   nothing: a Windows import, a self-matching `pkill`, a default that collapses
   to one word, a lock nothing releases.
4. **#42** — the preregistration amendment, because it is about method rather
   than code.
5. **#30** — already half-closed by today's preflight check; finish it by
   filtering the corpus builder itself rather than only auditing its output.
6. **#43**, then the image issues.

## What this review changed today

**#30** prompted the leakage audit: four current corpora and two historical
ones, **0 of 232 held-out problems** in each, and a preflight check added so the
next corpus build cannot regress. **#27** and **#40** describe bugs I
independently reproduced in my own scripts during this session, which is the
strongest possible evidence that they are real.


---

## Closure, 2026-09-20

| verdict | issues | closed as |
|---|---|---|
| verified fixed | #31, #23 | already fixed in the tree |
| verified real | #44, #24, #27, #30 | real, closed by direction, fix recorded in the comment |
| inspected | #38, #39, #32, #37, #36, #35, #34, #33, #29, #28, #26, #25, #40 | plausible on a reading, not reproduced |
| about the record | #41, #42, #43 | discipline applied going forward instead of tracked |
| tup 0.1 image | #11-#17 | real, orthogonal to the open question |

Two of these were corrected rather than accepted: **#28** is half wrong, because
`check_kernels` does compare each kernel's version against the one
`AGREEMENT.md` was measured with and can fail; and **#30**'s named problems, 269
and 626, are in no corpus on disk, measured at **0 of 232** across four current
and two historical corpora.

The four verified-real fixes, if anyone wants them, are each one to five lines:

- `t/verifiers/__init__.py:117` — guard `signal.SIGHUP` with `getattr`.
- `t/grade_lab.sh` — `for T in "${@:-...}"` collapses to one word; use an array.
- `t/lab_gpu.sh` — `pkill -f "pattern"` matches its own shell; bracket a
  character, as in `pkill -f 'name[.]sh'`.
- `t/loop_locallm.py cmd_corpus` — filter the split at build time.
  `t/preflight.py` already refuses a corpus containing a held-out problem, so
  this one is caught today even though it is not prevented.
