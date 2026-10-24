# dawnr 6.0.0

dawnr 6.0.0 is the first release numbered by version. Earlier releases were named "student" and "vN"; from here on a
release is dawnr MAJOR.MINOR.PATCH, and every later one is measured against this one before it ships.

**The model in 6.0.0 is the model first released on 2026-10-05, byte for byte.** Its three files have the SHA-256
sums listed in `dawnr.sha256`, the same sums the October 5 release published. Nothing trained since then has passed
the qualification protocol yet, so this release does not claim a better model. What is new in 6.0.0 is the
application around it, the version it carries, the installer, and a corrected account of what the October and later
readings measured. The next model is in training as the 6.1.0 candidate
([registration](../t/PREDICT-2026-10-24-release-6.1-candidate-a.md)); it ships only if it beats this one on the
measurements below.

## What the model does

It writes `t`: given a programming question in English with example tests, or a specification, it writes a `t` task
(what the program requires, what it guarantees, and a body the provers can check). It is never trusted on its own:
dawnr shows its answer only after the tests, an independent Python solution and the provers agree
([README](../README.md)).

## Files

- `dawnr-6.0.0-0000N-of-00003.gguf`: the merged model at 8 bits (Q8_0), split with llama.cpp's `gguf-split` into files
  under GitHub's 2 GiB limit. Load the first file; llama.cpp finds the rest by name.
- `dawnr.sha256`: the SHA-256 of every file. `install.sh` downloads the latest release's files and checks each one.
- `LICENSE-dawnr` (Apache License 2.0) and `NOTICE-dawnr` (the sources it was built from).

## How it was made (unchanged from October 5)

- **Base model:** [Qwen/Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B), Apache-2.0, chosen among six openly
  licensed candidates by a rule fixed before measuring ([selection](../t/PREDICT-2026-10-01-base-model-selection.md)).
- **Fine-tuning:** QLoRA (4-bit NF4 base, double quantisation, bf16 compute); LoRA rank 64, alpha 16, dropout 0.1 on
  all linear layers; learning rate 2e-4; five epochs; rows up to 2,845 tokens; seed 1 (`t/student_sft.py`). Merged
  into the base, exported with llama.cpp's `convert_hf_to_gguf.py --no-mtp` and quantised to Q8_0.
- **Training rows:** 5,095 (SHA-256 `848fca29…`), described in full, with their provenance and the corrections of
  October 5, in [the October 5 card](MODEL-CARD-student-v5.md): 61 rows descend from MBPP-DFY (GPL-3.0 at the source),
  and 18 of the original 200 held-out problems and 5 of the 100 development problems were in the rows under other
  names, so the panels are the other 182 and 95. A 2026-10-24 audit of the same rows also matches held-out problem
  629 by behaviour (one row; 629 is not among the 17 counted below, since the larger-inputs check of October 5
  already removed it) and 34 problems of the wider reader's pool (below).

## Measured

From the October 5 registration, at Q8_0 through llama-server as `dawnr` runs it
([registration](../t/PREDICT-2026-10-05-release-v5.md)):

| reading | result |
|---|---|
| the 33 given specifications, proved by all seven provers | 27 (28 by at least one) |
| the clean 182 held-out problems, 17 answers a problem, specification checked on larger inputs too | 17 proved, 12 by all seven |

Read again under the protocol of 22 October (three decodes, seed offsets 0, 1000 and 2000, the frozen 17-call route,
seven kernels):

| reading | result |
|---|---|
| the 95 development problems, fully clean | 6, 4, 6 (all seven kernels: 3, 2, 3) |
| the 206 unleaked development problems (the 95 plus the wider reader's 111 clean), mean clean per decode | 19.33 (all seven 8.67) |
| the ceiling instrument: gate precision on 20 specification candidates per solved problem | 0.785 |

**Corrected 2026-10-24.** The October 22 to 23 account of these readings said a model "retrained from the exact rows
and recipe with only the training seed changed" read 4, 5 and 4. That model trained on a different set of 4,189
corrected rows (its manifest records `e14f766f…`, not `848fca29…`), so it changed the data and the seed at once and
says nothing about a seed alone. The 240-problem panel used for the same comparison holds 34 problems this model's
rows had matched; on the 206 unleaked problems this model and that one read 19.33 and 14.67 clean per decode, 12
problems up and 8 down, permutation p 0.15: not separable. [CORRECTIONS.md](../CORRECTIONS.md) has the full entry.

## Running it

It runs offline on an ordinary CPU or an 8 GB laptop graphics card. The release is checked on such a laptop (an
RTX 5050 Laptop GPU with 8 GB, 16 cores, 15 GB of memory) before it ships; the numbers are in the
[release notes](https://github.com/trestoncuzzort/dawnr/releases/tag/v6.0.0).

## Limits

It writes a wrong specification more often than a right one, and it has only been trained and measured on short
programming problems over integers, booleans and sequences. See [../DISCLAIMERS.md](../DISCLAIMERS.md) and
[../LIMITS.md](../LIMITS.md).

## Licence and acknowledgement

Apache License 2.0 ([LICENSE-dawnr](LICENSE-dawnr)); the sources are credited in [NOTICE-dawnr](NOTICE-dawnr).
Work toward the next releases is supported by a Cohere Labs Catalyst Grant.
