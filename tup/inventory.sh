#!/bin/bash
# inventory.sh — hash every file tup contains, so two builds can be compared
# and so "we know exactly what is on this system" is a checkable claim.
#
#   bash tup/inventory.sh                 # run against the built $LFS tree
#   bash tup/inventory.sh /path/to/root   # or any root
#
# Output: tup/receipts/INVENTORY-<date>.txt — one line per regular file,
# `<sha256>  <mode> <size> <path>`, sorted by path, with symlinks recorded as
# `-> target` (their content is the target, and a link that changes target is
# a change worth seeing).
#
# WHY THIS EXISTS, in two parts:
#
# 1. THE REPRODUCIBILITY EXPERIMENT. Build tup twice from the same manifest
#    and diff two inventories. Files that differ are non-determinism —
#    embedded timestamps, build paths, ordering, parallelism. That is a
#    measurement with a yes/no answer and a countable result, and whatever
#    differs is a finding rather than a nuisance. Expect differences: this is
#    a plain LFS build, not a reproducible-builds-hardened one, so the honest
#    prediction is "many files differ" and the interesting number is WHICH.
#
# 2. THE COMPLETE INVENTORY. tup has no package manager, so the filesystem IS
#    the manifest. A system whose every file is enumerated and hashed is the
#    right subject for asking "is anything here that should not be" — which
#    is the security-smell question, asked of a system small enough to answer.
#
# Excluded (by directory, listed rather than silently dropped): the virtual
# filesystems (/proc /sys /dev /run), which are kernel state and not files;
# the build scaffolding (/sources /tup-build), which is not part of tup; and
# /tmp. Every exclusion is printed in the header, so the reader knows what
# was NOT looked at.
set -u
ROOT="${1:-/mnt/lfs}"
# A trailing slash used to disable every exclusion below and quietly change the
# format. The prune patterns are built as "$ROOT/$d", so "/mnt/lfs/" gave
# "/mnt/lfs//proc", which `find -path` never matches: /proc, /sys, /dev, /run,
# /tmp, /sources and /tup-build all walked into the inventory while the header
# still listed them as excluded. And "${f#$ROOT}" stripped one character too
# many, so every recorded path lost its leading slash and no two inventories
# taken with different spellings of the same root could be diffed. Normalize
# once, here. BASE is what actually prefixes a child: for "/" that is the empty
# string, since "//proc" is the very bug being fixed.
while :; do case "$ROOT" in ?*/) ROOT="${ROOT%/}";; *) break;; esac; done
case "$ROOT" in /) BASE="";; *) BASE="$ROOT";; esac
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/receipts"; mkdir -p "$OUT"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="$OUT/INVENTORY-$STAMP.txt"
EXCLUDE=(proc sys dev run tmp sources tup-build)

[ -d "$ROOT" ] || { echo "no root at $ROOT"; exit 1; }

PRUNE=()
for d in "${EXCLUDE[@]}"; do PRUNE+=(-path "$BASE/$d" -prune -o); done

{
  echo "# tup inventory — $STAMP"
  echo "# root: $ROOT"
  echo "# excluded (not examined): ${EXCLUDE[*]}"
  echo "# format: <sha256 | symlink target>  <mode> <size> <path relative to root>"
  echo "#"
} > "$DEST"

find "$ROOT" "${PRUNE[@]}" \( -type f -o -type l \) -print 2>/dev/null \
| LC_ALL=C sort \
| while read -r f; do
    rel="${f#$BASE}"
    if [ -L "$f" ]; then
      printf -- "-> %-58s %s %8s %s\n" "$(readlink "$f")" "lnk" "-" "$rel"
    else
      read -r h _ <<< "$(sha256sum "$f" 2>/dev/null)"
      m=$(stat -c %a "$f" 2>/dev/null || echo "???")
      s=$(stat -c %s "$f" 2>/dev/null || echo 0)
      printf "%s %s %8s %s\n" "${h:-UNREADABLE}" "$m" "$s" "$rel"
    fi
  done >> "$DEST"

FILES=$(grep -cv "^#" "$DEST")
LINKS=$(grep -c "^-> " "$DEST" || true)
BYTES=$(awk '!/^#/ && !/^-> / {s+=$3} END {print s+0}' "$DEST")
{
  echo "#"
  echo "# totals: $((FILES - LINKS)) files, $LINKS symlinks, $BYTES bytes hashed"
} >> "$DEST"

echo "wrote ${DEST#$HERE/}"
echo "  $((FILES - LINKS)) files, $LINKS symlinks, $BYTES bytes"
echo
echo "to compare two builds:  diff INVENTORY-A.txt INVENTORY-B.txt | grep '^[<>]' | wc -l"
