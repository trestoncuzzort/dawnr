#!/bin/bash
# The door's condition 3 (internal/RELEASE-6.0-PLAN.md, section 3): the 33 held-out given specifications, one greedy
# answer each from a GGUF served by the pinned llama-server on the laptop's GPU, kept by t/score_spec_given.py's gates,
# graded by the seven kernels, counted by level. Questions, system prompt and token budget are the matched run's of
# 2026-10-11 (t/recipes/v5-matched-2026-10-11-generate.sh); the released model is measured by the same script, so the
# comparison is one instrument.
#   spec33.sh LABEL GGUF        -> t/out/spec33-LABEL/spec-levels.json
set -u
LABEL=${1:?label}; GGUF=${2:?gguf}
D=$HOME/Projects/dawnr; L=$HOME/.local/share/dawnr/llama.cpp; OUT=$D/t/out/spec33-$LABEL; PORT=${PORT:-8853}
export PATH=$HOME/.local/bin:$HOME/.cargo/bin:$HOME/.elan/bin:$PATH PYTHONPATH=$D/t PYTHONUNBUFFERED=1
cd $D || exit 1; mkdir -p $OUT
Q=t/out/gcp-student-2026-10-11-s1/spec-heldout.jsonl
serve_and_ask() {
  LD_LIBRARY_PATH=$L $L/llama-server --model "$GGUF" --alias dawnr-33 --host 127.0.0.1 --port $PORT --n-gpu-layers 99 \
    --threads 8 --parallel 1 --ctx-size 8192 --chat-template-kwargs '{"enable_thinking":false}' > $OUT/server.log 2>&1 &
  local sp=$!
  for i in $(seq 1 180); do curl -sf http://127.0.0.1:$PORT/health >/dev/null && break; sleep 1; done
  python3 t/score_spec_given.py ask --model "$LABEL" --host 127.0.0.1:$PORT --questions $Q \
    --out $OUT/spec-answers.jsonl --system s1 --max-new 1024
  local rc=$?
  kill $sp 2>/dev/null; wait $sp 2>/dev/null
  return $rc
}
export -f serve_and_ask; export L GGUF OUT PORT LABEL Q
flock $D/t/out/.laptop-gpu.lock bash -c serve_and_ask || { echo "asking failed"; exit 1; }
python3 t/score_spec_given.py prepare --questions $Q --answers $OUT/spec-answers.jsonl --tasks $OUT/spec-tasks \
  --report $OUT/spec-report.json || exit 1
rm -f $OUT/spec-kernels.md
flock $D/t/out/.laptop-grade.lock python3 t/run_par.py --table $OUT/spec-kernels.md --tasks $OUT/spec-tasks \
  --out $OUT/spec-kernels --jobs 4 --no-cache
python3 t/score_spec_given.py levels --report $OUT/spec-report.json --table $OUT/spec-kernels.md --json $OUT/spec-levels.json
