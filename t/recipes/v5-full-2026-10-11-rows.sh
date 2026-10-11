#!/usr/bin/env bash
# Fixed panels and family removals; reuse existing auditors on the same bytes.
# Source: https://github.com/trestoncuzzort/dawnr/blob/1994e06a/t/heldout_audit.py
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")/../.."
export T_SANDBOX=landlock CUDA_VISIBLE_DEVICES= PYTHONUNBUFFERED=1
PY="${PYTHON:-python3}"
OUT=t/out/v5-full-20261011
mkdir -p "$OUT"
"$PY" t/recipes/v5-full-2026-10-11-build.py > "$OUT/build.log" 2>&1
INPUT_SHA=$(sha256sum "$OUT/raw-rows.jsonl" | cut -d ' ' -f 1)
"$PY" t/heldout_audit.py --rows "$OUT/raw-rows.jsonl" --refuse-gpl --jobs 4 \
  --json "$OUT/audit-raw.json" > "$OUT/audit-raw.log" 2>&1 || test "$?" -eq 1
"$PY" t/spec_panel.py check --rows "$OUT/raw-rows.jsonl" --panel "$OUT/spec-heldout.jsonl" --jobs 4 \
  --json "$OUT/spec-audit-raw.json" > "$OUT/spec-audit-raw.log" 2>&1 || test "$?" -eq 1
"$PY" t/recipes/student_row_families.py --rows "$OUT/raw-rows.jsonl" --input-sha256 "$INPUT_SHA" \
  --findings "$OUT/audit-raw.json" "$OUT/spec-audit-raw.json" --split t/out/loop/split-v5.json \
  --nl-data "$OUT/reference-data" \
  --keep "$OUT/train-rows.jsonl" --report "$OUT/family-removals.json" > "$OUT/family-removals.log" 2>&1
"$PY" t/heldout_audit.py --rows "$OUT/train-rows.jsonl" --refuse-gpl --jobs 4 \
  --json "$OUT/audit-final.json" > "$OUT/audit-final.log" 2>&1
"$PY" t/heldout_audit.py --rows "$OUT/train-rows.jsonl" --panels --refuse-gpl --jobs 4 \
  --json "$OUT/audit-final-panels.json" > "$OUT/audit-final-panels.log" 2>&1
"$PY" t/spec_panel.py check --rows "$OUT/train-rows.jsonl" --panel "$OUT/spec-heldout.jsonl" --jobs 4 \
  --json "$OUT/spec-audit-final.json" > "$OUT/spec-audit-final.log" 2>&1
sha256sum "$OUT/train-rows.jsonl" "$OUT/spec-heldout.jsonl"
wc -l "$OUT/train-rows.jsonl"
touch "$OUT/ROWS-AUDITED"
