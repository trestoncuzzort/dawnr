#!/bin/bash
# Generate a held-out answer set with every card at once instead of one problem
# at a time on one card.
#
#   bash t/gen_fleet.sh <model-dir> <tag> [shards] [cards] [extra args...]
#   bash t/gen_fleet.sh t/out/locallm-r9 locallm-r9 4 "0 2 3" --temperature 0
#
# Measured 2026-09-19: three arms of 232 answers finished in about ten minutes,
# against roughly forty-five minutes per arm serially, because one generation
# process uses about 1.5 GB of a 48 GB card and leaves the rest idle.
#
# Why this needs no coordination: loop_locallm.py skips any problem that
# already has a raw/<id>.json, so workers cannot collide and a rerun costs
# nothing. Shards are strided, not blocked, so a slow region of the id space
# does not fall entirely on one worker.
#
# The one rule: do not run this while the kernels are grading. Ten workers plus
# a 7B model plus 32 grading cells put the load average at 80 on a 120-core box
# shared with another user, and the ssh carrying the grading died.
set -u
cd "$(dirname "$0")/.."
MODEL=${1:?model directory, e.g. t/out/locallm-r9}
TAG=${2:?answer set tag}
SHARDS=${3:-4}
CARDS=${4:-"0 1 2 3"}
shift 4 2>/dev/null || shift $#
# Everything after the four fixed arguments belongs to the generator: that is
# how "--temperature 0" reaches it, both in the example above and in
# t/steps.json. It has to be captured here, because the card loop below runs
# `set -- $CARDS`, which replaces the positional parameters, so by then "$@" is
# the card list. 75a43fa changed that call site to read "${EXTRA[@]}" but never
# added this assignment, so EXTRA stayed unset and every fleet run since then
# dropped the caller's flags and still exited 0.
#
# The call site expands it as ${EXTRA[@]+"${EXTRA[@]}"}, not "${EXTRA[@]}",
# because the usual case is no extra arguments and an empty array is not safe
# to expand under set -u on every bash: BashFAQ 112 records that "An empty
# array becomes an error (in bash 4.3, but not in bash 4.4, where there is no
# error even without assignment array=())". Both machines here are past that
# line, 5.2.21 on the lab and 5.3.9 on the desktop, which is why this failed
# silently instead of aborting. The + form tests "only for existence" (bash
# manual, Shell Parameter Expansion), so it contributes nothing when EXTRA is
# empty and each element quoted separately when it is not.
# https://mywiki.wooledge.org/BashFAQ/112
# https://www.gnu.org/software/bash/manual/html_node/Shell-Parameter-Expansion.html
EXTRA=("$@")
SPLIT=${T_SPLIT:-t/out/loop/split-v5.json}
PY=${T_PY:-~/.venv-vllm/bin/python}
DONE="t/out/gen-$TAG.done"
rm -f "$DONE"

python3 - "$SPLIT" "$SHARDS" <<'PYEOF'
import json, sys
from pathlib import Path
split, shards = sys.argv[1], int(sys.argv[2])
ids = sorted(map(int, json.loads(Path(split).read_text())["eval_ids"]))
for k in range(shards):
    Path(f"t/out/loop/eval-chunk{k}.txt").write_text("\n".join(map(str, ids[k::shards])) + "\n")
print(f"{len(ids)} problems over {shards} shards", flush=True)
PYEOF

set -- $CARDS
ncards=$#
pids=""
for k in $(seq 0 $((SHARDS - 1))); do
  eval "card=\${$(( k % ncards + 1 ))}"
  PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True CUDA_VISIBLE_DEVICES="$card" \
    $PY t/loop_locallm.py generate --model "$MODEL" --tag "$TAG" --split "$SPLIT" \
      --ids-file "t/out/loop/eval-chunk$k.txt" ${EXTRA[@]+"${EXTRA[@]}"} \
      > "t/out/gen-$TAG-$k.log" 2>&1 &
  pids="$pids $!"
  echo "shard $k -> card $card (pid $!)"
done

rc=0
for p in $pids; do wait "$p" || rc=1; done
answered=$(ls "t/out/spec-experiment/$TAG/raw" 2>/dev/null | wc -l)
echo "$TAG: $answered answers, worker status $rc"
# The sentinel means finished, not merely exited: a chain that waits on it would
# otherwise score a partial answer set, which is how two chains were fooled on
# 2026-09-19.
[ "$rc" = "0" ] && touch "$DONE" || echo "at least one shard failed; no sentinel written"
exit $rc
