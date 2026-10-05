# Student v3: the release recipe with more permissively licensed specifications. Registered 2026-10-02 13:21Z, before it trains

> **Correction, 2026-10-05:** counts on the clean 200 in this file include 18 problems that an audit of the training rows
> later took out of the panel. Every published row is restated on the clean 182 in
> [DECONTAMINATION-2026-10-05.md](DECONTAMINATION-2026-10-05.md).
> A second correction that day holds each specification to inputs larger than the examples as well; the rows are
> restated again in [LARGER-INPUTS-2026-10-05.md](LARGER-INPUTS-2026-10-05.md).

## Why

v2, the v5 recipe without the 44 GPL-derived specification-given rows, proves 24 of the 33 held-out given
specifications by all seven provers at Q8_0, two fewer than the published v1 (26)
(`t/PREDICT-2026-10-02-release-student.md`). The rows it lost were of exactly the kind those questions test.

The specification-given rows come from the r12 corpus, which admits a lifted program only when all seven provers
read it clean (the program verifies and its mutated twin is refuted; `--min-kernels 7`). The project's own rule
for data is graded trust, "clean in seven or six with the gap named" (AMBITION.md, "t grows as dawnr does").
Rebuilt at `--min-kernels 6` with the same inputs, the same heads and the same split (the rebuild at seven
reproduces the published corpus and the published row files byte for byte, sha256 12491a7f... and 02cd247d...),
the corpus admits 634 documents instead of 531, and the specification-given builder (`t/student_rows.py`,
`--split-seed 1338`) gives 566 training rows instead of 476. **All 33 held-out questions stay held out and all
476 earlier rows are kept.** Of the 90 new rows, 7 come from dafny-synthesis (GPL-3.0) and are left out; the other
83 are permissive (61 vericoding, MIT; the rest DafnyBench, ACSL by Example and others under the same policy as
v1's rows). Every one is clean in six provers with the seventh recorded in the trust file.

## The build

`sft-student-v5-0750-nogpl-k6.jsonl` (sha256 b2fbb089...): the 3,944 rows of v2 with the 83 added after the
earlier specification-given rows, 4,027 in all, 515 specification-given (v5 had 476, v2 432). The recipe is v2's
exactly (`t/student_sft.py`, Qwen3.5-4B, rank 64, five epochs, rows up to 2,845 tokens, seed 1), merged, exported
to Q8_0 and measured the same way: the 33 given specifications and one greedy answer to each of the 100 dev
problems through the gate, at Q8_0 through llama-server. No training row answers a held-out question (checked by
normalised program text on the built file).

118. Given the specification, it proves at least 27 of the 33 by all seven (v1 26, v2 24).
119. One greedy dev answer proves at least 3 dev problems on complete specifications (v1 4, v2 3).

If both hold it is released as `student-v3` and the installer moves to it; otherwise `student-v1` stays.
It trains on the desktop card when the card is back, before the specification round.

## Amendment, 2026-10-03 18:26Z, before it trains: where

The desktop card fell off the bus an eighth time (2026-10-03 04:26Z) and the lab's GPUs 1 to 3 are free, with the
operator's leave to use the lab freely. v3 trains on the lab's GPU 1 (an RTX 6000 Ada) with the same command, rows
(sha256 b2fbb089...) and base weights (the same Hugging Face snapshot, copied), merges and exports there, and is
measured on the desktop's CPU exactly as v1 and v2 were. The lab's PyTorch is 2.13 (the desktop's 2.11); the other
libraries are the same versions (transformers 5.17, peft 0.21, bitsandbytes 0.50.2). Predictions 118 and 119 stand.

## Outcome, 2026-10-04 00:11Z (`~/scratch/release-v3/log`)

At Q8_0 through llama-server on the desktop's CPU, the way `dawnr` runs it:

118. **Falsified:** 25 of the 33 given specifications proved by all seven (27 by at least one), not 27. v1 26,
     v2 24.
119. **Holds:** one greedy dev answer proves 4 dev problems on complete specifications (2 of them by all seven).

118 failed, so v3 is not released and `student-v1` stays what `install.sh` downloads. The 33-question gate and
the clean 200 disagree about v3's rows: on the gate it is one behind v1, on the clean 200 its first training seed
is proved by all seven on 10 problems, more than any v5 seed (7, 8, 7;
`t/PREDICT-2026-10-03-shipped-recipe.md`). One seed on 33 questions moves by a problem or two, so neither
reading is taken as the rows' effect until the shipped recipe's three seeds are in.
