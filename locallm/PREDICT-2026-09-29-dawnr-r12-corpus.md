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
