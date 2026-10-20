#!/bin/bash
# Runs on the desktop GPU box (tlab) with the pinned Dafny 4.11.0 (the engine Dockerfile's zip) at ~/.local/dafny.
# P2 of t/PREDICT-2026-10-19-decomposed-rows.md on the desktop: v7 then v5, each served by the pinned llama-server,
# t/recipes/v7_annotate_test.py over the 55 held-out rows, verified by the pinned Dafny 4.11.0.
set -u
H=/home/t; L=$H/.local/share/dawnr/llama.cpp; D=$H/dawnr; A=$H/v7/annotate
export LD_LIBRARY_PATH=$L PYTHONPATH=$D/t PYTHONUNBUFFERED=1 PATH=$H/.local/bin:$PATH
cd $D; rm -f $A/p2.done; : > $A/p2.log
for i in $(seq 1 180); do [ -f $H/.local/dafny.done ] && (cd $H/v5 && sha256sum -c --quiet dawnr-student.sha256 >/dev/null 2>&1) && break; timeout 10 tail -f /dev/null; done
[ -f $H/.local/dafny.done ] || { echo "dafny missing" | tee -a $A/p2.log > $A/p2.done; exit 1; }
echo "$(date -u +%FT%TZ) dafny: $(dafny --version 2>&1 | head -1)" >> $A/p2.log
run_arm() {
  name=$1; ident=$2; shift 2
  $L/llama-server "$@" --alias $name --host 127.0.0.1 --port 8848 --n-gpu-layers 99 --threads 16 --parallel 4 \
    --ctx-size 16384 --chat-template-kwargs '{"enable_thinking":false}' > $A/server-$name.log 2>&1 &
  SP=$!
  for i in $(seq 1 300); do curl -sf http://127.0.0.1:8848/health >/dev/null && break; timeout 1 tail -f /dev/null; done
  echo "$(date -u +%FT%TZ) $name serving; test starting" >> $A/p2.log
  python3 $D/t/recipes/v7_annotate_test.py --heldout $A/annotate-heldout.jsonl --endpoint http://127.0.0.1:8848/v1/chat/completions \
    --model $name --identity "$ident" --cache $A/cache-$name --out $A/out-$name --concurrency 4 > $A/test-$name.log 2>&1
  echo "$(date -u +%FT%TZ) $name test rc=$?" >> $A/p2.log
  kill $SP 2>/dev/null; wait $SP 2>/dev/null
}
V7SHA=$(python3 -c "import json;print(json.load(open('$H/v7/export.json'))['output']['sha256'])")
run_arm dawnr-v7 "student-v7:$V7SHA:llama-f1cee9941b0e843ea260bf8dd9a090fbd9711b6a" --model $H/v7/model-Q8_0.gguf
run_arm dawnr-v5 "student-v5:d855000c3dffd9772da5a2f9dc238b41d7f8337d9bf58e578e5274ebb9566a4e:llama-f1cee9941b0e843ea260bf8dd9a090fbd9711b6a" --model $H/v5/dawnr-student-00001-of-00003.gguf
echo done > $A/p2.done
