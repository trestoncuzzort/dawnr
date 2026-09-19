# Working in this repository

Read this first, then `internal/HANDOFF-2026-09-19.md`, which is the live state of the work.

## What this is

`t` is a small specification language. A program written in it is lowered into **seven independent proof
systems** — Dafny, Verus, SPARK, Frama-C, Lean 4, Rocq, F\* — and every program is paired with a deliberately
broken twin that all seven must refute at a concrete input. On top of that sits a data pipeline: a model
answers a natural-language problem in t, the answer is kept only if it passes the problem's own tests and all
seven verify it with the twin refuted, and the surviving answers train a small model. The question the project
exists to answer is whether a model built from that data does more per parameter than one built from raw code.

`README.md` is the honest public summary, including what has been ruled out and what this project got wrong.

## The rules that matter

1. **Measure before you claim.** Every number in this repository links to the script that produced it. If you
   assert something, run the thing that would falsify it first. Two beliefs written in this codebase were
   wrong in ways nobody noticed for weeks, and both were caught by a number that did not fit.
2. **An honest refusal beats a false verdict.** A lowering that cannot express something must abstain by name.
   Never weaken a specification, drop an invariant, or let a tactic chain succeed without closing its goal.
   This has gone wrong here — Lean once left goals for `sorryAx` to discharge, and Frama-C once emitted an
   invariant of its own that was false.
3. **Write predictions before runs, with the number that falsifies them.** See
   `t/PREDICT-2026-09-18-round6.md` and `t/PREREG-2026-09-18-constrained.md`. Two of the three predictions in
   the first file were wrong; the file says so.
4. **Report the failure plainly, then what it bought.** Failures are the instrument here, not something to
   soften. A report that stops at the bad number throws away the useful half.
5. **No assistant attribution anywhere** — not in commits, docs or comments. Commit messages explain what was
   measured and why, in plain prose.
6. **This repository is public.** No personal or institutional identifiers: no home directories naming an
   account, no hostnames, no credentials. `t/lab-workstation.conf` holds the only machine address and is
   gitignored.

## Where things are

| Path | What |
|---|---|
| `internal/HANDOFF-2026-09-19.md` | **start here** — current state, what is running, the traps that have cost hours |
| `internal/ROADMAP-LOG.md` | the roadmap of record: every hurdle, its measurement, its DONE WHEN |
| `ROADMAP.md` | the public face of the same, updated as things finish |
| `t/RUN-NEXT.md` | the recipe for the next pipeline run, with the number behind each choice |
| `t/` | the language, the seven lowerings, and every pipeline script |
| `t/twins/` | 426 verified programs each paired with a near-miss and the input that separates them |
| `locallm/` | a transformer trained from random weights on the filtered data |
| `internal/CODEX-SKILLS.md` | index of the skill library pulled from the lab workstation |

## Running anything

All compute runs on the lab workstation, never the home desktop. `t/lab-workstation.conf` (gitignored) holds
`T_LAB=user@host`; the python with the whole stack is `~/.venv-vllm/bin/python` there. The four GPUs are
**shared with another user** and must be given back the moment they ask: `bash t/lab_gpu.sh stop` clears every
process of ours off them in seconds, and every answer is written to its own file so nothing in flight is lost.

Kernels need their PATH or Verus silently reports MALFORMED for every cell:

    export PATH="$HOME/.cargo/bin:$HOME/.opam/default/bin:$HOME/.elan/bin:$HOME/.local/fstar/fstar/bin:$HOME/.local/gnatprove/gnatprove-x86_64-linux-16.1.0-1/bin:$HOME/.local/verus/verus-x86-linux:$PATH"

Then `python3 t/preflight.py` before a run, and `python3 t/lab.py` for a window that watches (it has no Run
buttons on purpose — steps are driven from a terminal, and a second copy of a running step loses a night).

`internal/HANDOFF-2026-09-19.md` section 4 has the pipeline command by command, and section 5 lists seven
ideas already measured and closed. Do not spend a night re-testing those.
