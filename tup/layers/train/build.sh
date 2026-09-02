#!/bin/bash
# build.sh — install the train layer into a built tup, with a measured diff.
#
#   sudo bash tup/layers/train/build.sh          # inside the build VM
#
# WHAT A LAYER IS, and why this is not just "some more packages": the base
# system is built from source with a receipt per step, and its inventory is a
# complete list of every file on the machine. A layer keeps that property by
# construction — inventory BEFORE, install, inventory AFTER, and the diff IS
# the layer's contents. "Here is what installing an AI coding agent added to
# my operating system, file by file" stops being a shrug and becomes a number.
#
# The layer is built INSIDE THE CHROOT on the build VM, which has a network.
# tup itself ships no curl and no wget, so a freshly booted tup cannot fetch
# anything; doing the install here is what makes the finished image arrive
# with the agent already on it.
#
# Sources are fetched on the build VM and CHECKED against MANIFEST before use.
# Node is a prebuilt binary and that is stated in its page rather than hidden:
# it is the one thing in tup this machine did not compile.
set -u
export LFS=${LFS:-/mnt/lfs}
HERE="$(cd "$(dirname "$0")" && pwd)"
LOG=$LFS/sources/log
RECEIPTS_DIR="$(cd "$HERE/../../receipts" 2>/dev/null && pwd || echo /tmp)"
TUP_DIR="$(cd "$HERE/../.." 2>/dev/null && pwd || echo /tmp)"

fail() { echo "!!! train layer: $*" >&2; exit 1; }

[ -d "$LFS/usr/bin" ] || fail "no built tup at $LFS"
grep -q "^ch11" "$LOG/driver.state" 2>/dev/null \
  || echo "note: base system does not look finished; continuing anyway"

# --- 1. fetch and verify sources -----------------------------------------
cd "$LFS/sources" || fail "no sources dir"
case "$(uname -m)" in aarch64) export TUP_ARCH=arm64 ;; x86_64) export TUP_ARCH=x86_64 ;; esac
# A MANIFEST row may end in arch=<arch>; rows for another arch are not
# fetched (the prebuilt binaries differ per arch, the sources do not).
while read -r name want url arch; do
  case "$name" in ''|'#'*) continue;; esac
  case "$arch" in arch=*) [ "${arch#arch=}" = "$TUP_ARCH" ] || continue ;; esac
  [ -s "$name" ] || { echo "fetching $name"; curl -fSL --retry 3 -o "$name" "$url" \
      || fail "cannot fetch $name"; }
  got=$(sha256sum "$name" | cut -d' ' -f1)
  if [ "$want" = "SHA256-RECORDED-AT-FETCH" ]; then
    echo "  $name sha256 $got   (recorded, not pinned — upstream rotates this file)"
  elif [ "$got" != "$want" ]; then
    fail "$name hash mismatch: manifest $want, got $got"
  else
    echo "  $name sha256 OK"
  fi
done < "$HERE/MANIFEST"

# --- 2. inventory BEFORE --------------------------------------------------
# inventory.sh PRINTS the path it wrote and RETURNS a status. Both used to be
# discarded: the path was guessed with `ls -t` over the receipts directory, and
# that guess succeeds precisely when the inventory FAILED — it hands back a
# stale file from an earlier run. Measured on synthetic runs: a failing BEFORE
# silently diffed the layer against a year-old inventory, and a failing AFTER
# made both names resolve to the SAME file, so the layer diff came out empty
# and the script announced "added 0 files" for a layer it had just installed.
# An unmeasured layer is a failure, never a zero.
take_inventory() {                       # $1 = where to keep the transcript
  local out rc rel
  out=$(bash "$HERE/../../inventory.sh" "$LFS" 2>&1); rc=$?
  printf '%s\n' "$out" > "$1"
  [ "$rc" -eq 0 ] || { printf '%s\n' "$out" | tail -5 >&2; return 1; }
  rel=$(printf '%s\n' "$out" | sed -n 's/^wrote //p' | head -1)
  [ -n "$rel" ] || { echo "inventory.sh exited 0 but named no file" >&2; return 1; }
  case "$rel" in /*) printf '%s\n' "$rel";; *) printf '%s\n' "$TUP_DIR/$rel";; esac
}
echo "=== inventory before the layer"
BEFORE=$(take_inventory /tmp/agent-before.txt) \
  || fail "inventory BEFORE the layer failed — refusing to measure a layer against a guess"
[ -s "$BEFORE" ] || fail "inventory BEFORE the layer wrote nothing at $BEFORE"
echo "  $BEFORE"

# --- 3. install the layer through the same driver -------------------------
mkdir -p "$LFS/tup-build/layers"
rm -rf "$LFS/tup-build/layers/train"          # else the second run nests pages/
cp -r "$HERE/pages" "$LFS/tup-build/layers/train"
rm -rf "$LFS/tup-build/locallm-src"; cp -r "$HERE/../../../locallm" "$LFS/tup-build/locallm-src"
mountpoint -q "$LFS/proc" || bash -e /home/lfs/book/ch07/03-kernfs.sh >/dev/null 2>&1

# No resolver: this layer builds OFFLINE from pinned sources. A build
# that cannot reach the network cannot be tempted by it.
cleanup_resolv() { :; }

chroot "$LFS" /usr/bin/env -i HOME=/root TERM=xterm TUP_ARCH="$TUP_ARCH" \
  PATH=/usr/bin:/usr/sbin:/opt/node-v24.20.0/bin MAKEFLAGS=-j"$(nproc)" LFS=/ \
  TUP_OVERRIDES=/tup-build/overrides \
  /bin/bash /tup-build/driver.sh /tup-build/layers/train \
  || { cleanup_resolv; fail "layer install failed; the driver stopped on a named page"; }
cleanup_resolv; RESOLV_BOUND=""

# --- 4. inventory AFTER, and the diff that IS the layer -------------------
echo "=== inventory after the layer"
AFTER=$(take_inventory /tmp/agent-after.txt) \
  || fail "inventory AFTER the layer failed — the layer is installed but unmeasured"
[ -s "$AFTER" ] || fail "inventory AFTER the layer wrote nothing at $AFTER"
[ "$AFTER" != "$BEFORE" ] \
  || fail "before and after name the SAME inventory — refusing to report an empty diff as a measurement"
DIFF="$RECEIPTS_DIR/LAYER-train-$(date -u +%Y%m%dT%H%M%SZ).txt"
{
  echo "# tup layer: agent — what it added"
  echo "# before: $(basename "$BEFORE")"
  echo "# after : $(basename "$AFTER")"
  echo "#"
  # Key on hash+path, not path alone. Keying on the filename makes MODIFIED
  # files invisible, and this layer modifies /etc/profile (pages/01 appends the
  # CA variables to it) — a diff that cannot see that is not a diff.
  # A symlink's line is "-> <target> lnk - <path>", so $1 is the literal "->"
  # for every symlink on the system: the old key gave them all the same value,
  # and a link retargeted from /usr/bin/bash to /usr/bin/dash landed in no
  # section at all — not added, not removed, not modified. A symlink's content
  # IS its target, which is what it is keyed on now. The "->" prefix keeps a
  # symlink and a regular file at one path from ever comparing equal.
  key='NF { if ($1 == "->") {
              v = ""; for (i = 2; i <= NF - 3; i++) v = v (i > 2 ? " " : "") $i
              print $NF "\t->" v
            } else print $NF "\t" $1 }'
  b=$(mktemp); a=$(mktemp)
  grep -v '^#' "$BEFORE" | awk "$key" | sort > "$b"
  grep -v '^#' "$AFTER"  | awk "$key" | sort > "$a"
  added=$(comm -13 <(cut -f1 "$b") <(cut -f1 "$a"))
  removed=$(comm -23 <(cut -f1 "$b") <(cut -f1 "$a"))
  modified=$(join -t"$(printf '\t')" "$b" "$a" 2>/dev/null \
             | awk -F'\t' '$2 != $3 {print $1}')
  n_added=$(printf '%s\n' "$added"    | grep -c . || true)
  n_removed=$(printf '%s\n' "$removed"  | grep -c . || true)
  n_modified=$(printf '%s\n' "$modified" | grep -c . || true)
  echo "# files added:    $n_added"
  echo "# files removed:  $n_removed"
  echo "# files MODIFIED: $n_modified"
  echo "#"
  echo "## added"; printf '%s\n' "$added"
  echo "## removed"; printf '%s\n' "$removed"
  echo "## modified"; printf '%s\n' "$modified"
  rm -f "$b" "$a"
} > "$DIFF"
echo
# `grep -c '^/' "$DIFF"` counted every path line in the file — the added, the
# removed and the modified alike — so a layer that added 1, removed 2 and
# modified 1 announced "added 4 files". (And on a count of zero grep exits 1,
# so the `|| echo 0` fired as well and printed the number twice.) The sections
# were already counted while the diff was written; say all three.
echo "layer installed. added $n_added files, removed $n_removed, modified $n_modified"
echo "diff: $DIFF"
