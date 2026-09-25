# Training locallm on ~50K verified tokens: ranked changes (r12)

Every item rests on a page fetched and read this session (11 `research-first` receipts, ids below). No repository file was edited.

**Measured locally first**
- Validation loss bottoms at step 150–250 in all ten r11 seeds and stays flat to step 300 (rerun: 0.875 → 0.891, while training loss goes 0.23 → 0.11). Validation loss cannot choose the stopping step.
- `Corpus.get_batch` cuts random 512-token windows from the concatenated corpus. With 301 documents of ~185 tokens, **about 23% of training target tokens belong to a document whose `Problem/Signature` head was cut off**. A head lands at position 0 in only ~0.6% of windows, yet that is the only situation `loop_locallm.py generate` ever uses.
- **Only 79 of 301 documents carry an English `Problem:` line.** The other 222, lifted from DafnyBench-family repositories, have only a signature line.
- Fine-tune weight decay does nothing: 0.1 × mean lr 1.65e-5 × 300 steps shrinks weights by ~0.05%.
- Core model: 92.9M params trained on 46M tokens for 5.7 epochs, lr 3e-4, wd 0.1 applied to every tensor, dropout 0.

## Ranked changes

**1. Start every fine-tune row at a document boundary.** Add `continue_from_checkpoint.py --doc-batches`: each row is one whole document plus `"\n\n"`, starting at position 0 and right-padded, with padding targets set to −1 (`model.py` already ignores −1). Use `--steps ~400`, about 12 epochs. Cut generated replies at the first blank line; no corpus document contains one.
- Sources: Ding https://arxiv.org/html/2404.10830 and Zhao https://arxiv.org/html/2402.13991 (receipt 67f7ca3cf599). Tokens trained without their grounding context teach a model to ignore context it is later given. Removing truncation gave +9.2% relative on program synthesis and up to 58.3% less hallucination. Masking attention within each document cut GitHub perplexity from 5.531 to 4.252.
- Cost: ~40 lines plus a test; training still takes ~30 s.
- Effect: aims directly at "proofs of the wrong function".
- Risk: the evidence comes from pretraining at scale, and phi-1 did well with plain concatenation.

**2. Choose the stopping step on a dev split by tests passed.** Add `--keep-every 50`; today `--save-every` overwrites `state.pt`. Dev set: 100 of the 451 train-side MBPP ids in `split-v5.json` that are absent from the corpus. Decode with `t/loop_locallm.py generate --ids-file` and score tests only, with no kernels.
- Sources: LIMA https://ar5iv.labs.arxiv.org/html/2305.11206 (63eda36902d8): "perplexity does not correlate with generation quality", so checkpoints were picked between epochs 5 and 10 on a 50-example dev set. phi-1 https://arxiv.org/html/2306.11644 (afabd547c1da) ran ~17 fine-tune passes and kept the best of checkpoints saved every 1,000 steps.
- Cost: ~3 GB of checkpoints and minutes of decoding; no kernel grading.
- Effect: the stopping step is measured instead of guessed, and soups get a selection signal that never touches the 232 test problems.
- Risk: dev pass counts will be small; sum them over seeds.

**3. Add curated English heads to the 222 head-less documents.** `t/loop_locallm.py corpus --lifted` writes the t task alone; add `--heads heads.jsonl`.
- Sources: Humpback https://arxiv.org/html/2308.06259 (dc3365f2a2eb): uncurated generated instructions did "not improve … despite scaling up data quantity". Curated pairs (score ≥4.5 of 5) kept improving as more were added, with a scaling coefficient of 6.95 against LIMA's 2.86. phi-1: docstring-to-function exercises took HumanEval from 29% to 51%.
- Cost: one lab-model pass over 222 programs plus curation. Curation can be mechanical: regenerate the program from the English and keep the head only if the result agrees with the verified original on the twin-separating inputs.
- Effect: English-to-program pairs grow from 79 to up to 301.
- Risk: a wrong description teaches the wrong mapping.

**4. Dropout 0.1.** Set `--dropout 0.1` in the fine-tune (the flag exists; default 0.0), and the same in `run_pretraining_study.py` CONFIG.
- Sources: Xue https://arxiv.org/html/2305.13230 (63eda36902d8): under repeated data, dropout was the only regularizer that helped (61.7 → 62.9). Adding weight decay on top diverged, and label smoothing was not adopted. phi-1 and Humpback use 0.1.
- Cost: no code.
- Risk: slower fitting; pair it with #2.

**5. Measure forgetting, then replay 25% source code.** Add `--replay-data <source train.txt> --replay-frac 0.25` and log source-corpus validation loss before and after the fine-tune.
- Sources: Ibrahim https://arxiv.org/html/2403.08763 and MiniCPM https://arxiv.org/html/2404.06395 (a478fb7b045f). Ibrahim used 5% replay for a weak distribution shift and 25% for a strong one. MiniCPM mixed its fine-tune data into the pretraining decay phase and lifted MBPP from 24.4 to 30.3; doubling fine-tune tokens instead changed nothing.
- Cost: ~30 lines.
- Risk: never measured at 50K tokens.

**6. Re-pretrain the 92M core for the small-data regime.**
- Add a `weight_decay` argument to `train.py make_optimizer` and decay only tensors with 2 or more dimensions, as nanoGPT does (https://raw.githubusercontent.com/karpathy/nanoGPT/master/model.py, 99f40fbf68d4). Expose it as `train_distributed.py --weight-decay`.
- Train for `--steps 11200` (16 epochs); run lr {1e-3, 3e-3} at wd 0.8, plus a wd 0.1 control.
- Later: a warmup-stable-decay schedule with the t corpus mixed into the final 20%.
- Sources (5d66d7599d7f):
  - Muennighoff https://arxiv.org/html/2305.16264v5: 4 epochs cost 0.5% in loss; repeated data keeps most of its value for ~16 epochs.
  - Kim https://arxiv.org/html/2509.14786: tuned wd 0.8 (150M) and 1.6 (300M) at lr 3e-3 and 16 epochs, "30× larger than standard practice".
  - Xu https://arxiv.org/html/2606.06888v2: a 257M model on 100M tokens went from loss 3.88 to 3.42 once wd was tuned.
  - SmolLM2 https://arxiv.org/html/2502.02737: its 135M model used lr 3e-3.
- Cost: ~45 min per arm on 4 cards (measured 961 s per 4,000 updates).
- Risk: loss has twice failed to predict behaviour here; judge the result by #2.

**7. Model size: no increase for the next run.**
- Hernandez https://ar5iv.labs.arxiv.org/html/2102.01293 (8482fdfa94a6): extra parameters beat extra fine-tune data (exponent 0.38 vs 0.096–0.18), but its pretraining corpora were ~1,000× ours.
- Muennighoff: extra parameters lose value faster than repeated epochs.
- Kim: at wd 0.1, 1.4B scored worse than 600M. Tuned, 300M beats 150M by ~0.17 nats, and two 300M models beat one 600M.
- Xue: larger models overfit more under repeated data.
- So: try 300M only after #6, at wd ~1.6 (~7 h on 4 cards). Nothing supports 875M on 46M tokens; spend that compute on seeds and soups instead.

## Not recommended
- **Masking the loss to answer tokens only.** Shi https://arxiv.org/html/2405.14394v2 (cb3d9202395a): masking choices matter when instructions are long relative to outputs. Ours is ~0.4, where the LIMA-sized case moved only +0.81 / −0.12. Keep the loss on every token.
- **LoRA.** Biderman https://arxiv.org/html/2405.09673 (1b7c0e940167): it "substantially underperforms full finetuning" on code. Revisit only if #5 shows forgetting.
- **Label smoothing and fine-tune weight decay.** See #4 and the 0.05% figure above.
- **NEFTune.** https://arxiv.org/html/2310.05914: its AlpacaEval gain (29.79 → 64.69) comes with 2.8× longer answers, and standard benchmarks stayed flat.
- **Muon / modded-nanogpt.** https://raw.githubusercontent.com/KellerJordan/modded-nanogpt/master/README.md (3ae2feff30d3): 400M vs 10B tokens to reach its target loss, but on fresh data. Our "modern" architecture arm lost here at an untuned lr, so this comes after #6.

## Protocol
Run five seeds per arm and compare the mean of clean answers the model wrote itself and of dev tests passed. The r11 seeds alone span 1–4 such answers.

## What this bought
The literature points at the batcher and the data before the model size. Our training windows hide the problem statement from about a fifth of the tokens trained on, and three quarters of the verified programs carry no English at all. Model size has a sourced answer: not until the core is retrained for small data.
