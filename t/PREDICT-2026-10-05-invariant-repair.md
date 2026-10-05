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
