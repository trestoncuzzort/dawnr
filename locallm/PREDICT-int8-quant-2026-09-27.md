# int8 weight quantization, predicted before it is measured

Written before `bench_int8.py` runs against the included checkpoint
(`t/runs/2026-09-17/home-4080/models/model-r4`, L6 H6 D384, context 512, vocab
82, 10,875,648 parameters), so nothing below was tuned to a result. The scheme
is Krishnamoorthi 2018 (arXiv:1806.08342) sections 2.2 and 2.6: per-output-row
symmetric int8, scale = max(abs(row))/127, restricted to [-127, 127]. Both
paths do WEIGHT-ONLY quantization (activations stay float32); `plain_generate.py`
also quantizes the embedding tables (`wte`, `wpe`) row by row, which the torch
path (`quant_int8.py`) does not attempt (it only replaces `nn.Linear`).

Protocol for every number below: prompt `"task "`, 200 tokens, `temperature=0`
(greedy — the only mode float32 and int8 can be sanely compared token for
token), 3 repeats per configuration, median reported. Agreement is computed
position by position between two independently generated 200-token sequences
from the same prompt and seed-free greedy decoding. All four `plain_generate.py`
configurations (none, `--quantize`, `--quantize-kv`, both) and both
`quant_int8.py` states (float, `quantize_model_int8` applied) run on CPU only —
this is a 10.9M-parameter model measuring standard-library and CPU-torch code
paths, so the GPU is not involved and is not asked to be.

## What I expect, with the number that would prove me wrong

1. **Memory drops to close to a quarter, not exactly a quarter.** Every
   quantized weight matrix in this checkpoint has rows of width 384 except
   `mlp.c_proj`'s, which are width 1536 (`SHIPPING.md`'s own per-layer table).
   int8 row bytes + one float32 scale per row, over float32 row bytes, is
   `(W + 4) / (4W)`: 0.2526 at W=384, 0.2507 at W=1536. I expect
   `PlainGPT.weight_bytes()` (quantized) / `weight_bytes()` (float) **between
   0.25 and 0.27**, and `quant_int8.linear_weight_bytes` similarly **between
   0.25 and 0.27** (it skips the embeddings, which does not change the ratio
   much since they are also width-384 rows). Outside that band means either
   the scale array is costing more than one float32 per row, or a row width is
   not what SHIPPING.md's table says.

2. **Weight quantization is not free at this model's size, and I expect the
   failure to show up quickly.** Greedy decoding is autoregressive: once one
   token differs, every later token is conditioned on a context the float
   model never produced, so nothing beyond that point is expected to match
   except by the roughly 1-in-82 chance of picking the same character anyway.
   I expect **the first divergence between `--quantize` and the unquantized
   text before token 50**, and **20-token-window agreement over the full 200
   between 5% and 45%** (above pure chance, because this small a model repeats
   common characters and short fragments often enough to coincide sometimes;
   nowhere near 100%, because nothing here claims quantization is lossless).
   100% agreement would say this model's logits are far more decisive than
   `AMBITION.md`'s own account of it ("rarely succeeds" outside its training
   text) suggests, and would be the more surprising outcome.

3. **`--quantize-kv` alone disturbs the text less than `--quantize` does.**
   Only the attention values and keys are perturbed, and `SHIPPING.md`'s own
   MAC table gives attention 2,359,296 of the 13,007,616 multiply-accumulates
   per token at full context (18%) against the four linear layers' 10,616,832
   (82%) — a smaller share of the arithmetic touched should mean a smaller
   share of the argmax decisions flipped. I expect **`--quantize-kv` alone to
   still diverge from the unquantized text somewhere in 200 tokens** (it is
   lossy, not exact) but with **agreement between 30% and 80%**, higher than
   `--quantize` alone.

4. **Speed moves less than memory does, in either direction, on the
   standard-library path.** The dot product itself is the same number of
   Python-level operations whether the row is `array('b')` or `array('f')` —
   `math.sumprod`/`sum(map(mul, ...))` do not skip work for int8 — plus one
   extra scale multiply per output row, which is O(out_features), not
   O(out_features x in_features). I expect **`--quantize`'s ms/token between
   0.85x and 1.20x of the unquantized baseline**: a genuine 4x memory cut
   could still come with a small slowdown (the extra multiply, plus the loss
   of the CPython small-int cache for int8 values outside -5..256, which is
   every negative one below -5) or a small speedup (array('b') is a quarter
   the bytes moved through cache). `--quantize-kv` costs an extra
   quantize-and-append per step; I expect it in the same 0.85x-1.20x band,
   because the attention share of the arithmetic is only 18% here (item 3).

5. **The torch path moves the same weight-memory needle and, on CPU, a similar
   or slightly worse speed one.** `QuantizedLinear.forward` casts the int8
   weight back to float32 and runs the ordinary `F.linear`, so it does
   strictly more work per call than the plain float `nn.Linear` (a cast plus a
   multiply before the same matmul), not less. I expect quantized CPU ms/token
   **between 1.0x and 1.6x of float32's**, i.e. quantizing the torch path buys
   memory, not speed, at this model's size and on this hardware — a genuine
   speedup would mean the cast+multiply is cheaper than I am predicting, or
   that CPU cache effects favor int8 storage more than expected.

## What each outcome changes

- If memory lands outside 0.25-0.27: `weight_bytes`/`linear_weight_bytes` has a
  counting bug (wrong itemsize, a missed row, or the scale array counted
  twice), not a property of the scheme, and needs fixing before the ratio is
  reported anywhere else.
- If `--quantize` agreement is at or near 100%: either this checkpoint's
  logits are far more separated than expected (worth its own finding) or the
  comparison is accidentally comparing a model to itself (a test bug to chase
  down before trusting the number).
- If `--quantize`'s speed is far outside 0.85x-1.20x in either direction: the
  dominant cost is not the dot product (maybe row-object overhead from
  `array('b')` vs `array('f')`, or GC pressure from int construction) and is
  worth its own profile before this is called "no speed effect."
- If the torch path is faster quantized than float on CPU: this build's BLAS
  is not fusing the float32 matmul as well as expected, or `QuantizedLinear`'s
  cast is cheaper than the extra float32 memory bandwidth `nn.Linear` pays for
  a 4x larger weight — either way worth a second measurement before trusting
  a stray fast run.
