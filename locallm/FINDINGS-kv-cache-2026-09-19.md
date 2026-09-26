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

### Measured

AMD Ryzen 9 7900X (12 cores, 24 threads), PyTorch 2.14.0 CPU, Python 3.14,
fp32. 58 configurations, one `bench_decode.py` process at a time, 15:02 to
15:42; the one-minute load average over each configuration's runs is in the
last column. A first attempt at 04:07 ran at load 22 to 27 while a grading
burst filled the machine, and was killed when the desktop ran out of memory;
none of its numbers are used. Every timing, argument and load reading is in
[`kv-cache-cpu-results-2026-09-26.json`](kv-cache-cpu-results-2026-09-26.json).
Each cell is the median milliseconds per token (batch 1) over 5 alternating
repeats, then the median speedup, uncached over cached, with the noise in
brackets and the verdict under the threshold above.

| shape | vocab | prefix | new | window | 1 thread: ms/token uncached / cached | speedup (noise) | 4 threads: ms/token uncached / cached | speedup (noise) | load |
|---|---:|---:|---:|---|---:|---|---:|---|---|
| Small | 82 | 32 | 128 | fills after 96 | 0.92 / 0.46 | 1.99 (0.29) faster | 0.59 / 0.36 | 1.64 (0.24) faster | 1.9-2.8 |
| Small | 82 | 128 | 128 | full from the start | 1.28 / 1.22 | 1.05 (0.10) within noise | 0.68 / 0.64 | 1.06 (0.36) within noise | 2.8-2.8 |
| Small | 82 | 512 | 128 | full from the start | 1.19 / 1.20 | 0.99 (0.08) within noise | 0.60 / 0.61 | 0.99 (0.07) within noise | 2.8-2.8 |
| Small | 8192 | 32 | 128 | fills after 96 | 1.00 / 0.55 | 1.82 (0.03) faster | 0.59 / 0.41 | 1.43 (0.01) faster | 2.8-3.0 |
| Small | 8192 | 128 | 128 | full from the start | 1.29 / 1.29 | 1.00 (0.01) within noise | 0.70 / 0.70 | 0.99 (0.02) within noise | 2.9-3.0 |
| Small | 8192 | 512 | 128 | full from the start | 1.29 / 1.31 | 0.98 (0.04) within noise | 0.86 / 0.82 | 1.04 (0.32) within noise | 2.9-3.7 |
| Medium | 82 | 32 | 128 | fills after 96 | 5.29 / 2.25 | 2.35 (0.02) faster | 2.23 / 1.20 | 1.86 (0.04) faster | 3.5-3.6 |
| Medium | 82 | 128 | 128 | full from the start | 7.06 / 7.37 | 0.96 (0.02) **slower** | 2.83 / 3.04 | 0.93 (0.03) **slower** | 3.1-3.3 |
| Medium | 82 | 512 | 128 | full from the start | 6.96 / 7.32 | 0.95 (0.05) **slower** | 2.85 / 3.01 | 0.95 (0.03) **slower** | 3.0-3.2 |
| Medium | 8192 | 32 | 128 | fills after 96 | 5.74 / 2.54 | 2.26 (0.09) faster | 2.58 / 1.52 | 1.70 (0.23) faster | 3.0-3.1 |
| Medium | 8192 | 128 | 128 | full from the start | 7.69 / 7.77 | 0.99 (0.04) within noise | 3.28 / 3.40 | 0.97 (0.03) **slower** | 2.9-3.1 |
| Medium | 8192 | 512 | 128 | full from the start | 7.76 / 7.90 | 0.98 (0.06) within noise | 3.27 / 3.38 | 0.97 (0.03) **slower** | 2.9-3.1 |
| Large | 82 | 32 | 128 | inside | 32.61 / 4.49 | 7.26 (0.10) faster | 12.70 / 4.32 | 2.94 (0.06) faster | 3.2-4.2 |
| Large | 82 | 128 | 128 | inside | 60.79 / 4.69 | 12.96 (0.01) faster | 24.00 / 4.69 | 5.12 (0.16) faster | 4.2-5.4 |
| Large | 82 | 512 | 128 | full from the start | 88.28 / 84.93 | 1.04 (0.09) within noise | 29.08 / 30.92 | 0.94 (0.06) **slower** | 4.6-8.0 |
| Large | 8192 | 32 | 128 | inside | 33.64 / 5.38 | 6.25 (0.11) faster | 13.90 / 5.26 | 2.64 (0.08) faster | 5.8-7.0 |
| Large | 8192 | 128 | 128 | inside | 62.47 / 5.69 | 10.99 (0.08) faster | 22.84 / 5.33 | 4.28 (0.03) faster | 4.7-5.5 |
| Large | 8192 | 512 | 128 | full from the start | 78.36 / 77.39 | 1.01 (0.08) within noise | 28.52 / 28.62 | 1.00 (0.04) within noise | 2.6-4.0 |
| included | 82 | 32 | 128 | inside | 18.02 / 2.66 | 6.78 (0.05) faster | 7.04 / 2.65 | 2.65 (0.01) faster | 3.1-3.6 |
| included | 82 | 128 | 128 | inside | 34.91 / 3.01 | 11.60 (0.07) faster | 12.47 / 2.78 | 4.48 (0.16) faster | 2.8-3.2 |
| included | 82 | 512 | 128 | full from the start | 102.05 / 104.39 | 0.98 (0.07) within noise | 35.51 / 38.31 | 0.93 (0.09) within noise | 1.9-4.9 |
| included | 8192 | 32 | 128 | inside | 19.90 / 3.95 | 5.04 (0.18) faster | 7.53 / 3.36 | 2.24 (0.04) faster | 4.4-5.2 |
| included | 8192 | 128 | 128 | inside | 37.04 / 4.04 | 9.16 (0.26) faster | 14.18 / 3.84 | 3.69 (0.04) faster | 3.8-4.4 |
| included | 8192 | 512 | 128 | full from the start | 103.18 / 103.03 | 1.00 (0.04) within noise | 36.29 / 37.29 | 0.97 (0.06) within noise | 4.1-6.3 |

The window's own request (3 repeats) and the GPU shape on this CPU:

| shape | vocab | prefix | new | window | 1 thread: ms/token uncached / cached | speedup (noise) | 4 threads: ms/token uncached / cached | speedup (noise) | load |
|---|---:|---:|---:|---|---:|---|---:|---|---|
| Small | 82 | 32 | 400 | fills after 96 | 1.12 / 0.98 | 1.14 (0.00) faster | 0.62 / 0.54 | 1.14 (0.07) faster | 6.0-6.0 |
| Medium | 82 | 32 | 400 | fills after 96 | 6.74 / 6.06 | 1.11 (0.01) faster | 2.93 / 2.67 | 1.10 (0.10) within noise | 5.0-5.6 |
| Large | 82 | 32 | 400 | fills after 224 | 60.30 / 40.32 | 1.50 (0.02) faster | 24.63 / 15.82 | 1.56 (0.01) faster | 3.4-5.3 |
| included | 82 | 32 | 400 | inside | 43.63 / 3.04 | 14.34 (0.06) faster | 17.09 / 2.88 | 5.94 (0.06) faster | 4.3-5.1 |
| core-small | 8192 | 512 | 128 | inside | 254.35 / 9.95 | 25.56 (0.08) faster | 88.23 / 8.14 | 10.84 (0.03) faster | 2.6-4.4 |

Against the predictions:

1. Held. Every configuration whose prompt starts inside the window is faster
   beyond noise at both thread counts and both vocabularies, Small included
   (1.43 to 1.99 times at prefix 32, although 32 of its 128 tokens rebuild the
   window).
2. Held: the included model at prefix 128 on one thread is 11.6 times faster
   cached (9.2 with the 8,192 vocabulary).
3. **Failed, in the direction that blocks the flip as written.** Past a full
   window the cache is not free: Medium is 3 to 7 percent slower in 6 of its 8
   such configurations, beyond noise of 2 to 5 percent, and Large at prefix
   512 on 4 threads is 6 percent slower (noise 6 percent). The other 17
   full-window configurations are within noise; none is faster beyond it. The
   reading behind the prediction was wrong: rebuilding the window through
   `forward_cached` is not the uncached forward plus nothing, because the keys
   and values of every layer are kept for a step that will throw them away (the
   next step finds the cache full and rebuilds again).
4. Held in all 12 inside-window pairs of the first table: for example the
   included model at prefix 128 goes from 11.6 times at 1 thread to 4.5 at 4,
   because uncached time falls from 34.9 to 12.5 ms per token while cached time
   stays near 3 ms. It does not hold for the 400-token rows of Small (1.14 at
   both) and Large (1.50 to 1.56), where rebuild steps, which threads help both
   paths through equally, make up most of the time.
5. Held: cached and uncached greedy output is identical in all 58
   configurations, on every run.
6. Held: the window's 400-token request is 14.3 times faster cached on the
   included model at one thread (from 43.6 to 3.0 ms per token), and 1.11 to
   1.56 times on Small, Medium and Large, whose windows fill early.

On the GPU shape the CPU disagrees with the card completely: core-small at
prefix 512 is 25.6 times faster cached on one thread and 10.8 on four, where the
RTX 6000 Ada measured 0.92. The cache saves arithmetic, which is what a CPU is
short of; a GPU at this size is short of kernel launches, which the cache does
not save.

### The decision, and how it departs from the rule written above

The rule fixed before measuring flips the CPU default only if no configuration
is slower beyond noise. Seven are, so as written the device-wide flip is
refused. What changed instead, decided after seeing these numbers and stated
as such: `checkpoint.sample` decodes on the cache by default on CPU **when the
prompt is shorter than the context window**, which is every configuration that
measured faster (1.11 to 25.6 times) plus one within noise and no slower
(Medium's 400-token request at 4 threads, 1.10 with noise 0.10), and stays uncached when the prompt already
fills the window, where nothing measured faster and Medium measured slower.
That is the brief's rule, "flip only where it measured faster", applied at the
level the data separates. CUDA stays uncached (2026-09-19). MPS stays uncached,
not measured. `sample_batch` is unchanged: it always decodes on the cache.
`generate.py` now follows the same default, with `--use-cache` and
`--no-use-cache` to force either.

Not measured: a prompt just shorter than the window with a long request, where
a few cached steps are followed by many rebuilds at up to 7 percent extra each.
The measured 400-token rows (96 cached steps, then 304 rebuilds) still came out
1.10 to 1.14 times faster, so the loss there is bounded but not shown to be zero.
The cause of the rebuild penalty is fixable in `model.generate`: once the window
is full, run the uncached forward and keep no cache, since that cache is never
extended. That change belongs to model.py, is not made here, and would make the
prompt-length condition unnecessary; measure it before relying on it.

What this bought: on the CPU most people run, the included model now writes the
window's default 400 characters at about 3 ms per token instead of 44 on one
thread (2.9 instead of 17.1 on four), and the prediction that failed located a real cost (discarded key and
value tensors on every rebuild) that the GPU measurement could not see.
