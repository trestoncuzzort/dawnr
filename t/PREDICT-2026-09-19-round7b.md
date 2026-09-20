# Round 7b predictions: three arms, each isolating one of round 7's excuses

Round 7 scored 1 clean of 232 with 55 of 136 well-formed answers disqualified
on the signature. Three things could be blamed for that and each was named in
the round 7 findings before this was written. This round tests all three,
cheaply, and registers what would falsify each. Written before any arm has
generated an answer.

## The arms

| arm | what changes | what it isolates |
|---|---|---|
| `locallm-r7b-step150` | the exported checkpoint is step 150, not 300 | my choice to export the end of the schedule over the better validation loss (0.5738 against 0.5927) |
| `locallm-r7b-headed` | every training document carries a `Signature:` line derived from its own program, 222 added to the 58 that had heads | a corpus where 79% of documents taught "write a program from nothing" |
| `locallm-r7b-greedy` | round 7's own checkpoint, decoded greedily instead of temperature 0.5, top-k 20 | sampling noise derailing the header |

Everything else is held: same initialization, same 4000-step GPT core, same
232 held-out problems, same extract/tests/seven-kernel path, same scorer, and
the same fresh Phi baseline already graded today beside round 7.

## Predictions

1. **`headed` cuts signature failures below 20% of its well-formed answers**,
   from round 7's 55 of 136 (40%). Falsified at 20% or above. This is the
   mechanism claim and the reason the arm exists.
2. **No arm reaches 3 clean.** None of these three changes is about solving the
   problem, and the model that writes 91 proven-but-wrong specifications is not
   fixed by being told which types to use. Falsified by any arm at 3 or more,
   which would also be the first locallm row to match Phi.
3. **`step150` lands within one clean answer of round 7's 1**, i.e. the export
   choice was not the explanation. Falsified if it reaches 3 or more, or if its
   signature failure rate differs from round 7's by more than 10 points.
4. **`greedy` writes more well-formed answers than round 7's 136**, because
   removing sampling noise should cost fewer malformed headers. Falsified at
   136 or below.
5. **Tests passing stays in single digits for every arm.** Round 7 passed 1 and
   the 3.2M rows passed 2. Falsified by any arm at 10 or more.

## What I expect

Prediction 1 to hold and prediction 2 to hold with it: the signature failures
are a conditioning defect with an obvious cause, and fixing them should convert
some of those 55 answers into *graded* answers without making them *right*.
The interesting number is not clean at all. It is how many of the rescued
answers land in "proven but wrong", because that is the count that says the
model writes confident specifications of the wrong function.
