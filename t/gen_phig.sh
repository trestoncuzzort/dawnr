#!/bin/bash
# Phi decoding against t's own grammar: the arm that answers "Phi has never seen
# this language". Run this ON THE LAB WORKSTATION, not from the desktop.
#
#   bash t/gen_phig.sh              # one worker per card, cards 0 1 2 3
#   bash t/gen_phig.sh 0 3          # two workers, cards 0 and 3 (kernels busy)
#
# Safe to re-run: loop_generate.py skips a problem that already has an answer,
# so this resumes a killed run without regenerating anything. The set is the
# held-out 232, split across the four eval-chunk files.
#
# This script exists as a committed file because its predecessor lived in /tmp,
# did not survive a reboot, and pinned its cards in a way that did nothing.
#
# PIN THE CARD WITH --gpu, NEVER WITH CUDA_VISIBLE_DEVICES. loop_generate.py
# chooses a card itself (--gpu, default "most free VRAM") and then WRITES
# os.environ["CUDA_VISIBLE_DEVICES"] with its choice, so an inherited value is
# discarded. The /tmp version pinned per-worker with `CUDA_VISIBLE_DEVICES=$2`,
# every worker started at the same moment, every worker measured the same free
# card, and every worker picked GPU 0: two workers shared one card while three
# sat idle, at 155 s an answer, and the log said nothing. Measured 2026-09-20 --
# both pids reported the same gpu_uuid under nvidia-smi --query-compute-apps.
# This is the configuration-inconsistency class from Yin et al., "An Empirical
# Study on Configuration Errors in Commercial and Open Source Systems", SOSP
# 2011 (https://dl.acm.org/doi/10.1145/2043556.2043572): of 546 real errors,
# 12.2--29.7 percent of parameter mistakes come from two settings that disagree,
# and the loser is silent. Two channels, last write wins, no message.
set -u
cd "$(dirname "$0")/.."
CARDS=${*:-0 1 2 3}
BASE=microsoft/Phi-4-mini-instruct
# Budget, grammar and tag are parameters because the 3072 default was found on
# 2026-09-20 to truncate 205 of 232 constrained answers and 232 of 232
# unconstrained ones -- every reply in the baseline the README compares against
# stopped at the cap, `done_reason: length`, median reply_tokens exactly 3072.
# A model that was cut off mid-program did not answer badly; it did not answer.
#   T_MAX_NEW=8192 T_TAG=phi4-mini-8k T_GRAMMAR= bash t/gen_phig.sh
TAG=${T_TAG:-phi4-mini-g}
MAX_NEW=${T_MAX_NEW:-3072}
GRAMMAR=${T_GRAMMAR-t/t.gbnf}          # set empty for unconstrained decoding
SENTINEL=t/out/gen-$TAG.done

command -v nvidia-smi >/dev/null || { echo "no nvidia-smi: this runs on the lab, not the desktop"; exit 1; }
[ -x ~/.venv-vllm/bin/python ] || { echo "no ~/.venv-vllm: this runs on the lab, not the desktop"; exit 1; }

rm -f "$SENTINEL"
before=$(ls "t/out/spec-experiment/$TAG/raw" 2>/dev/null | wc -l)
echo "== $TAG: $before of 232 answered, cards: $CARDS, max_new=$MAX_NEW, grammar=${GRAMMAR:-none} =="

chunk=0
pids=""
for card in $CARDS; do
  ids="t/out/loop/eval-chunk$chunk.txt"
  [ -s "$ids" ] || { echo "missing $ids"; exit 1; }
  ~/.venv-vllm/bin/python t/loop_generate.py --adapter none --base "$BASE" \
    --tag "$TAG" --pool v3 --prompt v3 --ids-file "$ids" --max-new "$MAX_NEW" \
    ${GRAMMAR:+--grammar "$GRAMMAR"} --gpu "$card" >> "t/out/gen-$TAG-$chunk.log" 2>&1 &
  pids="$pids $!:$chunk:$card"
  echo "chunk$chunk -> GPU $card (pid $!)"
  chunk=$((chunk + 1))
done

# A sentinel a wrapper touches after `wait` means "the process exited", not "the
# work finished" -- that mistake scored two partial answer sets on 2026-09-19.
# So collect every exit code and only write the sentinel if all of them are 0.
bad=0
for entry in $pids; do
  pid=${entry%%:*}; rest=${entry#*:}; c=${rest%%:*}; card=${rest#*:}
  if wait "$pid"; then
    echo "chunk$c (GPU $card): ok"
  else
    echo "chunk$c (GPU $card): EXIT $? -- see t/out/gen-$TAG-$c.log"
    bad=$((bad + 1))
  fi
done

after=$(ls "t/out/spec-experiment/$TAG/raw" 2>/dev/null | wc -l)
echo "== $TAG: $after of 232 answered ($((after - before)) this run) =="
if [ "$bad" = 0 ] && [ "$after" -ge 232 ]; then
  touch "$SENTINEL"
  echo "wrote $SENTINEL"
  echo "Now grade it FROM THE DESKTOP: bash t/grade_lab.sh heldout $TAG"
else
  echo "no sentinel: $bad worker(s) failed, $after of 232 answered. Re-run to resume."
  exit 1
fi
