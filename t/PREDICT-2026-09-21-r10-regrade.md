# Is locallm-r10's 5 clean real? Registered before the regrade

**Written 2026-09-21, before any regraded table exists.** One table has already
been read and this file says so rather than pretending otherwise.

## What was found

`t/out/spec-experiment/locallm-r10/` on the lab workstation holds 232 greedy
answers from a 92,920,320-parameter locallm and a `kernels.md` written
2026-09-20 07:01. Nobody scored it. Scored today with `t/score_heldout.py`
against `split-v3.json`'s 232 held-out ids:

| tag | well formed | tests pass | clean | converts | proven but wrong |
|---|---:|---:|---:|---|---:|
| `locallm-r10` (old table) | 112 | 6 | **5** | 5/6 | 67 |

That is above every locallm row on `SCOREBOARD.md` (best 3), above Phi-4-mini's
3, and above WS-22.5's own target of 4. It is not a result yet, for one reason:
**it came out of the session the operator had reversed** (`internal/ROADMAP-LOG.md`,
"Reversing Antigravity's session, 2026-09-20"). That section's rule is that raw
decodes survive and everything derived from them by the edited code does not. The
table was written at 07:01 on a tree carrying those edits.

## Why it is worth regrading rather than discarding

`locallm/`'s record for the checkpoint (`~/antigravity-backup-2026-09-20/t-out/locallm-r10/run.json`)
shows the recipe is `locallm-r9`'s exactly: init
`t/out/source-pretraining-longer-2026-09-19/gpt-seed1337`, 300 steps, lr 3e-5,
batch 8, block 512, seed 1337, greedy decoding. **The corpus is the only
difference** (`corpus-r10-headed.txt`, 299 documents, 50,111 training tokens,
built from 37 sample tags). `locallm-r9` scored 2 clean. If the 5 holds, it is a
single-variable data result: 2 to 5 from the corpus alone.

Checked already, before registering:

- The r10 eval ids are `split-v3.json`'s 232 exactly, and none of r10's
  `split-v6` train ids is among them.
- `run_par.py` and `t/verifiers/` are unchanged between the lab's HEAD
  (`ed0bf473`) and `main`; the lab's uncommitted edits to `t/spec_experiment.py`
  and `t/repair.py` are byte-identical to what `main` later committed, and the
  `spec_experiment.py` change is prompt v5's text, which extraction does not read.

## The regrade

`locallm-r10-regrade`: the 232 raw decodes copied unchanged, then
`t/grade_lab.sh heldout` with `T_LAB_RUN_PAR=--no-cache`, so extraction, the
problems' own tests and all seven kernels are recomputed by today's code and no
verdict is carried over from the 07:01 table.

## Predictions

1. **The regrade reproduces 5 clean exactly.** Falsified by any other count. The
   grading path is unchanged, so a different number means the 07:01 table was
   produced by something other than the code it appears to have been, or a cell
   flaked under load; either is a finding about the instrument.
2. **Tests pass stays at 6 and well formed at 112.** Falsified by any change;
   these two stages are deterministic given the raw text.
3. **At least 4 of the 5 clean answers agree with their problem under
   `t/spec_check.py`.** Falsified at 2 or more disagreeing. Every locallm arm
   except `r9-seed42` has been 100% on this column; one disagreement would match
   that arm, two would say the corpus bought clean answers by teaching wrong
   specifications.
4. **None of the clean answers is a copy of a training document.** Falsified if
   any clean answer's task body appears in `corpus-r10-headed.txt` with names
   erased. A held-out problem whose answer is recited from a train problem's
   document is a leak through similarity, not through ids, and the id check
   above cannot see it.

## What each outcome means for what happens next

If 1, 3 and 4 hold, r10's corpus is the best-measured locallm data recipe, and
the next step is to rebuild it **under the current strict gate** (the one the
reversal restored), retrain across three seeds, and see whether the gain survives
the gate. It could not be put on the scoreboard as it stands, because its training
positives were admitted by the widened pool check.

If 1 fails, the old table is wrong, r10 is dropped, and the instrument that let
an unscored table sit on the lab for a day is the finding.
