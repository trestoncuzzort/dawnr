# Core architecture check, 2026-09-19

Written before the first run. The old core has learned absolute positions, LayerNorm,
GELU, and an uncached full-prefix generation loop. The new optional core uses rotary
positions, RMSNorm, and SwiGLU. Block activation checkpointing trades recomputation
for memory. Neither design by itself supplies semantic knowledge.

Predictions and failure bars:

1. A legacy configuration loaded into the revised core has identical weights and
   outputs to the pre-change source under the same seed. Any changed tensor fails.
2. `test_model_core.py` passes causal-prefix, manual/fused attention, legacy load,
   modern checkpoint, finite gradients, rotary norm, and last-token projection checks.
   Activation recomputation preserves dropout loss and gradients within 1e-5 relative
   and 1e-6 absolute tolerance. Any failed assertion blocks use.
3. At the fixed `bench_core.py` default shape (6 layers, width 512, 8 heads, vocabulary
   8192, context 512, batch 4), checkpointing reduces peak allocated CUDA memory by
   at least 20% against the same modern core without checkpointing. Less than 20%
   falsifies this prediction; report the measured tradeoff anyway.

Run three repeats of all three variants, with fixed inputs/seeds, BF16 autocast,
three warmup steps and ten timed forward/backward steps, randomized variant order
per repeat. No optimizer steps; this measures executable training primitives, not
learning. Record every observation, peak allocated memory, exact parameter counts,
software version, and hardware. Other users share the machine, so timings describe
these runs and must not be presented as an uncontended hardware ranking.

Also check actual scale viability with one warmup and three AdamW updates on random
inputs, batch 1 and context 2048: `core-small` (8 layers, width 512, 8 heads),
`core-medium` (12, 768, 12), and `core-large` (24, 1024, 16). Use the modern core,
BF16 autocast, vocabulary 8192, and activation checkpointing. Prediction: each
completes within its card's measured 14–17 GiB free memory. Any OOM, non-finite
gradient, or failed update falsifies scale viability at that shape. These short
random-input updates establish execution and resource requirements, not learning.

No prediction of superior accuracy is made here. That requires the preregistered
equal-compute multi-seed task experiment in the enterprise plan. New presets and
checkpointing make that experiment possible; they do not satisfy it.

Algorithm and API references:
[RoFormer paper](https://arxiv.org/abs/2104.09864),
[GLU variants paper](https://arxiv.org/abs/2002.05202),
[PyTorch activation checkpointing](https://docs.pytorch.org/docs/stable/checkpoint.html).
