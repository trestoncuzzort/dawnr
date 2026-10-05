# Release v5: the candidate fixed by a rule and the gate, registered before its given specifications are measured

> **Correction, 2026-10-05:** counts on the clean 200 in this file include 18 problems that an audit of the training rows
> later took out of the panel. Every published row is restated on the clean 182 in
> [DECONTAMINATION-2026-10-05.md](DECONTAMINATION-2026-10-05.md).
> A second correction that day holds each specification to inputs larger than the examples as well; the rows are
> restated again in [LARGER-INPUTS-2026-10-05.md](LARGER-INPUTS-2026-10-05.md).

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

## Outcome, 2026-10-05 03:47Z (`~/scratch/release-v5/log`, `q33-levels.json`)

The candidate (teacher3's seed 1), exported to Q8_0 (4,482,402,752 bytes, sha256 15b28552a86ca3ca..., three shards) and
measured on this desktop's CPU through llama-server:

| | the candidate | v1 | v4's candidate |
|---|---:|---:|---:|
| the 33 given specifications, proved by all seven | **27** | 26 | 22 |
| the same, by at least one (a kernel refutes 4) | 28 | | 25 |
| one greedy dev answer, complete specifications, at least one / all seven | **4** / 2 | 4 | 7 / 3 |
| the clean 200 (its own route), at least one / all seven | **26** / **16** | | 23 / 13 |

- **R1 holds:** 27 of 33 by all seven, against at least 26.
- **R2 holds:** 4 dev problems on complete specifications, against at least 3.
- **R3 holds:** 26 and 16, against 17 and 9.

**Published as `student-v5`; `install.sh` moves to it** (the gate's commit cbc724eb). v4's candidate, one seed of the
round before on 516 fewer rows, read 22 on the same 33. With one seed of each, how much of that difference is the
seed and how much the rows is not measured; the candidate was fixed by a rule before this set was measured, so the
gate did not choose it.

## Installed from the release, 2026-10-05 04:28Z (`~/scratch/release-v5/install-from-release-2.log`, `ask-from-release.out`)

`install.sh` run with an empty home and a bare PATH downloaded the three shards from the `student-v5` release, checked
them against the published checksums and set up Dafny (done 04:25Z). The first question through `dawnr ask` from that
install (the larger of two numbers, three tests) was **shown**: proved by Dafny, the only prover a fresh install has,
none refuting; its specification passed the 3 tests, held at an independently written Python solution's answer on 100
drawn inputs and rejected every wrong output tried. The gate's first install run had failed at 04:23Z on a syntax
error that was this session's own doing (the working tree's `install.sh` was being edited while that run executed
it); nothing published was wrong, and the second run is the record.

## Correction, 2026-10-05 05:05Z: the panels this gate read

Forty minutes after the release, an audit of the training rows took 18 problems out of the clean 200 and 5 out of
the 100 dev problems ([DECONTAMINATION-2026-10-05.md](DECONTAMINATION-2026-10-05.md)). The gate is read again here on
the corrected panels, from the same saved answers and verdicts; nothing was generated or graded again.

| | as decided | on the corrected panels |
|---|---:|---:|
| R1: the 33 given specifications, by all seven | 27 | 27 |
| R2: one greedy dev answer, complete specifications, at least one / all seven | 4 / 2 of 100 | **3** / 2 of 95 |
| R3: the held-out panel, at least one / all seven | 26 / 16 of 200 | **18** / **12** of 182 |

- **R1 holds as counted** (27 against 26) and says less than it did: 19 of the 33 questions have a program of the
  same behaviour in the training rows under another name; the candidate proves 17 of those and 10 of the other 14.
- **R2 holds, exactly** (3 against 3): dev 727, one of the four, is a twin of `mbpp_676__remove_extra_char` in the
  rows and leaves the panel.
- **R3 holds** (18 and 12 against 17 and 9). Eight of the 26 were on problems that left the panel; the candidate's
  own untrained base had been credited with six of the same eight.

The release stays. Two statements of its model card and notice were wrong and are corrected there: 61 of the 5,095
rows descend from MBPP-DFY (GPL-3.0 at the source) under the vericoding benchmark's names, and the held-out problems
were kept out of training by name only. The next release's rows are built through `t/heldout_audit.py --panels
--refuse-gpl`.
