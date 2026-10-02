# dawnr-student-v1 (draft, not published)

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
  on all linear layers; learning rate 2e-4; five epochs; rows up to 2,845 tokens; seed 1 (`t/student_sft.py`).
  Merged into the base, exported with llama.cpp's `convert_hf_to_gguf.py --no-mtp`, quantised to Q8_0, the
  format measured to keep every proof of full precision ([small hardware](../t/PREDICT-2026-10-01-small-hardware.md)).
- **Training rows (3,944):** only answers the provers accepted, and rows built from them.

| rows | kind |
|---:|---|
| 693 | proved answers to English questions |
| 693 | proofs written from a problem's tested Python |
| 601 | specifications written from a problem's tested Python |
| 323 | Python solutions that pass the problem's tests |
| 432 | a body and proof for a given specification |
| 1,202 | repairs: a failed answer, the checker's message, the fixed answer |

- **Where the problems come from:** MBPP (CC-BY-4.0), HumanEval (MIT) and APPS (MIT) for the questions; the
  vericoding benchmark (MIT), DafnyBench (Apache-2.0; its programs come from many GitHub repositories),
  HumanEval-Dafny (Apache-2.0) and Clover (MIT) for the given specifications. The 44 rows built from
  dafny-synthesis programs, GPL-3.0 at their source, are left out
  ([provenance](../internal/RELEASE-PROVENANCE-2026-10-01.md)).
- **Kept out of training:** the 200 held-out problems, the 100 development problems and the 33 held-out
  specification questions used to measure it; every row set is checked for them before training.

## Measured

Before release it is measured at Q8_0 through llama-server, as `dawnr` runs it: the 33 held-out specification
questions and one answer to each of the 100 development problems through the gate. Registered in
[t/PREDICT-2026-10-02-release-student.md](../t/PREDICT-2026-10-02-release-student.md); **not yet run.** The
same recipe with the 44 rows included is proved on 15 to 19 of the 200 held-out problems across three training
seeds ([outcomes](../t/PREDICT-2026-10-01-replication.md)).

## Limits

It writes a wrong specification more often than a right one, and it has only been trained and measured on short
programming problems over integers, booleans and sequences. See [../DISCLAIMERS.md](../DISCLAIMERS.md).

## Licence

To be set by the operator before publication. The base model is Apache-2.0; MBPP's licence asks for attribution.
