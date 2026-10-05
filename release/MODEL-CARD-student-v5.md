# dawnr-student-v5

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
  with transformers' reference PyTorch kernels for the linear-attention layers. Merged into the base, exported with llama.cpp's
  `convert_hf_to_gguf.py --no-mtp` and quantised to Q8_0, the format measured to keep every proof of full precision
  ([small hardware](../t/PREDICT-2026-10-01-small-hardware.md)).
- **Training rows (5,095):** v3's 4,027 rows unchanged (the recipe of the 4B on v5 without the dafny-synthesis
  rows, with 83 permissive specification-given rows), then 1,068 rows from documents the provers admitted since: answers
  two openly licensed teacher models wrote on Amazon Bedrock (Qwen3-235B-A22B-Instruct-2507 and DeepSeek-V3.2, the
  latter also to 129 APPS problems) and the student's own specification-round answers, each kept only when it passed the problem's tests, the specification
  check and at least one prover, and specification documents only when six or seven provers read them clean
  ([rows](../t/PREDICT-2026-10-04-teacher3-student.md), [release](../t/PREDICT-2026-10-05-release-v5.md)). No row is
  built from a dafny-synthesis program, and none answers one of the 33 held-out specification questions (the strict
  check of `t/student_rows.py`). It holds no memory conversations.

| rows | kind |
|---:|---|
| 933 | proved answers to English questions |
| 933 | proofs written from a problem's tested Python |
| 839 | specifications written from a problem's tested Python |
| 549 | Python solutions that pass the problem's tests |
| 639 | a body and proof for a given specification |
| 1,202 | repairs: a failed answer, the checker's message, the fixed answer |

- **Where the problems come from:** MBPP (CC-BY-4.0), HumanEval (MIT) and APPS (MIT) for the questions; the
  vericoding benchmark (MIT), DafnyBench (Apache-2.0; its programs come from many GitHub repositories),
  HumanEval-Dafny (Apache-2.0), Clover (MIT), ACSL by Example (MIT) and the Verus repository's examples (MIT) for the
  given specifications; the two teacher models above for some of the answers. Every row built from a
  dafny-synthesis program, GPL-3.0 at its source, is left out
  ([provenance](../internal/RELEASE-PROVENANCE-2026-10-01.md)).
- **Kept out of training:** the 200 held-out problems, the 100 development problems and the 33 held-out
  specification questions used to measure it; every row set is checked for them before training.

## Measured

At Q8_0, the file published here, through llama-server as `dawnr` runs it: 27 of the 33 given specifications proved by all seven provers (28 by at least one; v1 26), and 4 development problems proved on complete specifications from one answer each (2 by all seven) ([registration](../t/PREDICT-2026-10-05-release-v5.md), R1, R2 and R3 hold).

## Limits

It writes a wrong specification more often than a right one, and it has only been trained and measured on short
programming problems over integers, booleans and sequences. See [../DISCLAIMERS.md](../DISCLAIMERS.md).

## Licence

Apache License 2.0 ([LICENSE-student](LICENSE-student)); the sources it was built from are credited in
[NOTICE-student](NOTICE-student).
