#!/usr/bin/env bash
# t/sync_engine.sh: bring dawnr's pinned copy of the t engine (t/ENGINE.md) up to a commit of
# github.com/trestoncuzzort/t-proof-engine, where engine changes land first.
#
#   bash t/sync_engine.sh [ENGINE_CHECKOUT] [COMMIT]
#
# ENGINE_CHECKOUT defaults to ../t-proof-engine beside this repository; COMMIT defaults to its origin/main after a
# fetch. Every file the engine tracks under t/ at COMMIT is written over this repository's t/, except the files
# dawnr owns (OWNED below). A file the previous pin tracked and COMMIT no longer does is deleted here. The new pin
# is recorded in t/ENGINE.md. Nothing is committed: read `git status` and run the tests that import what changed.
set -euo pipefail
export LC_ALL=C   # sort and comm must agree on one collation

here="$(cd "$(dirname "$0")/.." && pwd)"
eng="${1:-$here/../t-proof-engine}"
want="${2:-}"

# dawnr's own file of the same name: its pipeline (t/loop_train.py) needs `datasets`, the engine needs nothing
OWNED=(t/requirements.txt)

git -C "$eng" fetch -q origin
[ -n "$want" ] || want=origin/main
commit=$(git -C "$eng" rev-parse --verify "$want^{commit}")
prev=$(sed -n 's/^Pinned commit: `\([0-9a-f]\{40\}\)`.*/\1/p' "$here/t/ENGINE.md")
[ -n "$prev" ] || { echo "t/ENGINE.md names no pinned commit" >&2; exit 1; }

owned() { local f; for f in "${OWNED[@]}"; do [ "$1" = "$f" ] && return 0; done; return 1; }

# A file the engine adds at COMMIT that dawnr already tracks is dawnr's own file of the same name: extracting would
# overwrite it silently (2026-10-07: the engine's new t/repair.py would have replaced dawnr's model-repair loop).
clash=()
while IFS= read -r f; do
  owned "$f" && continue
  git -C "$here" ls-files --error-unmatch -- "$f" >/dev/null 2>&1 && clash+=("$f")
done < <(comm -13 <(git -C "$eng" ls-tree -r --name-only "$prev" -- t | sort) \
                  <(git -C "$eng" ls-tree -r --name-only "$commit" -- t | sort))
if [ "${#clash[@]}" -gt 0 ]; then
  echo "refused: t-proof-engine ${commit:0:8} adds files dawnr already owns; rename them in the engine or list them in OWNED:" >&2
  printf '  %s\n' "${clash[@]}" >&2
  exit 1
fi

excl=()
for f in "${OWNED[@]}"; do excl+=(--exclude="$f"); done
git -C "$eng" archive "$commit" -- t | tar -x -C "$here" "${excl[@]}"

gone=0
while IFS= read -r f; do
  owned "$f" && continue
  if [ -e "$here/$f" ]; then rm -f -- "$here/$f"; echo "deleted (no longer in the engine): $f"; gone=$((gone + 1)); fi
done < <(comm -23 <(git -C "$eng" ls-tree -r --name-only "$prev" -- t | sort) \
                  <(git -C "$eng" ls-tree -r --name-only "$commit" -- t | sort))

when=$(git -C "$eng" show -s --format=%cs "$commit")
sed -i "s/^Pinned commit: \`[0-9a-f]\{40\}\`.*/Pinned commit: \`$commit\` (t-proof-engine, $when)/" "$here/t/ENGINE.md"

echo "t/ synced to t-proof-engine $commit ($when), previous pin ${prev:0:8}; $gone file(s) deleted"
git -C "$here" status --short -- t | head -40
