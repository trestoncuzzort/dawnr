#!/bin/bash
# t/lab_gpu.sh -- the generator that runs on the lab workstation's GPUs, and the one command that stops it.
#
#   bash t/lab_gpu.sh start     serve the model with vLLM across the four cards and answer the APPS problems
#   bash t/lab_gpu.sh stop      stop everything of ours on those GPUs, at once
#   bash t/lab_gpu.sh status    what is running, what the cards hold, how far the answers have got
#   bash t/lab_gpu.sh fetch     bring the answers back to this machine
#
# The cards are shared with other people and the standing rule is that our work stops when they ask. `stop` is
# therefore the important command: it kills the server and the generation and leaves the cards as they were,
# within seconds, and nothing is lost because every answer is written to its own file as it arrives.
#
# vLLM is told to use a fraction of each card that leaves the other users' memory untouched
# (T_LAB_GPU_FRACTION, 0.26 of 48 GB, about 12.5 GB a card, against the 14 to 17 GB that were free).
set -u
[ -f t/lab-workstation.conf ] && . t/lab-workstation.conf
LAB=${T_LAB:?set T_LAB=user@host in t/lab-workstation.conf}
SSH="ssh -o BatchMode=yes -o ConnectTimeout=10 -o ServerAliveInterval=30"
MODEL=${T_LAB_MODEL:-Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8}
TAG=${T_LAB_TAG:-qwen3-coder-30b-apps-s1}
PORT=${T_LAB_PORT:-8077}
FRACTION=${T_LAB_GPU_FRACTION:-0.26}
JOBS=${T_LAB_GEN_JOBS:-16}

case "${1:-status}" in

start)
  $SSH "$LAB" "mkdir -p ~/lab-gpu && cd ~/tup && git pull -q --ff-only || true"
  echo "== serving $MODEL on the four cards (tensor parallel), port $PORT"
  # vLLM's FP8 path compiles kernels, so it needs a CUDA toolkit; this machine has none in /usr/local, but the
  # venv ships one inside the nvidia wheels (2026-09-18)
  CUDA_HOME_REMOTE='$HOME/.venv-vllm/lib/python3.12/site-packages/nvidia/cu13'
  # and the linker needs the runtime beside it: FlashInfer compiles a sampling kernel at startup and links
  # -lcudart, which lives only in the venv here. The sampler's JIT is switched off as well, so a first run does
  # not depend on a compiler at all.
  $SSH "$LAB" "cd ~/tup && CUDA_HOME=$CUDA_HOME_REMOTE PATH=$CUDA_HOME_REMOTE/bin:\$PATH \
      LIBRARY_PATH=$CUDA_HOME_REMOTE/lib:\${LIBRARY_PATH:-} \
      LD_LIBRARY_PATH=$CUDA_HOME_REMOTE/lib:\${LD_LIBRARY_PATH:-} \
      VLLM_USE_FLASHINFER_SAMPLER=0 \
      setsid nohup ~/.venv-vllm/bin/vllm serve '$MODEL' \
      --tensor-parallel-size 4 --gpu-memory-utilization $FRACTION --max-model-len 8192 \
      --port $PORT > ~/lab-gpu/vllm.log 2>&1 < /dev/null & echo started"
  echo "== waiting for the server (a first load reads 31 GB from disk)"
  for _ in $(seq 1 120); do
    sleep 10
    if $SSH "$LAB" "curl -sf http://127.0.0.1:$PORT/v1/models >/dev/null"; then echo "   up"; break; fi
  done
  $SSH "$LAB" "curl -sf http://127.0.0.1:$PORT/v1/models >/dev/null" || {
    echo "the server did not come up; its log:"; $SSH "$LAB" "tail -20 ~/lab-gpu/vllm.log"; exit 1; }
  echo "== answering the APPS problems as $TAG"
  $SSH "$LAB" "cd ~/tup && setsid nohup python3 t/spec_experiment.py generate --model '$MODEL' --tag '$TAG' \
      --pool v5 --ids-file t/out/loop/apps-upper.txt --prompt v3 --seed 1 --temperature 0 --num-predict 2048 \
      --host 127.0.0.1:$PORT --api openai --timeout 1800 --jobs $JOBS \
      > ~/lab-gpu/generate.log 2>&1 < /dev/null & echo started"
  ;;

stop)
  # The patterns are bracketed ([v]llm) because the shell running them carries them in its own command line:
  # a plain `pkill -f 'vllm serve'` matches that shell and kills the stop command halfway through, which on
  # 2026-09-18 left the server and all four workers alive while this printed "stopped". It now kills, waits,
  # kills harder, and then reports what is actually on the cards rather than what it tried to do.
  $SSH "$LAB" "pkill -f '[s]pec_experiment.py generate'; pkill -f '[v]llm serve'; pkill -f '[V]LLM::'; sleep 5; \
     pkill -9 -f '[v]llm serve' 2>/dev/null; pkill -9 -f '[V]LLM::' 2>/dev/null; sleep 2; \
     left=\$(pgrep -u \$USER -f '[v]llm|[V]LLM::' | wc -l); \
     echo \"ours still running: \$left\"; \
     echo '-- memory we hold on the cards:'; \
     for p in \$(nvidia-smi --query-compute-apps=pid --format=csv,noheader); do \
       ps -o user= -p \$p 2>/dev/null | grep -q \"^\$USER\" && nvidia-smi --query-compute-apps=pid,used_memory \
       --format=csv,noheader | grep \"^\$p,\"; done; true"
  echo "anything not listed above belongs to other users and was left alone"
  ;;

status)
  $SSH "$LAB" "echo '-- ours:'; pgrep -fa 'vllm serve|spec_experiment.py generate' | cut -c1-80; \
     echo '-- cards:'; nvidia-smi --query-gpu=index,memory.used,memory.total,utilization.gpu --format=csv,noheader; \
     echo '-- answers:'; ls ~/tup/t/out/spec-experiment/qwen3-coder-30b-apps-s*/raw 2>/dev/null | grep -c json; \
     tail -2 ~/lab-gpu/generate.log 2>/dev/null | cut -c1-100"
  ;;

takeover)
  # Hand the lab workstation every problem this desktop has not answered yet, and stop generating here. Every
  # answer is its own file, so nothing is half done: what is on disk stays, the rest moves.
  python3 - "$TAG" <<'PY'
import json, sys
from pathlib import Path
here = Path("t/out/spec-experiment")
want = {int(x) for x in Path("t/out/loop/apps-ids.txt").read_text().split()}
have = set()
for d in here.glob("*apps*"):
    have |= {int(p.stem) for p in (d / "raw").glob("*.json") if p.stem.isdigit()}
left = sorted(want - have)
Path("t/out/loop/apps-left.txt").write_text("\n".join(str(i) for i in left) + "\n")
print(f"{len(left)} problems have no answer yet, of {len(want)}")
PY
  rsync -a t/out/loop/apps-left.txt "$LAB:tup/t/out/loop/"
  pkill -f "spec_experiment.py generate --model qwen2.5-coder" 2>/dev/null
  systemctl --user stop t-gen 2>/dev/null
  echo "== this desktop has stopped generating"
  $SSH "$LAB" "pkill -f 'spec_experiment.py generate'; sleep 2; cd ~/tup && setsid nohup python3 \
      t/spec_experiment.py generate --model '$MODEL' --tag '$TAG' --pool v5 \
      --ids-file t/out/loop/apps-left.txt --prompt v3 --seed 1 --temperature 0 --num-predict 2048 \
      --host 127.0.0.1:$PORT --api openai --timeout 1800 --jobs $JOBS \
      >> ~/lab-gpu/generate.log 2>&1 < /dev/null & echo 'the lab workstation has the rest'"
  ;;

constrained)
  # The constrained arm of t/PREREG-2026-09-18-constrained.md: the same 1,133 problems, the same model, prompt,
  # temperature and seed as qwen3-coder-30b-apps-s1, with t's grammar sent on every request so the model cannot
  # write anything the parser would refuse. Nothing else differs, which is the whole design of the comparison.
  # Five problems first: if the grammar is not being honoured, five replies say so and 1,133 would only cost an
  # hour to say the same.
  GTAG=${T_LAB_GRAMMAR_TAG:-qwen3-coder-30b-apps-g1}
  $SSH "$LAB" "curl -sf http://127.0.0.1:$PORT/v1/models >/dev/null" || {
    echo "the server is not up; run 'bash t/lab_gpu.sh start' first (it also starts generating; stop that)"; exit 1; }
  echo "== five problems first, as a check that the grammar is honoured"
  $SSH "$LAB" "cd ~/tup && python3 t/spec_experiment.py generate --model '$MODEL' --tag '$GTAG-probe' \
      --pool v5 --ids-file t/out/loop/apps-upper.txt --limit 5 --prompt v3 --seed 1 --temperature 0 \
      --num-predict 2048 --host 127.0.0.1:$PORT --api openai --grammar t/t.gbnf --timeout 1800 --jobs 5 2>&1 | tail -3
    python3 t/spec_experiment.py extract --model '$GTAG-probe' --pool v5 2>&1 | tail -1"
  echo "== if that reads 5 task, the grammar is being honoured; answering all 1,133 as $GTAG"
  $SSH "$LAB" "cd ~/tup && setsid nohup python3 t/spec_experiment.py generate --model '$MODEL' --tag '$GTAG' \
      --pool v5 --ids-file t/out/loop/apps-upper.txt --prompt v3 --seed 1 --temperature 0 --num-predict 2048 \
      --host 127.0.0.1:$PORT --api openai --grammar t/t.gbnf --timeout 1800 --jobs $JOBS \
      > ~/lab-gpu/constrained.log 2>&1 < /dev/null & echo started"
  ;;

fetch)
  mkdir -p "t/out/spec-experiment/$TAG"
  rsync -a "$LAB:tup/t/out/spec-experiment/$TAG/" "t/out/spec-experiment/$TAG/"
  echo "$(ls "t/out/spec-experiment/$TAG/raw" 2>/dev/null | wc -l) answers here"
  ;;

*) sed -n '2,12p' "$0" ;;
esac
