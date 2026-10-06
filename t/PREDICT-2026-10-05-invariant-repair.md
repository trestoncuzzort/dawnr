# Proofs that fail on their invariants, repaired by rule: registered before it is run on any graded answer

Registered 2026-10-05 12:36Z. `t/invariant_repair.py` is written and tested (with Dafny: the one program it was
found on, a planted surplus invariant, and a wrong program that must stay unproved). It has been run on no answer
set. Research receipt e85d39d1a968; shift 9 of `internal/RESEARCH-2026-10-05-what-to-steal.md`.

## What was seen

A 35B model that has never been trained on `t`, writing through `dawnr verify` from the language reference, wrote
a correct `largest` whose loop listed the invariant that bounds the index last. `t` checks invariants in order
(`t/SPEC.md`), so Dafny and Verus read it unproved ("index out of range" inside the earlier invariants); only
Frama-C proved it. With that one invariant moved first, both verify it. DafnyPro (arXiv:2601.05385) reports the
neighbouring fault, an invariant that is not needed and not inductive, and prunes it; the idea is Houdini's.

## What is measured

Every answer in the graded sets behind the scoreboard's 24 rows (clean 182) that passes its problem's tests, has a
loop, and that no prover verified. On each, `invariant_repair.repair` with Dafny alone: reorder when an invariant
is reported undefined, then drop invariants reported as not proved on entry or not maintained, to a fixed point,
at most four rounds. A repair counts when Dafny verifies the result and nothing but invariants differs from the
answer as written. A scan of the same sets by a syntactic test, made before this registration, found 46 such
answers with a plain invariant listed after one that indexes (23 of them the prompted 9B's); that scan ran no
prover.

- **R1, the order fault is real beyond one program.** Reordering alone turns at least 5 of these answers into
  programs Dafny verifies.
- **R2, surplus invariants are there to prune.** Dropping invariants repairs at least 2% of the prompted 27B's
  unproved loop answers.
- **R3, the trained models rarely need it.** For each fine-tuned answer set, at most 3 answers are repaired:
  their rows were written in the checkable order with few spare invariants.
- **R4, a repair is not a loophole.** Regraded by all seven provers with their sabotaged twins, no repaired answer
  that Dafny verified is refuted by another prover; and held to the same specification check as any answer, the
  share of repaired answers that count is within 15 points of the share of as-written proved answers that count,
  for the model with the most repairs.

## What each outcome changes

- R1 or R2 holds, and R4 holds: the repair runs in the product's gate before an answer is refused for want of a
  proof (the repaired text is what is proved, shown and certified), and the scoreboard gains an "after repair"
  column beside the as-written one, which stays the count of record for every row registered before today.
- R4 fails: the repair is not used anywhere, and the refuted or uncounted repairs are read by hand.
- R1 and R2 both fail: it stays a tool (`t/invariant_repair.py --file`) for a person or a writer model that hits
  the order fault, and is not put in the gate.

## Not measured here

Invariants that are missing, which is the larger reason a loop goes unproved and needs a writer, not a pruner;
pooling invariants across several answers to one problem (Houdini with a larger candidate set), which is the
next step if R2 holds.

## Outcome, 2026-10-05 13:06Z

Run on the desktop from commit 81de8a65, Dafny 4.11 alone for R1 to R3 (`~/scratch/larger/repair_run.py`), then
the product gate's own call, all seven provers with their sabotaged twins, on every repaired answer for R4.

**755 answers** in the 24 rows' graded sets pass their problem's tests, have a loop and were verified by no
prover: 106 from the 17 fine-tuned sets, 649 from the prompted ones (429 of them the 27B's, 115 the 9B's).

| what Dafny reported | answers | repaired |
|---|---:|---:|
| an invariant undefined, and the order could be changed | 33 | 2 by the reordering alone |
| an invariant not proved on entry or not maintained (dropped, to a fixed point) | 494 | 10 |
| something that is not an invariant (the postcondition, a call's precondition, the measure) | 252 | none tried |
| nothing: it verifies as written this time | 1 | |

(The first two rows overlap: 25 answers had both done to them.) **12 answers repaired**, 1.6% of the 755.

- **R1 fails.** Reordering alone repaired 2 answers (the bar was 5): `left_rotate` in a fine-tuned set and
  `chkList` in the prompted 9B's. The order fault is there (33 answers, 19 of them the 9B's, which never saw a
  `t` program), but it is almost never the only thing wrong with the proof.
- **R2 fails, by one answer.** Pruning repaired 8 of the 27B's 429 (1.9%; the bar was 2%), on four problems.
- **R3 holds.** No fine-tuned set had more than one answer repaired; 3 of their 106 in all.
- **R4 holds in its first half and fails in its second.** Regraded by all seven, no repaired answer is refuted
  by any prover, and 10 of the 12 are verified by four or more that also refute the twin. But of the 27B's 8
  repaired answers only 2 would count once held to the specification check (25%), against 186 of its 281
  as-written proved answers (66%): a gap of 41 points where 15 were allowed.

Read by hand, as registered for a failed R4. The repairs are real: a rotation with two loops, a comparison of every
list against the first, two closed-form sums reached by a loop. What does not count is the specification that was
proved, and the check that says so is the one every answer already passes through: six of the 27B's eight are the
`increasing_trend` and `decreasing_trend` pair, proved against "each element is less than the next" where the
reference accepts equal neighbours, and the two fine-tuned repairs prove only that the result is one of two
fixed strings. A proof that needed pruning to go through was, in this sample, more often the proof of a wrong or
empty statement than a proof as written is. The sample is 8 answers on 4 problems.

**What it changes.** By the registered rule the repair is used nowhere: it is not in the product's gate, and the
scoreboard gets no "after repair" column. `t/invariant_repair.py` stays as the instrument of this measurement.
What the count says about where unproved loops are lost is the useful part: in 494 of 755 Dafny pointed at an
invariant the model wrote, dropping it left a proof that failed somewhere else in 484, and in 252 more the
invariants were not the complaint. The loop goes unproved because the invariant that is needed is missing or
wrong, which a rule cannot supply; that is work for a writer with the prover's message in front of it
(`t/proof_repair.py`), not for a pruner. Pooling invariants across answers, the next step named above, was
conditional on R2 and is not taken.
