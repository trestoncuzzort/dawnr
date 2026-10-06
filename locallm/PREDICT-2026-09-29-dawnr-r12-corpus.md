# dawnr's pipeline on the r12 corpus and core, registered before the run (2026-09-29)

**Why this run.** The nanochat-derived pipeline (`DAWNR-PIPELINE.md`: chat format, masked
mid-training, the t tool live in the engine) has only ever been trained on the 358-document
corpus of 2026-09-26 and the sweep's wd0.8 core. The data engine now stands at 531 documents
(463 clean in all seven kernels, 147 with an English head; `t/PREDICT-r12.md`) and the
pretraining core at its early-stopped best (`best.pt`, step 7,600). r12 measures that corpus and
core under the old head-prompt fine-tune; this measures them under the pipeline the project is
on. Same dev problems (`t/r12-dev-ids.json`, 100 MBPP problems named by no training document),
never the held-out 200.

**What runs, three seeds, on the desktop card under the GPU lock:**

    dawnr_pipeline.py --corpus t/out/loop/corpus-r12-headed.txt --core <r12 core, ckpt.pt = best.pt>
      --harness-tokens --tool-rate 0.5 --mid-steps 400 --mid-lr 1e-4 --dev 100 --max-tokens 800
      --seed S     for S in 1337, 1338, 1339
    then chat_eval.py on each mid model with the 2026-09-27 arms' exact evaluation:
      greedy, 800 tokens, the call grammar on, --max-calls 2, --answer best-verdict, 100 dev problems

**Baseline, the 2026-09-27 A arms** (358 documents, wd0.8 sweep core, the same stages and
evaluation, `locallm/tool-conversations-results-2026-09-27.json`): dev well formed 30 / 9 / 17
(mean 18.7), pass all examples 0 / 1 / 0 (mean 0.33), used the tool 29 / 44 / 16.

**Predictions.**

1. Well formed on dev, mean over the three seeds, is at or above the baseline's 18.7. More
   documents and more English heads teach the format better, not worse. Falsified if the mean
   is below 18.7.
2. Pass all examples, mean over three seeds, is above the baseline's 0.33, and at least one seed
   passes 2 or more. Falsified if every seed passes at most 1: 48% more proved documents and the
   better core would then have bought nothing the dev split can see, the same reading r12's
   prediction 1 gives for the head-prompt paradigm.
3. The pipeline passes at least as many dev problems as r12 seed 1's best checkpoint does under
   the fixed reply stop (its `selection.json`, the same 100 problems, tests run the same way).
   The chat model sees the problem's examples and can call the tool; the head-prompt model sees
   the head alone. Falsified if r12's best checkpoint passes more.
4. Nothing here changes the held-out scoreboard: the 232 are not asked. If prediction 2 holds,
   the next step is the held-out answer set from the chat model, exported once, graded by the
   seven kernels like every other arm, under the one-look rule.

Seeds and numbers land in `locallm/dawnr-r12-corpus-results-2026-09-29.json`; the run
directories are `~/scratch/dawnr-r12/A-s<seed>` on the desktop (not in the repository).

## Outcome (2026-09-29 05:38Z, three seeds, `locallm/dawnr-r12-corpus-results-2026-09-29.json`)

| seed | parses | well formed | pass all examples | used the tool |
|---|---|---|---|---|
| 1337 | 68 | 51 | 0 | 16 |
| 1338 | 61 | 36 | 1 | 35 |
| 1339 | 76 | 61 | 3 | 52 |
| mean | 68.3 | **49.3** (baseline 18.7) | **1.33** (baseline 0.33) | 34.3 |

1. **Holds.** Well formed 49.3 against 18.7: the format is learned far better from 531 headed
   documents and the early-stopped core.
2. **Holds.** 1.33 against 0.33, and seed 1339 passes 3. Small numbers at three seeds; the
   direction is the corpus and core, the size is inside seed noise until more seeds run.
3. **Holds.** r12 seed 1's head-prompt model passes 0 of the same 100 at every checkpoint (5
   assertions at best); the pipeline passes 0, 1 and 3.
4. **Kept.** The held-out 200 were not asked. Next: one held-out answer set from the chat model.

One conversation was dropped whole at mid-training on every seed
(`vericoding_da0085__findMinimumTotalDistance`, 2,109 tokens against a 2,048 context; the drop
rule and its record, a69078ac). Each seed took about seven minutes on the desktop card.
