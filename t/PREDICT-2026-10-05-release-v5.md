# Release v5: the candidate fixed by a rule and the gate, registered before its given specifications are measured

Registered 2026-10-05 01:41Z. `student-v1` is what `install.sh` downloads; v2, v3 and v4 each missed the gate's R1 (the 33
held-out given specifications by all seven; v4 22 against 26, `t/PREDICT-2026-10-04-release-v4.md`), each measured on
one seed. The teacher3 round's rows (5,095: v3's 4,027 and 1,068 from documents the provers admitted, some written by
Qwen3-235B-A22B-Instruct-2507 and DeepSeek-V3.2 on Amazon Bedrock) carry no GPL-derived row and no row the strict
held-out check flags (`t/PREDICT-2026-10-04-teacher3-student.md`), so its seeds are release candidates as trained.

## The candidate, by a rule fixed now

The teacher3 seed with the most clean-200 problems proved by all seven: **seed 1** (26 at one kernel, 16 by all
seven). No seed of this round has been measured on the 33 given specifications or on dev.

## The measurement and the gate (v4's exactly)

Merged, exported to GGUF Q8_0 (`convert_hf_to_gguf.py --no-mtp`, `llama-quantize`), split under GitHub's 2 GiB a
file with its SHA-256 manifest, and measured at Q8_0 through llama-server on this desktop's CPU the way `dawnr` runs
it: the 33 given specifications (`t/score_spec_given.py`, graded on the lab in all seven kernels) and one greedy
answer to each of the 100 dev problems through the gate.

- **R1.** Given the specification, at least 26 of the 33 are proved by all seven (v1's 26).
- **R2.** One greedy dev answer proves at least 3 dev problems on complete specifications.
- **R3.** The candidate's clean-200 measurement is at least 17 at one kernel and 9 by all seven (it reads 26 and 16).

If all three hold it is published as `student-v5` under Apache-2.0, its model card and NOTICE crediting the data
sources and naming the two teacher models (Apache-2.0 and MIT), and `install.sh` moves to it. Otherwise
`student-v1` stays. Measuring any other seed on the 33 waits until this gate has decided, so the gate set never
chooses its own candidate.
