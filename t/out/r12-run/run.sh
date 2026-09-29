#!/bin/bash
# t/out/r12-run/run.sh -- launch the r12 fine-tune, once pretraining's core checkpoint is ready.
#
# Waits for t/out/pretrain-r12-2026-09-25/wd0.8-lr1e-3-seed1337-desktop-best/{best.pt,run.json}
# to report status "complete" or "stopped" (early stop at its best; t/RUN-NEXT-locallm-r12.md F 0-2), then for each of
# ten seeds: trains on this desktop's GPU (section C's command), picks its dev-chosen stopping
# step, generates the 232 held-out answers, and grades them on the lab. Finally scores all twenty
# arms (ten r11 base seeds already graded, ten new r12 seeds) and compares them under
# t/PREDICT-r12.md's registration.
#
# Every GPU-touching step (train, pick-step -- it decodes, generate) runs as
#   flock $GPU_LOCK systemd-run --user --scope -p MemoryMax=$MEM_CAP <cmd>
# one job at a time: flock serializes access to the one RTX 4080 across every track that might
# want it; MemoryMax is a cgroup cap systemd enforces over the whole scope (every child the job
# forks), not a per-process rlimit (freedesktop.org/software/systemd/man/latest/systemd.
# resource-control.html, fetched 2026-09-27, research-first receipt f6c069f35a64). Grading goes to
# the lab (T_LAB) with T_LAB_JOBS capped at 2 cells (about 8 cores), a courtesy limit on a machine
# shared with other users; raise it if the operator says the lab is otherwise idle.
#
#   bash t/out/r12-run/run.sh --dry-run     check every precondition, print every command, run nothing
#   bash t/out/r12-run/run.sh --wait        poll every five minutes until the core is ready, then run
#   bash t/out/r12-run/run.sh               run once; refuse immediately if the core is not ready yet
#
# Resumable: every stage is skipped when its own output already says it finished (a run.json whose
# status is complete, a selection.json, a gen-<tag>.done sentinel, a kernels.md), the same rule
# t/r12_data_queue.sh uses for its steps. Nothing here deletes or overwrites another track's files;
# it only reads the pretrain checkpoint and writes under t/out/locallm-r12-s<seed>/.
set -u -o pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$REPO_ROOT" || exit 1

DRY=0
POLL=0
for a in "$@"; do
  case "$a" in
    --dry-run) DRY=1 ;;
    --wait) POLL=1 ;;
    *) echo "REFUSED: unknown argument $a (--dry-run or --wait)"; exit 3 ;;
  esac
done

PRETRAIN_DIR=t/out/pretrain-r12-2026-09-25/wd0.8-lr1e-3-seed1337-desktop-best
CORE="$PRETRAIN_DIR/best.pt"
CORPUS=t/out/loop/corpus-r12-headed.txt
SPLIT=t/out/loop/split-v5.json
DEV_IDS=t/r12-dev-ids.json
# R12_RUN_SEEDS: a subset, for a second launcher on another card or machine (2026-09-29, the
# move to the lab: one launcher per free card, disjoint seeds, each with its own R12_RUN_GPU_LOCK
# and CUDA_VISIBLE_DEVICES; every stage still skips when its own output exists, so a seed that
# finished here is skipped there once its t/out/locallm-r12-s<seed>/, t/out/spec-experiment/
# locallm-r12-s<seed>*/ and gen sentinel are copied over).
SEEDS=${R12_RUN_SEEDS:-"1 2 3 4 5 6 7 8 9 10"}
BASE_TAGS="locallm-r11-rerun locallm-r11-s1 locallm-r11-s2 locallm-r11-s3 locallm-r11-s4 locallm-r11-s5 locallm-r11-s6 locallm-r11-s7 locallm-r11-s8 locallm-r11-s9"
GPU_LOCK=${R12_RUN_GPU_LOCK:-$HOME/scratch/gpu.lock}
MEM_CAP=6G
# T_LAB: the environment wins, else t/lab-workstation.conf (gitignored; the only place this
# repository names a machine address, AGENTS.md's public-repo rule), same lookup as
# t/r12_data_queue.sh and t/lab_mode.sh use.
[ -z "${T_LAB:-}" ] && [ -f t/lab-workstation.conf ] && . t/lab-workstation.conf
T_LAB=${T_LAB:?set T_LAB=user@host or T_LAB=local in t/lab-workstation.conf, or export it}
GRADE_CELLS=${R12_RUN_GRADE_CELLS:-2}          # ~8 cores; see the header note
PY=${R12_RUN_PY:-$HOME/.venv-locallm/bin/python}   # every stage that imports torch runs under this venv: training,
                                       # the stopping-step choice (it decodes) and gen_fleet.sh (T_PY;
                                       # its default is the lab's vLLM venv, absent here). 2026-09-29:
                                       # the first launch died at pick-step on the system python3.
OUT_DIR=t/out/r12-run
LOG="$OUT_DIR/run.log"
mkdir -p "$OUT_DIR"

log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$LOG"; }
run() {                                        # logs, then executes unless --dry-run
  log "+ $*"
  [ "$DRY" = 1 ] && return 0
  "$@"
}
json_field_is() {                              # json_field_is FILE FIELD VALUE
  [ -f "$1" ] && python3 -c "
import json, sys
try:
    d = json.load(open('$1'))
except (OSError, ValueError):
    sys.exit(1)
sys.exit(0 if d.get('$2') == '$3' else 1)
" 2>/dev/null
}

# ---------------------------------------------------------------- preflight --
preflight_ok() {
  log "== preflight: split, corpus, decontamination (t/RUN-NEXT-locallm-r12.md section F step 2)"
  run env T_LAB="$T_LAB" python3 t/preflight.py --split "$SPLIT" --corpus "$CORPUS" --strict
  rc=$?
  # the one standing warning preflight raises here is t/steps.json's teacher-generation prompt
  # (v3) contradicting the parser about division; r12's own generation decodes the fine-tuned
  # model directly from the corpus's Problem:/Signature: head, never through that prompt template,
  # so --strict's other failure would be a real block and this one is not: accept exactly it.
  if [ "$rc" != 0 ] && [ "$DRY" != 1 ]; then
    env T_LAB="$T_LAB" python3 t/preflight.py --split "$SPLIT" --corpus "$CORPUS" --strict 2>&1 \
      | grep -v "a prompt in use says t has no division" | grep -q "\[FAIL\]" && {
        log "REFUSED: preflight has a failure beyond the known, accepted division-prompt warning"
        return 1
      }
    log "preflight: only the known division-prompt warning remains (see comment above); continuing"
  fi
  return 0
}

# --------------------------------------------------------- wait for the core --
core_ready() {
  # "complete" = ran every step; "stopped" = the early-stop rule ended it at its best (the trainer
  # writes "stopped" for any run that ends before --steps, and best.pt is the state to use)
  [ -f "$CORE" ] && { json_field_is "$PRETRAIN_DIR/run.json" status complete \
                      || json_field_is "$PRETRAIN_DIR/run.json" status stopped; }
}
core_failed() {
  [ -f "$PRETRAIN_DIR/run.json" ] && json_field_is "$PRETRAIN_DIR/run.json" status failed
}
wait_for_core() {
  if core_ready; then
    log "core ready: $CORE ($PRETRAIN_DIR/run.json status complete)"
    return 0
  fi
  if core_failed; then
    log "REFUSED: $PRETRAIN_DIR/run.json status is failed; the pretraining sweep did not finish cleanly"
    return 1
  fi
  local status="not started"
  [ -f "$PRETRAIN_DIR/run.json" ] && status=$(python3 -c "import json; print(json.load(open('$PRETRAIN_DIR/run.json')).get('status','?'))" 2>/dev/null || echo "unreadable")
  if [ "$DRY" = 1 ]; then
    log "(dry run) core not ready yet (run.json status: $status); would $([ "$POLL" = 1 ] && echo "poll every 5 minutes" || echo "refuse and exit"). Continuing the dry run so every later step is still checked."
    return 0
  fi
  if [ "$POLL" != 1 ]; then
    log "REFUSED: $CORE / $PRETRAIN_DIR/run.json is not complete yet (status: $status). Pass --wait to poll, or rerun once it finishes."
    return 1
  fi
  log "waiting for $PRETRAIN_DIR/run.json to report complete (status: $status); checking every 5 minutes"
  while ! core_ready; do
    core_failed && { log "REFUSED: pretraining failed while waiting"; return 1; }
    sleep 300
  done
  log "core ready: $CORE"
}

# -------------------------------------------------------------- per-seed steps --
train_seed() {
  local s=$1 out=t/out/locallm-r12-s$s
  if json_field_is "$out/run.json" status complete; then log "seed $s: already trained ($out/run.json complete)"; return 0; fi
  run flock "$GPU_LOCK" systemd-run --user --scope -p MemoryMax="$MEM_CAP" \
    "$PY" locallm/continue_from_checkpoint.py \
      --init "$CORE" --data "$CORPUS" --split "$SPLIT" \
      --out "$out" --steps 300 --lr 3e-5 --block-size 512 \
      --doc-batches --keep-every 50 --dropout 0.1 --split-seed 1338 --seed "$s" --deterministic
}
pick_step_seed() {
  local s=$1 out=t/out/locallm-r12-s$s
  [ -f "$out/selection.json" ] && { log "seed $s: stopping step already chosen"; return 0; }
  run flock "$GPU_LOCK" systemd-run --user --scope -p MemoryMax="$MEM_CAP" \
    "$PY" t/pick_stopping_step.py --run "$out" --split "$SPLIT" --dev-ids "$DEV_IDS" --install
}
generate_seed() {
  local s=$1 tag=locallm-r12-s$s out=t/out/locallm-r12-s$s
  [ -f "t/out/gen-$tag.done" ] && { log "seed $s: already generated (t/out/gen-$tag.done)"; return 0; }
  run flock "$GPU_LOCK" systemd-run --user --scope -p MemoryMax="$MEM_CAP" \
    env T_PY="$PY" bash t/gen_fleet.sh "$out" "$tag" 1 "0" --temperature 0
}
grade_seed() {
  local s=$1 tag=locallm-r12-s$s
  [ -f "t/out/spec-experiment/$tag/kernels.md" ] && { log "seed $s: already graded"; return 0; }
  run env T_LAB="$T_LAB" T_LAB_JOBS="$GRADE_CELLS" T_LAB_RUN_PAR=--no-cache bash t/grade_lab.sh heldout "$tag" \
    && return 0
  # 2026-09-29: an answer set with no well-formed answer has nothing for the kernels, and
  # run_par refuses an empty task set (exit 2), which grade_lab.sh reports as a failure. That
  # is a measured outcome, not a fault: 0 well-formed, 0 clean, which score_heldout.py counts
  # from extract.json and tests.json with no kernels.md present. Recorded, and the run goes on.
  if [ "$DRY" != 1 ] && [ -d "t/out/spec-experiment/$tag/tasks" ] \
     && [ -z "$(ls -A "t/out/spec-experiment/$tag/tasks" 2>/dev/null)" ]; then
    log "seed $s: no well-formed answer parsed, nothing to grade; scored as 0 (extract.json, tests.json)"
    return 0
  fi
  return 1
}

# ------------------------------------------------------------------ compare --
score_and_compare() {
  local new_tags="" s
  for s in $SEEDS; do new_tags="$new_tags locallm-r12-s$s"; done
  run python3 t/score_heldout.py --split "$SPLIT" --outcomes t/out/r12-outcomes.json $BASE_TAGS $new_tags
  local new_csv; new_csv=$(echo "$new_tags" | tr -s ' ' ',' | sed 's/^,//')
  local base_csv; base_csv=$(echo "$BASE_TAGS" | tr -s ' ' ',')
  run python3 t/compare_arms.py --outcomes t/out/r12-outcomes.json \
    --arm "base=$base_csv" --arm "new=$new_csv" --prereg t/PREDICT-r12.md \
    --json "$OUT_DIR/compare.json"
}

# ------------------------------------------------------------------- main --
main() {
  log "== r12 run start (dry-run=$DRY wait=$POLL)"
  preflight_ok || exit 1
  wait_for_core || exit 1
  local s
  for s in $SEEDS; do
    log "== seed $s"
    train_seed "$s" || { log "REFUSED: seed $s training failed"; exit 1; }
    pick_step_seed "$s" || { log "REFUSED: seed $s stopping-step selection failed"; exit 1; }
    generate_seed "$s" || { log "REFUSED: seed $s generation failed"; exit 1; }
    grade_seed "$s" || { log "REFUSED: seed $s grading failed"; exit 1; }
  done
  score_and_compare || { log "REFUSED: scoring or comparison failed"; exit 1; }
  log "== r12 run done: see $OUT_DIR/compare.json and t/out/r12-outcomes.json"
}
main
