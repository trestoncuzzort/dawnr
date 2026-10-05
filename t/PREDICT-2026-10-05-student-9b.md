# A 9B student on the round-4 rows: registered before it is trained

Registered 2026-10-05 09:41Z. Nothing below has been run: the 9B's weights are not on the lab and no fine-tune of
any model larger than the 4B has been tried in this repository.

## Why

Everything built on 2026-10-05 (`internal/PLAN-2026-10-05-usable-for-everyone.md`) stands behind one number: how
often the model writes something the gate can admit. The published 4B is shown for about one held-out problem in
ten. Size is the lever with a measurement behind it. On the clean 182, with 17 answers a problem, prompted
Qwen3.5 reads 9, 15 and 33 proved by at least one prover at 4B, 9B and 27B (6, 6 and 23 by all seven;
`PREDICT-2026-10-04-size-curve.md`, corrected), and fine-tuning on what the gate admitted took the 4B from 9 to
between 14 and 18. The 9B has only been prompted.

## What is run

- **Base:** `Qwen/Qwen3.5-9B` (Apache-2.0), the next size of the family the 4B student comes from.
- **Rows:** the round-4 rows exactly, `sft-student-teacher4.jsonl` (5,479 rows, sha256 `ccd49a66059662f4…`), built
  through `t/heldout_audit.py --panels --refuse-gpl` and `t/spec_panel.py` (`PREDICT-2026-10-05-teacher4-student.md`).
- **Recipe:** `t/student_sft.py` as the 4B seeds ran it (QLoRA rank 64, five epochs, rows up to 2,845 tokens),
  seed 1, from the same tree the three 4B seeds run from (`bf23d4ee`), so the only thing that differs is the base.
  A four-step probe runs first to read the step time and the card's memory; it changes nothing.
- **Instrument:** the scoreboard's, as for the 4B seeds: `t/spec_first.py --python 3` on the clean 182, graded by
  all seven provers, levels with the reference-checked specification at completeness 0.6; then the 73
  specification questions and the wider panel (generated on 114, scored on the 111).
- **One seed.** A card for about nine hours. One seed is a story and not yet a number (AMBITION.md, section 1), and
  is reported as one; seeds 2 and 3 are run only if N1 and N3 hold.

## Predictions

- **N1.** On the clean 182 it is proved on at least 22 problems by at least one prover.
- **N2.** By all seven provers, on at least 12.
- **N3.** It is above the 4B's seed 1 on the same rows at both levels.
- **N4.** On the wider 111, at least one and a half times the three 4B seeds' mean at one prover.
- **N5.** Given the specification, it proves at least as many of the new 40 by all seven as the 4B's seed 1 does.

## What each outcome changes

- N1 and N3 hold: seeds 2 and 3 are trained; the 9B is exported at 4 bits and measured through `dawnr ask` and
  `dawnr verify` on the wider 111 on a 12 GB card, under its own registration, as the candidate for a second
  model the installer picks where the hardware allows.
- N1 or N3 fails: a 9B costs about twice the 4B's time a token and has not earned it on these rows; the size lever
  is then the prompted 27B for 24 GB cards (`PREDICT-2026-10-05-wider-reader.md`, W5) and the data.
- Whatever it reads, it is not released from this registration.
