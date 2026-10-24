#!/usr/bin/env bash
# The release's laptop condition (internal/RELEASE-6.0-PLAN.md, section 3, condition 5): the README's example
# commands from a cold start on this laptop, each command's wall time and exit status, peak memory in use, and the
# GPU's temperature and software thermal slowdown sampled every second. The same script measures every candidate, so
# the comparison is one machine, one workload, one sampler.
#   LABEL=6.0.0 OUT=release/evidence/laptop-6.0.0-2026-10-24.json bash t/recipes/laptop_smoothness.sh
#   DAWNR_HOME=/path/with/a/candidate/env LABEL=6.1.0-candidate ... (a home whose env names another model)
set -u
# a user unit starts with PATH=/usr/local/bin:/usr/bin, where Lean and Rust (which Verus needs) are not; the person's
# shell has ~/.local/bin, and a measurement without it reads two provers as undecided (2026-10-24)
export PATH=$HOME/.local/bin:$HOME/.cargo/bin:$HOME/.elan/bin:$PATH
REPO=$(cd "$(dirname "$0")/../.." && pwd)
LABEL=${LABEL:?label}; OUT=${OUT:?output json}; DAWNR=${DAWNR:-$REPO/bin/dawnr}
W=$(mktemp -d); SAMPLES=$W/samples.tsv; TIMES=$W/times.tsv
sample() {
  while :; do
    avail=$(awk '/MemAvailable/ {print $2}' /proc/meminfo)
    gpu=$(nvidia-smi --query-gpu=temperature.gpu,clocks_event_reasons.sw_thermal_slowdown,memory.used,utilization.gpu \
          --format=csv,noheader,nounits 2>/dev/null | tr -d ' ' | tr ',' '\t')
    printf '%s\t%s\t%s\n' "$(date +%s.%N)" "$avail" "${gpu:-NA}" >> "$SAMPLES"
    sleep 1
  done
}
run() {  # name, folder, command...
  local name=$1 dir=$2; shift 2
  local t0 t1 rc
  t0=$(date +%s.%N); (cd "$dir" && "$@" > "$W/$name.out" 2>&1 < /dev/null); rc=$?; t1=$(date +%s.%N)
  local secs; secs=$(awk -v a="$t0" -v b="$t1" 'BEGIN { printf "%.2f", b - a }')
  printf '%s\t%s\t%s\n' "$name" "$secs" "$rc" >> "$TIMES"
  echo "$name rc=$rc ${secs}s"
}
"$DAWNR" serve stop > /dev/null 2>&1 || true
sleep 2
base_avail=$(awk '/MemAvailable/ {print $2}' /proc/meminfo); total=$(awk '/MemTotal/ {print $2}' /proc/meminfo)
sample & SP=$!; trap 'kill $SP 2>/dev/null' EXIT
run doctor "$W" "$DAWNR" doctor
run ask "$W" "$DAWNR" ask "Write a function that returns the larger of two integers." \
  --test "assert larger(3, 5) == 5" --test "assert larger(9, 2) == 9" --save-python larger.py --certificate larger.cert.json
run check "$W" "$DAWNR" check larger.cert.json
run do "$REPO" "$DAWNR" do "Describe the modules in this repository." --read-only
run cite "$W" "$DAWNR" cite "What does a comparison receipt not capture?" "$REPO/t/flight/README.md"
run calc "$W" "$DAWNR" calc "A logger records 12 samples per second for 15 seconds. How many samples is that?"
kill $SP 2>/dev/null; trap - EXIT
"$DAWNR" serve stop > /dev/null 2>&1 || true
python3 - "$SAMPLES" "$TIMES" "$OUT" "$LABEL" "$base_avail" "$total" "$W" "$REPO" <<'PY'
import json, sys, statistics, pathlib, subprocess
samples, times, out, label, base_avail, total, w, repo = sys.argv[1:]
rows = [l.split('\t') for l in open(samples).read().splitlines() if l.strip()]
avail = [int(r[1]) for r in rows]
gpu = [r[2:] for r in rows if len(r) >= 6 and r[2] != 'NA']
temps = [int(g[0]) for g in gpu if g[0].isdigit()]
slow = [g[1] for g in gpu]
cmds = [l.split('\t') for l in open(times).read().splitlines() if l.strip()]
doctor = pathlib.Path(w, 'doctor.out').read_text(errors='replace').splitlines()
# a command can exit 0 and still not have done its work (2026-10-24: `dawnr do` stopped on a model-server refusal)
FAILED = ('Stopped: the model server', 'did not answer', 'Traceback (most recent call last)', 'HTTP Error')
def ok(c):
    text = pathlib.Path(w, c[0] + '.out').read_text(errors='replace')
    return int(c[2]) == 0 and not any(f in text for f in FAILED)
rec = {'label': label, 'version': pathlib.Path(repo, 'VERSION').read_text().strip(),
       'commands': {c[0]: {'seconds': round(float(c[1]), 1), 'rc': int(c[2]), 'ok': ok(c)} for c in cmds},
       'median_seconds': round(statistics.median(float(c[1]) for c in cmds), 1),
       'all_succeeded': all(ok(c) for c in cmds),
       'memory_total_gib': round(int(total) / 1048576, 2),
       'memory_in_use_before_gib': round((int(total) - int(base_avail)) / 1048576, 2),
       'memory_in_use_peak_gib': round((int(total) - min(avail)) / 1048576, 2) if avail else None,
       'gpu_temperature_max_c': max(temps) if temps else None,
       'gpu_sw_thermal_slowdown_seen': any(s.lower() == 'active' for s in slow),
       'samples': len(rows), 'doctor': doctor[:4],
       'outputs': {c[0]: pathlib.Path(w, c[0] + '.out').read_text(errors='replace')[-600:] for c in cmds}}
pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
pathlib.Path(out).write_text(json.dumps(rec, indent=2) + '\n')
print(json.dumps({k: rec[k] for k in ('label', 'median_seconds', 'all_succeeded', 'memory_in_use_peak_gib', 'gpu_temperature_max_c', 'gpu_sw_thermal_slowdown_seen')}))
PY
