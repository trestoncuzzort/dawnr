# What the loan of Qwen3-235B produced, 2026-09-20

Every model-shaped roadmap item, run to completion before the cards went back.
`internal/QWEN-EXHAUSTED-2026-09-20.md` is the argument that this list is complete;
this is what it yielded. Nothing here is a result yet: all of it is banked evidence
for the seven provers to judge, which is CPU and outlives the loan.

| item | instrument | banked |
|---|---|---|
| WS-21 move 2 | `--prompt v5` | 232 answers, **graded, measured, closed** |
| WS-21 move 1 / WS-22.4 | `--grammar t/t.lark.gbnf` | 232 constrained answers |
| WS-22.2 / WS-18 | `--prompt v4` over the train split | 2,7xx answers, 499 well-formed at extract |
| WS-19 move 3 | `t/multiplier.py` | 221 of 221 tasks, three variants each |
| WS-16.2 | `t/hint_candidates.py` | 27 of 30 rows, 8 hints each |
| WS-19 move 2 | `t/repair.py` | 768 repaired answers over 16 arms |

## The one item that is already a measured result

**WS-21 move 2 is closed, and it closed negative.** Prompt v5's grammar-guidance
block moved well-formed answers 67 to 79 and test-passing answers 53 to 62, moved
clean answers 11 to 11, and after `spec_check.py` read 7 against the control's 8.
Four of five registered predictions held; the falsified one is the useful one, and
`t/PREDICT-2026-09-20-prompt-v5-OUTCOME.md` has the account. The reading: the parse
wall is the largest loss by count and was never the binding constraint on clean
answers.

## Three defects the night found, each costing work that looked like it had run

1. **xgrammar at 373.8 s a reply with four cards at 0%**, and then llguidance
   returning HTTP 400 on the GBNF file it cannot read. WS-21 move 1 was recorded as
   blocked on a card; the card was never involved.
   (`t/FINDINGS-constrained-decoding-2026-09-20.md`)
2. **Six of ten repair arms reported 0 candidates and exited 0**, holding about
   forty answers one kernel from clean, because the candidate loop globs `grade-in/`
   and those arms have `tasks/`. Fixed with a fallback, a loud warning and an opt-in
   `--require-candidates`, the shape
   `github.com/UCSC-Transients/dark-hunter_pop/issues/135` prescribes. Re-run, the
   six produced **278 answers**.
3. **Three clients sent one request at a time** to a server answering in 0.2 s. The
   multiplier went 1.9 to 14.5 tasks a minute once it had a thread pool; the six
   repair arms went from 34 minutes sequential to 7 concurrent; the hint banker was
   split across kernels with its own `--only-kernel` flag. An estimate of 3.7 hours
   became 8 minutes without dropping any roadmap work.

## Deliberately not run

The `qwen235-train-s2/s3/s4/p4s2` draw queue, four more passes over the **same**
2,771 ids at temperature 0.7, about 3.7 hours. Round 6 measured more samples per
problem as moving the clean count by zero; the lever that moved was more problems,
and that is pool v6, already answered. The wrapper was killed and `train-p4` left to
finish.

## What the CPU owes now

1. Grade `qwen235-train` (499 well-formed of 2,767), `qwen235-v6new`, `-p4`,
   `heldout-s2`, `heldout-s3`, and `heldout-g1`. The grade queue is running.
2. Filter the hint bank: a candidate counts only when the real VERIFIES and the twin
   is **still** REFUTED. That second half is DAISY's 25-percent warning made
   measurable.
3. Filter the multiplier bank the same way, with the problems' own tests separating a
   reconstruction that merely restated the body.
4. Grade the 768 repairs and read them against `t/FINDINGS-repair-2026-09-20.md`'s
   +3-cells-of-182 baseline.
5. **The extraction half of the multiplier, which needs no model.** PACT
   (arXiv:2102.06203) got 167x out of proof artifacts already on disk with zero model
   calls, and its 121M model beat an 837M one trained without them at a matched
   budget. The seven provers here emit obligation lists, which premises closed a
   goal, and a witness per twin, and this pipeline discards all of it after reading
   the verdict. That is the better lever and it was always CPU.

## The card question, restated once

WS-22.3 and WS-22.5 train locallm, not this model. locallm is 875M at its measured
ceiling and fits one card for minutes. Returning the 235B costs nothing there;
returning every card makes WS-22.5, the project's own target of 4 clean of 232,
unreachable.
