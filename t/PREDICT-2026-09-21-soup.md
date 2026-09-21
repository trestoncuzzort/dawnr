# Does averaging fine-tunes narrow locallm's spread? Registered before any soup exists

**Written 2026-09-21, before either soup is built and before any r11 arm is
graded.** No r11 score has been read by anyone.

## The question

`t/PREDICT-2026-09-21-recipe-variance.md` asks how wide one recipe's spread is.
This asks whether it can be narrowed without choosing a seed by its score, which
would be selecting on the 232 held-out problems. The method is the uniform model
soup (Wortsman et al., arXiv:2203.05482): average the weights of fine-tunes that
share one pretrained core, and decode the average as one model of the same size.
Dodge et al. (arXiv:2002.06305) is why it is worth trying: they measured that
fine-tuning with only the seed varied spreads out-of-sample scores widely, with
data order and initialization contributing comparably, and our training seed sets
both the data order and the validation split.

## Arms

Ten single fine-tunes of `locallm-r9`'s recipe (`corpus-r8-headed.txt`, core
`gpt-seed1337`, 300 steps, lr 3e-5), differing only in `--seed`: the five of the
variance study (`locallm-r11-rerun` at 1337, `-s1` to `-s4`) and five more,
`locallm-r11-s5` to `-s9` at seeds 5 to 9. Two soups over disjoint halves, built by
`locallm/soup.py` with no selection of any kind:

| soup | ingredients |
|---|---|
| `locallm-r11-soupA` | rerun, s1, s2, s3, s4 |
| `locallm-r11-soupB` | s5, s6, s7, s8, s9 |

All twelve decoded identically: `t/gen_fleet.sh`, temperature 0, 1200 tokens,
split-v5. Graded by `t/grade_lab.sh heldout`, scored with `t/score_heldout.py
--corpus` so recited and written answers are reported apart.

## Predictions

"Written" below is `clean, novel`: clean and not a training document.

1. **Each soup writes at least as many clean answers as the mean of its own five
   ingredients.** Falsified if either soup falls below its ingredients' mean.
2. **The two soups differ by at most 1 written clean answer, while the ten single
   seeds span at least 2.** Falsified if the soups differ by 2 or more, or if the
   singles span less than 2 (then there is no spread to narrow and this
   measures nothing).
3. **Each soup's well-formed count lies within its ingredients' range.** Falsified
   outside it. A soup outside the basin would show up first as broken syntax.
4. **Every written clean answer of either soup agrees with its problem under
   `t/spec_check.py`.**

## What follows

If 1 and 2 hold, a soup becomes the default way locallm is fine-tuned: several
seeds, averaged, no seed chosen. It is then compared against the next recipe
change by both soups and by the single-seed mean. If 1 fails, averaging loses
something the ingredients each had, and the paper's own warning applies: an
ingredient may have left the basin, which the soup's validation loss against its
ingredients' will show.

---

## Note added 2026-09-21, after registration and before any r11 table was read

"Written" (`clean, novel`) turned out to be too narrow a filter. It catches a
clean answer that is a training document with names erased, but not one whose
problem has a same-task source in training under a different program
(`t/DECONTAMINATION-2026-09-21.md`: 32 such held-out problems, and every locallm
clean answer so far is on them). So every r11 arm is also reported on the other
200 problems, where no locallm arm has yet been clean with a specification that
agrees with its problem (one, r9 seed 42's, disagrees). The predictions above are
left exactly as registered and are graded as written; the clean-200 column is
reported beside them, not in place of them.
