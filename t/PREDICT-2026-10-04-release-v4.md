# Release v4: the gate, registered before the candidate is measured

`student-v1` is what `install.sh` downloads; v3 missed its gate (25 of 33 by all seven against 27,
`t/PREDICT-2026-10-02-release-v3.md`) although its rows beat Phi-4-mini on the clean 200 with every seed. The candidate
here is the first seed of `t/PREDICT-2026-10-04-teacher2-student.md` (v3's rows plus every document the gates admitted
since, 4,625 rows, none answering one of the 33 held-out questions by the strict check of `t/student_rows.py`
`leaks_heldout`), chosen by that rule before any of its seeds is measured.

## The measurement

Exactly v3's: the merged weights exported to GGUF Q8_0 (`convert_hf_to_gguf.py --no-mtp`, `llama-quantize`), split
under GitHub's 2 GiB a file with their SHA-256 manifest, and measured at Q8_0 through llama-server on the desktop's
CPU the way `dawnr` runs it: the 33 given specifications (`t/score_spec_given.py`, graded on the lab in all seven
kernels) and one greedy answer to each of the 100 dev problems through the gate.

## The gate

- **R1.** Given the specification, at least 26 of the 33 are proved by all seven (v1's 26).
- **R2.** One greedy dev answer proves at least 3 dev problems on complete specifications (v1 4, v3 4).
- **R3.** The candidate's clean-200 measurement meets its round's Q1 (at least 17 at one kernel and 9 by all seven).

If all three hold it is published as `student-v4` under Apache-2.0, its model card and NOTICE crediting the data
sources as v1's do and naming the two teacher models whose admitted outputs it trained on (Qwen3-235B-A22B-Instruct-2507,
Apache-2.0; DeepSeek-V3.2, MIT), and `install.sh` moves to it. Otherwise `student-v1` stays.

## Amendment, 2026-10-04 07:52Z, before any candidate is trained or measured: the candidate's rows leave out GPL-derived documents

52 of the 442 lifted specification prompts trace to dafny-synthesis (their vericoding `source_id` names it), GPL-3.0 at
the source; v1 and v3 leave every such row out (`internal/RELEASE-PROVENANCE-2026-10-01.md`). The teacher2 round's rows
hold 46 specification-given rows built from them, so its seeds are measurements, not release candidates. **The candidate
is instead one model trained with the teacher2 recipe and seed 1 on those rows without the 46**
(`sft-student-teacher2-nogpl.jsonl`, 4,579 rows, sha256 1adba7e4a9df95d3...), on the lab's GPU 1. R3 is read on this
candidate's own clean-200 measurement, taken by the shipped seeds' route. R1 and R2 are unchanged.

## Outcome, 2026-10-04 14:43Z (`~/scratch/release-v4/log`, `q33-levels.json`, `levels-v4cand-seed1.md`; recorded 14:43Z)

The candidate (seed 1 on the GPL-free teacher2 rows, 1,425 steps, final loss 0.0253), exported to Q8_0 (4,482,402,752
bytes, sha256 c937a44c0b1c81b7..., three shards) and measured on this desktop's CPU through llama-server:

| | the candidate | v1 | v3 |
|---|---:|---:|---:|
| the 33 given specifications, proved by all seven | **22** | 26 | 25 |
| the same, by at least one (a kernel refutes 8) | 25 | | |
| one greedy dev answer, complete specifications, at least one / all seven | **7** / 3 | 4 | 4 |
| the clean 200 (its own route), at least one / all seven | **23** / **13** | | |

- **R1 falsified:** 22 of 33 by all seven, not at least 26.
- **R2 holds:** 7 dev problems on complete specifications, against 3.
- **R3 holds:** 23 and 13, against 17 and 9 (the same as teacher2's seed 1 with the 46 GPL-derived rows: leaving
  them out cost nothing there).

**Not published; `student-v1` stays what `install.sh` downloads.** The rows that lift the student from a problem
statement (the clean 200 from 17 to 23 at one kernel and from 10 to 13 by all seven for seed 1, dev from 4 to 7) cost
it proofs when the specification is given (26 to 22 by all seven). A release candidate has to hold both; the next one
needs rows that keep the given-specification skill while the teacher documents grow.

**Which questions (v3's seed 1 against the candidate, both at Q8_0 by this pipeline):** of v3's 25 proved by all seven
the candidate loses 4 and gains 1. Two of the four are wrong programs, refuted on both sides by every kernel
(`vericoding_da0075`, `vericoding_dd0077`); two are a kernel's reach (framac abstains on `da0580`, rocq leaves
`dv0138`'s real side unproved). One seed of each, so whether the rows cost given-specification proofs at all is not yet
told from the seeds' own spread on this set, which has not been measured.
