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

## The CPU, 2026-09-26

### Written before measurement

The GPU null above rests on one card, and most people who use this product have
no GPU. `checkpoint.sample`, which the window (studio.py, home.py) and
generate.py call, decodes uncached by default on every device.
(`checkpoint.sample_batch` always decodes on the cache, through `sample_many`.)
This section measures the two paths on a CPU at the product's own shapes, with
random weights, the `gpt` core, fp32, batch 1 and greedy decoding:

| shape | layers | heads | width | context |
|---|---:|---:|---:|---:|
| Small (studio.py) | 2 | 4 | 128 | 128 |
| Medium (studio.py) | 4 | 4 | 256 | 128 |
| Large (studio.py) | 6 | 8 | 512 | 256 |
| included model (model-r4) | 6 | 6 | 384 | 512 |

Each shape runs with an 82-entry character vocabulary and an 8,192-entry BPE
vocabulary, at prefixes of 32, 128 and 512 tokens and 128 new tokens, at 1 and
4 torch threads. Two further rows: the window's own request, a 32-token prompt
and 400 new tokens (home.py and studio.py ask for 400 by default), on the
character vocabulary; and the 2026-09-19 GPU shape (core-small: 8 layers, width
512, context 2048, vocabulary 8192, prefix 512, `gpt` core) as a cross-check.

Which runs are inside the window matters. The cache saves work only while the
prefix and the tokens generated so far fit the context. At prefix 512 every
product shape starts with a full window, and at prefix 128 so do Small and
Medium: from the first token the cached path rebuilds the whole window on every
step, which is the uncached path's work plus keeping the keys. Prefix 32 on
Small and Medium fills the window after 96 tokens and rebuilds for the last 32.
The 400-token request stays inside the window only on the included model.

Method: `bench_decode.py --device cpu --architecture gpt --threads N --order
alternate --warmup 1 --repeats 5` (3 repeats for the 400-token rows), under
`nice -n 10` with `CUDA_VISIBLE_DEVICES=""` and `OMP_NUM_THREADS=N`. Uncached
and cached runs alternate, A B A B, so both see the same load; the machine is
shared with a grading queue, and the one-minute load average is recorded beside
every run.

Noise and the threshold. For each configuration the noise is the larger of the
two variants' relative range, (max - min) / median, over its repeats. Cached
counts as faster when the median speedup exceeds 1 + noise and every paired
repeat is faster; as slower when the median speedup is below 1 - noise; and
otherwise as within noise.

Predictions, each with what falsifies it:

1. Inside the window (prefix 32 on every shape, prefix 128 on Large and the
   included model) the cache is faster beyond noise at both thread counts and
   both vocabularies. Any such configuration that is not falsifies it. The one
   most at risk is Small at prefix 32: a smoke run of the bench at width 16 and
   one layer, not a product shape, ran 0.96 times cached, so at a small enough
   width the cache's fixed cost per step can exceed what it saves.
2. The included model at prefix 128 on one thread is at least 5 times faster
   cached. The arithmetic: uncached, each token runs the body over about 192
   positions, about 4 GFLOP; cached, over one position, 21 MFLOP, plus reading
   43 MB of weights. Less than 5 times falsifies it.
3. Past the window (prefix 512 everywhere, prefix 128 on Small and Medium) the
   cache is within noise of uncached. Slower beyond noise falsifies it and
   blocks the flip; faster beyond noise falsifies it too, and would mean the
   uncached path does work this reading has missed.
4. Inside the window the speedup is smaller at 4 threads than at 1: the
   uncached forward is matrix work that threads divide, the cached step is a
   string of small products that they barely help. Falsified if most in-window
   configurations gain more at 4 threads.
5. Cached and uncached greedy output is identical in every configuration. Any
   difference falsifies it.
6. The window's 400-token request is at least 5 times faster cached on the
   included model at one thread, and under 2 times on Small, Medium and Large,
   whose windows fill after 96, 96 and 224 tokens and rebuild for the rest.

The decision, fixed now: `checkpoint.sample` decodes with the cache by default
on CPU if prediction 1 holds at prefix 128 and no configuration is slower
beyond noise. CUDA stays uncached, as measured on 2026-09-19. MPS stays as it
is, not measured: the one MPS number to hand (Llama 3.2 1B, 15 to 62 tokens
per second, rasbt/LLMs-from-scratch ch05/07_gpt_to_llama, "Pro tip 3") is for
a model about 100 times the included one, and the same author found the cache's
advantage gone on CUDA at 124M, so on a GPU the size decides it.

Prior art: rasbt/LLMs-from-scratch ch04/03_kv-cache measured a 124M GPT on a
Mac Mini M4 CPU at 27 tokens per second uncached and 144 cached (200 tokens),
and notes that "the speed advantages disappear on CUDA devices as this is a
tiny model". Its uncached baseline projects logits at every position; this
one's projects only the last (`only_last=True`), so any gain here comes from
the transformer body alone.
