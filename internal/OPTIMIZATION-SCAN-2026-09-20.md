# A CPU-side optimization scan, with the paper behind each finding

Scanned `locallm/`, `t/` and `tup/` for work that makes runs cheaper to deploy
without touching a GPU. Every issue below was searched in the literature before
anything was changed, and two of the four candidates were **refuted by
measurements already in this repository**, which is the more useful half of the
result.

## Fixed: the corpus is re-tokenized at every training start

**Measured.** The frozen source corpus is byte-BPE encoded every time training
begins: **104.6 seconds for 48,798,887 tokens**, plus the validation half, for
text that never changes. A six-arm study pays it twelve times and every resume
pays it again — about 9% of each arm's wall clock spent recomputing a pure
function of two frozen inputs.

**The literature.** Pre-tokenizing into a binary companion file is what every
large pipeline does: Megatron-style `.bin`/`.idx` pairs with memory-mapped
reads, so tokenization happens once as a preprocessing step rather than per
epoch ([Apertus engineering report, arXiv 2604.12973](https://arxiv.org/pdf/2604.12973)).
Ours is 46M tokens and 184 MB as int32, so it fits in memory and needs no index.

**The fix.** `locallm/data.py:cached_encode` keys the ids on the sha256 of the
text **and** the tokenizer's fingerprint, so a hit is only possible for the
exact pair that produced it. Cold 104.6 s, warm **1.6 s**, ids identical. Off
unless `LOCALLM_TOKEN_CACHE` names a directory, and an unreadable or corrupt
entry is a miss rather than an error. Five tests.

## Refuted by our own measurements: a prover portfolio for SPARK

**The hypothesis.** SPARK costs 21.88 s median against 4.23 s for the
next-slowest kernel and is 44% of all proof time, and
`t/verifiers/spark.py:185` pins it to one solver: *"Prover pinned to the bundled
Z3 with `--prover=z3`."* `alt-ergo` and `cvc5` are installed beside it and never
invoked. The literature supports portfolios: different solvers win different
goals, and per-goal dispatch beats pinning one
([Predicting SMT Solver Performance for Software Verification, arXiv 1701.08466](https://arxiv.org/abs/1701.08466),
and the Where4 line of work on Why3 proof-obligation dispatch).

**Why it is wrong here.** `t/verifiers/spark.py:350-365` already measured it:
*"the PROVER is not the cost either. `--report=statistics` accounts for every
one of is_prime's 93 obligations at 'max 0.0 seconds', 164 steps in TOTAL
against a 20000-step budget. What costs is per-obligation PROCESS overhead, run
strictly serially"* — 111 `execve`s per run, measured by `strace`. A portfolio
adds processes to a workload whose cost *is* processes.

## Refuted as already done: parallelizing those processes

The same profile led to the real fix on 2026-09-19, before this scan: gnatprove
now runs with `-j`, described as *"a scheduling knob and NOT a budget: it is
absent from Result.budget by design, it leaves the audit, the exit code, the
stdout and the verdict byte-identical (MEASURED), and `T_SPARK_JOBS=1` restores
the old serial behaviour exactly."* The literature agrees that this is the
lever for a workload of many small shared-context queries
([Shared-Context Batched Satisfiability, arXiv 2606.21983](https://arxiv.org/html/2606.21983),
which cuts solver calls 72.5% by batching and model reuse, and reports
order-of-magnitude speedups for incremental verification).

The remaining 34 `cvc5` launches belong to `--proof-warnings=on`, the vacuity
instrument, which is 11 of 13.9 seconds. **It is not a candidate for removal:**
it is one of the two instruments that mint VACUOUS, and this project's whole
claim rests on a proof that cannot be discharged by a contradictory
precondition. Buying speed there would be buying it from the gate.

## Refuted by measurement: parallelizing extract and tests

`t/spec_experiment.py:916` and `:1061` are serial loops over 232 answers, and
the file already uses a `ThreadPoolExecutor` elsewhere, so the fix looked free.
**Measured on a real answer set: extract 1.2 s, tests 1.06 s.** Parallelizing
would save about one second a round. Not done, and recorded here so nobody
spends an afternoon on it.

## Queued, with its bar: the verdict cache the grading machine has never had

**Measured.** `t/cache.py` keys a verdict on the lowered source, the kernel, its
version, the budget and the adapter fingerprint. It is uncommitted desktop work,
and the machine that runs the kernels has never had it: `grep -c "import cache"`
returns **0** on the lab's `t/run_par.py`. Every regrade re-runs all seven
kernels over every answer, including answers whose lowered text has not changed.

**The literature.** This is exactly
[Leino and Wüstholz, *Fine-Grained Caching of Verification Results*, CAV 2015](https://pm.inf.ethz.ch/publications/LeinoWuestholz2015.pdf):
compare against a verified snapshot and reuse what did not change. Their
coarse-grained level is a checksum over everything a contract depends on, which
is what `cache.key_for` already computes; their fine-grained level tracks
dependencies per obligation and is more than a one-program cell needs.

**Not done here, because it has a bar and the bar takes CPU hours**: grade the
whole corpus twice, then once with `--no-cache`, and require all three tables to
agree apart from the timestamp. Until that passes, the cache stays exactly where
it is.

## Queued, with its bar: wall-clock backstops are unsound under contention

**Measured, in the repo's own words.** `t/verifiers/framac.py:325-328`: *"how
much CPU each prover gets decides how far it got — measured wall is 22.7 s at 1,
10.2 s at 4, 8.0 s at 8."* `t/grade_lab.sh` records that at 96 provers the
backstop *"fires on cells that would prove alone"*, flaking nine cells. A
timeout is not a verdict — `t/preflight.py` refuses any clean answer resting on
one — so every flake from contention is a lost answer.

**The literature.** This is the reason SVCOMP and its BenchExec harness measure
CPU time rather than wall time and pin cores: under oversubscription a
descheduled process is indistinguishable from a slow one
([Evaluation of SMT solvers in abstraction-based software model checking](https://dl.acm.org/doi/fullHtml/10.1145/3569902.3570187),
which uses BenchExec for exactly this).

**The fix, and why it is not made tonight.** Where a budget is a backstop rather
than a semantic limit, make it a CPU-time limit (`RLIMIT_CPU`) instead of a wall
clock, leaving `--steps` and `wp-steps` untouched because those are already
machine-independent. Changing a verifier's resource discipline requires
re-measuring its column cell for cell against `t/AGREEMENT.md`, which is hours
of CPU. The change without the bar is not an improvement, it is an unmeasured
edit to a gate.

## What this scan says about `tup/`

`tup/` is 340 shell scripts that build a Linux distribution with a receipt per
step. It is not in the path of a training or grading run, so nothing in it makes
runs cheaper to deploy. Its scripts use `set -u` deliberately and the one file
without `set -e` is a sourced library, where `set -e` would be wrong. No changes
proposed: a scan that invents work in a directory it was asked to look at is
worth less than one that says the directory is fine.
