# Shipping locallm on a stick

What it costs to hand a stranger a USB stick that either trains a model on their
own text or talks to one that is already trained. Every size here was either
measured on disk in this working tree or read from a published index; where a
number is arithmetic rather than a measurement it says so on the same line.

The short version, and it is not the expected one:

1. **Generation needs no torch at all.** It is now implemented and measured:
   [`plain_generate.py`](plain_generate.py), 26 KB of standard library, reads a
   `ckpt.pt` and writes text at 181–245 ms per token on the round-4 checkpoint,
   on a machine with neither torch nor numpy installed. One copy of that file
   plus one copy of the weights serves Linux, macOS and Windows.
2. **Training needs the platform's own torch.** Not because of an engineering
   gap — because plain Python turns the studio's shortest fallback run into
   20 days and its worked example into 451 days (arithmetic in §4). That needs one
   environment per operating system and CPU architecture, and there are five in
   play, not three.
3. **A generation-only stick that works on all three, with nothing installed on
   the target, is 200,599,772 bytes.** A training stick for the same three is
   about 2 GB unpacked. Both are far below the 2.5 GB-per-platform figure that a
   plain `pip install torch` suggests, and §3 says why that figure is real but
   avoidable.
4. **The model on the stick writes `t`, not English.** That is the honest
   headline and §6 shows the actual output.

## 1. What weights actually exist here

The repository puts `*.pt` through Git LFS (`.gitattributes`), so the first
question is whether the weights are present or merely referenced. **They are
present.** `git lfs ls-files` marks all fourteen objects `*` (content available
locally, not a pointer), `.git/lfs/objects` holds 147 MB in fourteen files, and
the working-tree `sha256sum` of `t/runs/2026-09-17/home-4080/models/model-r4/ckpt.pt`
equals the `oid` in its 133-byte LFS pointer. Nothing was pulled to establish
this and no `git lfs pull` was run.

Every row below was read by `plain_generate.py` on 2026-09-20 — the config comes
out of the checkpoint's own pickle, the parameter count from its shapes.

| model dir | in the repository? | `ckpt.pt` bytes | parameters | config | vocab |
|---|---|---:|---:|---|---:|
| `t/runs/2026-09-17/home-4080/models/model-r4` | **yes**, LFS, content present | 43,526,601 | 10,875,648 | L6 H6 D384 ctx512 | 82 |
| `t/runs/2026-09-16/heldout-locallm-r0/model` | yes, LFS, present | 19,588,553 | 4,891,136 | L6 H8 D256 ctx512 | 82 |
| `t/runs/2026-09-16/filter-loop/clean/r{0,1,2}/model` | yes, LFS, present | 12,869,977 each | 3,213,312 | L4 H4 D256 ctx128 | 82 |
| `t/runs/2026-09-16/filter-loop/raw-full/r0/model` | yes, LFS, present | 12,879,193 | 3,215,616 | L4 H4 D256 ctx128 | 91 |
| `t/runs/2026-09-16/filter-loop/raw-matched/r0/model` | yes, LFS, present | 12,872,025 | 3,213,824 | L4 H4 D256 ctx128 | 84 |
| `t/runs/2026-09-17/filter-loop-mac/r{0,1}/model` | yes, LFS, present | 12,869,273 each | 3,213,312 | L4 H4 D256 ctx128 | 82 |
| `t/out/loop-locallm/model-r4` | **no**, `t/out/**` is gitignored | 43,526,601 | 10,875,648 | — | 82 |
| `t/out/loop-locallm/model-r5` | **no**, gitignored | 102,152,825 | 25,530,368 | L8 H8 D512 ctx512 | 94 |
| `t/out/spec-experiment/locallm-r0/model` | **no**, gitignored | 19,588,553 | 4,891,136 | — | 82 |

Nine tracked checkpoints, 153,214,849 bytes, which is the whole LFS store bar
the five `nl/data/*.jsonl.gz` corpora (176 KB). The two gitignored ones are not
extra models: `t/out/loop-locallm/model-r4` is byte-identical to the tracked
round-4 (`sha256 31fe60b3…`) and `t/out/spec-experiment/locallm-r0/model` is
byte-identical to `heldout-locallm-r0` (`sha256 5b6b87e6…`). **Round 5 is the one
real model with no copy in the repository.**

Three things follow, and two of them are uncomfortable.

* The best from-scratch arm whose weights exist here is **round 4**:
  [`SCOREBOARD.md`](../SCOREBOARD.md) gives it 209 well-formed answers of 232, 2
  that pass their tests, 2 clean, 1 surviving the specification check.
* **The best row on the scoreboard is not shippable from this tree.** Round 8
  with signature-headed training — 3 clean, the row that ties Phi-4-mini — is a
  92M pretrained-then-specialized model, and there is no checkpoint for rounds 7,
  7b, 8 or 9 anywhere in this working tree. `t/runs/2026-09-18/`,
  `2026-09-19/` and `2026-09-20/` contain `logs/` and nothing else. Those weights
  are on the machine that trained them.
* `t/out/loop/adapter-r4`, `-r5`, `-r6` are **not** locallm models. Their
  `adapter_config.json` reads `"peft_type": "LORA"`,
  `"base_model_name_or_path": "Qwen/Qwen2.5-Coder-1.5B-Instruct"`, so each 37 MB
  adapter is useless without a multi-gigabyte base model download. Nothing about
  them fits on a self-contained stick.

## 2. Loading and generating: can it be done without torch?

Yes, and it is done. Two separate questions had to be answered.

**Can the checkpoint be read?** `torch.save` since PyTorch 1.6.0 writes an
uncompressed ZIP64 archive of `data.pkl`, `byteorder`, `data/0`, `data/1`, …,
`version`, where `data.pkl` is the pickle of the object *excluding* its storages
and each storage is one archive member holding raw element bytes
(docs.pytorch.org/docs/2.14/notes/serialization.html). Checked against the real
file: `ckpt/byteorder` is `b'little'`, `ckpt/version` is `b'3'`, `ckpt/data/0` is
125,952 bytes = 31,488 float32 = exactly the `(82, 384)` embedding. `zipfile` +
`pickle` + `array` is the whole loader, and `pickle`'s `persistent_load` hook is
where the storage references arrive. `location` in each reference reads
`'cuda:0'` and is simply ignored — raw bytes have no device.

**Can the forward pass be run?** The arithmetic, for round 4 (D=384, L=6, vocab
82, context 512), per token with a key/value cache:

| what | multiply-accumulates |
|---|---:|
| `c_attn`, `attn.c_proj`, `c_fc`, `mlp.c_proj` = 12·D² per layer, ×6 | 10,616,832 |
| attention itself, 2·D·T per layer at T=512, ×6 | 2,359,296 |
| `lm_head`, D·V | 31,488 |
| **per token at full context** | **13,007,616** |

That is 1.2 multiply-accumulates per parameter per token. Plain CPython on this
machine does 47.7M of them per second through `sum(map(mul, row, x))` over
`array('f')` rows — measured three ways, because the shape of the loop matters
more than the arithmetic: 25.4M for an explicit `for`, 30.5M for a generator
expression with `zip`, 47.7M for `sum(map(mul, …))`. 13.0M ÷ 47.7M predicts
273 ms per token. Measured: **244.6 ms**, 12% better than predicted because the
1536-wide MLP rows amortize per-row call overhead better than the 384-wide
benchmark did.

Measured end to end, greedy decoding, no torch and no numpy importable on this
machine:

| checkpoint | parameters | context | ms per token | 200 tokens asked | peak process RSS |
|---|---:|---:|---:|---|---:|
| `filter-loop/clean/r0` | 3,213,312 | 128 | 58 → 67 | 7.4 s, clamped to 119 (see below) | — |
| `heldout-locallm-r0` | 4,891,136 | 512 | 87–93 | 18.7 s, 0 rebuilds | 73 MiB |
| **`home-4080/models/model-r4`** | **10,875,648** | **512** | **181 → 245** | **51 s, 0 rebuilds** | **154 MiB** |
| `loop-locallm/model-r5` | 25,530,368 | 512 | 441 → 451 | 94.3 s, 0 rebuilds | — |

All twelve checkpoints in this tree load and decode. Growth with context is mild
because attention is only 18% of the work at the far end of a 512 window.

**The one sharp edge, and the first thing measuring it corrected.** When the
context fills, the key/value cache has to be rebuilt from the retained token IDs.
The first draft of this file said that costs one re-prefill per `block_size`
tokens and amortizes to about 215 ms each. **That was wrong, and the measurement
says so.** Re-prefilling leaves the cache full again, so the *next* token
re-prefills too: every token past the window costs a whole window.

| checkpoint | in-window forward | forward 1 past the window | past the window |
|---|---:|---:|---|
| `filter-loop/clean/r0`, ctx 128 | 58–67 ms | **7,461 ms** | 7,397–7,428 ms, every token |
| `home-4080/models/model-r4`, ctx 512 | 181–245 ms | **109,802 ms** | not measured further; the shape is the same |

That is 112× on the ctx-128 arm, per token, indefinitely — not a pause, a wall.

This is `model.py`'s behaviour, not a defect introduced here, and the repository
already had it right:
[`FINDINGS-kv-cache-2026-09-19.md`](FINDINGS-kv-cache-2026-09-19.md) states that
"once the context fills, generation rebuilds the cache from the retained window
on every step", gives the reason — "merely deleting old keys would retain hidden
states influenced by dropped tokens and change the old model's sliding-window
behavior" — and is explicit that its timings "remain within the window and do not
claim a speedup after rollover". `test_kv_cache.py` exercises the crossing
directly at `block_size=8` with 14 new tokens. Under torch the refill is one
batched forward and reads as a slowdown; in an interpreter it is a wall.

So `plain_generate.sample` **stops at the window by default** and reports that
it stopped, rather than returning short text that reads like a model running out
of things to say; `--past-context` is there for anyone who means it. Sliding the
window was rejected for the reason that findings file already gives.

### Prior art this rests on

* **tairov/llama2.py** — a fork of karpathy/llama2.c that runs the whole
  transformer in one file of pure Python, and publishes the number that made this
  worth trying: **1.3 tok/s** in native CPython on stories15M (dim 288, 6 layers,
  vocabulary 32,000) on an M1 Max, and **32 tok/s** under PyPy. We measure
  **5.0 tok/s**. The work per token is comparable — theirs is about 15.2M
  multiply-accumulates, of which 9.2M is the 32,000-entry output projection
  alone, against our 13.0M with an 82-entry vocabulary costing 31,488 — so the
  3.8× is throughput, not model size: a different machine and, from the
  microbenchmark above, an inner loop that is 1.9× faster written as
  `sum(map(mul, …))` than as an explicit `for`. Their PyPy row is the honest
  answer to "make it faster" and was not reproduced here.
* **jaymody/picoGPT** — GPT-2 inference in ~40 lines of NumPy. Rejected only
  because NumPy is a per-platform wheel, which is the thing being avoided.
* **pytorch/pytorch#45394** — "Due to prerequisites limitations, I am not able to
  install torch. Is it possible to load the pt file with python library pickle?"
  Opened 2020, closed with no answer. This is that answer.

### What `plain_generate.py` is, and what it weighs

**26,819 bytes, 539 lines, one file, zero dependencies** — `argparse`, `array`,
`io`, `json`, `math`, `pickle`, `random`, `sys`, `zipfile`, `operator.mul`,
`pathlib`. It mirrors [`checkpoint.py`](checkpoint.py)'s interface on purpose —
`checkpoint_exists`, `load_checkpoint`, `sample` with the same arguments — so a
caller switches between the torch path and this one by changing an import.

    python3 plain_generate.py --out mymodel --prompt "function to " --temperature 0

What it refuses, by name, with the reason in the message:

| refusal | why |
|---|---|
| `architecture="modern"` | needs RMSNorm, rotary positions and SwiGLU — about 25 more lines, and there is no `modern` checkpoint here to check them against, so writing them would ship untested code |
| byte-BPE `tokenizer.json` | decoding needs the `tokenizers` package, which is a wheel again |
| bfloat16 / other storages | `array` has no bfloat16 code; the conversion is a 16-bit shift, and no checkpoint here is saved that way |
| strided tensor views | needs index arithmetic this does not do; a state dict of ordinary parameters never produces one |
| a pickle naming anything outside a three-entry allowlist | unpickling is arbitrary code execution (docs.python.org/3/library/pickle.html), and a stranger's stick may hold a checkpoint a stranger sent them; this is the equivalent of `torch.load(weights_only=True)` |
| a Git LFS pointer in place of the weights | the likeliest way a stranger's copy arrives broken, and `zipfile`'s "File is not a zip file" gives no way to guess it |

Two things it will never do. It does not train (§4). And its sampler is
`random.choices`, which draws from the same distribution as `torch.multinomial`
but not the same stream, so **a seed here and a seed there give different text**.
Only `--temperature 0` is comparable to the torch path, and even that can differ
in the last place because float32 sums accumulate in a different order. That
comparison has not been run: this machine has no torch to run it against, so
**agreement with `checkpoint.sample` is unverified and no claim is made.**

Everything a stranger trains in the studio falls inside what this reads:
`studio.py` never passes `architecture`, so it gets `GPTConfig`'s default `gpt`,
and it builds `CharTokenizer.from_text` (`studio.py:513`, `studio.py:567`).
`train.py` on the command line defaults the same way unless `--preset` is given.

## 3. The real size of a stick, per platform

### Why "torch is 2.5 GB" is true and avoidable

A plain `pip install torch` on Linux downloads, at torch 2.14.0:

| wheel | bytes |
|---|---:|
| `torch-2.14.0-cp313-cp313-manylinux_2_28_x86_64.whl` | 554,619,993 |
| `nvidia_cudnn_cu13` | 519,150,073 |
| `nvidia_nccl_cu13` | 252,442,223 |
| `triton` | 247,838,081 |
| `nvidia_cusparselt_cu13` | 171,537,569 |
| `nvidia_nvshmem_cu13` | 135,397,797 |
| `cuda-toolkit[cublas,cudart,cufft,…]`, eleven x86-64 wheels | 1,192,445,434 |
| **total** | **≈ 3.07 GB** |

All of it CUDA, on a machine that may have no NVIDIA card. Those dependencies are
`torch`'s own `requires_dist`, every one of them guarded
`platform_system == "Linux"`. The CUDA figures are the newest 13.x wheels rather
than torch's exact pins, so treat the total as approximate; the first six are
exact.

The CPU-only index makes that go away, and
[`install.py`](install.py) already uses it — it asks `nvidia-smi` and falls back
to `download.pytorch.org/whl/cpu` when there is no card. Reaching either index
needs a network, which a stick has not; the sizes below are what staging those
wheels on the stick instead would cost. [`OFFLINE.md`](OFFLINE.md), written the
same day, audits that from the other end and finds the same single blocker:
"`INSTALL.bat` cannot work offline at all, because it installs PyTorch from
`download.pytorch.org` with pip".

| torch 2.14.0+cpu, cp313 | wheel bytes | unpacked bytes |
|---|---:|---:|
| `manylinux_2_28_x86_64` | 196,253,940 | 715,510,253 (measured locally) |
| `win_amd64` | 123,995,955 | 475,874,512 (zip directory, 12,210 entries) |
| macOS `arm64` (no `+cpu` variant exists; the PyPI macOS wheel *is* the CPU/MPS build) | 127,311,393 | 524,013,492 (zip directory, 13,691 entries) |
| `manylinux_2_28_aarch64` | 159,257,719 | not measured |
| `win_arm64` | 76,139,492 | not measured |

Plus torch's pure-Python dependencies — filelock, typing-extensions, setuptools,
sympy, networkx, jinja2, fsspec and their own mpmath and MarkupSafe — which are
**10,273,918 bytes** together and platform-independent.

### The Python interpreter, if the stranger has none

| runtime | download | unpacked | tkinter? |
|---|---:|---:|---|
| python.org Windows embeddable 3.14.0 amd64 | 11,994,671 | 22,814,689 | **no**, and no pip either |
| python-build-standalone 20260901, Windows x86-64 | 47,042,104 | 151,270,537 | yes |
| python-build-standalone 20260901, macOS arm64 | 25,293,188 | 65,443,266 | yes |
| python-build-standalone 20260901, Linux x86-64 gnu | 119,758,082 | 390,245,787 | yes |

The embeddable zip is enough for `plain_generate.py` and **not** enough for the
studio window, which needs tkinter. On a Linux machine that already has Python,
tkinter is frequently a separate system package (`python3-tk`), which is a
platform dependency a stick cannot carry.

### Generation-only stick: one copy serves everybody

| item | bytes |
|---|---:|
| `plain_generate.py` | 26,819 |
| round-4 `ckpt.pt` | 43,526,601 |
| round-4 `tokenizer.json` | 411 |
| *shared subtotal* | *43,553,831* |
| Windows embeddable Python | 11,994,671 |
| macOS arm64 standalone Python | 25,293,188 |
| Linux x86-64 standalone Python | 119,758,082 |
| **total, three platforms** | **200,599,772** (191 MiB) |

Add the other two CPU architectures — macOS x86-64 (25,037,769) and Linux
aarch64 (91,086,530) — and it is 316,724,071 bytes, 302 MiB. On a machine that
already has Python 3.10 or newer, the whole stick is the 41.5 MiB shared subtotal
and nothing else.

### Training stick: per platform, and it does not share

| platform | Python + torch + pure-python deps, as downloads | torch unpacked |
|---|---:|---:|
| Linux x86-64 | 326,285,940 | 715,510,253 |
| Windows x86-64 | 181,311,977 | 475,874,512 |
| macOS arm64 | 162,878,499 | 524,013,492 |
| **three, downloads** | **670,476,416** (639 MiB) | **1,715,398,257** (1.60 GiB) |

Unpacked and ready to run, the three Pythons (606,959,590) plus the three torch
trees (1,715,398,257) plus every `.py` in `locallm/` (about 0.7 MB across 44
modules, excluding tests — other agents are editing that directory as this is
written, so it is rounded) is **about 2.3 GB**, before any training text. Code is
0.03% of that; the binaries are all of it.

### One stick, or three?

**One stick, three copies of the machinery, one copy of the model.** A single
exFAT volume mounts on all three systems, so the stick is not the problem. What
cannot be shared is a compiled artifact: `libtorch_cpu.so` (438,232,064 bytes),
`torch_cpu.dll` (305,887,744) and `libtorch_cpu.dylib` (386,016,976) are three
different files doing one job, and the CPython binary beside each is equally
specific. And it is not three environments but **five**, because macOS ships both
arm64 and x86-64 and Linux is used on both — the count is one per (OS, CPU
architecture) pair, not per OS.

What genuinely ships once, for everybody: every `.py` file, the checkpoint, the
`tokenizer.json`, the corpus, and `plain_generate.py`.

## 4. Why training cannot follow generation off torch

Not a tuning gap. A backward pass costs roughly twice the forward, so a training
step is about 3× the forward per token, over `steps × batch × block` tokens. Take
the studio's Medium size, which is what it trains by default: L4 H4 D256, block
128, batch 32 (`studio.py` `SIZES`). Its forward is 3,428,864
multiply-accumulates per token, so a training step is 10,286,592, and at the
measured 47.7M per second that is **0.216 s per token**.

Step counts are derived from the machine's own measured speed against a
wall-clock target — "Normal" asks for 300 seconds (`studio.py` `LENGTHS`) — so
there are two honest anchors rather than one:

| run | tokens | pure Python |
|---|---:|---:|
| `UNTIMED_NORMAL_STEPS = 2000`, the fallback on a machine that has never been benchmarked | 8,192,000 | 1,766,620 s = **20.4 days** |
| 44,100 steps, the worked example `get_corpus.py` sizes its download against | 180,633,600 | 38,953,965 s = **451 days** |

Three to four orders of magnitude is not something an optimizer pass closes, and
both rows are arithmetic from two measured numbers, not benchmarks.

So training is torch's, on the platform it was built for, and the split is:

| | needs torch | ships once for all platforms |
|---|---|---|
| train on your own text (`studio.py`, `train.py`) | **yes**, plus tkinter for the window | no — one environment per OS and CPU |
| load a trained checkpoint | no | yes |
| generate text from it | no | yes |
| byte-BPE tokenizer | needs `tokenizers` | no |
| the `modern` core (RMSNorm/RoPE/SwiGLU) | not inherently — ~25 more lines in `plain_generate.py` | would, once written and checked |

## 5. If generation should be faster

Three levers, in order of how much they buy and how much they cost.

1. **Run it under PyPy.** tairov/llama2.py measures 32 tok/s against 1.3 for the
   same file, about 25×, which would put round 4 near 10 ms per token. It costs
   a second per-platform runtime on the stick and nothing in code. Not measured
   here; the number is theirs.
2. **Use numpy if it happens to be installed.** One `try: import numpy` and a
   second `_matvec` would likely give one to two orders of magnitude, at the cost
   of a per-platform wheel and a second code path that can silently disagree with
   the first. Not measured, and deliberately not written.
3. **Stay inside the context window**, which `generate` now does by default.
   Crossing it costs a full re-prefill on every token — 7.4 s each on a ctx-128
   arm, 110 s each on round 4 — so this is the largest single factor available
   and it costs nothing.

## 6. What actually arrives, in its own words

The honest expectation-setting, greedy decoding from the round-4 checkpoint that
would be on the stick. Its corpus was this project's verified `t` programs, so
that is what it writes, whatever it is asked:

    $ python3 plain_generate.py --out model-r4 --temperature 0 \
        --prompt "function to find the sum of the first n natural numbers."
    function to find the sum of the first n natural numbers.
    Signature: find_star_num(int) -> int
    t 0
    task mbpp_268__find_star_num(n: int) returns (r: int)
      ensures r == 6 * n * (n - 1) + 1
    {
      r := 6 * n * (n - 1) + 1;
    }

Well-formed `t`, with a specification and a body that agree — and the wrong
problem: it was asked for a sum and answered with star numbers. That is exactly
the result [`SCOREBOARD.md`](../SCOREBOARD.md) reports (209 well-formed, 2
correct) arriving on a stranger's laptop with no machine-learning software on it.

Asked anything outside its world it does not degrade gracefully:

    --prompt "Hello, how are you?"
    Hello, how are youth: int) returns (r: int)
      ensures r == length * width

A stranger who boots this expecting a chatbot has been misled. The stick has to
say, on its front page, that this model writes a specification language. The
alternative — shipping a model trained on the TinyStories corpus
[`get_corpus.py`](get_corpus.py) fetches, which would answer in English — does
not exist as a checkpoint in this repository and would have to be trained first.

## 7. What is still not answered

* **Agreement with torch is unverified.** No machine in this loop has torch, so
  `plain_generate.sample` has never been compared against `checkpoint.sample` on
  the same checkpoint, prompt and seed at `temperature=0`. Until it is, the claim
  is only that the output is well-formed `t` of the kind the scoreboard
  describes — not that it is bit-for-bit what torch would produce. Running that
  comparison on a machine with torch is the first thing to do with this file.
* **The `modern` core is unread.** Nothing here can check it.
* **Nothing was found wrong in any file this one does not own.** The one
  candidate — per-token window refill after rollover — turned out to be
  documented, reasoned and tested already, and the draft that called it
  undocumented was wrong before it was checked.
* **The best model is not here.** Shipping the round-8 arm means fetching a 92M
  checkpoint from the machine that trained it; at 92M parameters
  `plain_generate.py` would need about 1.9 s per token by the same arithmetic,
  which is a different product.
* **No stick has been built.** Every size is measured, but the assembly — layout,
  a launcher per platform, the front-page wording — has not been done, and the
  Windows launchers that exist ([`INSTALL.bat`](INSTALL.bat),
  [`Train My AI.bat`](Train%20My%20AI.bat)) assume a machine with Python on its
  PATH and an internet connection to `download.pytorch.org`.

## Sources

* docs.pytorch.org/docs/2.14/notes/serialization.html — the ZIP64 layout of
  `torch.save`, `data.pkl` excluding storages, `byteorder` since 2.1.0
* docs.python.org/3/library/pickle.html — `persistent_load`, and the warning that
  unpickling executes arbitrary code
* github.com/tairov/llama2.py — one file of pure Python, 1.3 tok/s native
  CPython on 15M parameters, 32 tok/s under PyPy
* github.com/jaymody/picoGPT — GPT-2 in ~40 lines of NumPy
* github.com/pytorch/pytorch/issues/45394 — reading a `.pt` without torch, asked
  and unanswered
* github.com/pytorch/pytorch/issues/94262 — "the linux x86_64 wheels are huge and
  are more than 800MB"
* pypi.org/pypi/torch/json and download.pytorch.org/whl/cpu — the wheel sizes and
  `requires_dist` in §3
* www.python.org/ftp/python/3.14.0/ and
  github.com/astral-sh/python-build-standalone/releases/tag/20260901 — the
  interpreter sizes
