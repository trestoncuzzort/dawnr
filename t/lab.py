#!/usr/bin/env python3
"""t/lab.py -- one window to watch the checks and the models locallm
builds, with every word explained (2026-09-16).

It was "one dark window" until 2026-09-20. The colours, the fonts, the
spacing and the marks now come from locallm/look.py, which both halves of
the window import, so it is light by default and follows the operating
system where it can read it (Windows today; LOCALLLM_THEME=dark|light
everywhere, and that is the only way to dark on Linux so far).

locallm builds small AI models from scratch. The models write programs in
t. Seven independent checkers each try to prove a program does what it
promises, and try to catch a deliberately broken copy of it. A program is
clean only when all seven prove it and catch the broken copy.

FIVE TABS, AND WHAT LEADS CHANGED ON 2026-09-20. Home, Train, Proof,
Collect data, AI. Home is locallm/home.py -- point it at your own text and
get a model, in four numbered steps -- and it is what the window opens on,
because that is the thing locallm claims to do; Train is the full training
surface (locallm/studio.py) with every setting on it. The three pages about
the seven checkers are behind Proof, which has a strip of its own: they were
three of six top-level tabs and the paragraph explaining proof kernels sat
above every page, so the machinery was the first thing a stranger met. Proof
is where it is now explained.

Proof -> Live checks: every check as it runs (run_par.py writes a start and
an end line to the file named by T_WATCH, and t/paths.py names the file when
that is unset), each result in plain words, and a loop's rounds when a loop log
is chosen.

Proof -> Test a model: pick a model folder locallm wrote, say how many
programs it should write, pick the checks, press Run. Each row is one
program; click it to read the program.

Proof -> Results: what every answer set counted out to.

--page takes any page name, the three behind Proof included, and the View
menu lists every one of them.

Runs on macOS, Windows and Linux with Python 3.10 or newer and Tk (on macOS
the python.org installer includes Tk; with Homebrew, brew install
python-tk). Model tests also need torch, the one locallm uses. Collect data
presses shell recipes rather than reading files, so that one page needs a
POSIX shell and says so when there is none; everything else here is files:

    python3 t/lab.py
"""

from __future__ import annotations

import copy
import json
import os
import queue
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

HERE = Path(__file__).resolve().parent
TUP = HERE.parent
LOCALLM = TUP / "locallm"
sys.path.insert(0, str(HERE))
sys.path.insert(1, str(LOCALLM))

import fuzz_lower                                               # noqa: E402
# The design system, from locallm/, at module scope -- unlike studio.py, which is
# imported inside build_train because it pulls in torch. look.py imports math, os
# and typing and asks tkinter a question only when a font has to be resolved, so
# it costs this window nothing on a machine with no training stack.
import look                                                     # noqa: E402
import paths                                                    # noqa: E402
import proc                                                     # noqa: E402
import spec_experiment as se                                    # noqa: E402
import surface                                                  # noqa: E402
from lab_status import count_set as count_answer_set             # noqa: E402

# Both of these fell back to ~/.cache, which is a folder only Linux has agreed to: on Windows it
# made C:\Users\<name>\.cache\t-lab, which nothing there cleans up, and on a USB stick it wrote
# to the borrowed machine instead of the stick. t/paths.py picks the place per platform and prefers
# locallm-data/ beside the program when that can be written to; T_WATCH and T_LAB_SCRATCH still win,
# and T_WATCH has to, because the lab workstation sets it and run_par.py is told the same value below.
EVENTS = paths.state_path("T_WATCH", "watch", "events.jsonl")
SCRATCH = paths.state_path("T_LAB_SCRATCH", "scratch")
KERNELS = ["dafny", "verus", "spark", "framac", "lean", "rocq", "fstar"]
CHECKER = {"dafny": "Dafny", "verus": "Verus", "spark": "SPARK", "framac": "Frama-C",
           "lean": "Lean", "rocq": "Rocq", "fstar": "F*"}
KERNEL_PATH = os.pathsep.join(str(Path.home() / p) for p in (
    ".cargo/bin", ".opam/default/bin", ".elan/bin", ".local/fstar/fstar/bin",
    ".local/gnatprove/gnatprove-x86_64-linux-16.1.0-1/bin", ".local/verus/verus-x86-linux"))
# Can this machine run the Collect data steps at all? Every step is a shell recipe -- bash -lc, ssh, rsync,
# nvidia-smi, systemctl, sudo -- and a missing program is not a non-zero exit, it is an exception: "The most
# common exception raised is OSError. This occurs, for example, when trying to execute a non-existent file"
# (docs.python.org/3/library/subprocess.html). Off Linux that turned a two-second poll into a traceback twice a
# second with nothing on screen, so the capability is asked once, here, instead of guessed at each call site.
# shutil.which is what that same page points at for an unqualified name on PATH. macOS passes this test and
# should: bash, ssh, rsync and python3 are all there, and the parts that are Linux's alone (systemctl,
# nvidia-smi) now say so where they are used rather than raising.
HOST_CAN_RUN_STEPS = os.name == "posix" and shutil.which("bash") is not None

# the data run of internal/HANDOFF-2026-09-17-rtx4080.md, one button per step; commands run from the repo root
# The python that has torch, transformers, xgrammar, peft and bitsandbytes. Every step now runs on the lab
# workstation (the operator's instruction, 2026-09-18), where that is ~/.venv-vllm; the desktop's ~/.venv-t is
# left behind. These commands are the recipe a person runs there over ssh -- this window only watches.
PY = os.environ.get("T_PY", "~/.venv-vllm/bin/python")
SE = "t/out/spec-experiment"
GEN = "qwen2.5-coder-14b-v3-s"
HELDOUT = "phi4-mini-v3 qwen15b-base-v3 student-r4-v3 locallm-r4"
POOL_TAGS = "qwen3.8-27b-fp8 qwen3.8-27b-fp8-v3 qwen3.8-27b-fp8-v3-s2 " + " ".join(f"{GEN}{i}" for i in range(1, 9))
EVAL = "--pool v3 --prompt v3 --ids-file t/out/loop/eval-ids.txt"
GEN2 = "deepseek-coder-v2:16b"      # a second generator family, for answers the first one does not write
GEN2_TAG = "deepseek-coder-v2-16b-v4-s"
HE = "qwen2.5-coder-14b-he-s"       # the first generator on pool v4's HumanEval problems
QWEN_FIX = " ".join(f"{GEN}{i}-fix1" for i in range(1, 9))
GROWTH_TAGS = " ".join([f"{HE}{i}" for i in range(1, 9)] + [f"{GEN2_TAG}{i}" for i in (1, 2)])
GROWTH_FIX = " ".join(f"{t}-fix1" for t in GROWTH_TAGS.split())
# every answer set whose clean answers train a model: the 27B's, then everything this run wrote
SAMPLE_TAGS = ("$(cd t/out/spec-experiment && ls -d qwen3.8-27b-fp8 qwen3.8-27b-fp8-v3 qwen3.8-27b-fp8-v3-s2 "
               "qwen2.5-coder-14b-* qwen3-coder-30b-* deepseek-coder-v2-16b-* 2>/dev/null)")
# (key, title, what it does and what good looks like, command, done when this succeeds, uses: gpu/cpu/sudo/"")
STEPS = [
    ("preflight", "Check before running", "Everything that could make a round's numbers wrong, checked first: "
     "the seven checkers present at the versions AGREEMENT.md was measured with, no held-out problem in the "
     "training set, nothing counted clean resting on a flake or a timeout, no answer in the pool whose "
     "specification disagrees with its problem, unique copy-check keys, room on both disks. Run it before "
     "every round; it says what to fix.",
     "python3 t/preflight.py", "python3 t/preflight.py >/dev/null 2>&1", ""),
    ("packages", "Python packages", "Installs the training libraries into ~/.venv-t.",
     f"{PY} -m pip install transformers peft trl datasets accelerate bitsandbytes safetensors",
     f"{PY} -c 'import transformers, peft, trl, datasets, accelerate, bitsandbytes'", ""),
    ("data", "Committed data", "Copies the 2026-09-16 answers and split into t/out. Good: the score table's clean "
     "column reads 12 and 0.",
     "mkdir -p t/out/spec-experiment t/out/loop && cp -r t/runs/2026-09-16/27b-answers/* t/out/spec-experiment/ && "
     "cp -r t/runs/2026-09-16/heldout-locallm-r0 t/out/spec-experiment/locallm-r0 && "
     "cp t/runs/2026-09-16/loop-data/{split-v3.json,sft-r3-27b.jsonl,pairs-r3-27b.jsonl} t/out/loop/ && "
     "python3 -c \"import json; print('\\n'.join(map(str, json.load(open('t/out/loop/split-v3.json'))['eval_ids'])))\" "
     "> t/out/loop/eval-ids.txt && python3 t/score_heldout.py qwen3.8-27b-fp8-v3 locallm-r0 && "
     "for T in qwen3.8-27b-fp8 qwen3.8-27b-fp8-v3 qwen3.8-27b-fp8-v3-s2; do python3 t/pool_pick.py t/out/spec-experiment/$T --control 25; done",
     "test -s t/out/loop/eval-ids.txt && test -s t/out/pool-keys.txt", ""),
    ("ollama-install", "Install Ollama", "Opens a terminal because it asks for your password. Turns off Ollama's own "
     "service afterwards so the next step owns the port.",
     "curl -fsSL https://ollama.com/install.sh | sh && sudo systemctl disable --now ollama",
     "command -v ollama", "sudo"),
    ("ollama-serve", "Start Ollama", "Keeps running in the background, also after this window closes. Models live in "
     "/data/ollama. Flash attention and an 8-bit KV cache keep 4 parallel answers inside the 16 GB card, "
     "so nothing spills into the 14 GB of RAM.", "OLLAMA_MODELS=${OLLAMA_MODELS:-/data/ollama} OLLAMA_NUM_PARALLEL=4 OLLAMA_FLASH_ATTENTION=1 OLLAMA_KV_CACHE_TYPE=q8_0 exec ollama serve",
     "curl -sf http://127.0.0.1:11434/ >/dev/null", ""),
    ("pull", "Download qwen2.5-coder:14b", "About 9 GB. Needs Ollama started.", "ollama pull qwen2.5-coder:14b",
     # on disk, not through the server: a pulled model stays pulled while Ollama is stopped for a GPU step
     'test -e "${OLLAMA_MODELS:-/data/ollama}/manifests/registry.ollama.ai/library/qwen2.5-coder/14b" || '
     "ollama list 2>/dev/null | grep -q 'qwen2.5-coder:14b'", ""),
    ("generate", "Write answers, 8 seeds", "Hours. Seed 1 at temperature 0, seeds 2 to 8 at 0.7. A finished seed is "
     "skipped, so Stop and Run again resumes. Good: each seed puts tasks in grade-in/.",
     f"for S in 1 2 3 4 5 6 7 8; do T={GEN}$S; D={SE}/$T; [ -d $D/grade-in ] && continue; TEMP=0.7; [ $S = 1 ] && TEMP=0; "
     "echo \"== seed $S\"; python3 t/spec_experiment.py generate --model qwen2.5-coder:14b --tag $T --pool v3 --prompt v3 "
     "--seed $S --temperature $TEMP --num-ctx 8192 --num-predict 3072 --timeout 1800 --jobs 4 && "
     "python3 t/spec_experiment.py extract --model $T --pool v3 && python3 t/spec_experiment.py tests --model $T --pool v3 && "
     "python3 t/pool_pick.py $D --control 25 && ls $D/grade-in | wc -l || exit 1; done",
     f"for S in 1 2 3 4 5 6 7 8; do [ -d {SE}/{GEN}$S/grade-in ] || exit 1; done", "gen"),
    ("matrix", "Check the checkers", "On the lab workstation, where all grading runs: regrades the 34 committed tasks. "
     "Good: 30 of 34 in all seven, as in t/AGREEMENT.md. Table comes back to t/out/AGREEMENT-lab.md.",
     "bash t/grade_lab.sh matrix", "test -s t/out/AGREEMENT-lab.md", "lab"),
    ("grade", "Grade what is ungraded", "Every answer set with tasks waiting and no table yet, in one "
     "pass on the lab workstation (four sets at a time, work in RAM). A new answer set needs no new step: "
     "it is graded because it is there. Checks show on Live checks.",
     "bash t/grade_lab.sh pending",
     f"! ls -d {SE}/*/grade-in >/dev/null 2>&1 || ! (cd {SE} && for d in */; do t=${{d%/}}; "
     "[ -d \"$t/grade-in\" ] || continue; [ -s \"$t/kernels.md\" ] || exit 0; done; exit 1)", "lab"),
    ("more-problems", "New problems and a second model", "Needs Ollama started. The 88 HumanEval problems of pool v4 "
     f"(8 answer sets, as for MBPP), then {GEN2} over all 737 problems (seed 1 at temperature 0, seed 2 at 0.7).",
     f"for S in 1 2 3 4 5 6 7 8; do T={HE}$S; D={SE}/$T; [ -d $D/grade-in ] && continue; TEMP=0.7; [ $S = 1 ] && TEMP=0; "
     "python3 t/spec_experiment.py generate --model qwen2.5-coder:14b --tag $T --pool v4 --min-id 100000 --prompt v3 "
     "--seed $S --temperature $TEMP --num-ctx 8192 --num-predict 3072 --timeout 1800 --jobs 4 && "
     "python3 t/spec_experiment.py extract --model $T --pool v4 && python3 t/spec_experiment.py tests --model $T --pool v4 && "
     f"python3 t/pool_pick.py $D --control 25 || exit 1; done && ollama pull {GEN2} && "
     f"for S in 1 2; do T={GEN2_TAG}$S; D={SE}/$T; [ -d $D/grade-in ] && continue; TEMP=0.7; [ $S = 1 ] && TEMP=0; "
     f"python3 t/spec_experiment.py generate --model {GEN2} --tag $T --pool v4 --prompt v3 "
     "--seed $S --temperature $TEMP --num-ctx 6144 --num-predict 2048 --timeout 1800 --jobs 2 && "
     "python3 t/spec_experiment.py extract --model $T --pool v4 && python3 t/spec_experiment.py tests --model $T --pool v4 && "
     "python3 t/pool_pick.py $D --control 25 || exit 1; done",
     f"for T in {GROWTH_TAGS}; do [ -d {SE}/$T/grade-in ] || exit 1; done", "gen"),
    ("spec-check", "Check the specifications", "The gate the provers do not give: each accepted answer's ensures "
     "against the problem's own solution, on arguments shaped like the problem's own examples. A disagreement is "
     "an answer that passed its tests, all seven proofs and a refuted twin and still does not say what the "
     "problem asked. Writes t/SPEC-CHECK-2026-09-18.md.",
     "python3 t/spec_check.py --n 100 --pool v4", "test -s t/SPEC-CHECK-2026-09-18.md", ""),
    ("pool", "Build the clean pool", "Every answer set that is not a held-out one, over split-v4 (split-v3's held-out "
     "problems unchanged, plus HumanEval as training problems). Good: many more problems than the 47 of r3.",
     f"python3 t/loop_dataset.py --from-samples {SAMPLE_TAGS} --split t/out/loop/split-v4.json --min-kernels 7 "
     "--out-suffix r4 && wc -l t/out/loop/sft-r4.jsonl t/out/loop/pairs-r4.jsonl",
     "test -s t/out/loop/sft-r4.jsonl", ""),
    ("phi", "Phi-4-mini answers", "The model to beat, in bf16, on the 232 held-out problems. If it fails, go back to "
     "deciding, before using a 4-bit Phi.",
     f"{PY} t/loop_generate.py --adapter none --base microsoft/Phi-4-mini-instruct --tag phi4-mini-v3 {EVAL} --max-new 3072",
     f"test $(ls {SE}/phi4-mini-v3/raw 2>/dev/null | wc -l) -ge 232", "gpu"),
    ("base", "Small base answers", "The untrained 1.5B, the starting point of the student.",
     f"{PY} t/loop_generate.py --adapter none --tag qwen15b-base-v3 {EVAL}",
     f"test $(ls {SE}/qwen15b-base-v3/raw 2>/dev/null | wc -l) -ge 232", "gpu"),
    ("train", "Train the student", "The 1.5B trained on the clean pool.",
     # --max-len 4608: the prompt alone is about 3,100 tokens (the few-shot grammar) and the default 1024
     # dropped every pair as fully truncated, so the preference phase got nothing (2026-09-17)
     f"{PY} t/loop_train.py --sft t/out/loop/sft-r4.jsonl --pairs t/out/loop/pairs-r4.jsonl --sft-first "
     "--max-len 4608 --out t/out/loop/adapter-r4",
     "test -s t/out/loop/adapter-r4/adapter_model.safetensors", "gpu"),
    ("student", "Student answers", "", f"{PY} t/loop_generate.py --adapter t/out/loop/adapter-r4 --tag student-r4-v3 {EVAL}",
     f"test $(ls {SE}/student-r4-v3/raw 2>/dev/null | wc -l) -ge 232", "gpu"),
    ("locallm", "Build a locallm model", "From scratch, on the clean pool, then its held-out answers.",
     "python3 t/loop_locallm.py corpus --base t/runs/2026-09-16/loop-data/corpus.txt --sft t/out/loop/sft-r4.jsonl "
     f"--out t/out/loop-locallm/corpus-r4.txt && {PY} t/loop_locallm.py train --corpus t/out/loop-locallm/corpus-r4.txt "
     f"--model t/out/loop-locallm/model-r4 && {PY} t/loop_locallm.py generate --temperature 0.5 --model t/out/loop-locallm/model-r4 --tag locallm-r4",
     f"test $(ls {SE}/locallm-r4/raw 2>/dev/null | wc -l) -ge 232", "gpu"),
    ("grade-heldout", "Grade held-out answers", "Every extracted task this time, so proven but wrong can be "
     "counted. Extract and tests run here, the checkers on the lab workstation.", "bash t/grade_lab.sh heldout",
     f"for T in {HELDOUT}; do [ -s {SE}/$T/kernels.md ] || exit 1; done", "lab"),
    # Round 5: the loop feeding on its own failures. The models answer the TRAINING problems, those answers are
    # graded, and what they get wrong there (proven but wrong, or tests failing) becomes the rejected side of the
    # next preference set. Held-out problems are never touched: their failures cannot be used at all.
    ("apps", "APPS problems, the pool's ceiling", "The 2,266 APPS problems whose own examples t can express, "
     "answered on whichever machine has a generator: this desktop through Ollama, the lab workstation through "
     "vLLM on its four cards (the AI tab starts and stops that one). This is the move that adds problems rather "
     "than more answers to the ones already held: pool v5 is 3,003 problems, 2,771 of them training, the "
     "held-out 232 unchanged.",
     "for S in 1 2; do T=qwen2.5-coder-14b-apps-s$S; D=" + SE + "/$T; [ -d $D/grade-in ] && continue; "
     "TEMP=0.7; [ $S = 1 ] && TEMP=0; "
     "python3 t/spec_experiment.py generate --model qwen2.5-coder:14b --tag $T --pool v5 --min-id 200000 "
     "--prompt v3 --seed $S --temperature $TEMP --num-ctx 8192 --num-predict 2048 --timeout 1800 --jobs 4 && "
     "python3 t/spec_experiment.py extract --model $T --pool v5 && "
     "python3 t/spec_experiment.py tests --model $T --pool v5 && "
     "python3 t/pool_pick.py $D --control 25 || exit 1; done && "
     "T=deepseek-coder-v2-16b-apps-s1; D=" + SE + "/$T; [ -d $D/grade-in ] || { "
     "python3 t/spec_experiment.py generate --model deepseek-coder-v2:16b --tag $T --pool v5 --min-id 200000 "
     "--prompt v3 --seed 1 --temperature 0 --num-ctx 6144 --num-predict 2048 --timeout 1800 --jobs 2 && "
     "python3 t/spec_experiment.py extract --model $T --pool v5 && "
     "python3 t/spec_experiment.py tests --model $T --pool v5 && "
     "python3 t/pool_pick.py $D --control 25; }",
     # 2026-09-18: this read not-done for a day after the work was finished, because it asked for three answer
     # sets on THIS desktop and the problems were answered on the lab workstation instead, by the 30B through
     # vLLM. What the step is for is that every APPS problem has an answer somewhere, so that is what it asks
     # now: 2,200 of the pool's 2,266, counted over every APPS tag on this machine.
     "python3 -c \"import json,glob,sys; "
     "ids={int(k) for f in glob.glob('" + SE + "/*apps*/extract.json') for k in json.load(open(f))}; "
     "print(len(ids),'APPS problems answered'); sys.exit(0 if len(ids)>=2200 else 1)\"", "gen"),
    ("r5-answers", "Round 5: answer the training problems", "The student and locallm answer the 417 training "
     "problems, so their own failures can be graded and used. Held-out problems are not touched.",
     f"{PY} t/loop_generate.py --adapter t/out/loop/adapter-r4 --tag student-r4-train --pool v3 --prompt v3 "
     "--ids-file t/out/loop/train-ids.txt && "
     f"{PY} t/loop_locallm.py generate --temperature 0.5 --model t/out/loop-locallm/model-r4 --tag locallm-r4-train "
     "--ids-file t/out/loop/train-ids.txt || true",
     f"test $(ls {SE}/student-r4-train/raw 2>/dev/null | wc -l) -ge 417", "gpu"),
    ("r5-pool", "Round 5: pool and pairs", "Rebuilds the pool with the new clean answers and the new negatives.",
     f"python3 t/loop_dataset.py --from-samples {SAMPLE_TAGS} student-r4-train locallm-r4-train "
     "--split t/out/loop/split-v5.json --min-kernels 7 --out-suffix r5 && "
     "wc -l t/out/loop/sft-r5.jsonl t/out/loop/pairs-r5.jsonl",
     "test -s t/out/loop/sft-r5.jsonl", ""),
    ("r5-locallm", "Round 5: a bigger locallm", "From scratch on the round 5 pool, with more capacity and more "
     "steps than r4 (8 layers, 512 wide across 8 heads, 6000 steps), then its held-out answers.",
     "python3 t/loop_locallm.py corpus --pool v5 --base t/runs/2026-09-16/loop-data/corpus.txt "
     "--sft t/out/loop/sft-r5.jsonl "
     f"--out t/out/loop-locallm/corpus-r5.txt && {PY} t/loop_locallm.py train "
     "--corpus t/out/loop-locallm/corpus-r5.txt --model t/out/loop-locallm/model-r5 --layers 8 --width 512 "
     "--heads 8 "
     f"--steps 6000 && {PY} t/loop_locallm.py generate --temperature 0.5 --model t/out/loop-locallm/model-r5 --tag locallm-r5",
     f"test $(ls {SE}/locallm-r5/raw 2>/dev/null | wc -l) -ge 232", "gpu"),
    ("r5-train", "Round 5: train the student again", "The same 1.5B, now with the round 5 pairs, which include "
     "the model's own proven-but-wrong answers as the rejected side.",
     # 2026-09-18: 4,608 put DPO out of memory on this 16 GB card once APPS problems entered the pool, and so
     # did 3,584 and 3,328. trl 1.13 dropped use_logits_to_keep, which was this file's whole memory strategy,
     # so the policy forward now builds full-window full-vocabulary logits for chosen and rejected at once --
     # 1.84 GiB in bf16, with 1.83 GiB free. Probed on the card rather than reasoned about: 3,072 trains and
     # keeps 482 of the 489 pairs, 2,560 trains but keeps 45, which is round 4's silent-drop trap again.
     f"PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True {PY} t/loop_train.py --sft t/out/loop/sft-r5.jsonl "
     "--pairs t/out/loop/pairs-r5.jsonl --sft-first "
     "--max-len 3072 --out t/out/loop/adapter-r5",
     "test -s t/out/loop/adapter-r5/adapter_model.safetensors", "gpu"),
    ("r5-student", "Round 5: student answers", "",
     f"{PY} t/loop_generate.py --adapter t/out/loop/adapter-r5 --tag student-r5-v3 {EVAL}",
     f"test $(ls {SE}/student-r5-v3/raw 2>/dev/null | wc -l) -ge 232", "gpu"),
    ("r5-grade-heldout", "Round 5: grade held-out", "On the lab workstation.",
     "for T in student-r5-v3 locallm-r5; do [ -d t/out/spec-experiment/$T/raw ] || continue; "
     "python3 t/spec_experiment.py extract --model $T --pool v3 && "
     "python3 t/spec_experiment.py tests --model $T --pool v3; done && bash t/grade_lab.sh heldout student-r5-v3 locallm-r5",
     f"test -s {SE}/student-r5-v3/kernels.md", "lab"),
    ("r5-score", "Round 5: score", "The round 5 row next to round 4 and Phi.",
     "python3 t/score_heldout.py qwen3.8-27b-fp8-v3 phi4-mini-v3 qwen15b-base-v3 student-r4-v3 locallm-r4 "
     "student-r5-v3 locallm-r5 | tee t/out/score-r5.md", "test -s t/out/score-r5.md", ""),
    # Round 6 answers the round 5 score with the two things it measured: the student loses at the proof gate,
    # not the notation (it wrote 42 well-formed answers to Phi's 12 and converted 3 of 11 test-passing where
    # Phi converted 3 of 6), and its parse rate never moved off the untrained model's. So the pairs gained a
    # rejected side that is RIGHT and unprovable, and the answers are decoded against t's grammar -- both
    # arms, Phi included, because a constraint on one side only is not a comparison.
    ("r6-pool", "Round 6: pool with the proof gate in it",
     "Rebuilds the pairs with two negatives nothing in the pool had: an answer to the same problem that "
     "passes its own tests and does not verify, and one the seven proved whose specification disagrees with "
     "the problem. Those are the two ways round 5's student lost.",
     f"python3 t/loop_dataset.py --from-samples {SAMPLE_TAGS} student-r4-train locallm-r4-train "
     "--split t/out/loop/split-v5.json --min-kernels 7 --out-suffix r6 && "
     "wc -l t/out/loop/sft-r6.jsonl t/out/loop/pairs-r6.jsonl",
     "test -s t/out/loop/pairs-r6.jsonl", ""),
    ("r6-train", "Round 6: train the student", "The same 1.5B on the round 6 pairs.",
     f"PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True {PY} t/loop_train.py --sft t/out/loop/sft-r6.jsonl "
     "--pairs t/out/loop/pairs-r6.jsonl --sft-first --max-len 3072 --out t/out/loop/adapter-r6",
     "test -s t/out/loop/adapter-r6/adapter_model.safetensors", "gpu"),
    ("r6-student", "Round 6: student answers", "Held-out answers, unconstrained, so the round 4 and 5 rows "
     "stay comparable.",
     f"{PY} t/loop_generate.py --adapter t/out/loop/adapter-r6 --tag student-r6-v3 --pool v3 --prompt v3 "
     "--ids-file t/out/loop/eval-ids.txt",
     f"test $(ls {SE}/student-r6-v3/raw 2>/dev/null | wc -l) -ge 232", "gpu"),
    ("r6-student-g", "Round 6: student answers, under the grammar",
     "The same held-out problems with t's grammar on the decoder, so the model cannot write what the parser "
     "would refuse.",
     f"{PY} t/loop_generate.py --adapter t/out/loop/adapter-r6 --tag student-r6-g --pool v3 --prompt v3 "
     "--ids-file t/out/loop/eval-ids.txt --grammar t/t.gbnf",
     f"test $(ls {SE}/student-r6-g/raw 2>/dev/null | wc -l) -ge 232", "gpu"),
    ("phi-g", "Phi-4-mini, under the same grammar",
     "Phi answering the same problems with the same constraint. Without this row a constrained student "
     "against an unconstrained Phi would be a comparison of two different experiments.",
     f"{PY} t/loop_generate.py --adapter none --base microsoft/Phi-4-mini-instruct --tag phi4-mini-g "
     "--pool v3 --prompt v3 --ids-file t/out/loop/eval-ids.txt --max-new 3072 --grammar t/t.gbnf",
     f"test $(ls {SE}/phi4-mini-g/raw 2>/dev/null | wc -l) -ge 232", "gpu"),
    ("r6-grade-heldout", "Round 6: grade held-out",
     "All four new sets through the seven checkers on the lab workstation.",
     "for T in student-r6-v3 student-r6-g phi4-mini-g; do [ -d t/out/spec-experiment/$T/raw ] || continue; "
     "python3 t/spec_experiment.py extract --model $T --pool v3 && "
     "python3 t/spec_experiment.py tests --model $T --pool v3; done && "
     "bash t/grade_lab.sh heldout student-r6-v3 student-r6-g phi4-mini-g",
     f"test -s {SE}/student-r6-v3/kernels.md", "lab"),
    ("r6-score", "Round 6: score", "Every row: the two Phis, the untrained base, rounds 4, 5 and 6, and both "
     "locallms.",
     "python3 t/score_heldout.py qwen3.8-27b-fp8-v3 phi4-mini-v3 phi4-mini-g qwen15b-base-v3 student-r4-v3 "
     "student-r5-v3 student-r6-v3 student-r6-g locallm-r4 locallm-r5 | tee t/out/score-r6.md",
     "test -s t/out/score-r6.md", ""),
    # WS-21, the parse wall. The funnel measured that 62 percent of a stock model's replies never reach a
    # prover because they are not t; these three are the answer to that, in the order the preregistration
    # fixes (t/PREREG-2026-09-18-constrained.md).
    ("funnel", "Where answers die", "Walks every answer set from the model's reply to a clean training "
     "example and counts the survivors at each gate. Writes t/FUNNEL-2026-09-18.md. Cheap, and worth "
     "re-running after a round so the picture is the current one.",
     "python3 t/funnel.py", "test -s t/FUNNEL-2026-09-18.md", ""),
    ("grammar", "Is the grammar the notation?",
     "t/t.gbnf is t's own syntax as a grammar a generator can decode against. This proves it accepts exactly "
     "what the parser accepts, in both directions, on the lab workstation because it needs xgrammar. The "
     "preregistration forbids generating a constrained answer until this passes.",
     "L=$(grep '^T_LAB=' t/lab-workstation.conf | cut -d= -f2) && "
     "ssh -o BatchMode=yes $L \"cd ~/tup && git fetch -q origin && git reset -q --hard origin/main && "
     "~/.venv-vllm/bin/python t/grammar_check.py --refused 600\" | tee t/out/grammar-check.txt",
     "grep -q 'agree on every program tested' t/out/grammar-check.txt", "lab"),
    ("constrained", "Answers the parser cannot refuse",
     "The constrained arm: the same 1,133 problems, model, prompt, temperature and seed as the control set, "
     "with t's grammar sent on every request so the model cannot write anything the parser would refuse. "
     "Needs the lab workstation's cards, which are the operator's to lend.",
     "bash t/lab_gpu.sh constrained",
     "test -d t/out/spec-experiment/qwen3-coder-30b-apps-g1/raw", "gen"),
    ("constrained-grade", "Grade the constrained arm",
     "Extract, test and filter the constrained answers the same way as every other set -- same gates, same "
     "control sample of failing answers -- then the seven checkers on the lab workstation at the same 32 "
     "cells the control arm was graded at, because a timeout is not a verdict.",
     "python3 t/spec_experiment.py extract --model qwen3-coder-30b-apps-g1 --pool v5 && "
     "python3 t/spec_experiment.py tests --model qwen3-coder-30b-apps-g1 --pool v5 && "
     "python3 t/pool_pick.py t/out/spec-experiment/qwen3-coder-30b-apps-g1 --control 40 && "
     "bash t/grade_lab.sh tags qwen3-coder-30b-apps-g1",
     "test -s t/out/spec-experiment/qwen3-coder-30b-apps-g1/kernels.md", "lab"),
    ("constrained-score", "What the constraint bought",
     "The preregistered comparison: clean answers in each arm, the test-pass rate among answers that parse, "
     "problems covered, and generation seconds per clean answer. The decision rule was fixed before either "
     "arm existed, in t/PREREG-2026-09-18-constrained.md.",
     "python3 t/constrained_compare.py | tee t/out/CONSTRAINED-2026-09-18.md",
     "test -s t/out/CONSTRAINED-2026-09-18.md", ""),
    ("score", "Score against Phi", "The result. Saved to t/out/score-r4.md.",
     f"python3 t/score_heldout.py qwen3.8-27b-fp8-v3 {HELDOUT} locallm-r0 | tee t/out/score-r4.md",
     "test -s t/out/score-r4.md", ""),
]
STEPS_DEFAULT = STEPS
# What must be finished before a step can start. t/autopilot.py reads this; a key missing here has no
# prerequisites. Not a schedule: the orchestrator and a person may still run a step whenever they like.
NEEDS = {
    "data": ["packages"], "ollama-serve": ["ollama-install"], "pull": ["ollama-serve"], "run-all": ["data"],
    "generate": ["pull", "data"], "grade": ["generate"],
    # a grading step takes whatever answer sets exist and skips the rest, so it waits on nothing
    "grade-growth": [],
    "more-problems": ["pull", "data"],
    "phi": ["data", "packages"], "base": ["data", "packages"],
    "spec-check": ["grade"], "pool": ["grade", "spec-check"], "train": ["pool"],
    "student": ["train"], "locallm": ["pool"], "grade-heldout": ["phi"], "score": ["grade-heldout"],
    "r5-pool": ["grade"], "r5-locallm": ["r5-pool"], "r5-train": ["r5-pool"],
    "r5-student": ["r5-train"], "r5-grade-heldout": ["r5-student"], "r5-score": ["r5-grade-heldout"],
    "r6-train": ["r6-pool"], "r6-student": ["r6-train"], "r6-student-g": ["r6-train"],
    "r6-grade-heldout": ["r6-student"], "r6-score": ["r6-grade-heldout"],
    "constrained": ["grammar"], "constrained-grade": ["constrained"],
    "constrained-score": ["constrained-grade"],
}
RUNS = HERE / "runs" / time.strftime("%Y-%m-%d")
STEPS_FILE = HERE / "steps.json"


def load_steps() -> list:
    """The Collect data steps. t/steps.json wins when it is there, so a step can be added, reordered or its
    command changed without touching this file; the list above is written out as the starting point the first
    time locallm runs. One entry: [key, title, what it does, shell command, test that says it is done, uses]
    where uses is "" (anything), "gpu" (the graphics card), "cpu" (this machine's cores) or "lab" (the lab
    workstation over SSH). Press Reload steps after editing. Progress counting is by key; a new key with no
    rule shows none."""
    try:
        got = json.loads(STEPS_FILE.read_text(encoding="utf-8"))
        rows = [tuple(r[:6]) for r in got if isinstance(r, list) and len(r) >= 6]
        if rows:
            return rows
    except (OSError, ValueError):
        pass
    try:
        STEPS_FILE.write_text(json.dumps([list(s) for s in STEPS_DEFAULT], indent=1) + "\n", encoding="utf-8")
    except OSError:
        pass
    return list(STEPS_DEFAULT)


SPEC_EXP = HERE / "out" / "spec-experiment"
# Where the window was left. XDG_CACHE_HOME keeps its old meaning and its old layout under it,
# because t/shots.py points that variable at a throwaway folder so a documentation run cannot
# move the operator's real window; unset, this is state and not cache (basedir-spec calls a
# cache "non-essential"), so it goes where t/paths.py puts the rest.
GEOMETRY = paths.state_path("XDG_CACHE_HOME", "geometry", env_join=("t-lab", "geometry"))
# the files a fix lands in; when one moves, the window reloads itself (Lab.watch_own_code)
ROOT = HERE.parent


def watched_files() -> set[Path]:
    """Every source file the window is actually running, recomputed at each poll.

    A hand-written tuple of three names lived here until 2026-09-20 and was wrong
    the moment the window grew a fourth source file: merging the trainer in put
    locallm/studio.py on the Train page while the list still named lab.py,
    steps.json and lab_status.py, so a fix to the training surface would not have
    reloaded anything. Werkzeug's reloader takes the same lesson and derives its
    set from sys.modules instead of naming files, precisely so that adding a
    module cannot silently stop it watching (github.com/pallets/werkzeug,
    src/werkzeug/_reloader.py, _iter_module_paths, read 2026-09-20).

    This is the narrow version of that: modules whose file sits inside the
    repository, because the standard library and the virtualenv are not what gets
    fixed while the window is open. It is recomputed rather than cached because
    studio.py is imported lazily, so it joins the set only once Train has been
    opened, and a file that appears mid-run must not read as a file that changed.
    """
    files = {HERE / "steps.json"}
    for mod in list(sys.modules.values()):
        name = getattr(mod, "__file__", None)
        if not name:
            continue
        f = Path(name)
        if f.suffix == ".py" and f.is_relative_to(ROOT):
            files.add(f)
    return files


def lab_target() -> str:
    """Read the private connection setting without executing a shell configuration."""
    target = os.environ.get("T_LAB", "")
    if not target:
        try:
            for line in (HERE / "lab-workstation.conf").read_text().splitlines():
                words = shlex.split(line, comments=True)
                if words and words[0] == "export":
                    words = words[1:]
                if len(words) == 1 and words[0].startswith("T_LAB="):
                    target = words[0].split("=", 1)[1]
        except (OSError, ValueError):
            pass
    return target if target and not target.startswith("-") and not any(c.isspace() for c in target) else ""


def mtime(p: Path) -> float:
    try:
        return p.stat().st_mtime
    except OSError:
        return 0.0
STEPS = load_steps()
STEPS_TITLE = [(s[0], s[1]) for s in STEPS]

# ------------------------------------------------------------------------------
# THE LOOK IS locallm/look.py's, NOT THIS FILE'S.
#
# What stood here was a second design system: thirteen colour literals in four
# lines, six more #ffffff spread through the widgets, a copy of studio.py's two font
# lists carrying a comment that said the two copies must stay IDENTICAL, and its own
# four marks. Two of those three had already drifted -- the shell resolved to Inter
# and the Train page embedded in it to Cantarell, in one frame, measured 2026-09-20,
# and the two palettes were different sets of literals. A rule that says "keep these
# the same" has no enforcement; one copy has enforcement for free, and look.py is
# that copy.
#
# THE WINDOW IS LIGHT BY DEFAULT AND FOLLOWS THE OPERATING SYSTEM. That is the
# operator's decision, and it is what the platform asks for: "Most apps should use
# the standard light UI style by default", and apps that do "are encouraged to
# follow the system style setting" (developer.gnome.org/hig/guidelines/
# ui-styling.html, read 2026-09-20). The same page asks for three choices where
# there is a preference -- light, dark, follow the system -- which is
# LOCALLLM_THEME=light|dark and unset. This shell was dark-only and the studio was
# light-only for one reason: both had their colours written out as literals.
#
# "FOLLOWS THE SYSTEM" IS NOT YET TRUE ON LINUX, which is the desk this runs on.
# look.system_wants_dark reads the Windows registry and nothing else, so an unset
# LOCALLLM_THEME resolves to light here however the desktop is set. Measured
# 2026-09-20 on this machine: `gsettings get org.gnome.desktop.interface
# color-scheme` answers 'prefer-dark' and this window still opens light.
# LOCALLLM_THEME=dark is the way to dark meanwhile. Written down rather than left
# for someone to find by opening the window on a dark desktop.
#
# The names below are the ones the widget code already uses, each bound to one of
# look's eight roles, so the two thousand lines under them read as they did and no
# line here can invent a ninth colour. Where a name no longer describes its value
# the reason is beside it; where it named a colour that no longer exists, the name
# is gone.
# ------------------------------------------------------------------------------
C = look.palette()
BG, CARD, LINE = C["bg"], C["panel"], C["line"]
# SURFACE was a fourth grey between BG and CARD, under everything sunken: the
# entries, the log panes, the plot, a heading row. look calls that `field` and
# makes it the paper showing THROUGH a card rather than a shade of its own, so
# SURFACE and BG are one value now and the hairline does the separating.
SURFACE = C["field"]
TEXT, MUTED, FAINT = C["fg"], C["muted"], C["faint"]
# The third marking colour had no name in this file and it is the one this window
# needs most: look's amber says "not settled yet", which is exactly what a check
# still running, a bar part way along and a stop just sent to the lab workstation
# are. All three were blue, for no reason beyond blue being there.
GREEN, RED, UNSETTLED = C["ok"], C["bad"], C["warn"]
# THERE IS NO BLUE. look carries three marking colours and refuses a fourth accent,
# on the grounds that a fourth colour on a screen that says three things is a
# colour with nothing attached to it. Every blue in this file was interactive rather
# than a verdict -- a button, the open tab, the selected step, a bar that is moving
# -- so the interactive colour is now the pencil itself, the same ink the words are
# written in (look lends ink to the training curve for the same reason, and keeps
# green and red for the two things that are claims). ON_ACCENT is what goes on top
# of it: paper, so a filled button is the window inverted and measures what ink on
# paper measures.
ACCENT, ON_ACCENT = C["ink"], C["paper"]
# A SELECTED THING IS A SHADED BAND, not an inverted one. Measured in look: ink on
# this band is 10.92:1 light and 9.87:1 dark, and nothing quieter than ink clears
# the body bar on it, which is why the toggles and the selected row keep TEXT. This
# one value replaces BLUE_DIM (the toggle, the selected row, the active menu item)
# and GREEN_DIM (the tint behind a running step). RED_DIM had no call site left.
SELECT = C["select"]

# SPACING: every padx, pady and ipady in this file is one of look.SPACE's six
# steps. Fifteen distinct values lived here, among them the run 1, 2, 3, 5, 6, 7 --
# the signature of nudging a number until one panel looked right, which is how two
# boxes end up 6 and 7 pixels apart for no reason anyone can name. (look.py's note
# says fourteen; the fifteenth is the tooltip's 1, which was a border drawn with
# padding, and it is dealt with below rather than rounded.) Each value was rounded
# to the nearest step with ties going up (6 -> 8, 10 -> 12, 14 -> 16,
# 20 -> 24), and a two-value pair was rounded one side at a time, because -padx
# "may be a list of two values to specify padding for left and right separately"
# and -pady the same for top and bottom (tcl-lang.org/man/tcl8.6/TkCmd/pack.htm).
# Zero stays zero: it is the absence of a gap, not the smallest one. Two results
# worth knowing before anyone "corrects" them: the window's outer margin measured
# 22 and rounds to SPACE.group, one step in from the step look names `page`,
# because what was rounded is the measurement and not the layout; and the
# one-pixel hairline the tooltip got by packing its label one pixel in from a
# coloured toplevel is now drawn the way every card here draws one, since a border
# is not spacing.
SPACE = look.SPACE
LOOP_RE = re.compile(r"round (\d+): corpus (\d+) docs; samples (\d+), parsed (\d+), "
                     r"well-formed (\d+), novel (\d+)")
CLEAN_RE = re.compile(r"round (\d+): clean in all seven (\d+)")


# ------------------------------------------------------------ plain words --

def verdict(real: str, twin: str, agree: bool = True) -> look.Say:
    """One checker's result on one program: mark, short word, one plain sentence, tone.

    The words are unchanged. They are what a person reads in the Result and What it
    means columns, and they were written for someone who has never run a prover.
    What changed is the fourth field: it was a literal out of the old dark palette,
    which is the whole reason this function could only ever be used in the dark half
    of the window, and it is now a look palette KEY the caller resolves in whichever
    theme is live.

    NO VERDICT CHANGES TIER: grey -> "muted", green -> "proved", red -> "refuted",
    one for one. look's amber `unsettled` would fit several of the unresolved cases
    and is deliberately not spent on them, because moving a verdict from grey to
    amber is a different claim about a proof, not a different colour, and this
    change is about colour.

    THE SIX SYMBOLS ARE NOT look.MARKS' FOUR. ✔ ✘ – ◷ come from look; "?" and "!"
    are this table's own and stay. The Programs grid gives each checker a cell one
    character wide, so folding malformed and checker-error onto the dash would draw
    "the checker could not read this" exactly like "this checker abstains", which is
    the distinction that grid exists to make.
    """
    real, twin = (real or "").strip(), (twin or "").strip()
    if not agree:
        return look.Say("!", "Inconsistent", "Repeated checks disagreed; this is not a stable proof.", "muted")
    if real == "verified" and twin == "refuted":
        return look.Say(look.PROVED, "Proven",
                        "Proved the program keeps its promise, and caught the broken copy.", "proved")
    if real == "verified" and twin == "verified":
        return look.Say(look.REFUTED, "Promise too weak",
                        "It passed, but so did a broken copy, so the promise says too little.", "refuted")
    if real == "verified":
        return look.Say("?", "Twin unresolved",
                        "The program was proved, but catching the broken copy is unresolved.", "muted")
    if real == "vacuous":
        return look.Say(look.REFUTED, "Empty promise",
                        "It passed only because its promise can never be tested.", "refuted")
    if real == "refuted":
        return look.Say(look.REFUTED, "Bug found",
                        "The checker found an input where the program breaks its promise.", "refuted")
    if real == "unproved":
        return look.Say(look.REFUTED, "Not proven",
                        "The checker could not prove it, and found no bug either.", "refuted")
    if real == "timeout":
        return look.Say(look.TIMED_OUT, "Too slow",
                        "The checker ran out of time. That does not mean the program is wrong.", "muted")
    if real == "malformed":
        return look.Say("?", "Unreadable", "The checker could not read the program.", "refuted")
    if real == "abstain":
        return look.Say(look.NOT_APPLICABLE, "Not supported yet",
                        "This checker cannot handle this kind of program yet.", "muted")
    if real == "no-twin":
        return look.Say(look.NOT_APPLICABLE, "No broken copy",
                        "No broken copy could be made, so the promise could not be tested.", "muted")
    return look.Say("!", "Checker error", "The checker itself failed. This says nothing about the program.", "muted")


def mark(v) -> str:
    return look.NOT_APPLICABLE if v is None else (look.PROVED if v else look.REFUTED)


# --------------------------------------------------------------- widgets --

class Tip:
    """A short explanation shown while the mouse rests on a widget.

    On Aqua the override-redirect toplevel below is not a tooltip, it is three
    bugs. It takes the input focus when raised, filed against this exact
    balloon-help use (sourceforge.net/p/tktoolkit/bugs/1395). On Tk 8.6.11
    wm_overrideredirect(1) itself raises TclError, `expected boolean value but
    got "None"` (github.com/thonny/thonny/issues/1659). On Tk Aqua 8.7 the
    window draws blank (github.com/python/cpython/issues/104499, where IDLE's
    own fix is to branch on `_windowingsystem != "aqua"` -- the test used here,
    because X11 Tk on a Mac has none of this). So on Aqua the same sentence goes
    to the window's status line. The class and its three-argument call are
    unchanged: there are six call sites and none of them should have to know
    which windowing system it is on.
    """

    def __init__(self, widget, text: str, app):
        self.widget, self.text, self.app, self.win = widget, text, app, None
        widget.bind("<Enter>", self.show, add="+")
        widget.bind("<Leave>", self.hide, add="+")

    def show(self, _e=None):
        if self.app.aqua:
            self.app.say(self.text)
            return
        if self.win:
            return
        x = self.widget.winfo_rootx() + SPACE.inner
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + SPACE.inner
        self.win = tk.Toplevel(self.widget, bg=CARD)
        self.win.wm_overrideredirect(True)
        self.win.geometry(f"+{x}+{y}")
        # A tooltip is a small card, and its hairline is drawn the way every card
        # here draws one. It used to be a coloured toplevel with the label packed one
        # pixel in from it, which made a border out of padding.
        tk.Label(self.win, text=self.text, justify="left", bg=CARD, fg=TEXT, wraplength=380,
                 font=self.app.f_small, padx=SPACE.item, pady=SPACE.inner,
                 highlightthickness=1, highlightbackground=LINE).pack()

    def hide(self, _e=None):
        if self.app.aqua:
            self.app.say("", only_if=self.text)      # only if nothing else has written there since
            return
        if self.win:
            self.win.destroy()
            self.win = None


class Button(tk.Label):
    """A flat button: filled with its color, a lighter shade on hover."""

    def __init__(self, parent, text, command, color=ACCENT, app=None, filled=True):
        self.color, self.filled, self.command, self.enabled = color, filled, command, True
        super().__init__(parent, text=text, cursor="hand2", padx=SPACE.card, pady=SPACE.inner, font=app.f_bold,
                         bg=color if filled else CARD, fg=ON_ACCENT if filled else color)
        self.bind("<Button-1>", lambda _e: self.enabled and self.command())
        self.bind("<Enter>", lambda _e: self.enabled and self.configure(bg=self.shade(color) if filled else LINE))
        self.bind("<Leave>", lambda _e: self.configure(bg=color if filled else CARD))

    @staticmethod
    def shade(hex_color: str) -> str:
        r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
        return "#%02x%02x%02x" % tuple(min(255, int(c * 1.18) + 12) for c in (r, g, b))

    def set_enabled(self, on: bool):
        self.enabled = on
        self.configure(fg=(ON_ACCENT if self.filled else self.color) if on else FAINT)


class Chip(tk.Label):
    """A toggle: a shaded band with a check mark when on, quiet when off."""

    def __init__(self, parent, text, var: tk.BooleanVar, app, command=None):
        self.var, self.label, self.command = var, text, command
        super().__init__(parent, cursor="hand2", padx=SPACE.item, pady=SPACE.tight, font=app.f_body)
        self.bind("<Button-1>", self.toggle)
        self.paint()

    def toggle(self, _e=None):
        self.var.set(not self.var.get())
        self.paint()
        if self.command:
            self.command()

    def paint(self):
        on = self.var.get()
        self.configure(text=(f"{look.PROVED}  " if on else "    ") + self.label,
                       bg=SELECT if on else CARD, fg=TEXT if on else MUTED)


def log_pane(parent, app, height: int, wrap: str = "none") -> tk.Text:
    """A pane that is read back rather than typed in: a step's log, the GPU status,
    the score tables, the alerts. One constructor, the way entry() below is one."""
    # Eight of these were written out option by option, and all eight took two colours
    # from Tk rather than from look, because neither was named: the caret stayed black,
    # invisible on the old dark ground, and the one-pixel ring Tk gives every Text by
    # default stayed its own light grey, d9d9d9. The ring is kept and given the
    # hairline colour, because a pane on a card differs from it by look's measured
    # 1.101:1 and needs the seam.
    return tk.Text(parent, bg=SURFACE, fg=TEXT, insertbackground=TEXT, font=app.f_mono,
                   relief="flat", height=height, wrap=wrap,
                   highlightthickness=1, highlightbackground=LINE)


def entry(parent, var, app, width=None):
    e = tk.Entry(parent, textvariable=var, bg=SURFACE, fg=TEXT, insertbackground=TEXT, relief="flat",
                 highlightthickness=1, highlightbackground=LINE, highlightcolor=ACCENT, font=app.f_body)
    if width:
        e.configure(width=width)
    return e


# --------------------------------------------------------------- t checks --

def task_key(task: dict) -> str:
    """The program with its name, format version and gate erased (rename_task
    edits in place, so a copy). None of the three changes what the kernels
    check; keeping the version let a `t 1` sample copy a `t 0` corpus task
    unseen (loop_filter.key, 2026-09-17)."""
    t = se.rename_task(copy.deepcopy(task), "x_task")
    t.pop("gate", None); t["t"] = 1
    return surface.canon(t)


def first_task(text: str):
    m = re.search(r"(?m)^t \d+\s*$", text)
    lines = (text[m.start():] if m else text).split("\n")
    for i, line in enumerate(lines):
        if line.strip() == "}":
            try:
                return surface.parse("\n".join(lines[:i + 1]) + "\n")
            except Exception:                                   # noqa: BLE001
                pass
    return None


def corpus_keys(path: Path) -> set[str]:
    keys = set()
    for doc in re.split(r"\n\s*\n(?=Problem: |t \d)", path.read_text(encoding="utf-8", errors="replace")):
        doc = re.sub(r"^Problem: .*\nSignature: .*\n", "", doc.strip())
        try:
            keys.add(task_key(surface.parse(doc + "\n")))
        except Exception:                                       # noqa: BLE001
            pass
    return keys


def guess_corpus(model_dir: Path) -> Path | None:
    for c in (model_dir.parent / "corpus.txt", model_dir.with_suffix(".txt")):
        if c.is_file():
            return c
    return None


def find_models() -> list[str]:
    patterns = [HERE / "runs" / "*" / "filter-loop" / "*" / "*" / "model" / "ckpt.pt",
                HERE / "runs" / "*" / "*" / "model" / "ckpt.pt",
                HERE / "out" / "loop-locallm" / "model" / "ckpt.pt",
                HERE / "out" / "loop-filter" / "*" / "model" / "ckpt.pt",
                LOCALLM / "*" / "ckpt.pt", SCRATCH / "models" / "*" / "ckpt.pt"]
    found = set()
    for pat in patterns:
        anchor = Path(pat.anchor)
        for ck in anchor.glob(str(pat.relative_to(anchor))):
            if (ck.parent / "tokenizer.json").is_file():
                found.add(str(ck.parent))
    return sorted(found)


def memory_mb(root_pid: int) -> float | None:
    """Memory used by a check's processes, from /proc (Linux); None elsewhere."""
    if not os.path.isdir("/proc"):
        return None
    page_kb = os.sysconf("SC_PAGE_SIZE") // 1024
    table = {}
    for d in os.listdir("/proc"):
        if not d.isdigit():
            continue
        try:
            with open(f"/proc/{d}/stat", encoding="utf-8", errors="replace") as f:
                raw = f.read()
            with open(f"/proc/{d}/statm") as f:
                rss = int(f.read().split()[1]) * page_kb
        except (OSError, IndexError, ValueError):
            continue
        table[int(d)] = (int(raw[raw.rfind(")") + 2:].split()[1]), rss)
    kids: dict[int, list[int]] = {}
    for pid, (ppid, _rss) in table.items():
        kids.setdefault(ppid, []).append(pid)
    total, stack = 0, [root_pid]
    while stack:
        for c in kids.get(stack.pop(), []):
            total += table[c][1]
            stack.append(c)
    return total / 1024


# ------------------------------------------------------------------- app --

class Lab:
    def __init__(self, root: tk.Tk, start_page: str = "Live checks"):
        self.root = root
        # `tk windowingsystem`, not sys.platform: Tk built against X11 on a Mac has none of
        # Aqua's tooltip and menu-bar problems, and Aqua is what those two have to bend to.
        # IDLE branches on the same test for the same class of bug (github.com/python/cpython
        # /issues/104499).
        try:
            self.aqua = root.tk.call("tk", "windowingsystem") == "aqua"
        except tk.TclError:
            self.aqua = False
        self.start_page = start_page
        self.remote = lab_target()
        self.lab_snapshot = None
        self.lab_error = "Connecting to lab workstation"
        self.lab_received = 0.0
        # Both families are resolved once, here, against this root, and both halves of
        # the window then read the same memo: look.py holds the one copy of the two
        # lists, so the shell and the Train page embedded in it cannot come out in two
        # faces in one frame. They had -- Inter here, Cantarell there, measured
        # 2026-09-20 -- while a comment in this file said the two copies must stay
        # identical. Resolving before any widget is built is what look.resolve_fonts is
        # for: a bare SANS() call with no widget has no Tk to ask and falls back.
        # The sizes and the weights are decisions and stay here; the family is looked up.
        look.resolve_fonts(root)
        self.f_title, self.f_h2 = look.SANS(20, "bold"), look.SANS(13, "bold")
        self.f_body, self.f_bold, self.f_small = look.SANS(11), look.SANS(11, "bold"), look.SANS(10)
        self.f_num, self.f_mono = look.SANS(26, "bold"), look.MONO(10)
        root.configure(bg=BG)
        root.option_add("*Menu.background", SURFACE)
        root.option_add("*Menu.foreground", TEXT)
        root.option_add("*Menu.activeBackground", SELECT)
        root.option_add("*Menu.activeForeground", TEXT)
        self.style_tables()

        self.q: queue.Queue = queue.Queue()
        self.stop_flag = threading.Event()
        EVENTS.parent.mkdir(parents=True, exist_ok=True)   # run_par.py drops events silently when the folder is missing
        self.offset = EVENTS.stat().st_size if EVENTS.exists() else 0
        self.running: dict[tuple[str, str], dict] = {}
        self.counts = {"done": 0, "proven": 0, "not": 0}
        self.samples: dict[str, str] = {}
        self.end_times: list[float] = []     # every finished check's time, for the data run's progress bar
        self.end_pairs: list[tuple[float, str]] = []   # (time, task) for the same, to count one answer set's own
        try:                                 # earlier checks too, so a reopened window keeps a running bar right
            if self.remote:
                raise OSError("events come from the lab workstation")
            self.end_pairs = [(json.loads(l).get("t", 0), json.loads(l).get("task", ""))
                              for l in EVENTS.read_text(errors="replace").splitlines() if '"ev": "end"' in l]
            self.end_times = [t for t, _ in self.end_pairs]
        except (OSError, ValueError):
            pass

        # One line for a sentence that had nowhere to go before: a failed xdg-open was a
        # traceback in the terminal nobody is watching, and on Aqua this is where the
        # tooltips are written (see Tip, which cannot use a toplevel there).
        self.status_line = tk.Label(root, text="", bg=BG, fg=FAINT, font=self.f_small, anchor="w",
                                    justify="left", wraplength=900)
        self.status_line.pack(side="bottom", fill="x", padx=SPACE.group, pady=(0, SPACE.item))
        # a tooltip is two sentences: wrap it, do not cut it
        self.rewrap(self.status_line, pad=2 * SPACE.group + SPACE.item)

        head = tk.Frame(root, bg=BG)
        head.pack(fill="x", padx=SPACE.group, pady=(SPACE.card, SPACE.inner))
        tk.Label(head, text="locallm", bg=BG, fg=TEXT, font=self.f_title).pack(side="left")
        self.pulse = tk.Label(head, text="●  waiting for checks", bg=BG, fg=FAINT, font=self.f_small)
        self.pulse.pack(side="right")
        self.follow_btn_parent = head

        tabs = tk.Frame(root, bg=BG)
        tabs.pack(fill="x", padx=SPACE.group, pady=(SPACE.card, SPACE.inner))
        self.pages, self.tab_buttons = {}, {}
        body = tk.Frame(root, bg=BG)
        body.pack(fill="both", expand=True, padx=SPACE.group, pady=(0, SPACE.card))
        # HOME LEADS, AND THE SEVEN CHECKERS ARE ONE TAB, NOT THREE.
        #
        # Train led here until 2026-09-20 and the paragraph about seven proof kernels
        # sat above every page, so the first thing a stranger met was the machinery
        # rather than the thing locallm claims to do -- point it at your own text and
        # get a model. Home is that claim (locallm/home.py), it is first, and it is
        # what the window opens on; the paragraph moved into Proof, where it explains
        # the checkers to someone who chose to look at them.
        #
        # THE COUNT IS THE REASON FOR GROUPING. Six tabs locally was over the
        # platform's own bar: "As a rule of thumb, a view switcher should contain
        # between three and five views. If you have more views, a sidebar might be a
        # more appropriate choice", and views are labelled with nouns rather than
        # verbs (developer.gnome.org/hig/patterns/nav/view-switchers.html, read
        # 2026-09-20). Live checks, Test a model and Results are the same subject --
        # the seven provers judging work -- so they became one noun-labelled view
        # with a strip of its own (build_proof), and the list is five. NN/g puts the
        # same rule plainly, "the fewer tabs, the better", and adds the one that
        # decided the order: "Arrange tab content so high-use content is first in the
        # list and selected by default" (nngroup.com/articles/tabs-used-right/,
        # reviewed 2026-09-02).
        #
        # Home and Train are both present in remote mode, and that is a correction.
        # The first version dropped Train there, reasoning that training needs torch
        # on THIS machine exactly as "Test a model" does. Running it showed what that
        # costs: this desktop has a lab-workstation.conf, so remote is true, so the
        # tab simply was not there and nothing said why. A window whose own docstring
        # promises "every word explained" should not answer a missing capability by
        # hiding the word. So the tab always exists and build_train says what is
        # missing -- torch, or the fact that the work is happening elsewhere. Home
        # goes further and needs no note at all: home.py reaches studio through its
        # own lazy engine() and its cards say in words which of them cannot work, so
        # it is the real page on a machine with neither torch nor local compute.
        # "Test a model" is the one page still dropped in remote mode, in build_proof,
        # because it runs a model on this machine and there is nothing to run it with.
        for name in ("Home", "Train", "Proof", "Collect data", "AI"):
            b = tk.Label(tabs, text=name, cursor="hand2", padx=SPACE.card, pady=SPACE.inner, font=self.f_bold)
            b.pack(side="left", padx=(0, SPACE.inner))
            b.bind("<Button-1>", lambda _e, n=name: self.show_page(n))
            self.tab_buttons[name] = b
            self.pages[name] = tk.Frame(body, bg=BG)
            if name == "Proof":
                # Inside the loop, so the three pages behind Proof land in self.pages
                # between Proof and Collect data: the View menu is built by walking
                # that dict, and building them afterwards would leave the menu listing
                # Live checks after AI, in an order the window itself does not have.
                self.build_proof(self.pages[name])
        self.build_home(self.pages["Home"])
        self.build_train(self.pages["Train"])
        self.build_live(self.pages["Live checks"])
        if not self.remote:
            Button(self.follow_btn_parent, "Follow a loop run", self.follow_loop, ACCENT, self,
                   filled=False).pack(side="right", padx=(0, SPACE.card))
            self.build_test(self.pages["Test a model"])
        self.build_collect(self.pages["Collect data"])
        self.build_results(self.pages["Results"])
        self.build_ai(self.pages["AI"])
        self.build_menu()
        self.show_page(self.start_page if self.start_page in self.pages else "Home")
        if self.remote:
            threading.Thread(target=self.watch_lab, daemon=True).start()
        else:
            root.after(300, self.poll_events)
        root.after(1000, self.tick)
        root.after(200, self.drain)
        self.watched = {p: mtime(p) for p in watched_files()}
        root.after(2000, self.watch_own_code)

    # -- look ------------------------------------------------------------------
    def style_tables(self):
        s = ttk.Style(self.root)
        s.theme_use("clam")
        s.configure("Treeview", background=CARD, fieldbackground=CARD, foreground=TEXT, rowheight=30,
                    borderwidth=0, font=self.f_body)
        s.map("Treeview", background=[("selected", SELECT)], foreground=[("selected", TEXT)])
        s.configure("Treeview.Heading", background=SURFACE, foreground=MUTED, relief="flat", font=self.f_small,
                    borderwidth=0, padding=(SPACE.inner, SPACE.inner))
        s.map("Treeview.Heading", background=[("active", SURFACE)], foreground=[("active", TEXT)])
        s.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
        s.configure("Sash", background=BG, sashthickness=8)

    def say(self, text: str, only_if: str | None = None):
        """Put one sentence on the status line. only_if leaves it alone unless it still
        says that, so a tooltip clearing itself cannot wipe a message written since."""
        if only_if is not None and self.status_line.cget("text") != only_if:
            return
        self.status_line.configure(text=text, fg=MUTED if text else FAINT)

    def rewrap(self, label: tk.Label, pad: int = 16, floor: int = 280) -> tk.Label:
        """Wrap a paragraph to the width it actually has, not to a number written here.

        The wraplengths in this file were 1300, 1200 and 1100 while the window's own
        minimum width was 1000, so those paragraphs ran off the right edge at the size the
        window can be dragged to, before any display-scaling question. The training surface
        already fixed the same mistake the same way and says why (locallm/studio.py,
        _rewrap: "A hard-coded wraplength is a guess about the window width, and it was
        wrong").

        width=1 is not cosmetic and this does not work without it. A label asks for the
        width it wraps at, so a paragraph whose wrap is read back off its container makes
        the container follow the paragraph: measured here, the opening sentence went 1300,
        1144, 1100, then straight to the floor and oscillated there, and update() never
        returned. Asking for one character instead leaves the width to the tables and the
        window, which is what should be deciding it, and leaves the wrap free to follow.
        Every caller must therefore pack the label with fill="x".

        The guard in track is the other half of that lesson. A container's own <Configure>
        is not the only event a binding on it sees: a toplevel is one of the binding tags of
        every widget beneath it, so a label whose master is the root window was being handed
        its siblings' and children's widths -- 76, 13, 1 -- and rewrapped to each of them in
        turn, forever.
        """
        label.configure(width=1)

        def track(event):
            if event.widget is not label.master:
                return                             # a toplevel is in all its children's bindtags
            width = max(floor, event.width - pad)
            if label.cget("wraplength") != width:
                label.configure(wraplength=width)
        label.master.bind("<Configure>", track, add="+")
        return label

    def card(self, parent, title=None, hint=None, **pack):
        outer = tk.Frame(parent, bg=CARD, highlightthickness=1, highlightbackground=LINE)
        outer.pack(**({"fill": "x", "pady": (0, SPACE.item)} | pack))
        inner = tk.Frame(outer, bg=CARD)
        inner.pack(fill="both", expand=True, padx=SPACE.card, pady=SPACE.item)
        if title:
            row = tk.Frame(inner, bg=CARD)
            row.pack(fill="x", pady=(0, SPACE.inner))
            tk.Label(row, text=title, bg=CARD, fg=TEXT, font=self.f_h2).pack(side="left")
            if hint:
                tk.Label(row, text=hint, bg=CARD, fg=FAINT, font=self.f_small).pack(side="left", padx=SPACE.item)
        return inner

    def table(self, parent, cols, height):
        frame = tk.Frame(parent, bg=CARD)
        frame.pack(fill="both", expand=True)
        t = ttk.Treeview(frame, columns=[c for c, _, _ in cols], show="headings", height=height)
        for c, label, w in cols:
            t.heading(c, text=label.upper(), anchor="w")
            t.column(c, width=w, anchor="w", stretch=True)
        # A row's tag IS its look palette key, so a verdict's tone can be handed
        # straight to the table with nothing translating between the two names. The
        # tags are all four tones verdict() returns plus `ink` for a total line.
        for key in ("proved", "refuted", "unsettled", "muted", "ink"):
            t.tag_configure(key, foreground=C[key])
        t.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=t.yview)
        scrollbar.pack(side="right", fill="y")
        t.configure(yscrollcommand=scrollbar.set)
        return t

    def follow_loop(self):
        p = filedialog.askopenfilename(title="Choose a loop log (written by t/loop_filter.py)",
                                       initialdir=str(HERE / "runs"))
        if p:
            self.log_var.set(p)
            self.rounds_outer.pack(fill="x", pady=(0, SPACE.item), before=self.done_outer)

    #: The pages behind the Proof tab, in order. The first is what Proof opens on,
    #: because it is the one watched while a run is going: "Arrange tab content so
    #: high-use content is first in the list and selected by default"
    #: (nngroup.com/articles/tabs-used-right/). "Test a model" needs torch on this
    #: machine, so remote mode drops it here exactly as the tab list used to.
    PROOF_PAGES = ("Live checks", "Test a model", "Results")

    def build_proof(self, page):
        """The Proof tab: the sentence that explains the checkers, then a strip of three.

        THE STRIP IS NOT A SECOND COPY OF THE TAB STRIP, and that is the one thing
        the sources changed rather than confirmed. Two tab controls that look alike
        but work at different levels disorient a reader: "When using in-page tabs
        and navigation tabs in the same experience, visually differentiate between
        these tab types to convey to users that they behave differently"
        (nngroup.com/articles/tabs-used-right/, reviewed 2026-09-02). So the tabs
        above are a filled pill and these are an underline, with two selection
        indicators each as that page asks -- the rule and the text colour. The
        weight does NOT change with selection: f_bold and f_body are different
        widths, so switching would shift every label to its right by a pixel or
        two, and a strip that moves when you use it reads as a fault.

        The same page's "Use Only One Row of Tabs" is about stacking rows inside
        ONE control, which this is not: these are two controls at two levels, each
        directly above its own panel, which is the arrangement its own worked
        examples sanction. Its keyboard and ARIA advice is not taken here, and the
        reason is worth writing down: every tab in this window is a tk.Label with a
        <Button-1> binding and no focus ring, so giving these three keyboard
        traversal and not the five above them would be the inconsistency that page
        warns about. The View menu already reaches every page in the window from the
        keyboard.

        Built from the widgets this file already has -- tk.Frame, tk.Label and the
        one-pixel rule every card here draws -- rather than a ttk.Notebook, whose
        tab borders are drawn by the platform theme and ignore look.py's palette
        (the same reason the training surface gave for keeping plain Tk: a natively
        drawn ttk theme returned light grey boxes under a dark palette).
        """
        intro = tk.Label(page, bg=BG, fg=MUTED, font=self.f_body, justify="left", anchor="w", wraplength=1300, text=(
            "Models write programs on the lab workstation. Seven independent checkers "
            "try to prove each program keeps its promise, and try to catch a deliberately broken copy of it. "
            "A program is clean only when all seven prove it and catch the broken copy."))
        intro.pack(fill="x", pady=(0, SPACE.item))
        # the margin either side, plus room for the frame
        self.rewrap(intro, pad=2 * SPACE.group + SPACE.item)
        strip = tk.Frame(page, bg=BG)
        strip.pack(fill="x", pady=(0, SPACE.item))
        self.proof_buttons, self.proof_rules = {}, {}
        proof_body = tk.Frame(page, bg=BG)
        proof_body.pack(fill="both", expand=True)
        for name in self.PROOF_PAGES:
            if self.remote and name == "Test a model":
                continue
            holder = tk.Frame(strip, bg=BG)
            holder.pack(side="left", padx=(0, SPACE.card))
            b = tk.Label(holder, text=name, cursor="hand2", bg=BG, fg=MUTED, font=self.f_body,
                         padx=SPACE.tight, pady=SPACE.tight)
            b.pack(fill="x")
            # The underline, the ground's colour until it is selected. Two pixels
            # rather than one on the source's own instruction -- "Do not use thin,
            # single-pixel strokes or poor-contrast colors" for a line indicator --
            # and because one pixel is what every card in this file strokes its edge
            # with, so a one-pixel mark would read as a border rather than a state.
            rule = tk.Frame(holder, bg=BG, height=2)
            rule.pack(fill="x")
            b.bind("<Button-1>", lambda _e, n=name: self.show_page(n))
            self.proof_buttons[name] = b
            self.proof_rules[name] = rule
            self.pages[name] = tk.Frame(proof_body, bg=BG)
        # Which of the three Proof shows before anyone has chosen one. It is a name
        # rather than a packed frame because the window may open on another tab
        # entirely, and Proof must still have an answer the first time it is clicked.
        self.proof_page = self.PROOF_PAGES[0]

    def show_page(self, name):
        """Show one page by name, whether it is a tab or one of the three behind Proof.

        Both strips are driven from here so that every key of self.pages is a name
        that can be shown: the View menu walks that dict, and "Open Collect data",
        run_step's jump to Live checks and --page all hand it one name with no idea
        which level it sits at. Naming Proof itself shows whichever of its three was
        looked at last, which is why the outer loop below forgets only the tabs --
        forgetting every page, as this method used to, would unpack the nested
        selection inside a Proof frame that is about to be shown again.
        """
        if name == "Proof":
            name = self.proof_page
        if name in self.proof_buttons:
            self.proof_page = name
            for n, b in self.proof_buttons.items():
                self.pages[n].pack_forget()
                b.configure(fg=TEXT if n == name else MUTED)
                self.proof_rules[n].configure(bg=ACCENT if n == name else BG)
            self.pages[name].pack(fill="both", expand=True)
            name = "Proof"
        for n, b in self.tab_buttons.items():
            self.pages[n].pack_forget()
            b.configure(bg=ACCENT if n == name else CARD, fg=ON_ACCENT if n == name else MUTED)
        self.pages[name].pack(fill="both", expand=True)

    def open_path(self, path):
        """Hand a file to whatever the desktop opens it with. One xdg-open call lived here
        and raised FileNotFoundError on both other systems: xdg-open is freedesktop's, so
        it is not on macOS and not on Windows. The three-way branch is click's launcher
        (github.com/pallets/click, src/click/_termui_impl.py, open_url), which also reads an
        OSError as "the helper is not installed" rather than a crash. click then falls back
        to the webbrowser module for http URLs; there is nothing to fall back to for a local
        notes file, so the failure is said on the status line instead."""
        try:
            if os.name == "nt":
                os.startfile(str(path))                       # noqa: S606 -- Windows only, and Windows only has it
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except (OSError, subprocess.SubprocessError, AttributeError) as e:
            self.say(f"Could not open {path}: {e}")
            return
        self.say(f"Opened {path}")

    def build_menu(self):
        """The menu bar, which on macOS exists whether the application asks for one or not.

        Nothing here ever called root.config(menu=...), so beside the Apple logo the window
        offered a bare "Python" with no About and no Preferences: root.title() names the
        window, not the application. What can be fixed from here is the contents. Tk puts a
        menubar child whose last path element is `apple` first in the Application menu --
        "that menu's contents make up the first items of the Application menu"
        (tcl-lang.org/man/tcl8.6/TkCmd/menu.htm) -- and macOS enables the Preferences item
        only when a Tcl proc of that name exists: "The application menu Preferences menu
        item is only enabled when this proc is defined" (tcl-lang.org/man/tcl8.6/TkCmd/
        tk_mac.htm, ::tk::mac::ShowPreferences).

        What cannot be fixed from here is the NAME. It comes from the bundle's CFBundleName,
        so it reads "Python" until this ships as an application bundle, and no Tk call
        changes that. ::tk::mac::standardAboutPanel is not used for the About item for the
        same reason -- it fills itself from that bundle, so it would show Wish's version
        rather than locallm's.
        """
        bar = tk.Menu(self.root, tearoff=0)      # a menubar with a tearoff entry has one before the apple menu
        if self.aqua:
            apple = tk.Menu(bar, name="apple", tearoff=0)
            apple.add_command(label="About locallm", command=self.show_about)
            bar.add_cascade(menu=apple)
            for proc_name, command in (("tk::mac::ShowPreferences", self.show_preferences),
                                       ("tk::mac::ShowHelp", self.show_about)):
                try:
                    self.root.createcommand(proc_name, command)
                except tk.TclError:
                    pass
        m = tk.Menu(bar, tearoff=0)
        m.add_command(label="Open the run notes", command=lambda: self.open_path(RUNS / "NOTES-home.md"))
        m.add_command(label="Reload locallm's code", command=self.restart_app)
        if not self.aqua:                     # on Aqua both of these are the Application menu's own
            m.add_separator()
            m.add_command(label="Settings…", command=self.show_preferences)
            m.add_separator()
            m.add_command(label="Quit", command=self.root.destroy)
        bar.add_cascade(label="File", menu=m)
        m = tk.Menu(bar, tearoff=0)
        for name in self.pages:
            m.add_command(label=name, command=lambda n=name: self.show_page(n))
        bar.add_cascade(label="View", menu=m)
        m = tk.Menu(bar, tearoff=0)
        m.add_command(label="What this window shows", command=self.show_about)
        bar.add_cascade(label="Help", menu=m)
        self.root.config(menu=bar)
        self.menubar = bar

    def show_note(self, title: str, text: str):
        """A plain toplevel for About and for Settings. Plain on purpose: it is
        wm_overrideredirect, not Toplevel, that Aqua handles badly (see Tip)."""
        old = getattr(self, "note_win", None)
        if old is not None and old.winfo_exists():
            old.destroy()
        win = self.note_win = tk.Toplevel(self.root, bg=BG)
        win.title(title)
        win.transient(self.root)
        body = tk.Label(win, text=text, bg=BG, fg=TEXT, font=self.f_body, justify="left", anchor="w",
                        wraplength=520, padx=SPACE.group, pady=SPACE.card)
        body.pack(fill="both", expand=True)     # no rewrap: this toplevel takes its width from the text
        Button(win, "Close", win.destroy, ACCENT, self, filled=False).pack(pady=(0, SPACE.card))

    def show_about(self):
        """What this is, and the three facts that decide whether it behaves here."""
        self.show_note("About locallm", (
            "locallm\n\n"
            "locallm builds small AI models from scratch. The models write programs, and seven independent "
            "proof systems each try to prove a program keeps its promise and to catch a deliberately broken "
            "copy of it. This window watches that happen and reads what it produced.\n\n"
            f"Python {sys.version.split()[0]}\n"
            f"Tk {self.root.tk.call('info', 'patchlevel')}, windowing system "
            f"{self.root.tk.call('tk', 'windowingsystem')}\n"
            + ("Pipeline steps can run on this machine.\n" if HOST_CAN_RUN_STEPS else
               "Pipeline steps cannot run on this machine: they need a POSIX shell.\n")
            + ("Watching the lab workstation.\n" if self.remote else "Reading this machine's own files.\n")))

    def show_preferences(self):
        """macOS enables Preferences only when ::tk::mac::ShowPreferences is defined, so it
        has to lead somewhere real. Every setting this window has is a file or an environment
        variable read once at start -- there is nothing here to click -- so it says where
        they are, which is what someone opening Preferences wants to know."""
        rows = [("Lab workstation", "T_LAB, or t/lab-workstation.conf",
                 self.remote or "not set: this machine's own files"),
                ("Pipeline steps", "t/steps.json", f"{len(STEPS)} steps, reread by Reload steps"),
                ("Python that has torch", "T_PY", PY),
                ("Check events", "T_WATCH, or t/paths.py", str(EVENTS)),
                ("Scratch for model tests", "T_LAB_SCRATCH, or t/paths.py", str(SCRATCH)),
                ("Where the window was left", "XDG_CACHE_HOME, or t/paths.py", str(GEOMETRY))]
        self.show_note("Settings", "Read once at start, from these files and variables. Change them there, then "
                                   "Reload steps or Refresh locallm.\n\n"
                       + "\n\n".join(f"{what}\n    {where}\n    {value}" for what, where, value in rows))

    # -- Home, Train and Live checks ---------------------------------------------
    # What an embedded page is handed. This was a hand-written list of the eleven
    # keys the shell had an opinion about, with the rest -- the plot series, the log
    # surface, the amber warning -- left to studio.py's own literals, so one window
    # drew from two palettes. It is now look.py's whole palette, every key, so there
    # is nothing left to keep in step. A copy rather than the module's dict: an
    # embedded page must not be able to edit the shell's colours. Home takes the same
    # one; the name stays TRAIN_PALETTE because locallm/look.py and
    # locallm/studio.py both name it in comments and this file cannot edit those.
    TRAIN_PALETTE = dict(C)

    def build_home(self, page):
        """Host locallm/home.py's front page as the first page of this window.

        The same shape as build_train below, for the same two reasons. Home is a
        ttk.Frame that takes a parent and, embedded, the host's palette, so it needs
        no second Tk root -- two tk.Tk() roots in a process is undefined behaviour
        rather than untidy, since the first mainloop() opens both windows and blocks
        until both close (stackoverflow.com/q/39417091). And the import is lazy, so
        a front page that cannot be built costs this page and not the window.

        THE LAZINESS BUYS SOMETHING DIFFERENT HERE, and the difference is worth
        keeping straight. studio.py cannot be imported at all without torch;
        home.py deliberately can -- it reaches studio through its own engine() and
        its cards say in words which of them cannot work without it, which is why
        this page is built in remote mode and on a machine with no torch rather
        than replaced by a note. So the failure below is for home.py itself being
        absent or broken, and it names the file rather than torch.

        MEASURED here 2026-09-20 with no torch installed: home.Home(page,
        embedded=True) builds and update() returns, and engine() reports the missing
        torch to the cards.

        THE SELF-RELOAD WATCHER NEEDS NOTHING ADDED. watched_files() derives its set
        from sys.modules filtered to this repository, so the import below is what puts
        locallm/home.py in it, and because this runs inside __init__ -- before the
        first mtime snapshot is taken at the end of it -- an edit to that file reloads
        the window instead of reading as a file that only just appeared. Checked
        rather than assumed 2026-09-20: with Home built, watched_files() returns
        home.py, lab.py, look.py and steps.json.

        ONE TRAP THIS PAGE BRINGS, written down because it cost an hour and it is
        tkinter's, not ours. Home schedules its own queue drain with self.after, so
        the shell now has a descendant widget owning an after command -- nothing in
        this window did before, because studio.py cannot be imported here. Cancelling
        every pending after THROUGH THE ROOT and then destroying the root now raises
        TclError("can't delete Tcl command"): Misc.after_cancel deletes the script
        through whichever widget it was called on and drops the name from that
        widget's _tclCommands only, and Misc.destroy then walks the owning widget's
        list and calls tk.deletecommand on a name that is already gone, unguarded
        (github.com/python/cpython, Lib/tkinter/__init__.py, Misc.after_cancel,
        Misc.deletecommand, Misc.destroy -- read 2026-09-20 against 3.14). No path in
        this window does that; restart_app replaces the process with os.execv. A test
        teardown that cancels afters from the root and then destroys does, and the fix
        belongs there: cancel through the widget that scheduled it, or destroy first.
        """
        try:
            import home                                         # noqa: PLC0415
        except Exception as e:                                    # noqa: BLE001
            tk.Label(page, bg=BG, fg=RED, font=self.f_body, justify="left", anchor="w",
                     wraplength=760, padx=SPACE.tight, pady=SPACE.item,
                     text=("locallm's front page could not be loaded, so this window opened "
                           "on the page behind it.\n\n"
                           "It lives in locallm/home.py beside this file's own folder, and it "
                           "needs nothing but tkinter and locallm/look.py to open.\n\n"
                           f"What python said: {type(e).__name__}: {e}")
                     ).pack(anchor="w", padx=SPACE.inner, pady=SPACE.inner)
            return
        try:
            self.home = home.Home(page, embedded=True, palette=self.TRAIN_PALETTE)
        except Exception as e:                                    # noqa: BLE001
            tk.Label(page, bg=BG, fg=RED, font=self.f_body, justify="left", anchor="w",
                     wraplength=760, text=f"locallm's front page failed to start.\n\n"
                                          f"{type(e).__name__}: {e}"
                     ).pack(anchor="w", padx=SPACE.inner, pady=SPACE.inner)

    def build_train(self, page):
        """Host locallm/studio.py's training surface as a page of this window.

        Imported HERE rather than at the top of the file, on purpose: studio.py
        imports torch at module scope, and this shell runs perfectly well without
        torch for everything except training and testing a model. A top-level
        import would make the whole window refuse to open on a machine that only
        wants to watch the checkers. t/lab.py already does exactly this for torch
        itself (see run_model), so the pattern is the file's own.

        There is ONE Tk root in this process and this shell owns it. Studio is a
        ttk.Frame and takes a parent, so it embeds without a second root, which
        matters because two tk.Tk() roots is undefined behaviour rather than
        untidy: the first mainloop() opens both windows and blocks until both
        close (stackoverflow.com/q/39417091).
        """
        if self.remote:
            tk.Label(page, bg=BG, fg=MUTED, font=self.f_body, justify="left", anchor="w",
                     wraplength=760, padx=SPACE.tight, pady=SPACE.item,
                     text=("This window is pointed at the lab workstation, so the steps "
                           "run there and this machine only reads what they produce.\n\n"
                           "Training builds a model from text on the machine you are "
                           "sitting at. To do that here, unset the lab target "
                           "(t/lab-workstation.conf) and install torch for this python; "
                           "to train on the workstation, run locallm there.")
                     ).pack(anchor="w", padx=SPACE.inner, pady=SPACE.inner)
            return
        try:
            import studio                                       # noqa: PLC0415
        except Exception as e:                                   # noqa: BLE001
            missing = "torch" in str(e)
            tk.Label(page, bg=BG, fg=MUTED, font=self.f_body, justify="left",
                     anchor="w", wraplength=760, padx=SPACE.tight, pady=SPACE.item,
                     text=("Training needs torch, the one locallm trains with, and it is "
                           "not installed for this python.\n\n"
                           "Everything else in this window works without it: the live "
                           "checks, the results and the collected data are all read from "
                           "files.\n\n"
                           f"What python said: {e}"
                           if missing else
                           f"The training surface could not be loaded.\n\n{type(e).__name__}: {e}")
                     ).pack(anchor="w", padx=SPACE.inner, pady=SPACE.inner)
            return
        try:
            self.studio = studio.Studio(page, embedded=True, palette=self.TRAIN_PALETTE)
        except Exception as e:                                   # noqa: BLE001
            tk.Label(page, bg=BG, fg=RED, font=self.f_body, justify="left", anchor="w",
                     wraplength=760, text=f"The training surface failed to start.\n\n"
                                          f"{type(e).__name__}: {e}"
                     ).pack(anchor="w", padx=SPACE.inner, pady=SPACE.inner)

    def build_live(self, page):
        tiles = tk.Frame(page, bg=BG)
        tiles.pack(fill="x", pady=(0, SPACE.item))
        self.tile = {}
        for i, (key, label, color, hint) in enumerate((
                ("now", "Checking now", UNSETTLED, "Programs a checker is working on"),
                ("proven", "Proven", GREEN, "Promise proved, broken copy caught"),
                ("not", "Not proven", RED, "Bug found, not proven, or promise too weak"),
                ("done", "Finished", TEXT, "Every check that has ended"))):
            t = tk.Frame(tiles, bg=CARD, highlightthickness=1, highlightbackground=LINE)
            t.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else SPACE.item, 0))
            tiles.columnconfigure(i, weight=1)
            tk.Frame(t, bg=color, height=3).pack(fill="x")
            n = tk.Label(t, text="0", bg=CARD, fg=color, font=self.f_num)
            n.pack(anchor="w", padx=SPACE.card, pady=(SPACE.item, 0))
            tk.Label(t, text=label, bg=CARD, fg=TEXT, font=self.f_bold).pack(anchor="w", padx=SPACE.card)
            tk.Label(t, text=hint, bg=CARD, fg=FAINT, font=self.f_small).pack(
                anchor="w", padx=SPACE.card, pady=(0, SPACE.item))
            self.tile[key] = n

        cols = tk.Frame(page, bg=BG)
        cols.pack(fill="both", expand=True)
        right = tk.Frame(cols, bg=BG, width=370)
        right.pack(side="right", fill="y", padx=(SPACE.item, 0))
        right.pack_propagate(False)
        left = tk.Frame(cols, bg=BG)
        left.pack(side="left", fill="both", expand=True)

        c = self.card(left, "Checking right now")
        self.now = self.table(c, [("program", "Program", 300), ("checker", "Checker", 110),
                                  ("secs", "Running for", 110), ("mem", "Memory", 100)], 3)
        c = self.card(left, "Just finished", "newest first", fill="both", expand=True)
        self.done = self.table(c, [("time", "Time", 80), ("program", "Program", 230), ("checker", "Checker", 90),
                                   ("result", "Result", 170), ("meaning", "What it means", 460)], 6)
        self.rounds_parent, self.done_outer = left, c.master

        c = self.card(right, "What the results mean")
        for real, twin in (("verified", "refuted"), ("refuted", ""), ("unproved", ""), ("verified", "verified"),
                           ("timeout", ""), ("abstain", "")):
            say = verdict(real, twin)
            row = tk.Frame(c, bg=CARD)
            row.pack(fill="x", pady=SPACE.tight)
            tk.Label(row, text=say.mark, bg=CARD, fg=C[say.tone], font=self.f_h2, width=2,
                     anchor="n").pack(side="left", anchor="n")
            txt = tk.Frame(row, bg=CARD)
            txt.pack(side="left", fill="x")
            tk.Label(txt, text=say.word, bg=CARD, fg=C[say.tone], font=self.f_bold, anchor="w").pack(anchor="w")
            tk.Label(txt, text=say.why, bg=CARD, fg=MUTED, font=self.f_small, anchor="w", justify="left",
                     wraplength=290).pack(anchor="w")

        c = self.card(self.rounds_parent, "Model rounds", "from the loop log you chose", before=self.done_outer)
        self.rounds_outer = c.master
        self.rounds_outer.pack_forget()
        note = tk.Label(c, bg=CARD, fg=MUTED, font=self.f_small, justify="left", wraplength=900, anchor="w", text=(
            "Each round, locallm builds a new model from every clean program found so far, "
            "and that model writes new programs."))
        note.pack(fill="x")
        self.rewrap(note)
        row = tk.Frame(c, bg=CARD)
        row.pack(fill="x", pady=SPACE.inner)
        self.log_var = tk.StringVar()
        entry(row, self.log_var, self).pack(side="left", fill="x", expand=True, ipady=SPACE.tight)
        Button(row, "Choose another", self.follow_loop, ACCENT, self,
               filled=False).pack(side="left", padx=(SPACE.inner, 0))
        self.rounds = self.table(c, [("round", "Round", 55), ("written", "Written", 70), ("new", "New", 55),
                                     ("clean", "Clean", 55), ("share", "Clean %", 70)], 3)
        note = tk.Label(c, bg=CARD, fg=FAINT, font=self.f_small, justify="left", wraplength=900, anchor="w", text=(
            "Written: programs the model wrote. New: not copied from what it learned from. "
            "Clean: new and proven by all seven."))
        note.pack(fill="x", pady=(SPACE.inner, 0))
        self.rewrap(note)

    def poll_events(self):
        try:
            size = EVENTS.stat().st_size
            if size < self.offset:
                self.offset = 0
            if size > self.offset:
                with open(EVENTS, encoding="utf-8") as fh:
                    fh.seek(self.offset)
                    chunk = fh.read()
                keep = chunk.rfind("\n") + 1
                self.offset += len(chunk[:keep].encode("utf-8"))
                for line in chunk[:keep].splitlines():
                    try:
                        ev = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    key = (ev.get("task", "?"), ev.get("kernel", "?"))
                    if ev.get("ev") == "start":
                        self.running[key] = ev
                    elif ev.get("ev") == "end":
                        self.running.pop(key, None)
                        say = verdict(ev.get("real"), ev.get("twin"), ev.get("agree", True))
                        self.counts["done"] += 1
                        self.end_times.append(ev.get("t", time.time()))
                        self.end_pairs.append((ev.get("t", time.time()), ev.get("task", "")))
                        self.counts["proven"] += say.word == "Proven"
                        self.counts["not"] += say.tone == "refuted"
                        self.done.insert("", 0, tags=(say.tone,), values=(
                            time.strftime("%H:%M:%S", time.localtime(ev["t"])), key[0],
                            CHECKER.get(key[1], key[1]), f"{say.mark}  {say.word}", say.why))
                        for extra in self.done.get_children()[300:]:
                            self.done.delete(extra)
        except FileNotFoundError:
            pass
        self.root.after(300, self.poll_events)

    def tick(self):
        self.now.delete(*self.now.get_children())
        now = time.time()
        for (task, kernel), ev in sorted(self.running.items(), key=lambda kv: kv[1]["t"]):
            mem = None if self.remote else memory_mb(ev.get("pid", -1))
            self.now.insert("", "end", tags=("unsettled",), values=(
                task, CHECKER.get(kernel, kernel), f"{now - ev['t']:.0f} s", "" if mem is None else f"{mem:.0f} MB"))
        for key, value in (("now", len(self.running)), ("proven", self.counts["proven"]),
                           ("not", self.counts["not"]), ("done", self.counts["done"])):
            self.tile[key].configure(text=str(value))
        busy = bool(self.running)
        if self.remote:
            age = int(now - self.lab_received) if self.lab_received else 0
            status = self.lab_error or f"Lab connected · updated {age}s ago"
            self.pulse.configure(text=f"●  {status}", fg=RED if self.lab_error else GREEN)
        else:
            self.pulse.configure(text="●  checking" if busy else "●  idle", fg=UNSETTLED if busy else FAINT)
        rows = {}
        if self.log_var.get():
            try:
                for line in Path(self.log_var.get()).read_text(errors="replace").splitlines():
                    m = LOOP_RE.search(line)
                    if m:
                        rows.setdefault(m.group(1), {}).update(written=m.group(3), new=m.group(6))
                    m = CLEAN_RE.search(line)
                    if m:
                        rows.setdefault(m.group(1), {})["clean"] = m.group(2)
            except OSError:
                pass
        self.rounds.delete(*self.rounds.get_children())
        for r, v in sorted(rows.items(), key=lambda kv: int(kv[0])):
            share = (f"{100 * int(v['clean']) / int(v['written']):.1f}%"
                     if "clean" in v and int(v.get("written", 0) or 0) else "checking")
            self.rounds.insert("", "end", tags=("proved",) if "clean" in v else (), values=(
                r, v.get("written", ""), v.get("new", ""), v.get("clean", ""), share))
        self.root.after(1000, self.tick)

    # -- Test a model --------------------------------------------------------------
    def build_test(self, page):
        top = tk.Frame(page, bg=BG)
        top.pack(fill="x")
        leftcol = tk.Frame(top, bg=BG)
        leftcol.pack(side="left", fill="both", expand=True)
        rightcol = tk.Frame(top, bg=BG)
        rightcol.pack(side="left", fill="both", expand=True, padx=(SPACE.item, 0))
        self.models = find_models()

        c = self.card(leftcol, "1   Choose a model")
        self.model_a = tk.StringVar(value=self.models[0] if self.models else "")
        self.model_b, self.corpus_var = tk.StringVar(), tk.StringVar()
        for label, var, tip, is_dir in (
                ("Model", self.model_a, "A folder locallm wrote. It holds ckpt.pt (the model) and tokenizer.json.", True),
                ("Compare with", self.model_b, "Optional. A second model, tested the same way, for a side by side result.", True),
                ("Learned from", self.corpus_var, "The text the model was built from, used to spot programs it only "
                                                  "copied. Filled in when it can be found.", False)):
            row = tk.Frame(c, bg=CARD)
            row.pack(fill="x", pady=SPACE.tight)
            lab = tk.Label(row, text=label, bg=CARD, fg=MUTED, font=self.f_body, width=13, anchor="w")
            lab.pack(side="left")
            Tip(lab, tip, self)
            entry(row, var, self).pack(side="left", fill="x", expand=True, ipady=SPACE.tight)
            if is_dir:
                Button(row, "▾", lambda v=var: self.model_menu(v), ACCENT, self,
                       filled=False).pack(side="left", padx=(SPACE.inner, 0))
            Button(row, "Browse", (lambda v=var: self.browse_dir(v)) if is_dir else (lambda v=var: self.browse_file(v)),
                   ACCENT, self, filled=False).pack(side="left", padx=(SPACE.inner, 0))
        self.model_a.trace_add("write", lambda *_: self.fill_corpus())
        self.fill_corpus()

        c = self.card(leftcol, "2   What should it write?")
        row = tk.Frame(c, bg=CARD)
        row.pack(fill="x")
        lab = tk.Label(row, text="Start with", bg=CARD, fg=MUTED, font=self.f_body, width=13, anchor="w")
        lab.pack(side="left")
        Tip(lab, "The text the model continues from. \"t 1\" is how a t program begins. "
                 "\"Problem: ...\" asks for a specific program.", self)
        self.prompt_var = tk.StringVar(value="t 1")
        entry(row, self.prompt_var, self, width=18).pack(side="left", ipady=SPACE.tight)
        tk.Label(row, text="How many", bg=CARD, fg=MUTED,
                 font=self.f_body).pack(side="left", padx=(SPACE.card, SPACE.inner))
        self.n_var = tk.StringVar(value="50")
        entry(row, self.n_var, self, width=6).pack(side="left", ipady=SPACE.tight)
        self.more_on = tk.BooleanVar(value=False)
        Chip(row, "More settings", self.more_on, self, command=self.toggle_more).pack(side="left", padx=(SPACE.card, 0))
        self.more = tk.Frame(c, bg=CARD)
        self.len_var, self.temp_var = tk.StringVar(value="700"), tk.StringVar(value="0.8")
        self.topk_var, self.jobs_var = tk.StringVar(value="40"), tk.StringVar(value="4")
        for label, var, tip in (
                ("Length", self.len_var, "How many characters the model writes for each program."),
                ("Creativity", self.temp_var, "Higher gives more varied programs, lower gives safer, repetitive ones. 0.8 is a good start."),
                ("Choices", self.topk_var, "How many likely next letters the model picks from."),
                ("Checks at once", self.jobs_var, "How many programs are checked at the same time. About a quarter of your computer's cores.")):
            lab = tk.Label(self.more, text=label, bg=CARD, fg=MUTED, font=self.f_small)
            lab.pack(side="left", padx=(0, SPACE.inner))
            Tip(lab, tip, self)
            entry(self.more, var, self, width=6).pack(side="left", padx=(0, SPACE.card), ipady=SPACE.tight)

        c = self.card(rightcol, "3   Which checks?")
        self.chk = {k: tk.BooleanVar(value=True) for k in ("parse", "wf", "novel")}
        row = tk.Frame(c, bg=CARD)
        row.pack(fill="x")
        for k, label, tip in (("parse", "Readable", "The text is a valid t program."),
                              ("wf", "Follows the rules", "Passes t's basic rules: names defined, types line up, loops explained."),
                              ("novel", "New", "Not a copy of a program the model learned from.")):
            chip = Chip(row, label, self.chk[k], self)
            chip.pack(side="left", padx=(0, SPACE.inner))
            Tip(chip, tip, self)
        lab = tk.Label(c, text="Proven by", bg=CARD, fg=MUTED, font=self.f_body, anchor="w")
        lab.pack(fill="x", pady=(SPACE.item, SPACE.inner))
        Tip(lab, "Each checker tries to prove the program keeps its promise and to catch a broken copy. "
                 "Every checker adds time; Dafny is the fastest.", self)
        self.kchk = {k: tk.BooleanVar(value=(k == "dafny")) for k in KERNELS}
        row = tk.Frame(c, bg=CARD)
        row.pack(fill="x")
        for k in KERNELS:
            Chip(row, CHECKER[k], self.kchk[k], self).pack(side="left", padx=(0, SPACE.inner))
        lab = tk.Label(c, text="Your own test (optional)", bg=CARD, fg=MUTED, font=self.f_body, anchor="w")
        lab.pack(fill="x", pady=(SPACE.item, SPACE.inner))
        Tip(lab, "Any command. {file} becomes the program's file. It passes when the command exits with 0. "
                 "Example: grep -q ensures {file}", self)
        self.custom_var = tk.StringVar()
        entry(c, self.custom_var, self).pack(fill="x", ipady=SPACE.tight)

        bar = tk.Frame(page, bg=BG)
        bar.pack(fill="x", pady=(0, SPACE.item))
        self.run_btn = Button(bar, "▶   Run test", self.start_test, ACCENT, self)
        self.run_btn.pack(side="left")
        Button(bar, "■   Stop", self.stop_flag.set, RED, self, filled=False).pack(side="left", padx=SPACE.item)
        self.status = tk.Label(bar, text="", bg=BG, fg=MUTED, font=self.f_body)
        self.status.pack(side="left", padx=SPACE.inner)
        self.summary = tk.Label(page, text="", bg=BG, fg=TEXT, font=self.f_bold, justify="left", anchor="w",
                                wraplength=1300)
        self.summary.pack(fill="x", pady=(0, SPACE.inner))
        self.rewrap(self.summary)

        lower = tk.Frame(page, bg=BG)
        lower.pack(fill="both", expand=True)
        c = self.card(lower, "Programs", f"{look.PROVED} yes   {look.REFUTED} no   "
                                        f"{look.NOT_APPLICABLE} not checked   click a row to read it",
                      side="left", fill="both", expand=True)
        cols = [("model", "Model", 60), ("n", "#", 45), ("readable", "Readable", 80), ("rules", "Rules", 60),
                ("new", "New", 50)] + [(k, CHECKER[k], 62) for k in KERNELS] + [("yours", "Yours", 55), ("clean", "Clean", 60)]
        self.results = self.table(c, cols, 8)
        for col in self.results["columns"]:
            self.results.column(col, anchor="center")
        self.results.bind("<<TreeviewSelect>>", self.show_sample)
        c = self.card(lower, "The program", side="left", fill="both", expand=True, padx=(SPACE.item, 0))
        self.sample_text = tk.Text(c, width=46, height=12, wrap="none", bg=SURFACE, fg=TEXT, insertbackground=TEXT,
                                   relief="flat", font=self.f_mono, padx=SPACE.item, pady=SPACE.inner,
                                   highlightthickness=0)
        self.sample_text.pack(fill="both", expand=True)

    def toggle_more(self):
        if self.more_on.get():
            self.more.pack(fill="x", pady=(SPACE.item, 0))
        else:
            self.more.pack_forget()

    def model_menu(self, var):
        menu = tk.Menu(self.root, tearoff=0, font=self.f_small)
        if not self.models:
            menu.add_command(label="No models found yet. Use Browse.", state="disabled")
        for m in self.models:
            menu.add_command(label=m, command=lambda m=m: var.set(m))
        menu.tk_popup(self.root.winfo_pointerx(), self.root.winfo_pointery())

    def fill_corpus(self):
        c = guess_corpus(Path(self.model_a.get())) if self.model_a.get() else None
        if c:
            self.corpus_var.set(str(c))

    def browse_dir(self, var):
        d = filedialog.askdirectory(initialdir=var.get() or str(Path.home()))
        if d:
            var.set(d)

    def browse_file(self, var):
        p = filedialog.askopenfilename(initialdir=str(Path(var.get()).parent) if var.get() else str(Path.home()))
        if p:
            var.set(p)

    def show_sample(self, _e=None):
        sel = self.results.selection()
        if sel:
            self.sample_text.delete("1.0", "end")
            self.sample_text.insert("1.0", self.samples.get(sel[0], ""))

    @staticmethod
    def number(var, default, kind=int):
        try:
            return kind(var.get())
        except ValueError:
            return default

    def start_test(self):
        models = [m for m in (self.model_a.get(), self.model_b.get()) if m]
        if not models:
            self.status.configure(text="Choose a model first (step 1).", fg=RED)
            return
        prompt = self.prompt_var.get()
        s = dict(prompt=prompt if prompt.endswith("\n") else prompt + "\n",
                 n=self.number(self.n_var, 50), length=self.number(self.len_var, 700),
                 temp=self.number(self.temp_var, 0.8, float), topk=self.number(self.topk_var, 40),
                 jobs=self.number(self.jobs_var, 4), parse=self.chk["parse"].get(), wf=self.chk["wf"].get(),
                 novel=self.chk["novel"].get(), kernels=[k for k in KERNELS if self.kchk[k].get()],
                 custom=self.custom_var.get().strip(), corpus=self.corpus_var.get())
        self.results.delete(*self.results.get_children())
        self.samples.clear()
        self.summary.configure(text="")
        self.stop_flag.clear()
        self.run_btn.set_enabled(False)
        threading.Thread(target=self.run_tests, args=(models, s), daemon=True).start()

    def drain(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "lab_snapshot":
                    self.show_lab_snapshot(payload)
                elif kind == "lab_error":
                    self.lab_error = payload
                    self.remote_hint.configure(text=payload, fg=RED)
                elif kind == "labgpu":
                    self.show_lab_gpu(payload)
                elif kind == "steps_error":
                    self.step_hint.configure(text=payload, fg=RED)
                elif kind == "results":
                    self.show_results(*payload)
                elif kind == "status":
                    self.status.configure(text=payload, fg=MUTED)
                elif kind == "row":
                    iid, values, text, clean = payload
                    self.samples[iid] = text
                    tags = ("green" if clean else "red",)
                    if self.results.exists(iid):
                        self.results.item(iid, values=values, tags=tags)
                    else:
                        self.results.insert("", "end", iid=iid, values=values, tags=tags)
                elif kind == "summary":
                    self.summary.configure(text=payload)
                elif kind == "error":
                    self.status.configure(text=payload, fg=RED)
                elif kind == "done":
                    self.run_btn.set_enabled(True)
        except queue.Empty:
            pass
        self.root.after(200, self.drain)

    # -- the test itself, off the window's thread ---------------------------------
    def run_tests(self, models, s):
        lines = []
        try:
            for i, model in enumerate(models):
                lines.append(self.test_one("A" if i == 0 else "B", Path(model), s))
                self.q.put(("summary", "\n".join(lines)))
                if self.stop_flag.is_set():
                    break
        except Exception as e:                                  # noqa: BLE001
            self.q.put(("error", f"Something went wrong: {type(e).__name__}: {e}"))
        finally:
            self.q.put(("done", None))

    def test_one(self, label, model_dir: Path, s) -> str:
        import torch
        import checkpoint
        self.q.put(("status", f"Model {label}: loading"))
        model, tok, _cfg = checkpoint.load_checkpoint(str(model_dir))
        params = sum(p.numel() for p in model.parameters())
        corpus = guess_corpus(model_dir) if label == "B" else (Path(s["corpus"]) if s["corpus"] else None)
        seen = corpus_keys(corpus) if (s["novel"] and corpus and corpus.is_file()) else set()
        run = SCRATCH / time.strftime("%Y%m%d-%H%M%S") / label
        (run / "tasks").mkdir(parents=True, exist_ok=True)
        rows, texts = {}, {}
        torch.manual_seed(1)
        for i in range(s["n"]):
            if self.stop_flag.is_set():
                break
            self.q.put(("status", f"Model {label}: writing program {i + 1} of {s['n']}"))
            text = checkpoint.sample(model, tok, s["prompt"], s["length"], temperature=s["temp"], top_k=s["topk"])
            task = first_task(text)
            r = {"parse": task is not None, "wf": None, "novel": None, "k": {}, "custom": None}
            name = f"lab_{label.lower()}_{i}"
            if task is not None:
                try:
                    task = se.rename_task(task, name)
                    r["wf"] = not fuzz_lower.check_wf(task)
                except Exception:                               # noqa: BLE001
                    r["wf"] = False
                if s["novel"] and corpus:
                    r["novel"] = task_key(task) not in seen
                if r["wf"] and r["novel"] is not False:
                    (run / "tasks" / f"{name}.t").write_text(surface.print_task(task), encoding="utf-8")
            (run / f"{name}.txt").write_text(text, encoding="utf-8")
            if s["custom"]:
                path = str(run / f"{name}.txt")
                cmd = s["custom"].replace("{file}", f'"{path}"' if os.name == "nt" else shlex.quote(path))
                r["custom"] = subprocess.run(cmd, shell=True, capture_output=True).returncode == 0
            rows[name], texts[name] = r, text
            self.emit(label, i, name, r, s, text)
        if s["kernels"] and any((run / "tasks").iterdir()) and not self.stop_flag.is_set():
            n_tasks = len(list((run / "tasks").iterdir()))
            names = ", ".join(CHECKER[k] for k in s["kernels"])
            self.q.put(("status", f"Model {label}: {names} checking {n_tasks} programs (see Live checks)"))
            env = dict(os.environ, PATH=KERNEL_PATH + os.pathsep + os.environ.get("PATH", ""), T_WATCH=str(EVENTS),
                       T_MIN_KERNELS="1")
            EVENTS.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run([sys.executable, str(HERE / "run_par.py"), "--kernels", ",".join(s["kernels"]),
                            "--jobs", str(s["jobs"]), "--tasks", str(run / "tasks"), "--out", str(run / "kernels"),
                            "--table", str(run / "table.md")], env=env, capture_output=True)
            try:
                header = None
                for line in (run / "table.md").read_text().splitlines():
                    cells = [x.strip() for x in line.strip().strip("|").split("|")]
                    if cells and cells[0] == "task":
                        header = cells
                    elif header and cells and cells[0] in rows:
                        rows[cells[0]]["k"] = dict(zip(header[1:], cells[1:]))
            except OSError:
                pass
            for i, name in enumerate(rows):
                self.emit(label, i, name, rows[name], s, texts[name])
        n = len(rows)

        def count(fn):
            return sum(1 for r in rows.values() if fn(r))
        parts = []
        if s["parse"]:
            parts.append(f"{count(lambda r: r['parse'])} readable")
        if s["wf"]:
            parts.append(f"{count(lambda r: r['wf'])} follow the rules")
        if s["novel"]:
            parts.append(f"{count(lambda r: r['novel'])} new" if corpus else "copy check skipped (no training text)")
        for k in s["kernels"]:
            parts.append(f"{count(lambda r, k=k: r['k'].get(k) == 'verified / refuted')} proven by {CHECKER[k]}")
        if s["custom"]:
            parts.append(f"{count(lambda r: r['custom'])} pass your test")
        clean = count(lambda r: self.passes(r, s))
        self.q.put(("status", f"Model {label}: done. Files in {run}"))
        return (f"Model {label}  ({params / 1e6:.1f} million parameters) wrote {n} programs:  " + ",  ".join(parts)
                + f".     {look.PROVED} CLEAN: {clean} of {n} ({100 * clean / max(n, 1):.0f}%)")

    @staticmethod
    def passes(r, s) -> bool:
        if s["parse"] and not r["parse"]:
            return False
        if s["wf"] and not r["wf"]:
            return False
        if s["novel"] and r["novel"] is False:
            return False
        if any(r["k"].get(k) != "verified / refuted" for k in s["kernels"]):
            return False
        if s["custom"] and not r["custom"]:
            return False
        return True

    def emit(self, label, i, name, r, s, text):
        cells = []
        for k in KERNELS:
            if k not in s["kernels"] or k not in r["k"]:
                cells.append(look.NOT_APPLICABLE)
            else:
                real, _, twin = r["k"][k].partition("/")
                cells.append(verdict(real, twin).mark)
        values = (label, i + 1, mark(r["parse"]), mark(r["wf"]), mark(r["novel"]), *cells, mark(r["custom"]),
                  mark(self.passes(r, s)))
        self.q.put(("row", (name, values, text, self.passes(r, s))))

    # -- Collect data ----------------------------------------------------------------
    # `uses` still says which machine a step occupies, because t/overnight.py will not start two steps that
    # want the same one. The window does not print it: they all say the lab workstation now.
    USES_WORDS = {"gpu": "graphics card", "cpu": "cores here", "lab": "lab workstation",
                  "gen": "a generator, here or on the lab"}

    def reload_steps(self):
        """Re-read t/steps.json and rebuild the boxes, so a step added by hand appears without a restart."""
        STEPS[:] = load_steps()
        for w in list(self.box_area.winfo_children()):
            w.destroy()
        self.boxes = {}
        self.build_boxes()
        self.step_hint.configure(text=f"{len(STEPS)} steps from t/steps.json", fg=FAINT)

    def build_boxes(self):
        """One box per step: what it is, how far along, and what it has produced. Green while it runs."""
        for i, (key, title, what, _cmd, _check, uses) in enumerate([s[:6] for s in STEPS], 1):
            box = tk.Frame(self.box_area, bg=CARD, highlightthickness=2, highlightbackground=LINE)
            box.pack(fill="x", pady=(0, SPACE.inner))
            edge = tk.Frame(box, bg=LINE, width=4)
            edge.pack(side="left", fill="y")
            body = tk.Frame(box, bg=CARD)
            body.pack(side="left", fill="both", expand=True, padx=SPACE.item, pady=SPACE.item)
            head = tk.Frame(body, bg=CARD)
            head.pack(fill="x")
            name = tk.Label(head, text=f"{i}.  {title}", bg=CARD, fg=TEXT, font=self.f_h2)
            name.pack(side="left")
            state = tk.Label(head, text="not yet", bg=CARD, fg=FAINT, font=self.f_bold)
            state.pack(side="right")
            # No Run button, 2026-09-18: the steps are driven from a terminal, and a button that starts a
            # second copy of a step already running is a way to lose a night's work. This tab watches.
            # No machine on the box, 2026-09-18: every step runs on the lab workstation now, so naming a
            # machine said the same thing 39 times and said it wrongly whenever a step moved.
            #
            # The empty track takes a hairline, not just a fill shift. look measures the
            # sunken ground against a card at 1.101:1 in the light theme, which is a real
            # difference on this desk and none at all on a dim laptop screen, and a
            # progress bar nobody can see the end of is not a progress bar.
            bar = tk.Canvas(body, bg=SURFACE, height=8, highlightthickness=1,
                            highlightbackground=LINE)
            bar.pack(fill="x", pady=(SPACE.inner, SPACE.tight))
            prog = tk.Label(body, text="", bg=CARD, fg=MUTED, font=self.f_small, anchor="w")
            prog.pack(fill="x")
            desc = tk.Label(body, text=what, bg=CARD, fg=FAINT, font=self.f_small, justify="left", anchor="w",
                            wraplength=1100)
            desc.pack(fill="x", pady=(SPACE.tight, 0))
            self.rewrap(desc)
            self.boxes[key] = {"box": box, "edge": edge, "state": state, "bar": bar, "prog": prog}
            for w in (box, body, head, name, desc, prog):
                w.bind("<Button-1>", lambda _e, k=key: self.select_step(k))

    def scroll_by(self, pixels: float):
        """A wheel notch moves a target, which scroll_ease glides towards: smooth instead of jumping by rows."""
        if self.pages["Collect data"].winfo_ismapped():
            span = max(1, self.box_area.winfo_height() - self.scroll_canvas.winfo_height())
            self.scroll_to = min(1.0, max(0.0, self.scroll_to + pixels / span))

    def scroll_ease(self):
        at = self.scroll_canvas.yview()[0]
        if abs(self.scroll_to - at) > 0.0008:
            self.scroll_canvas.yview_moveto(at + (self.scroll_to - at) * 0.22)
        else:
            self.scroll_to = at
        self.root.after(16, self.scroll_ease)

    def select_step(self, key: str):
        self.sel_key = key
        self.show_log()
        self.refresh_steps(once=True)

    def watch_own_code(self):
        """Reload when locallm's own code is fixed, so a window left open overnight is never stale.

        A fix lands here as a git pull or an edit to t/lab.py or t/steps.json while the window is up, and until
        2026-09-18 the window kept showing the state it was built with until someone pressed Refresh -- which
        reads as a second bug. A changed file is taken twice, two seconds apart, so a half-written file is not
        read as a new version, and nothing reloads while a step is being started or a log is open in a dialog."""
        now = {p: mtime(p) for p in watched_files()}
        # .get(p, now[p]) so a file that only just joined the set -- studio.py the
        # first time Train is opened -- does not read as a file that changed.
        moved = [p for p in now if now[p] != self.watched.get(p, now[p])]
        if moved and all(now[p] == mtime(p) for p in moved) and not self.root.grab_current():
            self.restart_app()
            return
        self.watched = now
        self.root.after(2000, self.watch_own_code)

    def restart_app(self):
        """Reload locallm's own code in place, keeping the window where it is: the geometry is written to
        GEOMETRY and read back on start, so a refresh after an edit costs no repositioning. It comes back on
        Collect data, which is the page the runs are driven from."""
        try:
            GEOMETRY.parent.mkdir(parents=True, exist_ok=True)
            GEOMETRY.write_text(self.root.winfo_geometry())
        except OSError:
            pass
        self.root.destroy()
        os.execv(sys.executable, [sys.executable, str(HERE / "lab.py"), "--page", "Collect data"])

    def build_remote_collect(self, page):
        self.remote_hint = tk.Label(page, text="Connecting to lab workstation…", bg=BG, fg=MUTED,
                                    font=self.f_body, anchor="w")
        self.remote_hint.pack(fill="x", pady=(0, SPACE.item))
        c = self.card(page, "Running on the lab workstation", "select a row to read its output")
        self.remote_runs = self.table(c, [("job", "Job", 320), ("kind", "Stage", 110),
                                          ("progress", "Progress", 240), ("elapsed", "Elapsed", 90)], 6)
        self.remote_runs.bind("<<TreeviewSelect>>", lambda _e: self.show_remote_log())
        c = self.card(page, "Answer sets", "generation and grading counts from the lab")
        self.remote_sets = self.table(c, [("tag", "Answer set", 340), ("answers", "Written", 90),
                                          ("tasks", "Well formed", 100), ("passed", "Tests pass", 100),
                                          ("graded", "Graded", 90), ("clean", "Clean", 90)], 6)
        c = self.card(page, "Output", "updated with each lab snapshot", fill="both", expand=True)
        self.log_text = log_pane(c, self, 8, "word")
        self.log_text.pack(fill="both", expand=True)
        self.remote_run_rows = {}

    def build_remote_ai(self, page):
        c = self.card(page, "Lab workstation", "all generation, training and checks run here")
        note = tk.Label(c, text="This window watches the run. Start pipeline steps from a terminal. "
                                "Stop releases our GPU jobs when the cards are needed.",
                        bg=CARD, fg=MUTED, font=self.f_body, wraplength=1100, justify="left")
        note.pack(fill="x")
        self.rewrap(note)
        row = tk.Frame(c, bg=CARD)
        row.pack(fill="x", pady=SPACE.item)
        self.gpu_state = tk.Label(row, text="Waiting for lab status", bg=CARD, fg=MUTED, font=self.f_bold)
        self.gpu_state.pack(side="left")
        Button(row, "Stop our GPU jobs", lambda: self.lab_gpu("stop"), RED, self).pack(side="right")
        self.gpu_log = log_pane(c, self, 12, "word")
        self.gpu_log.pack(fill="both", expand=True)
        c = self.card(page, "Status notes", fill="both", expand=True)
        self.alert_text = log_pane(c, self, 8, "word")
        self.alert_text.pack(fill="both", expand=True)

    def watch_lab(self):
        """One bounded SSH read for all tabs; no Tk calls or pipeline commands in this thread."""
        cursor = None
        while True:
            try:
                args = ["python3", "t/lab_status.py"]
                if cursor is not None:
                    args.extend(["--events-cursor", json.dumps(cursor, separators=(",", ":"))])
                p = subprocess.run(
                    ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "-o", "ServerAliveInterval=5",
                     "-o", "ServerAliveCountMax=2", self.remote, "cd ~/tup && " + shlex.join(args)],
                    capture_output=True, text=True, timeout=25)
                if p.returncode:
                    raise RuntimeError("Lab connection failed; retrying. Last snapshot is retained.")
                snapshot = json.loads(p.stdout)
                if snapshot.get("version") != 1:
                    raise ValueError("Unexpected lab status format")
                cursor = snapshot.get("events", {}).get("cursor")
                self.q.put(("lab_snapshot", snapshot))
            except (OSError, subprocess.SubprocessError, ValueError, RuntimeError):
                self.q.put(("lab_error", "Lab unavailable; retrying. Last snapshot is retained."))
            time.sleep(5)

    @staticmethod
    def replace_text(widget, text):
        if widget.get("1.0", "end").strip() != text.strip():
            at_end = widget.yview()[1] > 0.999
            widget.delete("1.0", "end")
            widget.insert("end", text)
            if at_end:
                widget.see("end")

    def show_remote_log(self):
        selection = self.remote_runs.selection()
        row = self.remote_run_rows.get(selection[0], {}) if selection else {}
        text = row.get("log") or "No output captured for this job yet."
        if not self.remote_run_rows:
            text = "No pipeline jobs are running on the lab workstation."
        self.replace_text(self.log_text, text)

    def show_lab_snapshot(self, snapshot):
        self.lab_snapshot, self.lab_error, self.lab_received = snapshot, "", time.time()
        runs = snapshot.get("runs", [])
        self.remote_hint.configure(text=f"Lab connected · {len(runs)} running jobs · updates every 5 seconds", fg=GREEN)
        selection = self.remote_runs.selection()
        selected = selection[0] if selection else None
        self.remote_runs.delete(*self.remote_runs.get_children())
        self.remote_run_rows = {}
        for run in runs:
            key = str(run["pid"])
            self.remote_run_rows[key] = run
            progress = run.get("progress", "")
            if isinstance(progress, (list, tuple)):
                progress = progress[0]
            elapsed = max(0, int(time.time() - run.get("started", time.time()))) // 60
            self.remote_runs.insert("", "end", iid=key, tags=("proved",), values=(
                run.get("title") or run.get("tag") or run["key"], run.get("kind", ""), progress, f"{elapsed} min"))
        if self.remote_run_rows:
            self.remote_runs.selection_set(selected if selected in self.remote_run_rows else next(iter(self.remote_run_rows)))
        self.show_remote_log()
        results = snapshot.get("results", {})
        sets = results.get("sets", [])
        self.remote_sets.delete(*self.remote_sets.get_children())
        active_tags = {r.get("tag") for r in runs}
        ordered = sorted(sets, key=lambda item: (item[0] in active_tags, item[1].get("updated", 0)), reverse=True)
        for tag, row in ordered:
            self.remote_sets.insert("", "end", tags=("proved" if tag in active_tags else "muted",), values=(
                tag, row.get("answers", 0), row["tasks"], row["passed"], row["graded"], row["clean"]))
        if results:
            self.show_results(sets, results["totals"], results["n_problems"], results["text"])
        events = snapshot.get("events", {})
        self.running = {(ev.get("task", "?"), ev.get("kernel", "?")): ev for ev in events.get("active", [])}
        for ev in events.get("items", []):
            if ev.get("ev") != "end":
                continue
            say = verdict(ev.get("real"), ev.get("twin"), ev.get("agree", True))
            self.counts["done"] += 1
            self.counts["proven"] += say.word == "Proven"
            self.counts["not"] += say.tone == "refuted"
            self.done.insert("", 0, tags=(say.tone,), values=(
                time.strftime("%H:%M:%S", time.localtime(ev.get("t", time.time()))), ev.get("task", "?"),
                CHECKER.get(ev.get("kernel"), ev.get("kernel", "?")), f"{say.mark}  {say.word}", say.why))
        for extra in self.done.get_children()[300:]:
            self.done.delete(extra)
        gpu_runs = [r for r in runs if r.get("kind") in ("generate", "generation", "train", "training", "serve")]
        self.gpu_state.configure(text=f"{len(gpu_runs)} GPU jobs running", fg=GREEN if gpu_runs else MUTED)
        lines = []
        for gpu in snapshot.get("gpus", []):
            lines.append(f"GPU {gpu['index']}: {gpu['used_mb']} / {gpu['total_mb']} MB · {gpu['utilization']}% busy")
        lines.extend("\n" + (r.get("title") or r.get("tag") or r["key"]) for r in gpu_runs)
        self.replace_text(self.gpu_log, "\n".join(lines) or "GPU status unavailable")
        notes = list(snapshot.get("warnings", []))
        followup = snapshot.get("followup", {})
        if followup:
            notes.append("Follow-up processing: " + ("watching existing runs" if followup.get("alive") else "stopped"))
            for tag, state in followup.get("tags", {}).items():
                notes.append(f"{tag}: {state.get('state', 'unknown')} · {state.get('raw', '?')} / "
                             f"{state.get('expected', '?')} answers")
        self.replace_text(self.alert_text, "\n".join(notes) or "No status warnings.")

    def build_collect(self, page):
        if self.remote:
            self.build_remote_collect(page)
            return
        if not HOST_CAN_RUN_STEPS:
            # Buttons that raise are worse than no buttons, and build_train already settled how
            # this window answers a capability it does not have: keep the page, say what is
            # missing (the comment above the tab list, 2026-09-20).
            said = tk.Label(page, bg=BG, fg=MUTED, font=self.f_body, justify="left", anchor="w",
                            wraplength=760, padx=SPACE.tight, pady=SPACE.item,
                            text=("Every step of the data run is a shell recipe: bash to run it, ssh and rsync "
                                  "to reach the lab workstation, nvidia-smi for the cards, systemctl for the "
                                  "services it leaves running, sudo for the one install that needs a password. "
                                  "This system has no POSIX shell, so those steps cannot be started here and "
                                  "no box on this page could ever leave \"not yet\".\n\n"
                                  "What it would take: Linux or macOS, with bash on PATH, run from a checkout "
                                  "of this repository.\n\n"
                                  "The rest of this window works here. The live checks, the results and the "
                                  "answer sets are read from files, and pointing T_LAB (or "
                                  "t/lab-workstation.conf) at the lab workstation shows the run happening "
                                  "there, which is how the run is watched anyway."))
            said.pack(fill="x", padx=SPACE.inner, pady=SPACE.inner)
            self.rewrap(said, pad=2 * SPACE.group)
            return
        self.jobs: dict[str, subprocess.Popen] = {}
        self.step_state: dict[str, str] = {}
        self.step_prog: dict[str, tuple] = {}
        self.boxes: dict[str, dict] = {}
        self.sel_key = STEPS[0][0]
        (RUNS / "logs").mkdir(parents=True, exist_ok=True)
        head = tk.Frame(page, bg=BG)
        head.pack(fill="x")
        tk.Label(head, text="Collect data", bg=BG, fg=TEXT, font=self.f_h2).pack(side="left")
        self.step_hint = tk.Label(head, text="", bg=BG, fg=FAINT, font=self.f_small)
        self.step_hint.pack(side="left", padx=SPACE.item)
        Button(head, "Open notes", lambda: self.open_path(RUNS / "NOTES-home.md"), ACCENT, self,
               filled=False).pack(side="right")
        Button(head, "Reload steps", self.reload_steps, ACCENT, self,
               filled=False).pack(side="right", padx=SPACE.inner)
        Button(head, "Refresh locallm", self.restart_app, ACCENT, self,
               filled=False).pack(side="right", padx=SPACE.inner)
        self.show_done = tk.BooleanVar(value=False)
        Chip(head, "Show finished", self.show_done, self, command=lambda: self.refresh_steps(once=True)).pack(
            side="right", padx=SPACE.inner)
        Button(head, "Stop", lambda: self.stop_step(self.sel_key), RED, self,
               filled=False).pack(side="right", padx=SPACE.inner)

        holder = tk.Frame(page, bg=BG)          # scrollable: there are more steps than fit on a screen
        holder.pack(fill="both", expand=True, pady=(SPACE.item, 0))
        canvas = tk.Canvas(holder, bg=BG, highlightthickness=0)
        sbar = ttk.Scrollbar(holder, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sbar.set)
        sbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self.box_area = tk.Frame(canvas, bg=BG)
        window = canvas.create_window((0, 0), window=self.box_area, anchor="nw")
        self.box_area.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window, width=e.width))
        self.scroll_canvas, self.scroll_to = canvas, 0.0
        canvas.bind_all("<Button-4>", lambda _e: self.scroll_by(-120))
        canvas.bind_all("<Button-5>", lambda _e: self.scroll_by(120))
        canvas.bind_all("<MouseWheel>", lambda e: self.scroll_by(-e.delta))
        self.root.after(16, self.scroll_ease)
        self.build_boxes()

        c = self.card(page, "Output", "last lines of the chosen step's log", fill="x", pady=(SPACE.item, 0))
        self.log_text = log_pane(c, self, 9, "none")
        self.log_text.pack(fill="both", expand=True)
        live = self.pages["Live checks"]
        strip = tk.Frame(live, bg=CARD, highlightthickness=1, highlightbackground=LINE)
        strip.pack(fill="x", pady=(0, SPACE.item), before=live.winfo_children()[0])
        tk.Frame(strip, bg=GREEN, width=3).pack(side="left", fill="y")
        self.run_line = tk.Label(strip, text="", bg=CARD, fg=TEXT, font=self.f_bold, anchor="w",
                                 padx=SPACE.card, pady=SPACE.inner)
        self.run_line.pack(side="left")
        self.run_bar = tk.Canvas(strip, bg=SURFACE, height=10, width=260, highlightthickness=1,
                                 highlightbackground=LINE)     # the hairline, as in build_boxes
        self.run_bar.pack(side="left", padx=(0, SPACE.item))
        self.run_tail = tk.Label(strip, text="", bg=CARD, fg=MUTED, font=self.f_mono, anchor="w")
        self.run_tail.pack(side="left", fill="x", expand=True)
        Button(strip, "Open Collect data", lambda: self.show_page("Collect data"), ACCENT, self,
               filled=False).pack(side="right", padx=SPACE.inner, pady=SPACE.inner)
        threading.Thread(target=self.check_steps, daemon=True).start()
        self.root.after(1000, self.refresh_steps)
    # -- AI ---------------------------------------------------------------------------
    def build_ai(self, page):
        if self.remote:
            self.build_remote_ai(page)
            return
        """The two things that run the run: the orchestrator (a fixed plan) and the autopilot (a local model
        choosing the next legal step every minute). Both live here rather than among the data steps."""
        c = self.card(page, "Orchestrator", "t/run_everything.py: the fixed plan, start to score, unattended")
        note = tk.Label(c, bg=CARD, fg=MUTED, font=self.f_small, justify="left", wraplength=1200, anchor="w", text=(
            "Runs the steps of Collect data in order without asking: it waits for each one, retries a failed step "
            "once, writes what it did to NOTES-home.md and raises an alert it cannot fix. Press the steps by hand "
            "instead whenever you would rather drive."))
        note.pack(fill="x", pady=(0, SPACE.inner))
        self.rewrap(note)
        row = tk.Frame(c, bg=CARD)
        row.pack(fill="x", pady=(0, SPACE.inner))
        self.orch_state = tk.Label(row, text="", bg=CARD, fg=TEXT, font=self.f_bold)
        self.orch_state.pack(side="left")
        Button(row, "Stop", lambda: self.unit("stop", "t-run-all"), RED, self,
               filled=False).pack(side="right", padx=SPACE.inner)
        self.orch_log = log_pane(c, self, 6, "none")
        self.orch_log.pack(fill="x")

        c = self.card(page, "The lab workstation's GPUs", "t/lab_gpu.sh: a second generator on four shared cards")
        note = tk.Label(c, bg=CARD, fg=MUTED, font=self.f_small, justify="left", wraplength=1200, anchor="w", text=(
            "A 30B coder model served by vLLM across the four cards, answering its half of the problems while "
            "this desktop answers the other half. The cards belong to other people: Stop kills the server and "
            "the generation within seconds and loses nothing, because every answer is written as it arrives."))
        note.pack(fill="x", pady=(0, SPACE.inner))
        self.rewrap(note)
        row = tk.Frame(c, bg=CARD)
        row.pack(fill="x", pady=(0, SPACE.inner))
        self.gpu_state = tk.Label(row, text="", bg=CARD, fg=FAINT, font=self.f_bold)
        self.gpu_state.pack(side="left")
        Button(row, "Stop", lambda: self.lab_gpu("stop"), RED, self).pack(side="right")
        Button(row, "Start", lambda: self.lab_gpu("start"), GREEN, self,
               filled=False).pack(side="right", padx=SPACE.inner)
        Button(row, "Fetch answers", lambda: self.lab_gpu("fetch"), ACCENT, self,
               filled=False).pack(side="right", padx=SPACE.inner)
        self.gpu_log = log_pane(c, self, 7, "none")
        self.gpu_log.pack(fill="x")
        threading.Thread(target=self.lab_gpu_watch, daemon=True).start()

        c = self.card(page, "Alerts", "what the autopilot could not fix: t/runs/<date>/ALERTS.md", fill="both",
                      expand=True)
        self.alert_text = log_pane(c, self, 10, "word")
        self.alert_text.pack(fill="both", expand=True)
        self.root.after(2000, self.tick_ai)

    def unit(self, verb: str, name: str):
        """systemd is Linux's alone, so a button press here raised FileNotFoundError on the other
        two systems. Same shape as lab_gpu_watch: catch it, say it, carry on."""
        try:
            subprocess.Popen(["systemctl", "--user", verb, name])
        except (OSError, subprocess.SubprocessError) as e:
            self.say(f"systemctl --user {verb} {name} did not run: {e}")

    def start_orchestrator(self):
        """systemd-run puts the orchestrator in a unit that outlives this window; both it and
        systemctl are systemd's, so off Linux this says so rather than raising."""
        (RUNS / "logs").mkdir(parents=True, exist_ok=True)
        try:
            subprocess.Popen(["bash", "-lc",
                              "systemctl --user reset-failed t-run-all 2>/dev/null; systemd-run --user "
                              f"--unit=t-run-all --working-directory={TUP} "
                              f"-p StandardOutput=append:{RUNS}/logs/run-all.log "
                              f"-p StandardError=append:{RUNS}/logs/run-all.log --setenv=HOME=$HOME "
                              "--setenv=DISPLAY=:0 /usr/bin/python3 t/run_everything.py"], cwd=TUP)
        except (OSError, subprocess.SubprocessError) as e:
            self.say(f"The orchestrator did not start: {e}")

    def lab_gpu(self, verb: str):
        """Start, stop or fetch the lab workstation's generation. Stop runs in the foreground of its own thread
        so it cannot be queued behind anything: when the cards' owners ask, it goes now."""
        log = RUNS / "logs" / "lab-gpu.log"
        RUNS.joinpath("logs").mkdir(parents=True, exist_ok=True)

        def run():
            try:                        # a thread that dies here would leave the button looking pressed
                with open(log, "a") as out:
                    out.write(f"\n### {time.strftime('%Y-%m-%d %H:%M:%S')} lab_gpu.sh {verb}\n")
                    out.flush()
                    subprocess.run(["bash", "t/lab_gpu.sh", verb], cwd=TUP, stdout=out, stderr=subprocess.STDOUT,
                                   env=self.step_env())
            except (OSError, subprocess.SubprocessError) as e:
                self.q.put(("labgpu", f"lab_gpu.sh {verb} did not run: {e}"))
                return
            self.note(f"lab GPUs: {verb}")
        threading.Thread(target=run, daemon=True).start()
        self.gpu_state.configure(text=f"●  {verb} sent", fg=UNSETTLED)

    def lab_gpu_watch(self):
        if not HOST_CAN_RUN_STEPS:      # this polls every 20 seconds: one sentence beats a stream of failures
            self.q.put(("labgpu", "The lab scripts are shell scripts (t/lab_gpu.sh over ssh) and this system "
                                  "has no POSIX shell, so the cards cannot be read or released from here."))
            return
        while True:
            try:
                p = subprocess.run(["bash", "t/lab_gpu.sh", "status"], cwd=TUP, capture_output=True, text=True,
                                   timeout=60, env=self.step_env())
                self.q.put(("labgpu", p.stdout.strip() or p.stderr.strip()))
            except (OSError, subprocess.SubprocessError) as e:
                self.q.put(("labgpu", f"status failed: {e}"))
            time.sleep(20)

    def show_lab_gpu(self, text: str):
        for line in text.splitlines():
            if line.strip().isdigit():
                self.lab_answers = int(line.strip())
        gen = "spec_experiment.py generate" in text
        if gen and not getattr(self, "lab_generating", False):
            self.lab_since = time.time()
        self.lab_generating = gen
        ours = [l for l in text.splitlines() if "vllm serve" in l or "spec_experiment" in l]
        answers = ""
        lines = text.splitlines()
        for i, l in enumerate(lines):
            if l.startswith("-- answers:") and i + 1 < len(lines):
                answers = lines[i + 1].strip()
        self.gpu_state.configure(
            text=f"●  running, {answers} answers" if ours else "●  not running",
            fg=GREEN if ours else FAINT)
        if self.gpu_log.get("1.0", "end").strip() != text.strip():
            self.gpu_log.delete("1.0", "end")
            self.gpu_log.insert("end", text)

    def tick_ai(self):
        def active(name):
            """The orchestrator is a systemd user unit, so this is systemctl or nothing. It used
            to be unguarded while tick_ai reschedules itself every few seconds, which off Linux
            meant a FileNotFoundError traceback twice a second, forever, and a status line that
            never changed. The predicate first because a doomed call should not be made at all;
            the same (OSError, SubprocessError) as lab_gpu_watch for the machine that has a
            shell but no systemd, which is every Mac."""
            if not HOST_CAN_RUN_STEPS:
                return "needs a Linux machine with systemd"
            try:
                return subprocess.run(["systemctl", "--user", "is-active", name],
                                      capture_output=True, text=True).stdout.strip()
            except (OSError, subprocess.SubprocessError) as e:
                return f"systemctl could not be asked: {e}"
        st = active("t-run-all")
        self.orch_state.configure(text=f"●  {st}", fg=GREEN if st == "active" else FAINT)
        for widget, path, n in ((self.orch_log, RUNS / "logs" / "run-all.log", 8),
                                (self.alert_text, RUNS / "ALERTS.md", 60)):
            try:
                text = "\n".join(path.read_text(errors="replace").splitlines()[-n:]) or "nothing yet"
            except OSError:
                text = "nothing yet"
            if widget.get("1.0", "end").strip() != text.strip():
                widget.delete("1.0", "end")
                widget.insert("end", text)
                widget.see("end")
        self.root.after(5000, self.tick_ai)

    # -- Results ---------------------------------------------------------------------
    def build_results(self, page):
        c = self.card(page, "Answer sets", "counted from tests.json and kernels.md, refreshed every 30 seconds")
        note = tk.Label(c, bg=CARD, fg=MUTED, font=self.f_small, justify="left", wraplength=1200, anchor="w", text=(
            "Clean: the tests pass and all seven checkers proved it with the broken copy caught. Proven but wrong: "
            "all seven proved it and the tests fail, which is the number that must stay small. Problems: distinct "
            "problems with a clean answer."))
        note.pack(fill="x", pady=(0, SPACE.inner))
        self.rewrap(note)
        self.res_table = self.table(c, [("set", "Answer set", 320), ("graded", "Graded", 80), ("clean", "Clean", 70),
                                      ("wrong", "Proven but wrong", 130), ("problems", "Problems", 90),
                                      ("passed", "Tests pass", 100), ("tasks", "Well formed", 100)], 12)
        c = self.card(page, "Pool and score", fill="both", expand=True)
        self.results_text = log_pane(c, self, 12, "word")
        self.results_text.pack(fill="both", expand=True)
        if not self.remote:
            threading.Thread(target=self.results_loop, daemon=True).start()

    @staticmethod
    def count_set(d: Path) -> dict:
        """One answer set: well-formed answers, tests passed, clean in all seven, proven but wrong, problems."""
        r = count_answer_set(d)
        r["problems"] = set(r["problems"])
        return r

    def results_loop(self):
        while True:
            sets, totals, problems = [], {k: 0 for k in ("tasks", "passed", "graded", "clean", "wrong")}, set()
            for d in sorted(SPEC_EXP.glob("*")) if SPEC_EXP.is_dir() else []:
                if not d.is_dir():
                    continue
                r = self.count_set(d)
                if not any(r[k] for k in ("tasks", "graded")):
                    continue
                sets.append((d.name, r))
                problems |= r["problems"]
                for k in totals:
                    totals[k] += r[k]
            lines = []
            for f, label in (("out/loop/sft-r4.jsonl", "clean answers in the new pool (sft-r4.jsonl)"),
                             ("out/loop/pairs-r4.jsonl", "answer/broken-copy pairs (pairs-r4.jsonl)"),
                             ("out/loop/sft-r3-27b.jsonl", "the earlier pool (sft-r3-27b.jsonl)")):
                path = HERE / f
                if path.exists():
                    lines.append(f"{sum(1 for _ in open(path)):>6}  {label}")
            for f in ("out/score-r4.md", "out/AGREEMENT-lab.md"):
                path = HERE / f
                if path.exists():
                    lines.append("")
                    lines.append(f"{f}, written {time.strftime('%H:%M', time.localtime(path.stat().st_mtime))}:")
                    lines.append(path.read_text(errors="replace").strip()[:4000])
            self.q.put(("results", (sets, totals, len(problems), "\n".join(lines) or "Nothing built yet.")))
            time.sleep(30)

    def show_results(self, sets, totals, n_problems, text):
        self.res_table.delete(*self.res_table.get_children())
        for name, r in sets:
            tag = "proved" if r["clean"] else ("refuted" if r["wrong"] else "muted")
            self.res_table.insert("", "end", tags=(tag,), values=(
                name, r["graded"] or "", r["clean"] or "", r["wrong"] or "", len(r["problems"]) or "",
                r["passed"] or "", r["tasks"] or ""))
        self.res_table.insert("", "end", tags=("ink",), values=(
            f"all {len(sets)} answer sets", totals["graded"], totals["clean"], totals["wrong"], n_problems,
            totals["passed"], totals["tasks"]))
        if self.results_text.get("1.0", "end").strip() != text.strip():
            self.results_text.delete("1.0", "end")
            self.results_text.insert("end", text)

    def step_env(self):
        return dict(os.environ, PATH=KERNEL_PATH + os.pathsep + os.environ.get("PATH", ""), T_WATCH=str(EVENTS))

    def note(self, line):
        with open(RUNS / "NOTES-home.md", "a") as f:
            f.write(f"- {time.strftime('%Y-%m-%d %H:%M')} {line}\n")

    def title_of(self, key: str) -> str:
        return next((s[1] for s in STEPS if s[0] == key), key)

    def run_step(self, key: str):
        st = next((s for s in STEPS if s[0] == key), None)
        if st is None:
            return
        _key, title, _what, cmd, _check, uses = st[:6]
        live = {k for k, *_r in self.running_steps()}
        if key in live:
            self.step_hint.configure(text=f"{title} is already running.", fg=RED)
            return
        # one step per machine: this desktop can work while the lab workstation grades, but never two here
        # or two there
        where = "the lab workstation" if uses == "lab" else "this desktop"
        busy = [t for k, t, _w, _c, _ck, u, *_n in [s[:6] + (None,) for s in STEPS]
                if k in live and k not in ("ollama-serve", "run-all") and (u == "lab") == (uses == "lab")]
        if busy:
            self.step_hint.configure(text=f"Wait: {', '.join(busy)} is using {where}.", fg=RED)
            return
        unmet = [self.title_of(n) for n in NEEDS.get(key, []) if self.step_state.get(n) != "done"]
        if unmet:
            self.step_hint.configure(text=f"{title} needs {', '.join(unmet)} first.", fg=RED)
            return
        log = RUNS / "logs" / f"{key}.log"
        self.note(f"start `{key}`: `{cmd}` (log `logs/{key}.log`)")
        if uses == "sudo":
            script = RUNS / "logs" / f"{key}.sh"
            script.write_text(f"#!/bin/bash\ncd {shlex.quote(str(TUP))}\nsudo -v\n"
                              f"( {cmd} ) 2>&1 | tee -a {shlex.quote(str(log))}\nread -p 'Enter to close'\n")
            script.chmod(0o755)
            # `which` is POSIX's and both of these are Linux desktop programs, so the probe itself
            # raised before the terminal could. shutil.which is the portable form subprocess's own
            # documentation points at (docs.python.org/3/library/subprocess.html), and asking for
            # both names means a machine with neither is told to run the script by hand instead of
            # being handed a step that cannot ask for a password.
            term = next((t for t in ("ptyxis", "x-terminal-emulator") if shutil.which(t)), "")
            if not term:
                self.step_hint.configure(text=f"{title} needs a password, and no terminal program is here.",
                                         fg=RED)
                self.say(f"Run it in a terminal yourself: bash {script}")
                return
            try:
                subprocess.Popen([term, "-x", str(script)] if term == "ptyxis" else [term, "-e", str(script)])
            except (OSError, subprocess.SubprocessError) as e:
                self.step_hint.configure(text=f"{title} could not open {term}: {e}", fg=RED)
                self.say(f"Run it in a terminal yourself: bash {script}")
                return
            self.step_hint.configure(text=f"{title} opened in a terminal.", fg=MUTED)
            return
        out = open(log, "a")
        out.write(f"\n### {time.strftime('%Y-%m-%d %H:%M:%S')} {cmd}\n")
        out.flush()
        gpu_busy = any(u == "gpu" and k in live for k, _t, _w, _c, _ck, u in [s[:6] for s in STEPS])
        try:
            self.jobs[key] = subprocess.Popen(
                ["bash", "-lc", cmd], cwd=TUP, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                start_new_session=True,
                env=dict(self.step_env(), T_JOBS="6" if uses == "cpu" and gpu_busy else "12"))
        except (OSError, subprocess.SubprocessError) as e:
            out.close()
            self.step_hint.configure(text=f"{title} could not start: {e}", fg=RED)
            return
        self.jobs[key].started = time.time()
        (RUNS / "logs" / f"{key}.pid").write_text(f"{self.jobs[key].pid} {self.jobs[key].started}")
        self.sel_key = key
        self.step_hint.configure(text=f"{title} started.", fg=GREEN)
        if uses == "lab":
            self.show_page("Live checks")
        self.refresh_steps(once=True)

    def running_steps(self):
        """(key, title, started) for every step with a live process, including ones started before this window
        and, for the generation steps, one running on the lab workstation (2026-09-18)."""
        out = []
        if getattr(self, "lab_generating", False):
            out.append(("apps", "APPS problems, the pool's ceiling", getattr(self, "lab_since", time.time())))
        for key, title, *_r in STEPS:
            job = self.jobs.get(key)
            if job:
                if job.poll() is None:
                    out.append((key, title, job.started))
                continue
            try:                     # the pid file alone lies: a dead step's number may belong to something else
                pid, started = (RUNS / "logs" / f"{key}.pid").read_text().split()
                if not proc.alive(int(pid)):     # os.kill(pid, 0) is POSIX's; t/proc.py owns the difference
                    continue
                cmd = Path(f"/proc/{pid}/cmdline").read_bytes().decode(errors="replace").replace("\0", " ")
                want = next((s[3] for s in STEPS if s[0] == key), "")
                first = next((w for w in want.split() if "/" in w or w.endswith(".py") or w.endswith(".sh")), "")
                if (first and first in cmd) or key in cmd:
                    out.append((key, title, float(started)))
            except (OSError, ValueError):
                pass
        return out

    def stop_step(self, key: str):
        if key not in [k for k, *_r in self.running_steps()]:
            self.step_hint.configure(text=f"{self.title_of(key)} is not running.", fg=FAINT)
            return
        job = self.jobs.get(key)
        pid = job.pid if job else int((RUNS / "logs" / f"{key}.pid").read_text().split()[0])
        # A step is started with start_new_session=True, so what has to go is the whole group, not the
        # bash that leads it -- os.killpg is POSIX's and t/proc.py holds the other systems' version.
        if not proc.stop_tree(pid):
            self.step_hint.configure(text=f"{self.title_of(key)} would not stop; see the log.", fg=RED)
            return
        self.note(f"stopped `{key}` by hand")
        self.step_hint.configure(text=f"{self.title_of(key)} stopped.", fg=RED)

    def check_steps(self):
        """What each step's state and bar are read from, in its own thread.

        2026-09-18: this used to run all 39 done-tests every pass and then sleep ten seconds, so a bar moved
        once every sixteen -- `packages` alone costs three seconds, and a done-test that shells out is not
        free. A step that is done stays done (nothing here deletes its output), so those are re-checked once a
        minute and the rest every pass, which puts a running step's bar within a couple of seconds of the
        truth while costing less than the old loop did."""
        pass_n = 0
        while True:
            pass_n += 1
            for key, _t, _w, _c, check, _u in [s[:6] for s in STEPS]:
                if self.step_state.get(key) == "done" and pass_n % 20:
                    self.step_prog[key] = self.progress_of(key)
                    continue
                try:
                    ok = subprocess.run(["bash", "-lc", check], cwd=TUP, capture_output=True,
                                        env=self.step_env()).returncode == 0
                except (OSError, subprocess.SubprocessError) as e:
                    # Unguarded, this killed the thread on its first pass and every box sat at "not
                    # yet" with nothing saying why. One line on the page, then stop: the answer will
                    # not change while this process lives.
                    self.q.put(("steps_error", f"The steps cannot be tested here: {e}"))
                    return
                self.step_state[key] = "done" if ok else ""
                self.step_prog[key] = self.progress_of(key)
            time.sleep(3)

    @staticmethod
    def answers(tag: str) -> int:
        try:
            return sum(1 for _ in (SPEC_EXP / tag / "raw").glob("*.json"))
        except OSError:
            return 0

    def progress_of(self, key: str) -> tuple:
        """(what it has produced so far, how far along from 0 to 1), counted from the files themselves."""
        heldout = {"phi": ("phi4-mini-v3", 232), "base": ("qwen15b-base-v3", 232),
                   "student": ("student-r4-v3", 232), "locallm": ("locallm-r4", 232),
                   # every later round's held-out generation counts the same way; without these rows the new
                   # steps had a running light and no bar (2026-09-18)
                   "r5-student": ("student-r5-v3", 232), "r5-locallm": ("locallm-r5", 232),
                   "r6-student": ("student-r6-v3", 232), "r6-student-g": ("student-r6-g", 232),
                   "phi-g": ("phi4-mini-g", 232)}
        if key in heldout:
            tag, total = heldout[key]
            n = self.answers(tag)
            return f"{n} of {total} answers", n / total
        if key == "generate":
            per = [self.answers(f"{GEN}{i}") for i in range(1, 9)]
            whole = sum(1 for n in per if n >= 649)
            total = 8 * 649
            return (("all 8 seeds written" if whole == 8 else
                     f"{sum(per)} of {total} answers, seed {whole + 1}"), sum(per) / total)
        if key == "grade":
            sets = [d for d in SPEC_EXP.glob("*") if (d / "grade-in").is_dir()]
            done_n = sum(1 for d in sets if (d / "kernels.md").exists())
            return (f"{done_n} of {len(sets)} answer sets graded", done_n / len(sets) if sets else None)
        if key == "spec-check":
            try:
                n = json.loads((HERE / "out" / "spec-disagree.json").read_text())
                return (f"{n['checked']} answers checked, {len(n['disagree'])} disagree",
                        1.0 if self.step_state.get(key) == "done" else None)
            except (OSError, ValueError, KeyError):
                return "", None
        if key == "apps":
            # the lab workstation's answers live on the lab workstation: its count comes from the status the
            # GPU card's watcher reads every twenty seconds, not from this disk (2026-09-18)
            here = sum(self.answers(f"qwen2.5-coder-14b-apps-s{i}") for i in (1, 2))
            there = getattr(self, "lab_answers", 0)
            total = 2266 + 2266
            return (f"{here} answered here, {there} on the lab workstation", min(1.0, (here + there) / total))
        if key == "more-problems":
            he, ds = [self.answers(f"{HE}{i}") for i in range(1, 9)], [self.answers(f"{GEN2_TAG}{i}") for i in (1, 2)]
            total = 8 * 88 + 2 * 737
            return (f"{sum(he)} of {8 * 88} HumanEval, {sum(ds)} of {2 * 737} second model",
                    (sum(he) + sum(ds)) / total)
        if key in ("repair", "repair-growth"):
            tags = QWEN_FIX.split() if key == "repair" else GROWTH_FIX.split()
            n = sum(self.answers(t) for t in tags)
            return f"{n} answers repaired", (1.0 if self.step_state.get(key) == "done" else None) if not n else None
        graded = {"grade": [f"{GEN}{i}" for i in range(1, 9)], "grade-repair": QWEN_FIX.split(),
                  "grade-growth": GROWTH_TAGS.split(), "grade-growth-repair": GROWTH_FIX.split(),
                  "grade-heldout": HELDOUT.split(),
                  "r5-grade-heldout": ["student-r5-v3", "locallm-r5"],
                  "r6-grade-heldout": ["student-r6-v3", "student-r6-g", "phi4-mini-g"],
                  "constrained-grade": ["qwen3-coder-30b-apps-g1"]}
        if key in graded:
            tags = graded[key]
            done_n = sum(1 for t in tags if (SPEC_EXP / t / "kernels.md").exists())
            waiting = sum(1 for t in tags if (SPEC_EXP / t / "grade-in").is_dir()) or len(tags)
            part, part_text = 0.0, ""
            here = [st for k, _t, st in self.running_steps() if k == key]
            if here:                           # the set being graded now, cell by cell, so the bar keeps moving
                tag, tasks = self.grading_now(key)
                if tag:
                    total = tasks * len(KERNELS)
                    # the step's own lines, one per cell: a cell that abstains runs no checker and sends no
                    # event, and seed 7's Rocq column is mostly abstains (nested loops), so events alone stall
                    done_c = self.cells_printed(key)
                    part = min(1.0, done_c / total) if total else 0.0
                    part_text = f"; {tag.split('-')[-1]} at {min(done_c, total)} of {total} cells"
            return (f"{done_n} of {waiting} answer sets{part_text}",
                    min(1.0, (done_n + part) / waiting))
        if key in ("train", "r5-train", "r6-train", "r5-locallm", "r6-locallm"):
            # a training step's own progress bar, read back out of its log: transformers and locallm/train.py
            # both print "<done>/<total>", so the window can show the same fraction the terminal would
            return self.bar_from_log(key)
        if key == "constrained":
            n = self.answers("qwen3-coder-30b-apps-g1")
            return (f"{n} of 1133 answers, on the lab workstation", min(1.0, n / 1133) if n else None)
        return "", None

    def bar_from_log(self, key: str) -> tuple:
        """The last "<done>/<total>" a step printed, as a fraction. Steps that run a training loop print one
        of these a second; nothing else in the log looks like it, and the last one is the current one."""
        try:
            text = (RUNS / "logs" / f"{key}.log").read_text(errors="replace")
        except OSError:
            return "", None
        # A training step prints several bars in a row -- the dataset preparation, the reference log
        # probabilities, then the training loop itself -- and only the last carries no label. Reading any bar
        # and calling it the training would have shown 87 of 87 and full before the model took a step; reading
        # only the unlabelled one leaves the window blank for the minutes the others take. So: the last bar,
        # with its own label when it has one (2026-09-18).
        lines = text[-8000:].replace("\r", "\n").splitlines()
        for line in reversed(lines):
            m = re.match(r"\s*(.*?)\s*\d+%\|[^|]*\|\s*(\d+)/(\d+) \[", line)
            if not m:
                continue
            label, done, total = m.group(1).rstrip(":"), int(m.group(2)), int(m.group(3))
            what = f"{label.lower()}: " if label else ""
            return (f"{what}{done} of {total}" + ("" if label else " steps"),
                    min(1.0, done / total) if total else None)
        return "", None

    def cells_printed(self, key: str) -> int:
        """Cells the running step has reported since it last said which answer set it is on."""
        try:
            lines = (RUNS / "logs" / f"{key}.log").read_text(errors="replace").splitlines()
        except OSError:
            return 0
        start = max((i for i, l in enumerate(lines) if re.match(r"== \S+: \d+ tasks", l)), default=0)
        return sum(1 for l in lines[start:] if re.match(r"  \S+ x \S+", l))

    def grading_now(self, key: str) -> tuple:
        """(tag, task count) of the answer set a grading step is working on, from its log's own line."""
        try:
            lines = (RUNS / "logs" / f"{key}.log").read_text(errors="replace").splitlines()
        except OSError:
            return "", 0
        for line in reversed(lines):
            m = re.match(r"== (\S+): (\d+) tasks", line)
            if m:
                if f"== {m.group(1)}: kernels.md back" in "\n".join(lines[-40:]):
                    return "", 0
                return m.group(1), int(m.group(2))
        return "", 0

    def refresh_steps(self, once: bool = False):
        live = {k: (t, st) for k, t, st in self.running_steps()}
        finished = 0
        for key, title, *_r in STEPS:
            b = self.boxes.get(key)
            if b is None:
                continue
            job, state, color = self.jobs.get(key), self.step_state.get(key, ""), FAINT
            if key in live:
                state, color = f"running {int(time.time() - live[key][1]) // 60} min", GREEN
            elif job and not getattr(job, "noted", False):
                job.noted = True
                self.note(f"end `{key}`: exit {job.returncode} after {int(time.time() - job.started) // 60} min")
            if state == "done":
                state, color, finished = "done", GREEN, finished + 1
            elif job is not None and job.poll() not in (None, 0) and key not in live:
                state, color = f"failed ({job.returncode})", RED
            prog, frac = self.step_prog.get(key, ("", None))
            if state == "done" and frac is None:
                frac = 1.0
            b["state"].configure(text=state or "not yet", fg=color)
            b["prog"].configure(text=(f"{prog}   {frac * 100:.0f}%" if frac is not None and prog else
                                      prog or (f"{frac * 100:.0f}%" if frac is not None else "")))
            bar, w = b["bar"], max(1, b["bar"].winfo_width())
            bar.delete("all")
            if frac is not None:
                # green while it runs and once it is done; amber for a bar stopped part
                # way along, which is a step neither working nor finished -- look's "not
                # settled yet". That was a blue saying nothing.
                bar.create_rectangle(0, 0, int(w * min(1.0, max(0.0, frac))), 8,
                                     fill=GREEN if key in live or state == "done" else UNSETTLED, width=0)
            running = key in live
            # A running step is marked by its edge and its outline and no longer by a
            # tint behind it. The tint was a dim green this palette does not carry, and
            # look's own measurement rules out the obvious substitute: on the shaded
            # band, muted text comes to 4.00:1 against the 4.5 body bar, and two of the
            # four labels in a box -- the progress line and the description -- are muted.
            b["edge"].configure(bg=GREEN if running or state == "done" else LINE)
            b["box"].configure(highlightbackground=GREEN if running else
                               (ACCENT if key == self.sel_key else LINE))
            hide = state == "done" and not running and not self.show_done.get()
            if hide:
                b["box"].pack_forget()
            elif not b["box"].winfo_ismapped():
                b["box"].pack(fill="x", pady=(0, SPACE.inner))
        self.step_hint.configure(
            text=(f"{finished} of {len(STEPS)} steps finished and hidden" if finished and not self.show_done.get()
                  else f"{finished} of {len(STEPS)} steps finished"), fg=FAINT)
        if live:
            names = ", ".join(f"{t} ({int(time.time() - st) // 60} min)" for t, st in live.values())
            self.run_line.configure(text=f"Data run:  {names}")
            shown = next((k for k in ("grade", "grade-repair", "grade-growth", "grade-growth-repair",
                                      "grade-heldout", "matrix", "phi", "base", "student", "locallm", "repair",
                                      "more-problems", "generate") if k in live), next(iter(live)))
            try:
                last = [l for l in (RUNS / "logs" / f"{shown}.log").read_text(errors="replace")
                        .replace("\r", "\n").splitlines() if l.strip()][-1]
            except (OSError, IndexError):
                last = ""
            self.draw_progress(shown, live[shown][1], last)
        else:
            self.run_line.configure(text="Data run:  nothing running")
            self.run_tail.configure(text="")
            self.run_bar.delete("all")
        self.show_log()                      # the Output box tails the chosen step's log, live
        if not once:
            self.root.after(2000, self.refresh_steps)

    def draw_progress(self, key, started, last):
        """The Live checks strip: the running step's own count when it has one, else checks finished of the
        answer set being graded (the log's '== <tag>: N tasks' line), less the sets already brought back."""
        prog, frac = self.step_prog.get(key, ("", None))
        text = f"{self.title_of(key)}: {prog}    {last[:70]}" if prog else last[:140]
        if frac is None:
            try:
                lines = (RUNS / "logs" / f"{key}.log").read_text(errors="replace").splitlines()
                for line in reversed(lines):
                    m = re.match(r"== (\S+): (\d+) tasks", line)
                    if not m:
                        continue
                    total = int(m.group(2)) * len(KERNELS)
                    run = lines[max((i for i, l in enumerate(lines) if l.startswith("###")), default=0):]
                    earlier = sum(int(n) * len(KERNELS)
                                  for tag, n in re.findall(r"== (\S+): (\d+) tasks", "\n".join(run))
                                  if f"== {tag}: kernels.md back" in run)
                    try:
                        mine = {q.stem for q in (SPEC_EXP / m.group(1) / "grade-in").glob("*.json")}
                    except OSError:
                        mine = set()
                    done = sum(1 for t, name in self.end_pairs if t >= started and (not mine or name in mine))
                    done = max(0, done - earlier)
                    frac = min(1.0, done / total) if total else None
                    text = (f"{m.group(1)}: {done} of {total} checks" if done else
                            f"{m.group(1)}: translating {m.group(2)} tasks for the seven checkers")
                    break
            except OSError:
                pass
        self.run_tail.configure(text=text)
        self.run_bar.delete("all")
        if frac is not None:
            self.run_bar.create_rectangle(0, 0, int(260 * frac), 10, fill=GREEN, width=0)

    ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b[()][A-B0-9]")

    def show_log(self):
        log = RUNS / "logs" / f"{self.sel_key}.log"
        try:
            text = self.ANSI.sub("", log.read_text(errors="replace"))
            # a download's progress bar redraws one line with carriage returns: keep what it ended up saying
            lines = [l.split("\r")[-1].rstrip() for l in text.splitlines()]
            keep, last = [], None
            for l in lines:
                head = l.split(":")[0][:40]
                if l.strip() and head == last and "%" in l:      # the same bar, drawn again
                    keep[-1] = l
                    continue
                keep.append(l)
                last = head if "%" in l else None
            tail = "\n".join(keep[-200:])
        except OSError:
            tail = "No log yet: this step has not run."
        if self.log_text.get("1.0", "end").strip() == tail.strip():
            return
        at_end = self.log_text.yview()[1] > 0.999       # leave the view alone when it has been scrolled up
        self.log_text.delete("1.0", "end")
        self.log_text.insert("end", tail)
        if at_end:
            self.log_text.see("end")


def size_window(root: tk.Tk) -> None:
    """How big the window opens, asked of the display instead of written down here.

    locallm/studio.py's fit_to_screen already does this properly and lists the three
    failures it came from -- a fixed size taller than the work area of a 1366x768 laptop,
    DPI awareness scaling the fonts while the pixel count stayed where it was, and a
    position remembered from a monitor that is no longer there. Merging the trainer into
    this window left it unused here, with 1400x900 and a 1000x700 minimum written out by
    hand instead. It is imported lazily for the reason build_train gives: studio.py imports
    torch at module scope and this window must still open on a machine without torch, so
    those hand-written numbers stay as the fallback.
    """
    saved = ""
    try:                                  # where it was left, so Refresh locallm does not move the window
        saved = GEOMETRY.read_text().strip()
    except OSError:
        pass
    try:
        # look.py, not studio.py: studio imports torch at module scope, so this
        # import failed on every machine without torch -- which is the portable
        # case the sizing exists for -- and the window quietly took the fallback
        # below instead. The fallback stays, for a checkout with no locallm/.
        from look import fit_to_screen                     # noqa: PLC0415
    except Exception:                                      # noqa: BLE001
        root.geometry(f"{min(1400, root.winfo_screenwidth() - 20)}x"
                      f"{min(900, root.winfo_screenheight() - 60)}+10+30")
        root.minsize(1000, 700)
    else:
        fit_to_screen(root, want=(1400, 900))
    if saved:
        # RECONCILED, not just recalled. This used to apply the remembered string
        # straight after fit_to_screen had clamped the window to the work area,
        # which meant a geometry written while a projector or a second monitor was
        # attached silently defeated the function written to prevent exactly that:
        # the window opened where that monitor used to be, which is nowhere.
        # clamp_geometry reconciles it against the screen that exists now.
        safe = None
        try:
            from look import clamp_geometry                 # noqa: PLC0415
            safe = clamp_geometry(root, saved)
        except Exception:                                   # noqa: BLE001
            safe = None
        if safe:
            try:
                root.geometry(safe)
            except tk.TclError:
                pass


def main() -> int:
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    # Home, not Live checks: the window opens on what locallm is for. An unknown
    # name falls back to the same page rather than refusing (Lab.__init__), so
    # --page survives a page being renamed.
    page = "Home"
    if "--page" in sys.argv[1:]:
        page = sys.argv[sys.argv.index("--page") + 1]
    root = tk.Tk()
    root.title("locallm")
    # The other half of the call above. SetProcessDpiAwareness(1) promises Windows that this
    # process scales itself; nothing then told Tk the real pixel density, so it laid the window
    # out at one pixel per point and on a 150%-scaled display every font read a third too
    # small. `tk scaling` is pixels per point, 1.0 being a 72 dpi monitor, and the manual warns
    # that "it is undefined whether existing widgets will resize themselves dynamically to
    # accommodate the new scaling factor" (tcl-lang.org/man/tcl8.6/TkCmd/tk.htm) -- which is why
    # it is set here, before Lab builds a single widget. On X11 Tk has already derived the same
    # number from the display, so it changes nothing there; studio.py sets the same pair.
    try:
        root.tk.call("tk", "scaling", root.winfo_fpixels("1i") / 72.0)
    except tk.TclError:
        pass
    Lab(root, start_page=page)
    size_window(root)                     # after the widgets exist: fit_to_screen asks them how big they want to be
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
