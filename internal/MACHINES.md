# Machines

Where the project runs from 2026-09-17 on, and what each machine is for. Numbers measured on the lab workstation are marked as such; everything about the two new machines is a plan until it is measured there.

## The three machines

| Machine | Memory | GPU | CPU | Status |
|---|---|---|---|---|
| The lab workstation | 502 GB | 4 x RTX 6000 Ada, 48 GB each, shared with other users | 120 threads | All seven kernels installed. Work stopped 2026-09-16 at the lab's request. |
| Home desktop | to measure | RTX 4080, 16 GB | to measure | Lubuntu, minimal installation, native (2026-09-17). Kernels to install; setup in `internal/HANDOFF-2026-09-17-rtx4080.md`. |
| MacBook Pro, M3 Max | 36 GB unified | Apple M3 Max GPU (Metal, PyTorch MPS) | 14 cores in the 36 GB configuration | All seven kernels installed 2026-09-16; the committed matrix reads 30 of 34, every cell as the Dell's (`t/WITNESS-2026-09-16-macos-m3max.md`). |

## What each machine is for

**Home desktop (RTX 4080).** The CUDA work:
- Generation with a model that fits 16 GB: a 4-bit 14B, or the 1.5B student. The 27B at FP8 needs about 28 GB and does not fit.
- Training the student (QLoRA on Qwen2.5-Coder-1.5B, `t/loop_train.py`), which fit well under 16 GB on the lab workstation.
- The Phi-4-mini baseline in bf16 (about 8 GB).
- locallm builds. Its README's measured experiments ran on an RTX 4080.

**MacBook Pro (M3 Max, 36 GB).**
- locallm builds on the Apple GPU (the locallm README reports its Dafny corpus example on Apple silicon).
- `t/lab.py`, the monitor and model tester.
- Inference with larger 4-bit models through unified memory (a 4-bit 27B is about 16 GB), a second generator beside the desktop.
- Kernel grading, at a fraction of the lab workstation's rate.

## The verifiers

The seven kernels run on the CPU, so grading speed follows core count. The lab workstation graded at 8 to 16 cell jobs, each cell running up to six kernel calls. With 14 or so cores, start with 2 jobs and measure. Grade only what can pass the filter: `t/runs/2026-09-16/scripts/pick.py` sends only tasks that pass their tests and are not copies to the kernels.

Versions on the lab workstation (from `t/AGREEMENT.md`), the reference for every new install:

| Kernel | Version |
|---|---|
| dafny | 4.11.0 |
| verus | 0.2026.08.30 |
| spark | gnatprove FSF 16.1.0, Why3 1.8.2 |
| framac | 33.0 (Arsenic), alt-ergo 2.4.3 |
| lean | 4.33.1 |
| rocq | 9.2 |
| fstar | 2026.08.30 |

All seven install natively on macOS arm64 (`t/RUN-ON-MACOS.md`, the 2026-09-16 section for what differs on a Mac with Xcode 27); the desktop's OS is not yet checked. An install counts when `python3 t/run_par.py` on the committed tasks matches `t/AGREEMENT.md` (30 of 34 in all seven); the MacBook Pro did on 2026-09-16 at `--jobs 8`, with one SPARK load timeout re-measured alone.

## Picking up the loop

Everything the loop needs is on GitHub (`https://github.com/trestoncuzzort/tup.git`):
- `t/loop_filter.py`: locallm builds a model, t keeps the clean programs, the next model is built from the clean pool.
- `t/loop_locallm.py`: the clean corpus, and a model's answers to held-out problems graded like any model's.
- `t/lab.py`: one window for runs and model tests.
- `t/runs/2026-09-16/`: the data and scripts of the first measurements, including every model locallm built.

The next measurement that matters is the size-matched comparison on held-out problems with tests. It needs more problem examples in the clean pool, which is what generation on the desktop is for.

## Running the lab app on the Mac

`t/lab.py` is one dark window with two tabs: Live checks (every check as it runs, in plain words) and Test a model (pick a model locallm built, choose the checks, press Run).

1. Python 3.10 or newer with Tk. The python.org installer includes Tk. With Homebrew: `brew install python python-tk`.
2. For model tests, a virtual environment with torch: `python3 -m venv ~/.venv-t && ~/.venv-t/bin/pip install torch`.
3. From the repository root: `~/.venv-t/bin/python t/lab.py`.

The models locallm built on 2026-09-16 are in `t/runs/2026-09-16/` (Git LFS; run `git lfs pull` after cloning) and show up in the model list. The readable, rules and new checks work with Python alone. A "Proven by" check needs that checker installed; Dafny is the one to install first. The Live checks tab fills in whenever `t/run_par.py` runs with `T_WATCH` set, which the Test tab does by itself.
