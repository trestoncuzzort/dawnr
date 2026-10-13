#!/usr/bin/env bash
# Repair rounds and fresh sweeps for the uDebug solve-all goal (t/PREDICT-2026-10-13-udebug-solve-all.md).
# One instance per DeepSeek project; it waits for that project's scale lane to end, then runs three rounds:
#   refresh the bundle index -> refused problems of this parity get a repair prompt (--repair-from every lane),
#   untried problems of this parity get a fresh prompt -> grade both lanes.
# usage: udebug-solve-rounds.sh <name> <project> <adc-file> <parity 0|1|2=all> <scale-unit-to-wait-for|none>
# MODEL=<vertex model id> in the environment overrides the teacher's default (DeepSeek-V3.2).
set -u
cd ~/Projects/dawnr
NAME=$1; PROJECT=$2; ADC=$3; PAR=$4; WAIT=$5
LOG=t/out/udebug/solve-rounds-$NAME.log
BANK=t/out/udebug/bank.jsonl; CORPUS=t/out/udebug-bulk-20261011; OUT=t/out/udebug-solutions
EX=/home/t/Projects/t-proof-engine/problems/uva
log(){ echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" >> "$LOG"; }
log "waiting for $WAIT to end"
while systemctl --user is-active --quiet "$WAIT"; do sleep 300; done
log "$WAIT ended; rounds begin"
for round in 1 2 3; do
  flock $OUT/.export.lock python3 t/udebug_export.py --bank $BANK --corpus $CORPUS --lanes 't/out/udebug/teacher-*' --out $OUT --judges UVa --jobs 2 --only-new >> "$LOG" 2>&1
  python3 - "$PAR" <<'PY'
import json, sys
par = int(sys.argv[1])
refused, untried = [], []
for line in open("t/out/udebug-solutions/INDEX.jsonl", encoding="utf-8"):
    e = json.loads(line)
    if not e["id"].isdigit() or (par in (0, 1) and int(e["id"]) % 2 != par):
        continue
    best = (e.get("best") or {}).get("status")
    if e["status"] in ("unsolved", "accepted-but-not-confirmed") and best != "no-fences":
        refused.append(f"{e['judge']}/{e['id']}")           # a program to quote and a refusal to answer
    elif e["status"] == "untried" or best == "no-fences":
        untried.append(f"{e['judge']}/{e['id']}")           # nothing to quote: a fresh prompt, longer reply budget
open("t/out/udebug/solve-ids-refused.txt", "w").write(",".join(refused) + "\n")
open("t/out/udebug/solve-ids-untried.txt", "w").write(",".join(untried) + "\n")
print(f"parity {par}: {len(refused)} refused, {len(untried)} untried", flush=True)
PY
  mv t/out/udebug/solve-ids-refused.txt t/out/udebug/solve-ids-refused-$NAME.txt
  mv t/out/udebug/solve-ids-untried.txt t/out/udebug/solve-ids-untried-$NAME.txt
  LANES=$(ls -d t/out/udebug/teacher-*/ | sed 's|/$||' | grep -v "dry\|probe" | tr '\n' ',' | sed 's/,$//')
  COMMON="--bank $BANK --exemplars $EX --target python --provider vertex --project $PROJECT --location global --adc $ADC --judges UVa --shape any --split any --max-in-bytes 0 --samples 1 --temperature 0.7 --max-tokens 8192 --concurrency 4 --price-in-per-mtok 0.56 --price-out-per-mtok 1.68 --spend-cap-usd 25${MODEL:+ --model $MODEL}"
  for kind in repair fresh; do
    IDS=$(cat t/out/udebug/solve-ids-$([ $kind = repair ] && echo refused || echo untried)-$NAME.txt)
    [ -n "$IDS" ] || { log "round $round $kind: nothing to do"; continue; }
    TAG=solve-r$round-$NAME-$kind
    EXTRA=""; [ $kind = repair ] && EXTRA="--repair-from $LANES --corpus $CORPUS --max-tokens 16384"
    log "round $round $kind: $(echo $IDS | tr ',' '\n' | wc -l) problems -> $TAG"
    python3 t/udebug_teacher.py $COMMON --tag $TAG --ids "$IDS" $EXTRA >> t/out/udebug/teacher-$TAG.log 2>&1
    log "round $round $kind: teacher exit $?"
    python3 t/udebug_gate.py --samples t/out/udebug/teacher-$TAG --corpus $CORPUS --bank $BANK --kernels dafny --jobs 2 --judge-timeout 300 >> t/out/udebug/teacher-$TAG-gate.log 2>&1
    acc=$(grep -c 'accepted=True' t/out/udebug/teacher-$TAG-gate.log); tot=$(grep -c 'accepted=' t/out/udebug/teacher-$TAG-gate.log)
    log "round $round $kind: gate exit $?; accepted $acc of $tot"
    if [ $kind = repair ] && [ "$tot" -gt 20 ] && [ $((acc * 10)) -lt "$tot" ]; then log "stop rule: repair accepted under 10%; no further rounds"; break 2; fi
  done
done
flock $OUT/.export.lock python3 t/udebug_export.py --bank $BANK --corpus $CORPUS --lanes 't/out/udebug/teacher-*' --out $OUT --judges UVa --jobs 2 --only-new >> "$LOG" 2>&1
log "ROUNDS DONE"
