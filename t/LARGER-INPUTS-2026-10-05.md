# The specification check stopped at the size of the examples (2026-10-05)

The second correction of 2026-10-05. Found at 09:52Z, measured against every published row by 10:12Z.

## What was found

`dawnr verify` was being tried with a larger model as the writer (`DAWNR_WRITER_URL`, added that hour). It verified
a function the installed model could not, counting the even numbers in a list, and the specification it had
written read:

```
ensures r == (if len(s) == 0 then 0
         else if len(s) == 1 then (if s[0] % 2 == 0 then 1 else 0)
         else if len(s) == 2 then ...
         ...
         else if len(s) == 6 then ... six terms ...
         else r)
```

Every case up to a list of six, and for anything longer `r == r`, which says nothing. The loop invariant was
written the same way, so the proof went through, and the gate's measurement of the specification read "holds on
100 drawn inputs, rejects 100% of the wrong outputs tried".

The reason is in how inputs are drawn. `t/spec_check.draw` shapes each draw like one of the problem's own examples,
which is what keeps a draw inside what the problem defines (a sorted example stays sorted). It also bounds the
size by the example: a sequence is at most two elements longer than the longest example, an integer at most twice
the example. The examples here were lists of up to four, so no draw was longer than six, and a specification
exact to six and empty after it was indistinguishable from a complete one. The same hole was closed on the
program side on 2026-10-01 (a lookup table for the Bell numbers read as agreeing because every draw fell in
[0, 4]; CORRECTIONS.md); this is its specification-side twin, and it took a model that would rather enumerate than
generalise to show it.

## The remedy

- `t/spec_check.draw_beyond` draws in the example's style and past the ordinary bound: most from just beyond it to
  about three times it, some far beyond (sequences of 28 to 40, integers to twenty times the bound), because a
  case-by-case specification costs its writer text that grows with the size covered and an answer has a budget.
  QuickCheck grows its test size to 100 as a run proceeds; EvalPlus (arXiv:2305.01210) found tests the size of a
  benchmark's own missing a fifth to a quarter of wrong programs. `check_task(..., drawer=...)` takes it; without
  one, every draw is what it was, so no earlier measurement moves.
- The rule on the larger inputs (`spec_check.larger_reason`): never false at the solution's answer; at least 60% of
  wrong outputs rejected, as on the ordinary draws; and a `requires` that puts a number above a length or a
  parameter must admit at least half the share of larger inputs that it admits of ordinary ones. It counts once
  five larger inputs fall inside the `requires`; where the solution answers none, it is not measured and nothing
  is refused on its account.
- **The product's gate** (`t/spec_gate.judge`, so `dawnr ask`, `spec`, `verify` and the replay of a certificate)
  holds every specification that passes to 60 larger inputs, since commit 8836cdec. The enumerated specification
  above is refused: "the specification says too little about inputs larger than the examples".
- **The scoreboard's check** (`t/spec_check.py`) now stores the larger-input measurement with every agreeing
  verdict, from the task's own generator (200 draws), and `t/score_levels.py --larger` counts an answer only if it
  stands there too. `t/larger_inputs.py` adds the measurement to verdict files written before today.

## What it does to the published numbers

Every row of the scoreboard was restated from its saved answers and verdict files through the scorer itself
(1,480 verdicts measured on larger inputs; the middle column reproduces this morning's restatement exactly).

| row | on the 200, as first published | on the clean 182 | on the clean 182, specifications held to larger inputs | problems that leave |
|---|---|---|---|---|
| the 4B on v5's rows, training seed 1 | 18 and 7 | 13 and 5 | **12 and 5** | 629 |
| the 4B on v5's rows, training seed 2 | 18 and 8 | 13 and 5 | **12 and 5** | 629 |
| the 4B on v5's rows, training seed 3 | 15 and 7 | 9 and 6 | **9 and 6** | none |
| v3's rows, seed 1 | 17 and 10 | 12 and 7 | **11 and 7** | 629 |
| v3's rows, seed 2 | 16 and 8 | 10 and 4 | **9 and 4** | 629 |
| v3's rows, seed 3 | 17 and 8 | 11 and 4 | **10 and 4** | 629 |
| teacher1, seed 3 | 21 and 12 | 15 and 9 | **14 and 9** | 629 |
| teacher1, seed 1 | 19 and 8 | 15 and 5 | **14 and 5** | 629 |
| teacher1, seed 2 | 13 and 7 | 9 and 5 | **9 and 5** | none |
| teacher2, seed 1 | 23 and 13 | 16 and 10 | **13 and 9** | 271, 355, 629 |
| teacher2, seed 3 | 27 and 13 | 19 and 10 | **18 and 10** | 271 |
| teacher2, seed 2 | 24 and 15 | 17 and 10 | **16 and 10** | 629 |
| teacher3, seed 2 | 27 and 15 | 18 and 10 | **17 and 10** | 629 |
| teacher3, seed 3 | 23 and 13 | 14 and 8 | **12 and 7** | 221, 629 |
| teacher3, seed 1 (dawnr v5) | 26 and 16 | 18 and 12 | **17 and 12** | 629 |
| release-v4 candidate, seed 1 | 23 and 13 | 17 and 10 | **15 and 10** | 221, 629 |
| Qwen3.5-4B prompted | 15 and 8 | 9 and 6 | **9 and 6** | none |
| Qwen3.5-9B prompted | 18 and 7 | 15 and 6 | **14 and 6** | 375 |
| Qwen3.5-2B prompted | 4 and 3 | 2 and 2 | **2 and 2** | none |
| 2B dawnr on the v4 candidate's rows | 8 and 6 | 4 and 3 | **4 and 3** | none |
| Qwen3.5-0.8B prompted | 1 and 1 | 1 and 1 | **1 and 1** | none |
| Qwen3.5-27B prompted | 43 and 29 | 33 and 23 | **32 and 22** | 355 |
| Phi-4-mini prompted | 3 and 3 | 2 and 2 | **2 and 2** | none |
| Phi-4-mini under the grammar | 9 and 7 | 7 and 5 | **7 and 5** | none |

Five problems leave somewhere. What their specifications said:

- **629** (the even numbers of a list), in 13 rows: "every element of the result is an even element of the input,
  every even element of the input is in the result, and the result is no longer than the input". Nothing about
  order or how many times. On short lists a wrong output rarely fits; on a list of twenty with repeated values,
  dropping one repeat still fits (between 46% and 59% of the wrong outputs tried were accepted, by answer).
- **271** (the sum of the fifth powers of the first n even numbers) and **355** (rectangles in a circle), in two
  rows each: a table, `n == 0 ==> r == 0`, `n == 1 ==> r == 32`, `n == 2 ==> r == 1056`, `n == 3 ==> r == 8832`.
  The examples are at n = 2 and 3, and the draws stopped at 4 and 6.
- **221** (the first even number of a list), in two rows: "the result is -1 or even; -1 only if nothing is even;
  otherwise it is in the list". Any even element fits, not only the first.
- **375** (round to the nearest multiple), in one row: three clauses joined with `and` and `or` in an order that
  admits 1396 as 1403 rounded to a multiple of 25.

What survives: Phi-4-mini's two rows and the prompted 4B's, unchanged; the published model against Phi under the
grammar, **17 and 12 against 7 and 5**; every seed of its recipe above Phi at both levels (17 and 12, 17 and
10, 12 and 7). What changes: the published model reads 17, not 18, at one prover; fine-tuning adds 8 problems to its
own base model, not 9; the prompted 27B reads 32 and 22, not 33 and 23, and the 9B 14, not 15. Double Phi on every
seed was not met before and is not now (the third seed has 12 and 7 against 14 and 10). 3 pairs of rows change
order at one prover, all of them through one row (v3's rows plus every admitted document, seed 1, which loses three:
it falls from one above the two seeds of the row before it, and the prompted 9B, to one below).

## A rule that was wrong for an hour

The first form of the rule also refused a specification whose `requires` admitted under half of the larger inputs
the solution answers. Read against the rows before anything was published, it refused two right specifications:
"every character is a hexadecimal digit" (the reference answers any string, and a longer random string is less
often all digits) and "one length argument is not above the other". The share a `requires` admits is now compared
with the share it admits of ordinary draws, and only for a `requires` that itself puts a number above a length or
a parameter (`len(s) <= 6`, `n < 5`), which is what closing off size looks like. The table above is under that
rule; both specifications count.

## What is not yet done

- **The training rows.** A student that writes a table for a specification learned it somewhere: answers of this
  kind passed the old check on training problems too and became rows. The round-4 rows are being measured with the
  larger inputs, and the next build of rows leaves out the ones that do not stand; its registration will say how
  many.
- **Runs in flight.** The three round-4 seeds and the release gate for dawnr v6 were registered under the reading
  without larger inputs and are judged by it, as registered; each is reported both ways.
- **Certificates.** A certificate written before commit 8836cdec can now fail its replay on the specification
  step, which is the check being stricter than the producer was.
- **The sizes.** Sequences to 40 and integers to twenty times the example are bounds too. They are past what an
  enumeration fits in an answer's budget today, and that is an argument about budgets, not a proof.

## To reproduce

```
python3 t/larger_inputs.py --verdicts VERDICTS.json --out VERDICTS-larger.json TAG ...
python3 t/score_levels.py --verdicts VERDICTS-larger.json --min-completeness 0.6 --larger TAG ...
```

Research receipt 5deec846ed0c.
