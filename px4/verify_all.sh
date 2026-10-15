#!/usr/bin/env bash
# dawnr ▸ px4 formal gates: replay every certificate (no model) on this machine's provers.
# Non-zero exit if any PX4 invariant proof no longer reproduces.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
if ! command -v dawnr >/dev/null 2>&1; then
  echo "verify_all.sh: 'dawnr' not on PATH — install dawnr + a prover (SPARK/gnatprove). Skipping." >&2
  exit 2
fi
fail=0
for c in "$HERE"/*/cert.json; do
  name="$(basename "$(dirname "$c")")"
  echo "== $name =="
  if dawnr check "$c" >/tmp/gate-$name.log 2>&1; then
    echo "  OK (reproduced): $(grep -o 'real [a-z]*, twin [a-z]*' /tmp/gate-$name.log | tail -1)"
  else
    echo "  FAIL — proof did not reproduce; see /tmp/gate-$name.log"; fail=1
  fi
done
[ "$fail" = 0 ] && echo "ALL GATES REPRODUCED" || echo "SOME GATES FAILED"
exit $fail
