# locallm

Small language models built from scratch on your own machine, trained only on code that seven independent proof systems agree is correct.

The industry bet is scale: more parameters, more tokens, more scraped code. locallm bets the other way. Keep a training example only when it passes its tests, is proven against its specification by seven proof systems, and has a deliberately broken copy of itself caught by all seven. Then ask whether a small model built from that data does more per parameter than a model built from raw data, and than small open models such as Microsoft's Phi-4-mini.

Every number below was measured by a script in this repository, and links to the file that records it. Where the answer is not in yet, this page says so.

## The pipeline

```
problems in English, with tests (nl/, 24,748; a pool of 649, 232 of them held out)
  -> a generator model writes a specified program for each          spec_experiment.py generate
  -> keep only programs that pass their tests and copy nothing seen   spec_experiment.py tests, pool_pick.py
  -> prove each in Dafny, Verus, SPARK, Frama-C, Lean 4, Rocq, F*     run_par.py
     and require all seven to refute a deliberately broken twin
  -> the clean pool                                                  loop_dataset.py
  -> build a model from it: locallm from scratch, or a 1.5B student   loop_locallm.py, loop_train.py
  -> score every model on the 232 held-out problems                   score_heldout.py
```

A held-out answer counts as **clean** only when its tests pass and all seven proofs hold with the twin refuted. An answer that all seven prove but whose tests fail is counted separately, as **proven but wrong**: the proofs show the code meets its specification, not that the specification says what the problem asked. Held-out problems never enter a training set; `split-v3.json` fixes the split and never changes.

## Results so far

| What was measured | Result | Record |
|---|---|---|
| The same 3.2M-parameter locallm model, built from filtered data against raw data of the same size: new programs clean in all seven, of 500 written | **29 against 1** | [`t/runs/2026-09-17/`](t/runs/2026-09-17/) |
| The same loop, rerun on an M3 Max MacBook instead of the lab workstation | round 0: 25 clean and new | [`t/runs/2026-09-17/`](t/runs/2026-09-17/) |
| A 1.5B model (Qwen2.5-Coder) trained on the twins it refuted, 161 held-out problems | verified answers with a refuted twin: 9 to 15 after two rounds; test passes did not move | [`t/LOOP-CURVE.md`](t/LOOP-CURVE.md) |
| Qwen3.8-27B-FP8, temperature 0, on the 232 held-out problems | 12 clean, 7 proven but wrong | [`t/score_heldout.py`](t/score_heldout.py) |
| A locallm model built from the clean corpus, on the 232 held-out problems | **0 clean**, 188 proven but wrong | [`internal/HANDOFF-2026-09-17-rtx4080.md`](internal/HANDOFF-2026-09-17-rtx4080.md) |

**What the last row means.** The clean pool held 47 problem examples, so the model recited verified tasks it had memorized (151 exact copies) instead of solving new problems. The clean programs the filter loop writes are mostly short, loop-free near-copies of corpus tasks. Filtering works; the pool is too small. Growing it is the current work.

**A correction.** The copy check kept each task's format version, so exact copies of corpus tasks counted as new. The filtered-against-raw result was first recorded as 46 against 3; recounted, it is 29 against 1. The direction held and the effect was a third smaller. The recount is the number.

## In progress: against Phi-4-mini

No result yet (2026-09-17). On one RTX 4080:
1. qwen2.5-coder:14b (Ollama, 4-bit) writes eight answer sets over the 649-problem pool (answers to held-out problems never reach training); after pool picking, the first five hold 110, 61, 62, 65 and 63 test-passing, non-copy programs to grade.
2. The seven proof systems grade them, split between the lab workstation's CPUs and the desktop.
3. From the clean answers: a new clean pool, a locallm model and a fine-tuned 1.5B student.
4. Phi-4-mini (bf16), the untrained 1.5B, the student and locallm each answer the 232 held-out problems, and `score_heldout.py` counts clean and proven but wrong for each, next to its parameter count.

The table goes here when it exists, whichever way it comes out.

## New since 2026-09-16

- **The filter loop.** locallm rebuilds its model each round from every clean program found so far, and the new model writes the next round ([`t/loop_filter.py`](t/loop_filter.py), [`t/loop_locallm.py`](t/loop_locallm.py)).
- **A held-out benchmark with a wrong-answer column.** [`t/score_heldout.py`](t/score_heldout.py) reports tasks, tests passed, clean, and proven but wrong per answer set, over a split that never changes.
- **Only gradable answers reach the checkers.** [`t/pool_pick.py`](t/pool_pick.py) sends a proof system only answers that pass their tests and copy nothing already in the pool.
- **Local generators.** Answer sets from models served by Ollama on a 16 GB consumer GPU, not only the 27B on datacenter GPUs.
- **t lab** ([`t/lab.py`](t/lab.py)): one window with every proof check live as it runs, a tester for locallm models, and a Collect data tab that runs the whole pipeline one button per step, logged and resumable.
- **Grading across machines.** [`t/grade_lab.sh`](t/grade_lab.sh) sends answer sets to a many-core workstation over SSH and streams its checks back into t lab; [`t/grade_home.sh`](t/grade_home.sh) grades on the local CPU at the same time, and neither takes a set the other has claimed.
- **Unattended runs.** [`t/run_everything.py`](t/run_everything.py) chains generation, grading, the baselines, the pool, training and scoring, retries a failed step once, and notifies when Phi-4-mini starts and when the run ends.
- **Three machines reproduce the proof matrix.** The seven proof systems install without root on Linux (native and WSL2) and macOS; an M3 Max MacBook reproduced the committed matrix cell for cell (30 of 34 tasks in all seven, [`t/WITNESS-2026-09-16-macos-m3max.md`](t/WITNESS-2026-09-16-macos-m3max.md)).

## Run it

```
python3 t/lab.py                 # Collect data: every step as a button, in order
python3 t/run_everything.py      # or the rest of the run, unattended
```

Setup (the NVIDIA driver, the Python environment, Ollama and the seven proof systems at pinned versions) is in [`internal/HANDOFF-2026-09-17-rtx4080.md`](internal/HANDOFF-2026-09-17-rtx4080.md) and [`t/RUN-ON-LINUX.md`](t/RUN-ON-LINUX.md).

## What is in the repository

| Path | What it is |
|---|---|
| [`locallm/`](locallm/) | the model builder: a transformer trained from random weights on your own hardware |
| [`t/`](t/) | the filter: a small specification language translated into the seven proof systems (30 of 34 committed tasks agree in all seven, [`t/AGREEMENT.md`](t/AGREEMENT.md)), and every pipeline script above |
| [`nl/`](nl/) | 24,748 natural-language programming problems with tests, from four public sources |
| [`forge/`](forge/) | the earlier training pipeline that grades a model by the twins it refutes |
| [`tup/`](tup/) | a Linux distribution built from source with a receipt per step, so the machine running the proofs is accounted for |
| [`internal/`](internal/) | handoffs, the machine plan, the dated engineering log |

## Limits, stated plainly

- No model built here has beaten Phi-4-mini. That comparison is running.
- The clean pool is small, and the clean programs are short and close to their corpus. More pool, not more rounds, is what moves held-out results.
- A proof covers the specification, not the intent. That is why tests are a separate gate and proven but wrong is its own column.
- t covers integers, booleans, sequences, pairs, strings as character sequences, loops with invariants and recursive specification functions. No heap, no floats, no concurrency.

## License

Research use only: the whole repository may be used, copied, modified and redistributed for research and education, and for nothing else without written permission ([`LICENSE`](LICENSE)). Third-party material keeps its own licenses; the problem corpora under `nl/` list theirs. `locallm/` was MIT until 2026-09-15.

Copyright (c) 2026 Treston Malachi Cuzzort.
