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
#
# And when the scan itself does not finish, the file says so in its header and
# in its totals, and this script exits nonzero. The whole use of an inventory
# is to be diffed against another one as if both were complete; a short
# listing that reads like a complete one is worse than no listing at all.
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

# The two scratch files this script needs are ordinary files somewhere on this
# machine, and "somewhere" can be INSIDE the tree being inventoried: $TMPDIR
# under $ROOT, or $ROOT itself /tmp, or $ROOT = /. The scan then finds them —
# the listing is created by the redirect before find starts walking — hashes
# them, and counts their bytes in the totals. They are unique per run and the
# scan file holds the root's own path, so two inventories of one unchanged
# system differ, and the difference reads as non-determinism in tup, which is
# the exact question this file exists to answer. Measured 2026-09-02: a root
# holding three files and seventeen bytes filed "5 files, 0 symlinks, 774 bytes
# hashed", two of them its own.
#
# So they are named to find as paths not to walk into, in BOTH spellings, since
# find prints the path it walked and that need not be the path mktemp handed
# back: on macOS $TMPDIR sits under /var, which is a symlink to /private/var, so
# an inventory of / reaches the same file as /private/var/... while $SCAN still
# says /var/.... Leaving them out is an exclusion like any other, so it is
# printed in the header rather than done quietly.
SCAN=$(mktemp "${TMPDIR:-/tmp}/tup-inventory-scan-XXXXXX")
ERRS=$(mktemp "${TMPDIR:-/tmp}/tup-inventory-errs-XXXXXX")
trap 'rm -f "$SCAN" "$ERRS"' EXIT
SCRATCH=("$SCAN" "$ERRS")
SCRATCH_DIR=$(dirname "$SCAN")
SCRATCH_PHYS=$(cd "$SCRATCH_DIR" 2>/dev/null && pwd -P) || SCRATCH_PHYS="$SCRATCH_DIR"
if [ "$SCRATCH_PHYS" != "$SCRATCH_DIR" ]; then
  SCRATCH+=("$SCRATCH_PHYS/$(basename "$SCAN")" "$SCRATCH_PHYS/$(basename "$ERRS")")
fi

PRUNE=()
for d in "${EXCLUDE[@]}"; do PRUNE+=(-path "$BASE/$d" -prune -o); done
for s in "${SCRATCH[@]}"; do PRUNE+=(-path "$s" -prune -o); done

# find's verdict used to be discarded twice over: `2>/dev/null` threw away what
# it said, and the pipe into `sort` threw away that it had said anything at all,
# since the status of a pipeline is the status of its LAST command. A scan that
# died one file in -- an unreadable directory, a mount that went away -- still
# produced a file headed "tup inventory" with a totals line under it, and this
# script still exited 0. Measured: a root holding four files, a find that
# stopped after one, and a receipt reading "totals: 1 files ... 20 bytes hashed"
# with the reader invited at the end to diff it against another build.
#
# So the scan happens first, into a file, with its status and its complaints
# kept; the header is written afterwards and can therefore say which kind of
# scan this was. GNU find exits nonzero if ANY path could not be read, which is
# exactly the condition that makes the completeness claim false. (The scratch
# files it writes into were made, and excluded from the walk, above.)
find "$ROOT" "${PRUNE[@]}" \( -type f -o -type l \) -print > "$SCAN" 2> "$ERRS"
FIND_RC=$?

{
  echo "# tup inventory — $STAMP"
  echo "# root: $ROOT"
  echo "# excluded (not examined): ${EXCLUDE[*]}"
  echo "# also excluded: this script's own two scratch files, mktemp'd as"
  echo "#   tup-inventory-scan-XXXXXX and tup-inventory-errs-XXXXXX under \$TMPDIR,"
  echo "#   which is a directory that can fall inside the tree being scanned."
  echo "#   They are deleted when this script exits. Named by pattern and not by"
  echo "#   path on purpose: the path is unique per run, and a header line that"
  echo "#   changes every run is a line every diff of two inventories reports."
  echo "# format: <sha256 | symlink target>  <mode> <size> <path relative to root>"
  if [ "$FIND_RC" -ne 0 ]; then
    echo "#"
    echo "# !!! PARTIAL: THE SCAN FAILED. find exited $FIND_RC, so what follows is"
    echo "# !!! whatever it listed before it stopped. This is NOT an inventory of"
    echo "# !!! this system and it must not be diffed against one as though it"
    echo "# !!! were. find said:"
    sed 's/^/# !!!   /' "$ERRS"
  fi
  echo "#"
} > "$DEST"

if [ "$FIND_RC" -ne 0 ]; then
  echo "!!! the filesystem scan FAILED: find exited $FIND_RC" >&2
  sed 's/^/    /' "$ERRS" >&2
fi

LC_ALL=C sort "$SCAN" \
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
  if [ "$FIND_RC" -ne 0 ]; then
    echo "# totals of a PARTIAL scan (find exited $FIND_RC): $((FILES - LINKS)) files,"
    echo "# $LINKS symlinks, $BYTES bytes hashed. This is not the size of the system."
  else
    echo "# totals: $((FILES - LINKS)) files, $LINKS symlinks, $BYTES bytes hashed"
  fi
} >> "$DEST"

echo "wrote ${DEST#$HERE/}"
if [ "$FIND_RC" -ne 0 ]; then
  echo "  PARTIAL: $((FILES - LINKS)) files, $LINKS symlinks, $BYTES bytes — the scan"
  echo "  did not finish, so this file is not an inventory of the system."
  exit 1
fi
echo "  $((FILES - LINKS)) files, $LINKS symlinks, $BYTES bytes"
echo
echo "to compare two builds:  diff INVENTORY-A.txt INVENTORY-B.txt | grep '^[<>]' | wc -l"
