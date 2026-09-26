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

# Before a card is touched: the flags must be verifiable after the fact. The
# headline arm was sampled at 0.5 because no --temperature reached the
# generator and its default filled in (r12 plan, A6), so the flag is required
# here, and an abbreviation such as --temp is refused rather than guessed at:
# the check after the fleet compares records against these exact names.
python3 - ${EXTRA[@]+"${EXTRA[@]}"} <<'PYEOF' || exit 2
import argparse, sys
KNOWN = {"--temperature": float, "--top-k": int, "--tokens": int, "--seed": int}
ap = argparse.ArgumentParser(allow_abbrev=False)
for name, kind in KNOWN.items():
    ap.add_argument(name, type=kind)
ns, unknown = ap.parse_known_args(sys.argv[1:])
bad = [u for u in unknown if u.startswith("--")
       and any(k != u and k.startswith(u.split("=", 1)[0]) for k in KNOWN)]
if bad:
    sys.exit(f"refusing to launch: {bad} abbreviates a generator flag and cannot be verified afterwards; "
             "spell it out")
if ns.temperature is None:
    sys.exit("refusing to launch: no --temperature given; a default sampled the headline arm at 0.5 once")
PYEOF

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
echo "$TAG: worker status $rc"
# The sentinel means finished, not merely exited: a chain that waits on it would
# otherwise score a partial answer set, which is how two chains were fooled on
# 2026-09-19. A worker exits 0 with an id unanswered when the pool lookup misses
# or the raw record already exists, so the workers' status proves nothing about
# completeness (r12 plan, A4): the answered eval ids must equal the split's, as
# Deequ checks a table's size and completeness before it is consumed
# (github.com/awslabs/deequ). And every record must carry the flags passed here
# under one decoding key, the scorer's rule (t/score_heldout.decoding_key), so a
# dropped flag is caught where its used value is observable (PCheck, Xu et al.
# OSDI'16, usenix.org/conference/osdi16/technical-sessions/presentation/xu).
python3 - "$SPLIT" "$TAG" "$MODEL" ${EXTRA[@]+"${EXTRA[@]}"} <<'PYEOF'
import argparse, json, os, sys
from pathlib import Path
sys.path.insert(0, "t")
import spec_experiment as se
import score_heldout
split, tag, model, extra = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]
eval_ids = {int(i) for i in json.loads(Path(split).read_text())["eval_ids"]}
raw = se.OUT_ROOT / se.model_tag(tag) / "raw"
answered = {int(p.stem) for p in raw.glob("*.json")} if raw.is_dir() else set()
missing, extra_ids = sorted(eval_ids - answered), sorted(answered - eval_ids)
problems = []
if missing:
    problems.append(f"missing {len(missing)} of {len(eval_ids)}: {missing[:20]}{' ...' if len(missing) > 20 else ''}")
if extra_ids:
    problems.append(f"{len(extra_ids)} raw record(s) that are not eval ids of {split}: {extra_ids[:20]}")
ap = argparse.ArgumentParser(allow_abbrev=False)
for name, kind in (("--temperature", float), ("--top-k", int), ("--tokens", int), ("--seed", int)):
    ap.add_argument(name, type=kind)
flags, _ = ap.parse_known_args(extra)
passed = {"temperature": flags.temperature, "top_k": flags.top_k, "max_new_tokens": flags.tokens, "seed": flags.seed}
passed = {k: v for k, v in passed.items() if v is not None}
records = {}
for tid in sorted(eval_ids & answered):
    try:
        records[tid] = json.loads((raw / f"{tid}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        problems.append(f"raw/{tid}.json is not a readable record ({e})")
# The model is compared as a path, not as a string: records store "locallm:"
# plus the --model string exactly as passed, and a resume that spells the same
# directory differently must not read as a different model, nor a different
# directory as the same one.
want = os.path.realpath(model)
for tid, r in records.items():
    got = str(r.get("model", ""))
    if not got.startswith("locallm:") or os.path.realpath(got[len("locallm:"):]) != want:
        problems.append(f"raw/{tid}.json was written for model {got!r}, this fleet ran {model!r}")
    options = r.get("options") if isinstance(r.get("options"), dict) else {}
    for name, value in passed.items():
        have = options.get(name)
        if isinstance(have, bool) or not isinstance(have, (int, float)) or float(have) != float(value):
            problems.append(f"raw/{tid}.json has {name}={have!r}, this fleet passed {value!r}")
keys = {}
for tid, r in records.items():
    keys.setdefault(score_heldout.decoding_key(r), []).append(tid)
if len(keys) > 1:
    combos = "; ".join(f"{len(ids)} at {k}" for k, ids in sorted(keys.items(), key=lambda kv: -len(kv[1]))[:3])
    differ = score_heldout._differing_settings([records[ids[0]] for ids in keys.values()])
    problems.append(f"records were decoded under {len(keys)} settings, differing in {', '.join(differ)}: {combos}")
if problems:
    print(f"{tag}: {len(answered & eval_ids)} of {len(eval_ids)} answered; NOT complete:")
    for line in problems[:40]:
        print("  " + line)
    sys.exit(2)
print(f"{tag}: {len(answered)} of {len(eval_ids)} answered under one decoding, flags as passed")
PYEOF
check=$?
if [ "$rc" = "0" ] && [ "$check" = "0" ]; then
  touch "$DONE"
  exit 0
fi
echo "no sentinel written (worker status $rc, completeness check $check)"
[ "$rc" = "0" ] && exit "$check" || exit "$rc"
