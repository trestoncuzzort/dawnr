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
