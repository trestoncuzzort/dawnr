# Round 7 predictions, written while the kernels are still running

Registered before `t/out/score-r7.md` exists and before either `kernels.md` is
back. What is already known and therefore not predicted: `locallm-r7-92m` wrote
**136 well-formed tasks of 232** and the fresh Phi baseline wrote **12**, both
counted by `spec_experiment.py extract` before grading started.

The model: the 92M GPT core from the 4000-step source study, specialized on
39,191 tokens of filtered t data, sampled at temperature 0.5, top-k 20, 1200
tokens, one answer per problem. The comparison moves size, tokenizer,
pretraining corpus and recipe at once against the 3.2M rows, so none of these
predictions isolates a cause.

## The predictions, with what falsifies each

1. **Tests passing: at least 3, and fewer than 20.** Both 3.2M rows passed 2.
   The claim is that pretraining on real source buys *some* problem-solving
   above notation-only, and that 39,191 tokens of specialization does not buy
   much. Falsified below 3 or at 20 and above.

2. **Clean, all seven with the twin refuted: fewer than 3.** That is, it does
   **not** beat Phi-4-mini, and probably ties or loses to the 3.2M rows' 2.
   Falsified at 3 or more, which would be the first locallm row to match Phi.

3. **Conversion below 50%.** Phi converts 50% of its test-passing answers; the
   3.2M rows converted 2 of 2 on a denominator too small to mean anything.
   Falsified at 50% or above *if* the denominator is at least 5; below that the
   prediction is unscoreable and will be reported as such rather than as held.

4. **The fresh Phi baseline reproduces the historical Phi row within one
   answer in every column**: 12 well formed, 6 tests passing, 3 clean, 2 after
   the specification check. Falsified by any column differing by more than 1.
   This is the instrument prediction, and it is the one I most want to hold:
   the lab grades at `17d7aaf` with 109 dirty entries, and if the baseline
   drifts, no comparison in this round means anything.

5. **At least one specification disagreement among whatever `locallm-r7-92m`
   gets clean**, if it gets any. Every model measured here has lost at least
   one clean answer to `spec_check.py` except the prover. Unscoreable if the
   clean count is 0, and will be reported as unscoreable.

## What I expect to be wrong about

Prediction 1's floor is the shaky one. The 3.2M character models wrote 209
well-formed answers and passed 2 tests, which says notation is nearly free and
problem-solving is not. If 92M and real-source pretraining buy nothing at all
here, tests passing lands at 1 or 2 and prediction 1 fails low. I am registering
it anyway because the whole point of putting a pretrained core through the
pipeline is to find out whether that gap closes, and a floor of 3 is the
smallest number that would say it moved at all.
