# Cached decoding check, 2026-09-19

Written before measurement. Preserve the model's full training forward and saved
weight topology. Store inference keys and values in caller-owned tensors. Both
learned and rotary positions start at the cached prefix length. Chunk queries
must not see later keys. When the window shifts, rebuild from retained token IDs;
discarding only old keys would retain hidden states computed from dropped input.

Predictions and failure bars:

1. Cached logits match full causal forward within 1e-5 relative and 1e-6 absolute
   tolerance in float32 for GPT and modern cores, batch sizes 1 and 3, tokenwise
   and multi-token chunks, fused and manual attention. Any mismatch fails.
2. Greedy cached and uncached generation are identical across repeated context
   rollover, including initial prompts longer than the window. Any token differs
   fails. Cache tensors have no autograd history, are released when callers drop
   them, and do not change subsequent training gradients or checkpoint keys.
3. At core-small size (8 layers, width 512, 8 heads, vocabulary 8192, context
   2048), batch 1, prefix 512 and 128 generated tokens, median cached generation
   is at least 1.5 times faster than uncached generation on the same shared GPU.
   Less than 1.5 falsifies this prediction. Report every timing and peak allocated
   memory over three repeats, with one warmup per variant and randomized order.
   Use BF16 autocast, identical prompts, and greedy decoding; record output parity.

The speed claim applies before the context fills. After rollover, preserving the
existing sliding-window semantics requires full recomputation each step. Neither
random-weight timing nor output parity demonstrates language-model quality.

The registered timing prediction failed: at prefix 512 the observed median ratios
were 0.919 for GPT and 0.986 for modern, with identical greedy output. Keep that
result. A bounded follow-up uses the same core-small shape and 128 output tokens
with prefix 1536, still within the 2048 context. Prediction before this follow-up:
the uncached median takes at least 1.5 times its prefix-512 time; the cached median
takes less than 1.5 times its prefix-512 time. This distinguishes context scaling
from fixed call overhead. It does not replace the failed speedup prediction.

For this follow-up, untimed hooks also count all 128 attention input chunks and
their total input tokens; output shape must include all 128 requested new tokens.
Warmup and measured runs have no instrumentation hooks. Each measured interval
synchronizes CUDA before starting and after generation ends.
