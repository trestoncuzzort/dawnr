# The chat model's one look at the held-out 232, registered before any answer is generated (2026-09-29)

**Written 2026-09-29 05:55Z.** No chat-trained checkpoint has ever answered a held-out problem.
The three seeds of `locallm/PREDICT-2026-09-29-dawnr-r12-corpus.md` (the pipeline on the
531-document corpus and the r12 core) are the arms; each answers the 232 once through
`locallm/chat_heldout.py`, in the record every other arm uses, and is graded by
`t/grade_lab.sh heldout` and scored by `t/score_heldout.py`, the same harness and scorer as the
r11 base seeds and r12. This is one look for one decision: does the chat pipeline, on the same
corpus and core, do better on the held-out set than the head-prompt fine-tune.

    seeds: 3
    metric: clean
    problems: decontam

**The arms.** `dawnr-chat-r12c-s1337`, `dawnr-chat-r12c-s1338`, `dawnr-chat-r12c-s1339`: the
mid models of `~/scratch/dawnr-r12/A-s<seed>/4-mid/model`, greedy, 800 tokens, the chat-token
grammar on, two calls at most, the best-verdict answer (the evaluation registered for the dev
numbers). The comparison arms: the ten r11 base seeds (head-prompt, 0 clean on the 200 in nine
seeds and 2 in one) and the r12 seeds as they land (head-prompt, same corpus and core; seed 1's
91 of 232 well formed).

**Predictions.**

1. **Well formed on the 232, mean over the three seeds, is above r12 seed 1's 91.** On dev the
   chat model is well formed on 49 of 100 against the head-prompt model's 91 of 232 (39%);
   the tool and the examples in the prompt are the difference. Falsified if the mean is at
   or below 91.
2. **At least one seed has a clean answer on the 200 decontaminated problems.** On dev the three
   seeds pass all examples on 0, 1 and 3 problems; the held-out set is 2.3 times larger and the
   proof bar is higher than examples. Falsified if all three seeds score 0 clean: then the
   pipeline's dev gains do not reach the held-out set at this size, and the next lever is
   sampling with the verifier as the filter (section D of the r12 plan), not more of the same.
3. **`compare_arms.py --metric clean --problems decontam` against the r11 base is INCONCLUSIVE.**
   Three seeds against ten cannot clear ADOPT's bar; the point of this look is direction, not a
   verdict. Falsified by ADOPT (reported as the headline it would be, then rerun at more seeds
   before any public claim) or by NOT MEANINGFUL.
4. **Any clean answer is written, not recited** (`score_heldout.py`'s recitation check against
   the training documents). Falsified if every clean answer is a training document with names
   erased.

**What follows.** If 2 holds: the chat pipeline replaces the head-prompt fine-tune as the arm
the scoreboard reports for locallm, and the next round adds seeds and the repair, stop and RL
stages in the pipeline plan's order. If 2 fails: the sampling pilot, through the engine.
