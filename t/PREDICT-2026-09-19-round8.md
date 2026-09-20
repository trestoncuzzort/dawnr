# Round 8 predictions: a pool that is checked, and a splitter that works

Written before the corpus is built. Two things changed since round 7b, and
neither is a model change.

**The pool was never specification-checked.** Rebuilding it revealed that 246
training answers had passed their tests and all seven verifiers and had never
been run through `t/spec_check.py`, so the gate refused them. Checking all 34
training tags took minutes: 321 tasks checked, 288 agree, 5 disagree, 28 could
not be checked. The pool went from 87 preference pairs to **733**, and its
supervised set is now **79 answers that are verified, twin-refuted and
confirmed to specify the problem that was actually asked**. Round 6's 87
included answers nobody had checked, 28 of which disagree with their problem.

**The answer splitter now knows about `Signature:` heads**, so the headed arm
that collapsed to 16 well-formed answers in round 7b has regenerated and can be
scored for what it actually is.

Both arms decode greedily, which round 7b measured as the best setting.

## Predictions

1. **`locallm-r8` scores at least 2 clean**, matching the best locallm row.
   Falsified below 2. The corpus is cleaner and slightly larger; if a pool that
   is honest about its specifications cannot hold the line, that is worth
   knowing.
2. **`locallm-r8` does not reach 4 clean**, which is what beating Phi takes.
   Falsified at 4 or more. 79 supervised examples is not enough to move
   problem-solving, and problem-solving is the whole gap.
3. **`locallm-r7b-headed2` writes at least 100 well-formed answers**, against
   the 16 its broken-splitter predecessor managed. Falsified below 100. This
   is the test of whether that arm measured a corpus or a bug.
4. **`headed2` keeps signature failures below 25%** of its well-formed answers,
   against 32.2% for greedy on the unheaded corpus. Falsified at 25% or above.
5. **Neither arm passes more than 4 tests.** Round 7b's best was 2, the 3.2M
   rows managed 2, and nothing here changes how the model reasons about a
   problem. Falsified at 5 or more, which would be the first real movement in
   the column that decides the score.

## What I expect

Predictions 1, 2 and 5 to hold, and 3 to hold comfortably. The one I am least
sure of is 4: giving every document a head may teach the model to copy the head
it was given, or it may simply teach it that heads exist and are worth
inventing. Round 7b could not tell those apart because nothing parsed.
