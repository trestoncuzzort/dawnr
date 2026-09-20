# The RTX 4080 data run, 2026-09-17 (in progress)

The home desktop (Ryzen 9 7900X, 14 GB, RTX 4080 16 GB) grows the clean pool that `internal/HANDOFF-2026-09-17-rtx4080.md` calls for, then compares models built from it against Phi-4-mini on the 232 held-out problems. The running log, with every command, fix and failure, is `../NOTES-home.md`.

## What ran

- qwen2.5-coder:14b through Ollama (4-bit), eight answer sets over the 649-problem pool (`t/spec_experiment.py generate --pool v3 --prompt v3`), seed 1 at temperature 0 and seeds 2 to 8 at 0.7. From about 03:00 Ollama ran with flash attention and an 8-bit KV cache, after the first attempt ran out of memory.
- `t/pool_pick.py` kept the answers that pass their tests and copy nothing already in the pool (`answers/<tag>/grade-in/`).
- The seven proof systems graded them: seeds 1 to 6 on the lab workstation at 16 jobs, seed 8 on this desktop, seed 7 on the lab workstation (running). Each `answers/<tag>/kernels.md` is the table `run_par.py` wrote.

## Clean in all seven so far

Clean here means the task passed its tests, was not a copy, and reads `verified / refuted` in all seven columns of `kernels.md`.

| Answer set | Graded | Clean |
|---|---|---|
| s1 (temperature 0) | 110 | 34 |
| s2 | 61 | 13 |
| s3 | 62 | 15 |
| s4 | 65 | 13 |
| s5 | 63 | 12 |
| s6 | 59 | 7 |
| s7 | 57 | grading |
| s8 | 43 | 2 |
| **Total** | **463 of 520** | **96, over 50 distinct problems** |

8 of the 50 problems are held-out problems; `loop_dataset.py` keeps them out of training through `split-v3.json`, leaving 42 training problems. Later seeds mostly re-solve problems seed 1 already solved. 4 tasks are kept out of all seven by timeouts alone, which are not verdicts and will be re-graded.

## Not done yet

Phi-4-mini's held-out answers (190 of 232 written when this was recorded), the small base answers, the clean pool, the student, the locallm model, held-out grading and the score. `t/run_everything.py` is running them; the score table lands in this folder when it exists.

## Where the day ended

| | |
|---|---|
| Generations, all models | 10,099 |
| Well formed t tasks | 2,829 |
| Passing their tests | 1,989 |
| Graded in all seven | 1,433 |
| **Clean** | **238, over 80 distinct problems** |
| The training pool it makes | `loop-data/sft-r4.jsonl`, 55 examples over 55 problems (47 before), with 368 answer/broken-copy pairs |

Per accepted example: 42.4 generations, 560 s of generation, 4,522 s of proof (cells run in parallel, so the clock time is far lower). `t/yield.py` prints this table; `yield-2026-09-17.txt` is the run of it that these numbers come from.

Two results of the day worth more than the counts:

- **Self-repair does not work.** 110 answers that passed their tests but were not clean went back to the model with the seven verdicts: 2 came back clean, 1.8 percent, against about 21 percent for fresh samples from the same model. On seed 1, 4 improved and 8 got worse.
- **The pool grew by 8 problems, not by hundreds.** A day of generation across two model families added 10 problems (2 from HumanEval) and many more solutions to problems already held. What caps the corpus is what the lowerings can express, not how much is generated: nested loops abstain in Rocq, Lean and F\*. That is ROADMAP WS-20.

Machine notes for anyone repeating this: the lab workstation grades at 64 cells over 4 answer sets at once with its working set on a RAM disk, and Ollama must run without flash attention and without an 8-bit KV cache, which together cost 17 to 30 times the speed on a mixture-of-experts model.

## The score, 2026-09-17

| Model | Parameters | Well formed t | Tests pass | Clean | Proven but wrong |
|---|---|---|---|---|---|
| Qwen3.8-27B-FP8 | 27B | 116 | 81 | 12 | 7 |
| Phi-4-mini, bf16 | 3.8B | 12 | 6 | 3 | 1 |
| Qwen2.5-Coder 1.5B, untrained | 1.5B | 39 | 13 | 3 | 8 |
| The student: the same 1.5B trained on this pool | 1.5B | 37 | 12 | 3 | 8 |
| locallm r4, built from scratch on this pool | 10.9M | 209 | 2 | 2 | 204 |
| locallm r0, the previous pool | 4.9M | 199 | 0 | 0 | 188 |

Over the 232 held-out problems of `split-v3.json`, which never enter any training set. Clean means the tests
pass and all seven proof systems verify the program with its deliberately broken copy refuted.

**The student ties Phi-4-mini at 3 of 232 with less than half the parameters, and does not beat it.** Training
on this pool did not move it either: the same model untrained also reads 3. 55 problems is too small to change
a pretrained model.

**locallm went from 0 to 2**, the first clean held-out answers from a model built from scratch here. Its 204
proven-but-wrong answers are the honest counterweight: it writes specifications it can satisfy rather than the
one the problem asked for, and that column is what this project exists to count.

**The 27B leads by four times.** At this pool size scale wins, and the pool is what the lowerings cap: see
`ROADMAP.md` WS-20, first move.
