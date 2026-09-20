# The latent/execution factorial: the supervision took, and it did not transfer

Twelve arms, three seeds, four treatments, all from the frozen modern 4000-step
checkpoints, registered before any arm produced a scored output in
[PREREG-factorial-2026-09-19.md](PREREG-factorial-2026-09-19.md). Output
`t/out/factorial-2026-09-19`; `summary.md` and `summary.json` beside it are
written by `locallm/summarize_factorial.py`. All twelve arms completed 4000
updates with finite losses, and no arm was dropped.

## Primary response: one greedy program per held-out task

102 held-out tasks, 17 patterns that appear in training under no parameter
assignment. Malformed, ill-formed, undefined, over-budget, timed-out and
contract-altering answers are failures.

| seed | baseline | latent | execution | combined |
|---|---:|---:|---:|---:|
| 1337 | 2 | 1 | 3 | 4 |
| 7 | 2 | 3 | 7 | 1 |
| 42 | 2 | 9 | 2 | 2 |

| seed | latent − baseline | execution − baseline | combined − baseline | interaction |
|---|---:|---:|---:|---:|
| 1337 | -1.0 | +1.0 | +2.0 | +2.0 |
| 7 | +1.0 | +4.9 | -1.0 | -6.9 |
| 42 | +6.9 | +0.0 | +0.0 | -6.9 |

All three registered predictions are falsified. Combined never reaches the
5-point threshold; its paired difference is negative at seed 7 and zero at seed
42; the interaction is negative at two seeds of three. The single best cell,
latent at seed 42 with 9 of 102, is not reproduced at either other seed, where
the same arm scores 1 and 3. Baseline is 2 at all three seeds and every
treatment scatters around it: at this resolution the seed moves the score more
than the treatment does.

## The correct answers do not show composition

`t/audit_collapsible.py` asks of each held-out task whether a proper
sub-sequence of its own stages already passes all sixteen of its tests. `cap 12`
applied twice behaves exactly like `cap 12` applied once, so a model that writes
one stage and stops passes that task while composing nothing.

**Of the 78 held-out tasks whose stages can be recovered, 18 are collapsible.
Of the 38 correct answers produced by all twelve arms together, 38 are on those
18 tasks. Not one arm solved a task that required composing its stages.** The
primary response above is therefore not a measurement of compositional
synthesis at all; it is a measurement of how often a memorized single stage
happened to be enough.

Reading the candidates says the same thing. For `affine ∘ affine`, whose
contract reads `r == 3 * (3 * x + 4) + 1`, the seed-42 baseline writes the first
stage and stops; the latent arm writes a `shift` stage that belongs to a
different family. The bodies are syntactically valid t, with 102 of 102 closing
their braces in the first arm scored, and semantically the wrong program.

The generator now refuses these tasks: `t/build_composition_dataset.py` drops
any held-out task a proper sub-sequence passes, and drops a pattern that loses
every variant. Rebuilt as `t/out/composition-2026-09-19-v3`: 82 held-out tasks,
**0 collapsible**, three whole patterns removed as inherently non-compositional
(`cap affine cap`, `cap cap tri`, `shift cap cap`). The v2 dataset this
experiment ran on is kept exactly as it was.

## Secondary response: the supervision did what it was supposed to

150 held-out execution examples per arm, greedy continuation from the training
prompt, nothing teacher-forced (`locallm/score_execution.py`).

| arm | exact trace | line-prefix accuracy | final output correct |
|---|---:|---:|---:|
| baseline (3 seeds) | 0.000, 0.000, 0.000 | 0.000, 0.000, 0.000 | 0.027, 0.007, 0.080 |
| latent | 0.000, 0.000, 0.000 | 0.000, 0.000, 0.000 | 0.000, 0.020, 0.020 |
| execution | 0.000, 0.000, 0.000 | 0.518, 0.536, 0.483 | 0.260, 0.073, 0.147 |
| combined | 0.073, 0.047, 0.027 | 0.626, 0.605, 0.547 | 0.140, 0.267, 0.060 |

This is the check that matters for interpreting the null result. The two arms
that supervise intermediate states predict about half the trace correctly
before derailing and answer the final output several times more often; the two
that do not are at exactly zero, because a token they never receive loss on is
a token they never learn to emit. The combined arm is the only one that ever
reproduces a whole trace, at 3 to 7 percent, which is a small positive sign for
the latent objective *on state prediction* at three seeds.

So the intervention is not inert and it was not misconfigured. It taught the
model what it was asked to teach, and that skill did not reach unaided
synthesis. That is the finding.

## Cost

Training 450 s per arm at batch 8 over 4000 updates, 5.27 GB peak; 88 s to
generate 102 candidates; about 40 s to score 150 execution examples. 289,150
answer-supervised tokens per arm and 1,853,857 execution-supervised tokens in
the arms that use them. Twelve arms ran in about two hours on cards shared with
another user.

## What this buys, and what it does not

- **The experiment's own instrument was wrong and now says so.** A held-out
  composition that a shorter program passes measures nothing about
  composition. It cost one full study to find out; the check is now a script
  with tests, and the generator refuses those tasks.
- **Execution supervision transfers to execution, not to synthesis.** At this
  scale, on this curriculum, with a 91M core: no synthesis gain, at any seed,
  from either factor or their combination. The TracePile regression and
  ExeDec's mixed result both pointed here; this is our own measurement of it.
- **The next comparison needs more resolution, not another factorial.**
  Baseline at 2 of 102 with the seed moving the score by ±7 cannot detect a
  5-point effect. Either the curriculum has to be learnable enough that the
  baseline scores well above the floor, or the response has to be finer than
  one greedy program per task.
- Nothing here touches the seven-verifier, twin or specification gates. These
  are generated-task scores on an interpreter, and a gain here would still have
  to survive the project's original acceptance evaluation.
