# Drawn verdicts: the tool checks inputs the prompt does not show, registered before the run (2026-09-29)

**Written 2026-09-29 10:30Z, before any training.** The held-out look
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
