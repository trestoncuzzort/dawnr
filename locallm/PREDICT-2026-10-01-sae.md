# Understood from inside: a published sparse autoencoder on the student, registered 2026-10-01 11:33Z

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
