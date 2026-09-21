# How much of a locallm score is the recipe, and how much is the draw? Registered before training

**Written 2026-09-21, before any of these five models exists.**

## Why this has to be measured before anything else is optimized

`t/PREDICT-2026-09-21-r10-regrade.md` confirmed `locallm-r10` at 5 clean of 232
under today's code, all five agreeing with their problems. With the new
`clean, recited` / `clean, novel` columns in `t/score_heldout.py` (answer overlap
after Lewis, Stenetorp and Riedel, arXiv:2008.02637), every locallm arm reads:

| arm | corpus | clean | recited | **novel** |
|---|---|---:|---:|---:|
| `locallm-r9` | `corpus-r8-headed.txt` | 2 | 1 | **1** |
| `locallm-r9-seed7` | same, core seed 7 | 1 | 0 | **1** |
| `locallm-r9-seed42` | same, core seed 42 | 3 | 1 | **2** |
| `locallm-r10-regrade` | `corpus-r10-headed.txt` | 5 | 1 | **4** |

`locallm-r9` and `locallm-r10` share the pretrained core (`gpt-seed1337`), the
training seed (1337), 300 steps, lr 3e-5 and greedy decoding. Their corpora share
297 of about 300 documents: r10 drops 4, adds 2 and rewords 4. So a ~1% change in
the training text moved novel clean answers from 1 to 4. Either those ten
documents matter a great deal, or the recipe's run-to-run spread is as wide as
every difference the scoreboard has ever reported. Until that is known, no
"optimization" can be told apart from a lucky draw.

## The five arms

One corpus (`t/out/loop/corpus-r8-headed.txt`, sha256 `7bf538f3e836...`), one core
(`gpt-seed1337`), `locallm/continue_from_checkpoint.py --steps 300` with every
other setting at the defaults `locallm-r9`'s `run.json` records. Only `--seed`
varies, which sets both the batch order and which tenth of the documents is held
out for validation.

| arm | `--seed` |
|---|---|
| `locallm-r11-rerun` | 1337, `locallm-r9` exactly |
| `locallm-r11-s1` | 1 |
| `locallm-r11-s2` | 2 |
| `locallm-r11-s3` | 3 |
| `locallm-r11-s4` | 4 |

Decoded with `t/gen_fleet.sh`, `--temperature 0 --tokens 1200`, split-v5, and
graded by `t/grade_lab.sh heldout` with `T_SPARK_JOBS=1` now its default.

## Predictions

1. **The rerun is not byte-identical to `locallm-r9`, and at least 200 of its 232
   replies are.** Falsified either way. bf16 training on a GPU with
   non-deterministic attention kernels need not reproduce itself; if it does,
   training noise is zero and every difference between runs is the seed or the
   data. If fewer than 200 match, nondeterminism alone is a large noise source.
2. **Novel clean spans at least 2 across the five arms** (max minus min >= 2).
   Falsified at a span of 0 or 1.
3. **At least one of the five reaches 3 novel clean.** Falsified if all five read
   2 or fewer. This is the prediction that decides the reading of r10: if some
   seed of the r9 corpus gets 3 or 4, r10's 4 is inside the recipe's own spread,
   and its corpus is not shown to be better.
4. **The mean novel clean over the five lies between 1.0 and 2.5.**
5. **Every novel clean answer agrees with its problem under `t/spec_check.py`.**
   Falsified by any disagreement.

## What each outcome sends next

- **2 and 3 hold:** the scoreboard reports locallm as a mean and a range over
  seeds from now on, never a single run, and a recipe change counts only if it
  moves the mean. The first candidate then is one that attacks the spread itself:
  averaging the weights of fine-tunes from one core (model soups), which costs
  30 seconds of training per ingredient.
- **3 fails (all five at 2 or fewer):** r10's 4 sits outside the r9 recipe's
  spread, so the ten documents that differ are worth a controlled test: the same
  five seeds on `corpus-r10-headed.txt`, then the documents added and removed one
  group at a time.
- **1 fails with fewer than 200 identical:** the variance is in the hardware,
  and deterministic training has to come before any comparison.
