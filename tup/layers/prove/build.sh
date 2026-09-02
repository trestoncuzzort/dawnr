#!/bin/bash
# build.sh — install the prove layer into a built tup, with a measured diff.
#
#   sudo bash tup/layers/prove/build.sh          # inside the build VM
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

fail() { echo "!!! prove layer: $*" >&2; exit 1; }

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
echo "=== inventory before the layer"
bash "$HERE/../../inventory.sh" "$LFS" > /tmp/agent-before.txt 2>&1
BEFORE=$(ls -t "$RECEIPTS_DIR"/INVENTORY-*.txt 2>/dev/null | head -1)
[ -n "$BEFORE" ] || fail "inventory before failed"
echo "  $BEFORE"

# --- 3. install the layer through the same driver -------------------------
mkdir -p "$LFS/tup-build/layers"
rm -rf "$LFS/tup-build/layers/prove"          # else the second run nests pages/
cp -r "$HERE/pages" "$LFS/tup-build/layers/prove"
rm -rf "$LFS/tup-build/t-src"; cp -r "$HERE/../../../t" "$LFS/tup-build/t-src"
mountpoint -q "$LFS/proc" || bash -e /home/lfs/book/ch07/03-kernfs.sh >/dev/null 2>&1

# No resolver: this layer builds OFFLINE from pinned sources. A build
# that cannot reach the network cannot be tempted by it.
cleanup_resolv() { :; }

chroot "$LFS" /usr/bin/env -i HOME=/root TERM=xterm TUP_ARCH="$TUP_ARCH" \
  PATH=/usr/bin:/usr/sbin:/opt/node-v24.20.0/bin MAKEFLAGS=-j"$(nproc)" LFS=/ \
  TUP_OVERRIDES=/tup-build/overrides \
  /bin/bash /tup-build/driver.sh /tup-build/layers/prove \
  || { cleanup_resolv; fail "layer install failed; the driver stopped on a named page"; }
cleanup_resolv; RESOLV_BOUND=""

# --- 4. inventory AFTER, and the diff that IS the layer -------------------
echo "=== inventory after the layer"
bash "$HERE/../../inventory.sh" "$LFS" > /tmp/agent-after.txt 2>&1
AFTER=$(ls -t "$RECEIPTS_DIR"/INVENTORY-*.txt 2>/dev/null | head -1)
DIFF="$RECEIPTS_DIR/LAYER-prove-$(date -u +%Y%m%dT%H%M%SZ).txt"
{
  echo "# tup layer: agent — what it added"
  echo "# before: $(basename "$BEFORE")"
  echo "# after : $(basename "$AFTER")"
  echo "#"
  # Key on hash+path, not path alone. Keying on the filename makes MODIFIED
  # files invisible, and this layer modifies /etc/profile (pages/01 appends the
  # CA variables to it) — a diff that cannot see that is not a diff.
  b=$(mktemp); a=$(mktemp)
  grep -v '^#' "$BEFORE" | awk 'NF{print $NF"\t"$1}' | sort > "$b"
  grep -v '^#' "$AFTER"  | awk 'NF{print $NF"\t"$1}' | sort > "$a"
  added=$(comm -13 <(cut -f1 "$b") <(cut -f1 "$a"))
  removed=$(comm -23 <(cut -f1 "$b") <(cut -f1 "$a"))
  modified=$(join -t"$(printf '\t')" "$b" "$a" 2>/dev/null \
             | awk -F'\t' '$2 != $3 {print $1}')
  echo "# files added:    $(printf '%s\n' "$added"    | grep -c .)"
  echo "# files removed:  $(printf '%s\n' "$removed"  | grep -c .)"
  echo "# files MODIFIED: $(printf '%s\n' "$modified" | grep -c .)"
  echo "#"
  echo "## added"; printf '%s\n' "$added"
  echo "## removed"; printf '%s\n' "$removed"
  echo "## modified"; printf '%s\n' "$modified"
  rm -f "$b" "$a"
} > "$DIFF"
echo
echo "layer installed. added $(grep -c '^/' "$DIFF" || echo 0) files"
echo "diff: $DIFF"
