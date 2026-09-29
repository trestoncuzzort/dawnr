# Drawn verdicts: the tool checks inputs the prompt does not show, registered before the run (2026-09-29)

**Written 2026-09-29 09:30Z, before any training.** The held-out look
(`t/PREDICT-2026-09-29-dawnr-chat-heldout.md`) found the pipeline's largest failure on unseen
problems: a program that fits the two shown examples with a specification the problem rejects,
proved in seven kernels against itself (60 to 98 of 232 per seed), and the dev signal had the
same hole (`chat_eval` now reports `spec_agrees`, the answer's specification against the
problem's own solution on 200 drawn inputs: 0 on every existing seed). At training time the
proved program is an oracle the prompt does not exhaust. This stage (receipt d1226616438f;
CodeT, arXiv:2207.10397, selects code on generated tests beyond the given examples):

- `t_tool.call(..., drawn=...)`: Example lines the prompt does not show, judged as `drawn i:`.
- `chat_data --drawn 4`: every tool conversation's verdict carries four drawn lines from the
  proved program (`t_tool.drawn_examples`, inputs the prompt does not show, no distinct-output
  rule).
- `repair_data build --drawn 4`: a cross-fitted draft that passes the shown examples but fails
  a drawn one becomes a repair conversation (`repair-drawn`: the wrong draft unsupervised, the
  drawn failure, the proved program, its passing verdict). Before, such drafts were dropped.

**Arms, three seeds each (1337, 1338, 1339), the r12 corpus and the r12 core's `best.pt`,
mid 400 steps at 1e-4, tool rate 0.5, the harness tokens, the registered evaluation (greedy,
800 tokens, grammar on, two calls, best-verdict, 100 dev problems):**

- **A** (the baseline, already run, rescored with the specification check): drawn 0, no extras.
  Well formed 51 / 36 / 61; pass all examples 0 / 1 / 3; `spec_agrees` 0 / 0 / 0.
- **D**: `--drawn 4`, no extra conversations.
- **DR**: `--drawn 4` plus the repair conversations built with drawn verdicts
  (`repair_data` folds/drafts/build on D's conversations, five folds, 400 steps).

**Predictions.**

1. **`spec_agrees` moves off zero in DR:** at least one DR seed has a dev answer that passes
   its shown examples and agrees with the problem's solution on the draws. Falsified if all
   three DR seeds read 0; then the drawn signal, as data, is not enough and the reward has to
   carry it (RL through the engine with `spec_agrees` as the reward).
2. **`examples_pass_spec_disagrees` does not rise:** the mean over DR's seeds is at or below
   A's 0.33. Falsified if it rises; that would mean the model fits more examples without
   solving more problems.
3. **Well formed does not fall by more than a tenth:** D's and DR's means are at or above
   44.4 (A's 49.3 less 10%). A verdict change should not cost form. Falsified below 44.4.
4. **D alone does less than DR:** D's `spec_agrees` mean is at or below DR's. The lesson is in
   the repairs (a wrong draft shown failing a drawn input), not in passing verdicts alone.
   Falsified if D exceeds DR.

Nothing here touches the held-out 232. Results: `locallm/dawnr-drawn-verdicts-results-2026-09-29.json`;
run directories `~/scratch/dawnr-drawn/` on the desktop.

## Outcome (written 2026-09-29 11:00Z, after the run)

Run `~/scratch/dawnr-drawn/run.sh` on the desktop, 09:33Z to 10:42Z; results in
`locallm/dawnr-drawn-verdicts-results-2026-09-29.json`. Data as built: 531 conversations, 274 of
them tool conversations carrying 1,051 drawn lines (`--drawn 4`); the repair build drew 1,940
cross-fitted drafts over 485 training problems into 800 repair conversations, of which 13 are
`repair-drawn` (22 drafts passed the shown examples and failed a drawn input; 247 passed and
were not proved; 84 passed outright). Mid-training 400 steps, train 0.065, val 0.226, 76 s per
arm; one conversation over the block dropped by name in every arm.

Dev numbers (100 problems; seeds 1337 / 1338 / 1339; A is the rescored baseline):

| arm | well formed | pass all shown examples | `spec_agrees` | pass shown, spec disagrees | used the tool |
|---|---|---|---|---|---|
| A | 51 / 36 / 61 (49.3) | 0 / 1 / 3 (1.33) | 0 / 0 / 0 | 0 / 1 / 0 (0.33) | |
| D | 48 / 36 / 60 (48.0) | 0 / 0 / 1 (0.33) | 0 / 0 / 0 | 0 / 0 / 1 (0.33) | 11 / 38 / 52 (33.7) |
| DR | 58 / 62 / 60 (60.0) | 2 / 2 / 1 (1.67) | 0 / 0 / 0 | 1 / 2 / 1 (1.33) | 91 / 92 / 91 (91.3) |

1. **Falsified.** `spec_agrees` is 0 on every DR seed (and every D seed): of 600 dev answers
   across the six new arms, none passes its shown examples and agrees with the problem's own
   solution on the draws. The registered consequence stands: the drawn signal, as data, is not
   enough.
2. **Falsified.** DR's `examples_pass_spec_disagrees` mean is 1.33 (1 / 2 / 1) against A's 0.33.
   This is the same fact as 1 from the other side: DR passes more shown examples (1.67 against
   1.33) and every one of those answers disagrees with the specification, so it fits more
   examples without solving more problems.
3. **Holds.** D 48.0 and DR 60.0 are above 44.4. DR's form went up, not down: well formed 60
   against A's 49.3, and the tool is used in 91 of 100 answers against D's 34. The repair
   conversations teach the call; they do not teach the answer.
4. **Holds, but says nothing.** D's `spec_agrees` (0) is at or below DR's (0). At zero on both
   sides the prediction cannot separate the arms.

**Reading.** The dose was small before the run started: only 13 of the 800 repair conversations
carry a drawn failure, because most wrong drafts already fail a shown example (no drawn contrast
needed) and only 22 of 1,940 drafts pass the shown examples and fail a draw. So this run
measures drawn verdicts at 1.6% of the repair data and finds no effect on the specification
column, while the tool-use and form effects of the repair conversations themselves are large.
The registered consequence, the reward carrying the drawn signal, meets a precondition the
gathered research states plainly (the GRPO/RLVR notes in the operator's skills: RL reweights
toward samples that already succeed; it does not install a capability from zero): with 0 of 600
answers agreeing with the specification there is no success to reweight toward, and a reward of
`spec_agrees` alone would be a constant. A reward for that stage has to be dense (the fraction
of drawn inputs an answer matches, per input, not the all-or-nothing verdict), and the base rate
has to move first. That is what the general-English pretraining pilot registered the same
morning (`t/PREDICT-2026-09-29-dawnr-english-pilot.md`) tests on the core; the order of work
follows its result. Nothing here touched the held-out 232.
