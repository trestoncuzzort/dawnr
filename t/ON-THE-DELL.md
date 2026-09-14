# What still needs the Dell

Instructions for the next time you sit at the Dell. Written 2026-09-06 from the
MacBook while the Dell was off the VPN; the list got much shorter that day, so
read "no longer a Dell item" at the bottom before assuming anything here is
blocked.

Each item says what it is, the command to run, and how you know it is done.

Note on what "off the VPN" meant: unreachable BY US, not offline. The Dell kept
its own internet, its session finished the `lifter-785-review-fix` workflow, and
it pushed three commits to main at 02:52 to 03:16 (`ff1c324`, `eace133`,
`9ce8234`: the 785 run, WS-12.4 done, LIFTER-785.md's disagreement table). Two
items that were on this list when it was written are therefore already closed,
and are recorded below as closed rather than deleted.

## 1. The hand-lifted seed pairs. The only hard blocker.

`$T_CORPORA/lifter-design-2026-09-05/inventory/{lifts,lift3}/*.json`, 22 seed
pairs, referenced by `test_lifter.SEEDS`. A person read corpus programs and
lifted them by hand; nothing regenerates them. Everything else in the bank was
rebuilt from the corpus on the Mac in minutes.

Without them, `test_seeds_resolve` and `test_seed_acceptance` skip with a
reason and the rest of the suite passes.

    # on the Dell
    tar czf inventory.tgz -C ~/tup/t-corpora/lifter-design-2026-09-05 inventory
    # then copy to the Mac and unpack to the same relative path

DONE WHEN: `python3 test_lifter.py` on the Mac runs those two groups instead of
skipping them. Then commit them. They are small, irreplaceable, and being
outside the repo is what makes them a single point of failure; the argument
that t-corpora is a data checkout does not apply to a fixture a person wrote.

## 2. CLOSED. The lifter WIP patch is superseded; delete it.

`scratchpad/csdell/lifter-wip.patch` (458 insertions, based on `f2cd948`) was
pulled off the Dell mid-write. The workflow then finished and pushed, and what
landed is a strict superset: `lift_census.py` 215 lines and
`test_lift_report.py` 112 match the patch exactly, while `lift_check.py` (286
vs 83), `lift_classify.py` (83 vs 66) and `lift_rewrite.py` (49 vs 19) are
larger. Nothing in the patch is missing from main. Do not apply it; delete it.

## 3. CLOSED. The `lifter-785-review-fix` workflow finished.

Run `wf_39c9d22b-012`, session `40721cbd-6036-407e-8e9e-35b3828f9593`. Its
output is `ff1c324`, `eace133` and `9ce8234` on main: the 785 run with crashes
to zero, the review's two wrong lifts closed, WS-12.4 marked done, and
`t/LIFTER-785.md` (1,386 lines) carrying the disagreement table.

STILL WORTH DOING: read `t/LIFTER-785.md`'s residuals. A workflow that closes
its own findings is not the same as a person having read what it left open.

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

    git clone --depth 1 https://github.com/sun-wendy/DafnyBench.git ~/tup/t-corpora/DafnyBench
    python3 coverage_census.py ~/tup/t-corpora/DafnyBench/DafnyBench/dataset/ground_truth \
        --name dafnybench --out /tmp/census.md \
        --json ~/tup/t-corpora/lifter-design-2026-09-05/census.json

**The lifter test suite runs anywhere.** Corpus paths resolve through
`$T_CORPORA` over `~/tup/t-corpora` (`corpora.py`), and a missing checkout skips
with a reason instead of ending the run. The full fast suite passes on the Mac.

**The MBPP-DFY fidelity tier runs on the Mac.** `mbpp_dfy.py` and
`lift_gate.py`, against `nl/`, which is in the repo.
