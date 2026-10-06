# The round-4 rows without the specifications that do not stand on larger inputs: registered before training

Registered 2026-10-05 10:52Z. Nothing below has been trained or scored.

## What was found

`t/LARGER-INPUTS-2026-10-05.md`: the specification check drew inputs no larger than a problem's examples, so a
specification that lists the small cases read as complete, and five held-out problems were being counted on such
specifications. A student that writes a table of the first few answers learned to somewhere. The round-4 rows
(`sft-student-teacher4.jsonl`, 5,479 rows, sha256 `ccd49a66059662f4…`) were read with the larger inputs, each row's
specification against its own problem's solution (`spec_check.larger_inputs`, 200 draws, the rule of
`spec_check.larger_reason`): of the 4,239 rows that carry a specification for a problem the pool holds,
**384 do not stand (9.1%)**, from 61 problems: 280 say too little about larger inputs, 67 have a `requires` that
closes them off, 37 are false there. By kind of row: debugging 158, proof beside Python 77, graded answers 76,
specification rows 73. (98 more rows now disagree with their solution on the ordinary draws under this run's
seeds; they are a separate matter and stay in.)

## What is run

- **Rows:** the round-4 rows less those 384: 5,095 rows, sha256 `e1e13bd1923bad7b…`. Nothing is added. (The count
  happens to equal dawnr v5's; the sets are different.)
- **Recipe, tree and instrument:** exactly the round-4 seeds' (`PREDICT-2026-10-05-teacher4-student.md`): Qwen3.5-4B,
  `t/student_sft.py`, seed 1, tree `5a5acc1f`; the clean 182 by the scoreboard's route, the 73 specification
  questions, the wider panel. Scored with the larger inputs (`t/score_levels.py --larger`), the reading of record
  since today; the reading without them is reported beside it.
- **One seed**, on a lab card that also holds small measurement servers. A seed is a story, not yet a number; the
  three round-4 seeds on the unfiltered rows give the spread it is read against.

## Predictions

- **L1, it costs nothing that counts.** On the clean 182 with larger inputs it proves at least 16 at one prover and
  10 by all seven (the round-4 seed 1 reads 17 and 11).
- **L2, the habit goes with the rows.** Of its answers whose specification agrees with the reference on ordinary
  draws (the clean-182 set and the wider set together), the share that do not stand on larger inputs is at most
  half the share of the three round-4 seeds pooled.
- **L3.** Given the specification, on the new 40 by all seven it is within 2 of the round-4 seed 1.

## What each outcome changes

- L1 and L2 hold: every later row build applies the larger-input rule at admission, and the next release
  candidate is three seeds on rows built that way.
- L1 fails (15 or fewer, or 9 or fewer): the dropped rows carried something the count needs, most likely the
  debugging rows' proofs; the next build keeps the debugging rows and drops the other three kinds, and is measured.
- L2 fails: the habit is not coming from these rows; the specification stage of the route, not the data, is looked
  at next.

## A note on the tree (2026-10-05 10:55Z, before any result)

This registration names tree `5a5acc1f`. The lab's checkout is fast-forwarded by the grading scripts, and it was at
`3ce62a51` when this run started (its own log says so). Between the two commits the files the recipe runs
(`t/student_sft.py`, `t/spec_first.py`, `t/score_spec_given.py` and what they import) differ by two
well-formedness rules for set literals (`7838215f`) and one added function nothing in the recipe calls. The same
holds for the later stages of the three round-4 seeds, which were generated after the checkout had moved.
