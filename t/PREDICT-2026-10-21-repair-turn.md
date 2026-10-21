# A repair turn at the specification stage: registered 2026-10-21 04:47Z, before any run

Queue row 2 of `internal/RESEARCH-2026-10-19-number-one-fv.md` section 5. The route is changed, not the model: the
installed release (v5) is measured under the frozen route and under the route with a repair turn, on the same
machine, with one request cache, graded by the frozen instrument in the same pinned-kernel container.

## What is taken, and from where

- ExVerus (arXiv:2603.25810): a proof that fails is sent back with a counterexample the model can act on, because
  raw verifier messages are too coarse to name the cause. AxDafny (arXiv:2606.32007): a generate, check, repair
  loop in which Dafny's diagnostics and its `--counterexamples` output are the repair feedback.
- SAFE (arXiv:2410.15756, section 3.2): the two scores already in `t/spec_quality.py`, correctness (share of the
  problem's tests the specification holds on) and completeness (share of mutated results it rejects).
- Here the witness is the interpreter's, not a kernel's: the route already evaluates every written specification
  on the problem's own tests and on mutants of their results (that is how it drops them). A dropped specification
  therefore comes with a concrete reason the student never sees. The repair turn shows it.
- Research receipt 79b21fd4f47a (the three abstracts fetched 2026-10-21 04:41Z).

## The diagnosis that chose this row (v5, the 95-problem development panel, `t/out/spec-experiment/v6-20261018-v5-dev`)

| stage | problems left | lost here | why (counted from the run's own records) |
|---|---:|---:|---|
| asked | 95 | | |
| a Python solution that passes the tests (3 attempts) | 51 | 44 | no passing Python |
| a kept specification (5 asks, SAFE thresholds 0.8 / 0.6) | 18 | 33 | best candidate fails correctness only 18, completeness only 9, both 2, no parsable candidate 3, all unscorable 1 |
| a t answer accepted by the cheap gates | 13 | 5 | refusals: fails a test 10, not well formed 8, does not parse 3 |
| verified by at least one kernel, specification confirmed | 6 | 7 | kernels refute or abstain |
| all seven kernels | 3 | 3 | |

194 specifications were scored for 51 problems: 141 dropped, 29 kept, 13 unscorable, 11 duplicates. Median
correctness of a scored specification is 0.33 with median completeness 1.0: the student's specifications are
mostly strong and wrong, false on one or two of the three tests. That is the cheapest possible witness: the test
itself, and the clause that is false on it.

## The change (`t/spec_first.py --repair R`, default 0 = the frozen route byte for byte)

After the plain specification samples are scored, every problem that has a tested Python solution and no kept
specification gets up to R more calls. The conversation continues from the specification question, the
student's best candidate reply (highest correctness, then completeness; the last reply when none parsed) and one
user turn with the witnesses, in this order and at most three of them:

1. a test the specification rejects, with the first `ensures` that is false or undefined on it;
2. a wrong result for a test that the specification accepts (every `ensures` holds on it);
3. the parse, type or binding error when the candidate could not be scored.

The first repair call is greedy, the second sampled. A repaired specification is scored by the same two
thresholds and enters the proof stage like any other. The proof stage is unchanged in this row.

Budget: a problem with a kept specification is untouched, and its conversations are byte-identical to the
frozen route's (the cache returns them). A repaired problem has at most R kept specifications, so its proof
stage asks at most 3R times; with R = 2 the worst case is 3 + 5 + 2 + 6 = 16 calls, inside the 17.

## Arms

- control: v5 (identity `student-v5:d855000c…`, the installed shards) under the frozen route, generated fresh on the
  desktop GPU node (tag `v5-20261021-dev-desktop`);
- candidate: v5 under `--repair 2`, same server, same request cache (tag `v5-20261021-repair-dev`);
- both graded by `t/recipes/v6-grade.sh` inside the desktop's `dawnr-kernels` container (the same seven kernel
  versions the v5 and v7 grades used: dafny 4.11.0, verus 0.2026.08.30, gnatprove 16.1.0, frama-c 33.0 with
  alt-ergo 2.4.3, Lean 4.33.1, Rocq 9.2, F* 2026.08.30) with the same `t/` code, paired by
  `t/recipes/v7_local_pair.py`. The fresh control is the control of record for this row; its agreement with the
  graded v5 control of 2026-10-19 (51 / 13 / 6 / 3) is the instrument check and is reported either way.
- If P1 holds, v7 (decomposed rows) runs under both routes next, because its annotation sub-skill may show only
  when the specification stage lets more problems through.

## Predictions, with the numbers that falsify them

- **P1 (the funnel moves).** Problems with a kept specification: at least 24 (control 18). Problems with an
  accepted t answer: at least 17 (control 13). Either below falsifies P1.
- **P2 (the verdict, the frozen instrument).** Clean (at least one kernel after the specification check) at least 7
  and all-seven at least 3, with no control problem lost in the paired sets. Clean 6 or fewer, or a lost problem,
  falsifies P2.
- **P3 (the mechanism).** Of the problems whose best plain candidate failed correctness only, at least 7 obtain a
  kept specification by repair; of those that failed completeness only or both, at least 2. The witness kind
  behind every kept repair is recorded.
- **P4 (what decides the next row).** P1 and P2 hold: the repair route becomes the route of record (a release
  change with no training) and v7 is measured under it. P1 holds and P2 fails: the proof stage is the next
  bottleneck, and the next row is a proof-stage repair with the interpreter's refusal as the witness. P1 fails:
  the student cannot use a witness it is shown, and the next row is training on repair rows or the dense reward
  (queue row 3), not another route change.

## Cost

Generation ran 4.6 minutes for 95 problems on the desktop on 2026-10-20; two arms share one cache, so the
candidate pays only for the repair calls. Grading 13 to 25 answers under seven kernels in the container: one to
two hours.

## Result, stage 1 (generation on the desktop, 2026-10-21 04:58Z): P1 falsified at the funnel

The control arm replayed the v5 development generation of 2026-10-18 from its request cache (503 requests, same
identity, every call a cache hit): 51 Python, 18 kept specifications, 13 answers, as before. The repair arm reused
those calls and made 64 repair calls for the 33 problems with Python and no kept specification (33 greedy, 31
sampled; two problems had nothing to show by then).

| arm | Python | kept specification | answered |
|---|---:|---:|---:|
| control (frozen route) | 51 | 18 | 13 |
| repair (`--repair 2`) | 51 | **21** | **16** |

**P1 (kept at least 24, answered at least 17): falsified**, 21 and 16. The three repaired problems (92
`is_undulating`, 708, 958) all reached an accepted answer, so the repair's whole gain passed the cheap gates.

What the 64 repair replies did (`t/out/v5-repair-20261021/cache-repair`, the conversations and replies):

- 47 replies changed the specification, 6 repeated it verbatim, 11 did not parse. The student does act on the
  witness; it rewrites.
- Of the 53 scored repairs, 3 were kept, 3 scored better than the candidate shown, 7 worse and 41 the same: the
  rewrite usually changes the clause and keeps the same error. Example (150 `does_Contain_B`, witness "the test
  `does_Contain_B(1,7,3) == True` is rejected: `ensures r == (n >= a and (n - a) % b == 0)` is false on it"): the
  repair answers `r == (exists k in [0, n + 1) . a + k * b == n)`, false on the same test. The parameters' roles
  were misread, and a witness that names the test does not correct a misreading.
- Witness kinds shown: 21 rejected tests, 16 accepted wrong results, 3 parse errors (last round).
- **P3 (correctness-only group at least 7 repaired, completeness group at least 2): falsified**, 2 (92, 708) and
  1 (958).

Reading. The repair turn at 4B buys about one problem per 20 repair calls. The specification drop is not a
feedback problem: the student rewrites when told, and still writes the same wrong thing, because it has not
understood the problem the way its own tested Python has. A same-budget control (two more plain samples,
`--spec-samples 6`, tag `v5-20261021-samples6-dev`) runs after the grades to tell whether two repair calls beat two
samples at all. P2 waits on the seven-kernel grade of both arms.

## Result, stage 2 (the seven-kernel grade in the desktop container, 2026-10-21 05:44Z): P2 falsified

Both arms graded by `t/recipes/v6-grade.sh` inside `dawnr-kernels` with the same `t/` code (evaluator records
identical), paired by `t/recipes/v7_local_pair.py`; receipt `release/evidence/v5-repair-turn-2026-10-21.json`,
records under `t/out/v5-repair-20261021/`.

| arm | Python | t answers | tests pass | at least one kernel, before the specification check | after it (clean) | all seven |
|---|---:|---:|---:|---:|---:|---:|
| control (frozen route, replayed) | 51 | 13 | 13 | 8 | **6** | **3** |
| repair (`--repair 2`) | 51 | 16 | 16 | 9 | **6** | **3** |

Paired clean: the same six problems in both arms (251, 450, 476, 543, 549, 634); all-seven the same three (476,
549, 634); nothing gained, nothing lost. **P2 (clean at least 7, all-seven at least 3): falsified.**

Instrument check: the fresh control grade reproduces the 2026-10-19 grade of the same answers cell for cell
(13 / 13 / 6 / 3, the same kernel table), so the lowering fixes of 2026-10-20 (`lower_rocq` t_nf, `lower_framac`
bridging assert) change nothing on this panel, and the desktop container is the same instrument.

The three repaired problems under the kernels:

- 92 `is_undulating`: the repaired specification scored 1.0 / 1.0 on the three tests and the answer verified under
  SPARK, Lean and F* (Frama-C verified it with the twin unproved), then the specification check removed it:
  `ensures[0]` is false at `"44"`, where the problem's solution answers False. The repair fitted the three tests
  it was shown and not the problem.
- 708 `Convert`: unproved under every kernel that did not abstain.
- 958 `int_to_roman`: refuted by five kernels; the body passes the three tests and violates its own
  specification elsewhere.

Reading, by P4. P1 and P2 fail: the repair turn as a route change is closed. At 4B the student rewrites when
shown the test it fails, and the rewrite is either the same error again (41 of 53) or a patch that fits the
witness and nothing else (92). A witness drawn from three tests is too weak a signal to repair a
misunderstanding, and when it is strong enough to pass them, it is strong enough to overfit them. The next row
is on the training side: repair rows whose targets are reference-checked specifications (1,000 draws against
the problem's solution, the training-side check that already exists in `spec_check`), or the dense verifier
reward (queue row 3), where the signal is a prover's, not three tests'. The same-budget control (two more
plain samples instead of two repair calls) is recorded below when its grade lands.

## The same-budget control (two more plain samples, 2026-10-21 06:08Z): equal

`--spec-samples 6` (seven specification calls, no repair), tag `v5-20261021-samples6-dev`, graded the same way
(receipt `release/evidence/v5-samples6-control-2026-10-21.json`):

| arm | spec calls per problem | kept specification | answered | clean | all seven |
|---|---:|---:|---:|---:|---:|
| control | 5 | 18 | 13 | 6 | 3 |
| repair (`--repair 2`) | 5 + 2 | 21 | 16 | 6 | 3 |
| two more samples | 7 | 22 | 15 | 6 | 3 |

Two repair calls and two plain samples buy the same thing: three or four more kept specifications, two or
three more answers, and no clean answer. The seventh sample answered 150 `does_Contain_B` with a program all
seven kernels verify and the twin refuted; the specification check removed it, `ensures[0]` false at
`(1, -4, 1)` where the problem's solution answers False. With the repair arm's 92 that makes two candidates in
this row that pass the three tests and the kernels and fail the problem. The paired clean and all-seven sets
are the control's in every arm.

## Verdict

P1, P2 and P3 falsified; the repair turn as a route change is closed. What was learned: the student uses the
witness (47 of 64 rewrites) and keeps its error (41 of 53 same scores); three tests are too weak a target for a
specification, and the candidates that satisfy them and the kernels still fail the problem. By P4 the next row
is on the training side (repair rows with reference-checked targets, or the dense verifier reward), and the
specification stage needs a stronger inference-time target than three tests, for which the student's own
tested Python is the obvious oracle to try (the 1,000-draw agreement check `spec_check` already runs against
the reference on the training side).
