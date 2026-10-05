# What a proof is of: the scoreboard read once more (2026-10-05)

Nothing here changes a count. It says what the counts are counts of.

## What was looked at

A scout of the sweep in `internal/RESEARCH-2026-10-05-what-to-steal.md` brought back CLEVER (Thakur et al.,
arXiv:2505.13938): when a specification can be computed, "models can copy them into implementations and produce
trivial proofs via rewriting", and that benchmark writes every specification so that it cannot be computed. `t`
allows both kinds. The gate tests a specification against a solution (the problem's reference on the scoreboard,
an independently written Python in `dawnr ask`) and then proves the program against the specification. So when a
program is its specification written again, the proof says only that the two writings agree, and what the answer
rests on is the testing of the specification. Nobody here had counted how many proved answers are of that kind.

The published model's 17 counted answers on the clean 182 were read by hand. Eight are restatements:

- five are one expression or one table of cases on both sides (`ensures r == d1 * d2 / 2` over `r := d1 * d2 / 2`;
  a month name compared with seven names; "Even" or "Odd" by a last digit);
- two are a recursion held to a specification function that is the same recursion (Pell and Lucas numbers);
- one is a closed formula stated and assigned (`n * (n + 1) * (2 * n + 1) / 6`).

Nine are an algorithm held to a separate statement: five loops proved to reach a recursive definition or a closed
formula (the sum of the first n odd cubes against its recursive definition; `4 * n * (n + 1) * (2 * n + 1) / 6`
reached by adding `4 * i * i`), and four programs proved against a property that does not give the result (every
element of the result is the difference of two neighbours; every element is a power of the one in its place; no
element occurs more often than the result; the result is at least each of three numbers and is one of them).

## The rule

`t/proof_kind.py` reads the answer's text and runs nothing. A specification is a **formula** when some clause
gives the result, `r == E`, outright or as the conclusion of a case; otherwise it is a **property**. A proved
answer is

- **an algorithm** when its specification is a property, or is a formula that the program reaches another way:
  by a loop (the prover needed an invariant), or by a recursion that is not the specification function's own;
- **a restatement** when its specification is a formula and the program is that formula again: no loop and no
  recursion, or the same recursive calls as the specification function it is held to.

The rule was written from the 17 above, on which it agrees with the hand reading. It was then checked by hand on
41 more answers from other rows (Phi-4-mini's 7, 12 of the prompted 27B's, 22 drawn at random from three training
seeds and the prompted 9B). Two faults were found and fixed before the table below was made: cases written as
nested implications were not recognised, and a clause that only lists the allowed results hid the cases beside
it. One answer of the 41 is a matter of judgement (a specification that says "if the result is Equal then the
ends match" rather than "if the ends match the result is Equal" is counted as a property).

## Every row, on the clean 182, with the larger-input reading

A problem pooled over several answer sets is an algorithm if any set proves one for it.

| answer set | proved by at least one | an algorithm | a restatement | proved by all seven | an algorithm | a restatement |
|---|---:|---:|---:|---:|---:|---:|
| **dawnr v5** (the published model) | 17 | 9 | 8 | 12 | 6 | 6 |
| the same recipe, seed 2 | 17 | 8 | 9 | 10 | 4 | 6 |
| the same recipe, seed 3 | 12 | 6 | 6 | 7 | 3 | 4 |
| release-v4 candidate, seed 1 | 15 | 8 | 7 | 10 | 5 | 5 |
| teacher2, seed 1 | 13 | 3 | 10 | 9 | 2 | 7 |
| teacher2, seed 2 | 16 | 8 | 8 | 10 | 4 | 6 |
| teacher2, seed 3 | 18 | 9 | 9 | 10 | 4 | 6 |
| teacher1, seed 1 | 14 | 8 | 6 | 5 | 1 | 4 |
| teacher1, seed 2 | 9 | 4 | 5 | 5 | 1 | 4 |
| teacher1, seed 3 | 14 | 7 | 7 | 9 | 3 | 6 |
| dawnr on v5's rows, seed 1 | 12 | 6 | 6 | 5 | 1 | 4 |
| dawnr on v5's rows, seed 2 | 12 | 5 | 7 | 5 | 1 | 4 |
| dawnr on v5's rows, seed 3 | 9 | 3 | 6 | 6 | 1 | 5 |
| v3's rows, seed 1 | 11 | 4 | 7 | 7 | 2 | 5 |
| v3's rows, seed 2 | 9 | 3 | 6 | 4 | 1 | 3 |
| v3's rows, seed 3 | 10 | 5 | 5 | 4 | 1 | 3 |
| 2B dawnr on the v4 candidate's rows | 4 | 3 | 1 | 3 | 2 | 1 |
| Qwen3.5-0.8B prompted | 1 | 0 | 1 | 1 | 0 | 1 |
| Qwen3.5-2B prompted | 2 | 1 | 1 | 2 | 1 | 1 |
| Qwen3.5-4B prompted | 9 | 2 | 7 | 6 | 1 | 5 |
| Qwen3.5-9B prompted | 14 | 7 | 7 | 6 | 1 | 5 |
| Qwen3.5-27B prompted | 32 | 17 | 15 | 22 | 7 | 15 |
| Phi-4-mini under the grammar | 7 | 0 | 7 | 5 | 0 | 5 |
| Phi-4-mini prompted | 2 | 0 | 2 | 2 | 0 | 2 |

## What it says

- **The published model proves 9 algorithms and 8 restatements** (6 and 6 by all seven).
- **Phi-4-mini proves no algorithm at all**, prompted or with its output held to the grammar: its 7 problems are
  seven formulas stated and assigned. The untrained 4B proves 2 algorithms with 17 tries a problem.
- So what training on proved answers adds on this panel is mostly algorithms: 9 against the untrained model's 2,
  where the plain counts read 17 against 9. That is a sharper statement of the gain than the one published, and
  a smaller statement of what "17 proved" means.
- The prompted 27B proves 17 algorithms of its 32.
- "By all seven" favours restatements (for the 27B, 15 of 22): a formula stated twice is easy for every prover,
  and a loop is where the proof assistants abstain.

## What changes

- The README's table carries the algorithm count beside the proved count, and the headline says what the 17 are.
- `dawnr ask`, `dawnr prove` and `dawnr verify` say beside an answer which kind it is, and for a restatement that
  what the answer rests on is the specification, held to an independent solution on drawn inputs.
- Every registration from here on reports both counts. No bar set before today is re-read by this column.

## What it does not say

That a restatement is wrong. All of these specifications agree with the problem's own solution on a thousand drawn
inputs, larger ones included, and reject most wrong answers; for a one-line function the formula is the honest
specification. Nor that every "algorithm" is hard: a three-way maximum by cases is counted as one because its
specification does not hand over the program. The rule sorts by what the prover had to establish, by reading the
text; it measures no difficulty.
