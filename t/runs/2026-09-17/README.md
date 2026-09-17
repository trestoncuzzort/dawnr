# Runs of 2026-09-17

The filter loop on the M3 Max MacBook Pro, the first time it ran off the lab
workstation, and a correction to the copy check that changes the 2026-09-16
headline. The paragraph dated 2026-09-17 in `internal/ROADMAP-LOG.md` is the
summary; this page holds the numbers and the data.

## What ran

    cd t && ~/.venv-t/bin/python loop_filter.py \
      --corpus-file runs/2026-09-16/loop-data/corpus.txt \
      --rounds 3 --samples 500 --steps 1500 --jobs 2 --work out/loop-filter-mac

The same corpus, seeds and settings as `runs/2026-09-16/filter-loop/clean/`
(3.2M parameters, 1,500 steps, 500 samples at temperature 0.8, top_k 40).
locallm trained on Apple's GPU (MPS, torch 2.14.0, Homebrew Python 3.12.14);
the seven kernels graded at `--jobs 2` (the versions in
`t/WITNESS-2026-09-16-macos-m3max.md`). Round 1's grading was stopped by hand
at about 01:45Z with 698 of its 1,162 cells done; round 2 never started.

- `filter-loop-mac/r0/`: corpus, model, the 500 samples, the 112 novel tasks, `kernels.md`, the train and grade logs.
- `filter-loop-mac/r1/`: the same up to grading, plus `events-partial.jsonl`, the 1,398 start and end events `run_par.py` wrote for round 1's cells before the stop (the source of the round 1 counts below).
- `logs/loop.log`: the loop's own output.

## Where the time went

| Step | Round 0 | Round 1 |
|---|---|---|
| Train, 1,500 steps on MPS | 42 s | 45 s |
| Sample 500 programs | 11 min 0 s | 10 min 39 s |
| Grade in seven kernels at 2 jobs | 17 min 55 s, 784 cells | stopped after about 20 min, 698 cells |

Sampling is one program at a time; grading is the bottleneck, as on the lab
workstation.

## Round 0

| | This Mac | Lab workstation, `2026-09-16/filter-loop/clean/r0` |
|---|---|---|
| Samples | 500 | 500 |
| Parse | 341 | 375 |
| Well-formed | 125 | 180 |
| Novel, as the loop counted | 112 | 146 |
| Clean in all seven, as the loop counted | 35 | 46 |
| Of those, exact copies of a corpus task | 10 | 17 |
| Clean and new | 25 | 29 |

Same corpus, seed 1337 and sampling seed 100; the machines differ in device
(MPS against CUDA) and in `locallm/model.py`'s attention path on MPS (same
math, unfused). One run each, so the gap between 35 and 46 is not separable
from hardware nondeterminism.

Of the 112 novel tasks, 35 read all seven, 1 reads six (lean alone,
`r0_s485`), 1 reads one, and 75 read `verified / refuted` in none. Of those
75, 58 read `refuted / refuted` in every kernel (the program breaks its own
ensures at a concrete input) and 65 have at least one refuted real; the rest
are twins the ladder could not build (`no-twin`), unproved reals, and 2 specs
too weak to tell the twin apart (`decorative`).

**What the 35 look like.** Each was compared with its nearest corpus document
by `difflib` ratio after erasing the problem lines, the version line, the task
name and whitespace.

| Nearest-document similarity | Clean programs |
|---|---|
| 0.95 or more | 7 |
| 0.85 to 0.95 | 26 |
| 0.70 to 0.85 | 2 |
| below 0.70 | 0 |

3 of the 35 have a loop; the median is 8 lines. `r0_s261` and `r0_s45` are
token for token `mbpp_176__perimeter_triangle` and
`mbpp_369__lateralsurface_cuboid`; `r0_s297` differs from its document only by
a missing `gate loops` line. The loop's clean programs are, on this evidence,
mostly short loop-free tasks close to one in the corpus, which is what the
held-out run of 2026-09-16 (0 of 232 passing, 151 exact copies) predicts.

## Round 1, stopped

166 novel tasks from 500 samples (390 parse, 227 well-formed), graded partly:

| Kernel | Cells done | verified / refuted |
|---|---|---|
| dafny | 165 | 52 |
| verus | 165 | 52 |
| spark | 164 | 52 |
| framac | 165 | 52 |
| lean | 39 | 10 |
| rocq | 0 | 0 |
| fstar | 0 | 0 |

No task had all seven cells, so round 1 has no clean count. In round 0 the
first four columns read 36, 36, 37 and 36 against 35 in all seven, so about
50 is the number the finished round would likely have shown as the loop counts
it; that is an estimate, not a measurement. Round 1's novelty check ran with
the old key below, so its 166 include copies it did not see.

## The copy check, corrected

`t/loop_filter.py`'s `key()` (and `t/lab.py`'s `task_key()`) erased the task's
name before comparing canonical forms, and kept its format version. The 27B
answers in the corpus are written `t 0`; locallm's samples are written `t 1`.
So an exact copy of any 27B answer never matched, was counted novel, and, being
a correct task, graded clean. Both keys now also erase the version and the
gate, neither of which changes what the kernels check. Recounted with the new
key over the committed rounds and this one:

| Round | Corpus docs | Novel | Clean, as counted | Clean copies missed | Clean and new |
|---|---|---|---|---|---|
| This Mac, r0 | 269 | 112 | 35 | 10 | 25 |
| `2026-09-16/filter-loop/clean/r0` | 269 | 146 | 46 | 17 | 29 |
| `2026-09-16/filter-loop/clean/r1` | 315 | 144 | 57 | 26 | 31 |
| `2026-09-16/filter-loop/raw-matched/r0` | 129 | 7 | 3 | 2 | 1 |
| `2026-09-16/filter-loop/raw-full/r0` | 941 | 4 | 0 | 0 | 0 |

The 2026-09-16 headline, 46 clean from the clean corpus against 3 from raw
output at the same size, reads 29 against 1 with copies removed; round 1's 57
reads 31. The direction holds and the size of the effect is about a third
smaller than recorded. `runs/2026-09-16/scripts/pick.py` builds the same old
key when it picks 27B answers; it is kept as the record of what ran and was
not changed.
