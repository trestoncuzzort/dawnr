# Handoff for Antigravity, 2026-09-17: running the RTX 4080 data run

You are helping the user run `internal/HANDOFF-2026-09-17-rtx4080.md` on their home desktop. That file is the plan, and this file is the machine state plus how to help. Read the plan's sections 1 to 6 before acting. Do not redesign the experiment: the user returns to Claude for judgement calls.

## The goal in one paragraph

**The target is Microsoft Phi-4-mini (3.8B).** Win means: on the 232 held-out problems of `split-v3.json`, a model built from t-filtered data gets more clean answers than Phi-4-mini, either outright or per parameter, and is less often proven but wrong. Only `score_heldout.py` decides this. Phi-4-mini must run in bf16 through `loop_generate.py` (plan section 5); if it has to fall back to Ollama's 4-bit build, record that, because a quantized Phi is a weaker opponent and a win against it counts for less.

locallm builds small models from scratch, and t filters what they learn from. The last locallm model scored 0 of 232 on held-out problems because the clean pool had only 47 problem examples, so it memorized. This run makes the pool bigger: Ollama (qwen2.5-coder:14b) writes t answers to 649 problems, `pool_pick.py` and the seven checkers keep only the clean ones, locallm and a 1.5B student train on that pool, and `score_heldout.py` compares them with Phi-4-mini. Ollama is only a data generator. It is not the model being built.

## Machine state (2026-09-17)

- Ubuntu 26.04.1, GNOME session (not LXQt, despite Lubuntu leftovers), Python 3.14.4.
- RTX 4080, NVIDIA driver 595.91.07, `nvidia-smi` works.
- Repo at `~/tup`. `git lfs pull` done.
- `~/.venv-t` created, torch install in progress (cu128 has a cp314 wheel: torch 2.11.0). Verify with
  `~/.venv-t/bin/python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"`.
- Ryzen 9 7900X (24 threads) but only 14 GB RAM. 16 GB swap at /data/swapfile. Collect data allows one gpu step plus one cpu step (checkers drop to 6 jobs then). If memory runs out, stop the checkers first.
- Second SSD mounted at `/data` (ext4, in fstab). `~/.profile` sets `OLLAMA_MODELS=/data/ollama` and `HF_HOME=/data/huggingface`; the Ollama Serve launcher also sets `OLLAMA_MODELS`. Ollama's installer starts its own system service (other user, other model folder, same port): run `sudo systemctl disable --now ollama` right after installing, then use the launcher.
- Not done yet: `t/out` data copy and the 12 and 0 check (plan section 1), Ollama, the seven checkers.
- Dock and desktop launchers: tup Terminal, t Lab (`~/.local/bin/tup-lab`), Ollama Serve (`~/.local/bin/tup-ollama`), GPU Monitor, tup Handoff.

## The Collect data tab (use this, not pasted commands)

`t/lab.py` (the t Lab launcher) has a Collect data tab with every step of the plan as a row: pick a row, press Run, read the output below. A row turns done when its output files exist, so the tab is the source of truth for where the run stands. Each run is logged to `t/runs/<date>/logs/<step>.log`, and start, end, exit code and minutes are appended to `t/runs/<date>/NOTES-home.md`. Jobs run in the background and survive closing the window; Stop kills a job, and Generate and Grade skip seeds already finished, so Run again resumes. Your job: when a row reads failed, read its log, fix the environment, and tell the user to press Run again. Add a line to NOTES-home.md for each fix. The one row it cannot do alone is installing the seven checkers (before Check the checkers): do that with the user from `t/RUN-ON-LINUX.md`.

## Order of work

1. Finish plan section 1: torch check, then the `t/out` copy block. `score_heldout.py` must print 12 and 0 in the clean column. If not, stop and report.
2. Plan section 2: install Ollama, start it with the Ollama Serve launcher, `ollama pull qwen2.5-coder:14b`, then the eight-seed loop. Run long jobs with `nohup ... > ~/gen-sN.log 2>&1 &` so they survive a closed terminal.
3. Checkers (plan section 1, `t/RUN-ON-LINUX.md`) can be installed while generation runs, since they use the CPU. The install counts only at 30 of 34 in all seven.
4. Plan sections 3 to 6 in order, one at a time.

## How to help

- Give the user one command block at a time and say what a good result looks like.
- When something fails, read the last lines of the log and fix the environment (missing apt package, PATH, version). Do not edit t's Python scripts, prompts, pool, split or thresholds. Changes to those are Claude's call.
- Python 3.14 is newer than the lab workstation's. If a pip package has no 3.14 wheel, suggest `uv` or a 3.12 venv, and note it for the user.
- Keep a running log in `~/tup/t/runs/<date>/NOTES-home.md`: each command, how long it took, the counts it printed, and any fix applied. Claude reads this file when the user comes back, so it saves them re-explaining.
- Committing: the user has asked you to commit and push `t/lab.py` (the Collect data tab), this file and `t/runs/<date>/NOTES-home.md` and `t/runs/<date>/logs/`. Do it now as one commit, and again with the results the way plan section 6 lays them out. Run `git status` first and never add `t/out/`, `kernels/` folders or adapters. Commit only after the user confirms the message; end it with a line naming Antigravity as co-author.

## Stop and send the user back to Claude when

- A count looks wrong (for example the 12 and 0 check fails, a seed yields almost nothing in `grade-in/`, or the checker matrix is not 30 of 34).
- The next step would change the experiment: a different model, prompt, temperature, pool, split or training setting.
- A step fails twice after an environment fix.
- Sections 4 and 5 are done and the score table exists. Interpreting it is the point of the run.

## Rules from the repository (do not break)

- A number goes in a file only if it was measured, with the command that measured it.
- Clean means all three: tests pass, verified in all seven with the broken copy caught, not a copy of training data.
- Held-out problems never enter a training set. `split-v3.json` never changes.
- A checker timeout is not a verdict. Re-grade timeouts before calling a count final.
- No em-dashes in repository prose.
