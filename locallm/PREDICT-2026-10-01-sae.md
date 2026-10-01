# Understood from inside: a published sparse autoencoder on the student, registered 2026-10-01 11:30Z

## What this is

`AMBITION.md` asks that the model be understood from inside; the plan of record names published sparse
autoencoders for the base family where they exist, and "a feature that tracks specifications, registered
before looking". Qwen publishes them (Qwen-Scope, arXiv:2605.11887) for Qwen3.5-2B-Base, 9B-Base, 27B and
35B-A3B, not for the 4B; the student family's nearest member with one is the 2B, and a 2B student exists
(Qwen3.5-2B fine-tuned on the v4 rows).

## What it stands on

- Qwen-Scope's SAE for Qwen3.5-2B-Base (its card, fetched): TopK, 50 of 32,768 features, the residual
  stream after each of the 24 layers, no normalisation; the card says base-model SAEs are reasonable for
  post-trained checkpoints.
- Kissane, Krzyzanowski, Conmy and Nanda, "SAEs (usually) Transfer Between Base and Chat Models"
  (Alignment Forum, 2024, read): middle-layer base SAEs reconstruct the fine-tuned model about as well,
  except on Gemma v1 2B and on rare outlier-norm positions. So the transfer is measured before any feature
  is read.

## The measurement (`locallm/sae_spec_probe.py`)

- The 2B student reads 996 proved answers to training problems (the gate measurement's population, labels
  from the repaired reference check: 790 right and complete, 206 wrong or weak), each as its own prompt and
  the fenced answer; layer 12 of 24, the lab's CPU, fp32.
- **Transfer**: the fraction of variance the SAE explains over every answer position after the first.
- **Feature**: per answer, the SAE's activations averaged over the tokens of its `ensures` lines; problems
  split two to one by a fixed hash; the single feature (active on at least 5 choosing answers) that best
  separates right from not-right on the choosing problems is tested on the other problems.

## Predictions

74. The published SAE explains at least 60% of the variance of the student's layer-12 residual stream.
    Falsified below 60%.
75. The feature chosen on two thirds of the problems separates right from not-right specifications on the
    other third with AUROC at least 0.60. Falsified below 0.60.

## Outcome, 2026-10-01 12:35Z, and a confound found on reading it

The 2B student read all 996 answers in 62 minutes on 12 CPU threads (245,787 answer positions):

| | |
|---|---:|
| fraction of the layer-12 residual variance the published SAE explains | **0.559** |
| answers on the choosing problems / on the test problems | 599 / 397 (138 problems) |
| features active on at least 5 choosing answers | 8,773 |
| best feature on the choosing problems (21048, higher means right): AUROC | 0.813 |
| the same feature on the test problems: AUROC | **0.809** |

74. **The SAE explains at least 60% of the variance: falsified, narrowly.** 55.9%. The base model's
    SAE transfers to the fine-tuned student only partly at this layer.
75. **The chosen feature separates right from not-right on unseen problems at AUROC 0.60 or more:
    holds.** 0.809.

**Read before believing it.** The same split, with no model at all: the answer's length alone
separates right from not-right on the test problems at 0.786 (0.641 on the choosing ones), the
number of `ensures` lines at 0.748, whether the specification quantifies at 0.743, and which model
wrote the answer at 0.562. Right specifications here are longer and more often quantified than wrong
ones, so a feature that tracks how much a specification says would score about as well. Whether
feature 21048 adds anything beyond size is registered next and measured on the same answers:

76. Within the four quartiles of answer length on the test problems, the feature's AUROC, averaged
    over the quartiles weighted by their pairs, is at least 0.60. Falsified below 0.60.
