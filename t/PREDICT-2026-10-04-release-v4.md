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
