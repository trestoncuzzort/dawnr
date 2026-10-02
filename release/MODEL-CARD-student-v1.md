# dawnr-student-v1

The model inside dawnr that writes `t`: given a programming question in English with example tests, or a
specification, it writes a `t` task (what the program requires, what it guarantees, and a body the provers can
check). It is never trusted on its own: dawnr shows its answer only after the tests, an independent Python
solution and the provers agree (see [../README.md](../README.md)).

## Files

- `dawnr-student-0000N-of-0000M.gguf`: the merged model at 8 bits (Q8_0), split with llama.cpp's `gguf-split`
  into files under GitHub's 2 GiB limit. Load the first file; llama.cpp finds the rest by name.
- `dawnr-student.sha256`: the SHA-256 of every file. `install.sh` downloads and checks them.

## How it was made

- **Base model:** [Qwen/Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B), Apache-2.0, chosen among six openly
  licensed candidates by a rule fixed before measuring ([selection](../t/PREDICT-2026-10-01-base-model-selection.md)).
- **Fine-tuning:** QLoRA (4-bit NF4 base, double quantisation, bf16 compute); LoRA rank 64, alpha 16, dropout 0.1
  on all linear layers; learning rate 2e-4; five epochs; rows up to 2,845 tokens; seed 1 (`t/student_sft.py`),
  with the flash-linear-attention kernels for training. Merged into the base, exported with llama.cpp's
  `convert_hf_to_gguf.py --no-mtp` and quantised to Q8_0, the format measured to keep every proof of full precision
  ([small hardware](../t/PREDICT-2026-10-01-small-hardware.md)).
- **Training rows (3,835),** the 4B on v6 ([registration and outcomes](../t/PREDICT-2026-10-01-v6.md)): only
  answers the provers accepted, rows built from them, and conversations that use dawnr's memory.

| rows | kind |
|---:|---|
| 635 | proved answers to English questions |
| 635 | proofs written from a problem's tested Python |
| 548 | specifications written from a problem's tested Python |
| 296 | Python solutions that pass the problem's tests |
| 432 | a body and proof for a given specification |
| 1,112 | repairs: a failed answer, the checker's message (including a counterexample to a wrong specification), the fixed answer |
| 177 | conversations that recall and apply a remembered preference |

- **Where the problems come from:** MBPP (CC-BY-4.0), HumanEval (MIT) and APPS (MIT) for the questions; the
  vericoding benchmark (MIT), DafnyBench (Apache-2.0; its programs come from many GitHub repositories),
  HumanEval-Dafny (Apache-2.0) and Clover (MIT) for the given specifications. The 52 rows that name a
  dafny-synthesis program, GPL-3.0 at its source, are left out
  ([provenance](../internal/RELEASE-PROVENANCE-2026-10-01.md)).
- **Kept out of training:** the 200 held-out problems, the 100 development problems and the 33 held-out
  specification questions used to measure it; every row set is checked for them before training.

## Measured

In full precision (`t/PREDICT-2026-10-01-v6.md`): given 33 held-out specifications it writes a body all seven
provers accept on 26; from English, one answer to each of 100 development problems is proved on a complete
specification for 4. Given a person's remembered preference it recalls it 28 times in 28, invents none, and
applies it to its program 8 times in 14. At Q8_0, the file published here, through llama-server as `dawnr` runs it: 26 of the 33 given specifications proved by all seven provers (27 by at least one), and 4 development problems proved on complete specifications from one answer each (0 by all seven) ([registration](../t/PREDICT-2026-10-02-release-student.md), predictions 104 and 105 hold).

## Limits

It writes a wrong specification more often than a right one, and it has only been trained and measured on short
programming problems over integers, booleans and sequences. See [../DISCLAIMERS.md](../DISCLAIMERS.md).

## Licence

Apache License 2.0 ([LICENSE-student](LICENSE-student)); the sources it was built from are credited in
[NOTICE-student](NOTICE-student).
