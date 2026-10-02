# Student v3: the release recipe with more permissively licensed specifications. Registered 2026-10-02 13:21Z, before it trains

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
