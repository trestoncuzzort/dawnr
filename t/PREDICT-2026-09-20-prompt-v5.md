# Does a grammar-guidance block move the parse wall? (WS-21 move 2)

**Written 2026-09-20, before the arm ran.** `qwen235-heldout-p5` did not exist.

## The arms

Same 232 held-out problems, same model (Qwen3-235B-A22B-Instruct-2507-AWQ), pool
v3, temperature 0, seed 1, 8192 tokens. **Only the prompt differs.**

| arm | prompt | measured |
|---|---|---|
| control `qwen235-heldout` | v3 | 140 parse fail, 25 check_wf fail, **67 well formed**, 53 tests pass, 11 clean, 8 spec-checked |
| `qwen235-heldout-p5` | v5 | this run |

Every `done_reason` in the control is `stop`, so none of the 140 is truncation.

## Predictions

1. **Parse failures fall below 120, from 140.** Falsified at 120 or more. The block
   names the three refused shapes that cost the most replies. If it moves nothing,
   the wall is not ignorance of the notation and WS-21 move 2 is closed as measured
   rather than implemented.
2. **Well-formed answers land between 75 and 130, from 67.** Falsified outside.
   PostcondBench's block moved Corr@1 0.629 to 0.814, a 29% relative gain; the same
   relative gain here is 86. Above 130 would beat what the constrained decoder did
   for the 30B, which a prompt should not.
3. **Clean answers do not fall below 11.** Falsified at 10 or fewer. A longer
   system prompt could crowd out the problem; this is the check that it does not.
4. **Conversion does not improve.** The control converts 11 of 53, 21%. Falsified if
   the percentage rises. Syntax guidance acts on notation, and conversion is whether
   the specification says what the problem asked, so there is no mechanism.
5. **Tests passing rises by at least 5, from 53.** Falsified at 57 or fewer. This is
   the risky one: more well-formed answers should carry more test-passing answers
   proportionally, and if well-formedness rises while tests do not, the block bought
   notation without meaning, which is exactly what locallm already demonstrates and
   would make the gain worth much less than it looks.

## What would make this a default

Predictions 1, 2 and 5 together. Then v5 becomes the prompt for every later arm and
the control is re-measured under it, per 12.7's standing rule that no round is
compared across prompts until the control moves too.
