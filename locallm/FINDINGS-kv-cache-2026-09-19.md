# Cached decoding, 2026-09-19

The prediction of at least 1.5 times faster generation failed. Caching is correct
and remains opt-in through `generate(..., use_cache=True)`; the default stays
uncached because the measured small-prefix runs did not get faster.

| prefix tokens | core | uncached median, seconds | cached median, seconds | speed ratio |
|---:|---|---:|---:|---:|
| 512 | GPT | 0.1813 | 0.1973 | 0.919 |
| 512 | modern | 0.4387 | 0.4447 | 0.986 |
| 1536 | GPT | 0.2321 | 0.1911 | 1.214 |
| 1536 | modern | 0.4323 | 0.4359 | 0.992 |

These are random-weight core-small models: 8 layers, width 512, 8 heads,
vocabulary 8192, context 2048, batch 1, and 128 new tokens. GPU: NVIDIA RTX 6000
Ada Generation; PyTorch 2.13.0+cu130, BF16 autocast. Three repeats per variant,
randomized order, one warmup per variant. CUDA synchronization brackets every
measured interval. Both variants have identical greedy output in every run.
The GPU is shared, so these observations are not an uncontended hardware ranking.

Every timing, peak allocated memory reading, model parameter count, argument,
software version, and measured source hash is retained in
[`kv-cache-results-2026-09-19.json`](kv-cache-results-2026-09-19.json) and
[`kv-cache-long-results-2026-09-19.json`](kv-cache-long-results-2026-09-19.json).
The preregistration and the follow-up prediction are in
[`PREREG-kv-cache-2026-09-19.md`](PREREG-kv-cache-2026-09-19.md).

The follow-up scaling prediction also failed: increasing the prefix from 512 to
1536 did not increase uncached time by the predicted factor of 1.5. The observed
ratios were 1.280 for GPT and 0.985 for modern. Untimed instrumentation confirms
that the work was performed: every variant executed 128 attention calls and
returned 1664 tokens. The uncached first layer processed 204736 token positions;
the cached first layer processed 1663. The reduction in repeated computation did
not produce a general latency win at this size. No profiling result identifies
the cause yet.

Correctness checks cover both cores, both attention implementations, batches of
1 and 3, single-token and multi-token chunks, learned and rotary position offsets,
and exact greedy output through repeated context rollover. Cached float32 logits
match full forward within relative 1e-5 and absolute 1e-6 tolerance on CPU and GPU.
The seven focused cache tests passed on both devices. The latest integrated CPU
suite also passed 21 core/cache/BPE tests, five tokenizer-integrity tests, and nine
legacy checkpoint tests.

The API returns cache tensors to its caller and retains none on the model.
They carry no autograd graph and are released when the caller releases them.
Normal training forward, gradients, and checkpoint parameter names are preserved.
Sampling restores the previous training mode. Temperature zero now requests
greedy decoding explicitly.

Once the context fills, generation rebuilds the cache from the retained window
on every step. Merely deleting old keys would retain hidden states influenced by
dropped tokens and change the old model's sliding-window behavior. The timings
above remain within the window and do not claim a speedup after rollover.

What is gained is an independently checked incremental inference API, exact
window semantics, and measurements that prevent enabling a slower default.

## Batch above one, measured 2026-09-25

`GPT.sample_many` decodes k samples of one prompt as one batch on the cache
(t/pilot_sampling.py drives it). Lab CPU, 8 threads, niced, on a shared box, the
r9 92M core in fp32, held-out ids 3 and 39, a 1,200-token budget:

- greedy k=1 without the stop rule: 1,200 tokens in 9.0 s. With it: id 3 stops
  at 129 tokens in 0.86 s (10.5x less); id 39's greedy reply never closes and
  runs the whole budget (9.09 s). The stop check costs 1.6 percent.
- T=0.8: k=1 140 tokens/s; k=4 342-358 tokens/s (all four rows stopped); k=16
  663 tokens/s on id 3 (16 of 16 stopped) and 298 tokens/s on id 39 (15 of 16;
  one row ran alone to the budget). T=0.4, k=4, id 39: 2 of 4 rows ran to the
  budget.
- Against the predictions of 2026-09-21: "at most 420 tokens on average with the
  stop" was false here (mean 664); "k=16 at least 4x k=1" held for id 3 (4.7x)
  and failed for id 39 (2.1x) because of one straggler row.

No GPU was used: every card had under 8 GB free, and a k=64 batch of r9 peaks
near 14 GB with the torch.cat cache (use --rows-per-batch on a small card).
