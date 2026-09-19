# Round 6, predicted before it was scored

Written while `r6-train` was still computing its reference log probabilities, so nothing here was tuned to a
result. Round 5's row is the baseline: the student wrote 42 well-formed answers of 232, 11 passed their own
tests, 3 were clean, 3 survived the specification check, and 12 were proven while disagreeing with the problem.
Phi-4-mini wrote 12 well formed, 6 test-passing, 3 clean, 2 after the specification check.

Round 6 changes two things: the pairs gained 175 negatives whose rejected side is a program that is right and
cannot be proved (plus the three that all seven proved while disagreeing with their problem), and the answers
are also generated with t's grammar on the decoder -- for the student and for Phi alike.

## What I expect, with the number that would prove me wrong

1. **The unconstrained student barely moves at the first two gates.** Well formed 38 to 46 (was 42),
   test-passing 9 to 14 (was 11). The new pairs say nothing about notation, so a change here would mean the
   DPO objective is moving something I did not intend.

2. **Its conversion improves, and that is the whole point.** Test-passing answers that end clean: round 5 was
   3 of 11, 27 percent, against Phi's 3 of 6. I expect 35 to 55 percent, so **4 to 6 clean**. Below 4 and the
   new negatives did not teach the gate they were built for, which would be the clearest result of the round
   and would say the 1.5B cannot learn proof from 648 pairs.

3. **Proven-but-wrong falls.** It rose 8 to 12 across round 5 while the pool had no negative for it; three
   spec-disagreeing negatives is thin, so I expect a small fall, 12 to 6-11, not a collapse.

4. **The constraint roughly triples well-formed answers and does not triple clean ones.** For the student
   under the grammar: parse rate above 90 percent (the 30B went 32 to 63 with a third of its attempts timing
   out), well formed 80 to 130, test-passing 12 to 22. Clean 3 to 7. The gap between those last two rows is
   the same finding the constrained arm on the lab already gave: the notation was never the expensive part.

5. **The constraint helps Phi as much as it helps us, and possibly more.** Phi under the same grammar: well
   formed 50 to 110, test-passing 10 to 20, clean 3 to 7. This is the prediction I least want to be right,
   and it is why the row exists: if a constraint is worth having, it is worth having for the model we are
   being compared against, and a win that only appears when one side is constrained is not a win.

6. **The round does not beat Phi decisively.** Most likely outcome: student 4 to 6 clean against Phi's 3 to 7,
   overlapping, decided by one or two answers out of 232 -- which is noise, not a victory. Beating it
   decisively needs conversion at Phi's rate AND the constraint's volume at once, and I put that below one
   chance in four this round.

7. **Cost, so the prediction can be wrong about practicality too.** Constrained generation of 232 answers:
   20 to 60 minutes a set on this desktop. If it is over two hours a set, the masking cost is worse for a
   small model than the 30B measurement suggested and the constrained rows may not be worth repeating every
   round.

## What each outcome changes

- Conversion improves and the constraint adds volume: round 7 combines them and the pool grows the same way.
- Conversion does not improve: the pool cannot teach proof at this size, and the next move is WS-19's model
  that reads a verifier's error rather than more preference pairs.
- Phi gains as much from the constraint as the student does: the honest claim stays the system's 12 clean
  against Phi's 3, not the student's.
