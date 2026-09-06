# What still needs the Dell

Written 2026-09-06 from the MacBook, with the Dell off the VPN. The list got
much shorter that day, so read the second section before assuming something
here is blocked.

Each item says what it is, the command, and how you know it is done.

## 1. The hand-lifted seed pairs. The only hard blocker.

`$T_CORPORA/lifter-design-2026-09-05/inventory/{lifts,lift3}/*.json`, 22 seed
pairs, referenced by `test_lifter.SEEDS`. A person read corpus programs and
lifted them by hand; nothing regenerates them. Everything else in the bank was
rebuilt from the corpus on the Mac in minutes.

Without them, `test_seeds_resolve` and `test_seed_acceptance` skip with a
reason and the rest of the suite passes.

    # on the Dell
    tar czf inventory.tgz -C ~/t-corpora/lifter-design-2026-09-05 inventory
    # then copy to the Mac and unpack to the same relative path

DONE WHEN: `python3 test_lifter.py` on the Mac runs those two groups instead of
skipping them. Then commit them. They are small, irreplaceable, and being
outside the repo is what makes them a single point of failure; the argument
that t-corpora is a data checkout does not apply to a fixture a person wrote.

## 2. The uncommitted lifter WIP. Do not apply the patch.

Pulled off the Dell before the VPN dropped, saved at
`scratchpad/csdell/lifter-wip.patch`: 458 insertions across `lift_census.py`,
`lift_check.py`, `lift_classify.py`, `lift_rewrite.py` and
`test_lift_report.py`, based on `f2cd948`.

It is a snapshot of files the `lifter-785-review-fix` workflow was writing at
the time, not a finished change. Its final state supersedes the patch, so take
the workflow's result and use the patch only to see what was in flight.

DONE WHEN: the workflow's output is on main and the patch is deleted.

## 3. The `lifter-785-review-fix` workflow's results.

Run `wf_39c9d22b-012`, session `40721cbd-6036-407e-8e9e-35b3828f9593`. Four
Sonnet fixers (classify crashes and misses, `L_req` on array-as-seq,
parse-failure naming, census join tables) plus a reviewer, then one fixer for
the reviewer's findings. A workflow-nanny was watching it. It runs locally on
the Dell and did not need the VPN, so it should have finished.

DONE WHEN: its findings are read, the real fixes are on main, and the residuals
it names are recorded rather than lost.

## 4. GPU work: WS-12.6, the spec experiment.

The highest-risk unknown on the 1.0 path and the reason the Dell exists.
Generate t tasks from natural-language problems with local models on the GPUs,
grade them with the twin discipline, and check them against the problem's own
test cases. The corpus is committed now at `nl/` (24,748 problems), so nothing
about the data is blocking.

DONE WHEN: WS-12.6's own condition, a measured table of how many model-written
t tasks verify with a refuted twin, and how many of those also pass the
problem's tests.

## 5. The x86_64 tup build.

arm64 only today. Same driver pointed at the x86_64 book plus an x86 kernel
override (`arch/x86/boot/bzImage`, not `arch/arm64/boot/vmlinuz.efi`).

DONE WHEN: an x86_64 image boots under the witness and banks an inventory.

## What is NO LONGER a Dell item

Established on the Mac on 2026-09-06. If a note somewhere still says these
need the Dell, that note is stale.

**All seven kernels run on the Mac.** The earlier claim of "3 of 7" was a bad
measurement: `command -v` misses the kernels installed under `$HOME`, which is
exactly where `verifiers/discover.py`'s glob tier looks for them. Present and
version-matched: Dafny 4.11.0, Verus 0.2026.08.30.b432e82, GNATprove FSF
16.1.0, Frama-C 33.0, Lean 4.33.1, Rocq 9.2, F\* 2026.08.30 (installed that
day to `~/.local/fstar`), plus Agda 2.8.0 as an eighth backend. So the
seven-kernel agreement claim of WS-16.2 is reproducible on the Mac.

**The corpus is regenerable, not transferable.** DafnyBench is public
(Apache-2.0, 5.9 MB, `github.com/sun-wendy/DafnyBench`) and its layout already
matches the expected path. From it the Mac rebuilt the bank and reproduced the
Dell's numbers exactly: `coverage_census.py` over the 785 gives **77 in
fragment**, the documented figure, and **25 of the 164 MBPP-DFY in fragment**,
which is what ROADMAP WS-13.1 already claims. 785 rprints regenerated, 783
clean plus the two known exit-2 resolve failures.

    git clone --depth 1 https://github.com/sun-wendy/DafnyBench.git ~/t-corpora/DafnyBench
    python3 coverage_census.py ~/t-corpora/DafnyBench/DafnyBench/dataset/ground_truth \
        --name dafnybench --out /tmp/census.md \
        --json ~/t-corpora/lifter-design-2026-09-05/census.json

**The lifter test suite runs anywhere.** Corpus paths resolve through
`$T_CORPORA` over `~/t-corpora` (`corpora.py`), and a missing checkout skips
with a reason instead of ending the run. The full fast suite passes on the Mac.

**The MBPP-DFY fidelity tier runs on the Mac.** `mbpp_dfy.py` and
`lift_gate.py`, against `nl/`, which is in the repo.
