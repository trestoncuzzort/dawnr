# `dawnr verify` on the wider 111 with one record per function: registered before the run

Registered 2026-11-26, before the run below. The two panel runs of 2026-10-05
([V1 and V4](PREDICT-2026-10-05-verify-python.md)) kept their totals and nothing else: 9 of 111 proved, and of the
102 refused, 88 for want of a specification that held at the function's own answers and pinned them down, 14 for
want of a proved body. Which function stopped where was never recorded, so the share of refusals that are the
model's specification, the proof, or `t` itself could not be counted.

## What is run

- **The panel:** the wider 111 (`heldout_audit.wider_clean()`), rebuilt from the hash-verified MBPP files; its ids
  are the 111 the investigation of 2026-11-26 listed. Each problem's reference solution is the Python file, its
  words the docstring, its tests the examples, as V1 and V4 had them.
- **The driver:** `t/verify_panel.py`, which asks each function exactly as `dawnr verify FILE.py --test ...` does
  (whole answers first, then the specification route; `--whole 5 --specs 3 --answers 3`, the command's defaults)
  and writes one record per function and `run.json` to the run folder.
- **The writer:** not the published student. The model this machine had serving when the run started is the base
  model on port 8712 (a 27B Qwen at Q4_K_S, named in `run.json`); the student's port was not serving, and no model
  server was started or stopped for this run. The base has never seen `t`, so every question carries the
  language's reference and an answer may take 3072 tokens, as `bin/dawnr` asks a writer that is not the student
  (`DAWNR_WRITER_URL`). The results therefore do not compare with V1 or V4 as a measure of the student.
- **The provers:** Dafny alone (`--kernels dafny`, `T_MIN_KERNELS=1`), the condition of a fresh install, as in V1
  and V4.

## Predictions

- **R1, the records are complete.** 111 records, one per function; in every record, one stage entry per refusal
  line, in order. At most 3 records carry an error (a prover or sandbox failure). More than 3 errors, or any
  function without a record when the run ends, falsifies R1.
- **R2, the specification is still where most refusals stop.** Of the functions refused without an error, at
  least 60% stop at or before the specification check (`stopped at` one of `entry`, `reply`, `parse`, `well
  formed`, `examples`, `other`, `specification check`): no specification or answer the model wrote both held at the
  function's own answers and got further. On 2026-10-05 it was 88 of 102 (86%). Under 60% falsifies R2.
- **R3, a larger writer that has never seen `t` proves at least as many.** At least 9 functions are verified (V4's
  count with the published student) and at most 40. Fewer than 9 or more than 40 falsifies R3; either way the
  records say where the rest stopped.

## What each outcome changes

- R1 holds: the records are the unit later runs are compared on, and the next panel run (the student, when it is
  serving) is read function by function against this one.
- R1 fails: the driver is fixed before any number from it is used.
- R2 holds: the next work is the specification the model writes, not the provers; the records name which
  functions to read first (those whose specifications were false at an example).
- R2 fails: the proof or the comparison with the function is where `verify` loses most, and the records say which.
- R3 is read beside R2 and is not a claim about the student.

## Outcome, 2026-11-26 (run 17:42Z to 19:58Z, code at 0919a75a)

The run's folder is `release/evidence/verify-run-2026-11-26/`: `run.json` and one record per function. The writer was
the base model this machine was serving (`run.json` names it), with the reference and 3072 tokens; Dafny alone.

- **R1 holds.** 111 records for the 111 ids, no error, and in every record the stage entries are the refusal lines,
  one for one and in order.
- **R2 holds.** Of the 90 functions refused, 65 (72%) stopped at or before the specification check: examples 24,
  specification check 39, parse 1, well formed 1. The other 25 got further: 8 stopped at the comparison with the
  function and 17 at the prover. On 2026-10-05, with the student, it was 88 of 102 (86%).
- **R3 holds.** 21 of the 111 were verified, 14 by asking for whole answers and 7 by the specification route: 49, 70,
  81, 106, 154, 206, 257, 343, 353, 363, 380, 470, 551, 660, 710, 788, 805, 808, 878, 893, 942. Of the three the
  record of 2026-10-05 names as proved, 106 and 206 are again and 828 is not. 889, whose reference sorts where its
  words say reverse, is refused with the same sentence as on 2026-10-05.

Across the 111, the 832 refusal lines were at: parse 271, specification check 185, examples 147, prover 88, well
formed 84, same as the function 57. Of the 981 answers, specifications and bodies asked for (555, 291 and 135),
271 (28%) did not parse, with the language's reference in front of every question.

What it changes, as registered: the records are the unit the next panel run is read against, and the next work is
the specification the model writes. The specification route earned its place again (7 of the 21). The student was
not serving, so how it does on this panel with the records kept is still open.
