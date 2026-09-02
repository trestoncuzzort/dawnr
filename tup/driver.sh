#!/bin/bash
# driver.sh — run one extracted chapter of the tup build, with receipts.
#
#   bash driver.sh <chapter-dir> [start-after]
#
# Reads <chapter-dir>/ORDER and executes each page script in order. State
# lives in $LFS/sources/log/driver.state (one line per completed script), so
# a rerun resumes after the last success — a failed page is retried, never
# skipped. Every page appends one JSON line to log/receipts.jsonl: page,
# package, seconds, exit status, and the sha256 of its own log. That ledger,
# not this script's stdout, is the record.
#
# Page contract (written by extract_book.py):
#   # TUP_TARBALL=name-version.tar.xz -> tarball extracted fresh, cwd inside
#                                 it, tree deleted afterward (the book's
#                                 standing per-package instruction).
#   # TUP_TARBALL_<arch>=...    -> the same, chosen by $TUP_ARCH (layers with
#                                 prebuilt per-arch binaries).
#   # TUP_ACTION_PAGE          -> run with cwd $LFS/sources, no wrapping.
#
# Overrides replace a page body entirely and are matched BY PAGE NAME, never
# by page number. The x86 12.4 book and the arm64 book number chapter 8
# differently (85 pages against 87), so `29-shadow.sh` names one build on
# arm64 and a different one on x86; an override keyed to that number would
# unhook silently on the other book. Lookup order, first executable wins:
#   $TUP_OVERRIDES/$TUP_ARCH/<ch>/<page>.sh    arch-bound and chapter-scoped
#   $TUP_OVERRIDES/$TUP_ARCH/<page>.sh
#   $TUP_OVERRIDES/<ch>/<page>.sh              shared, chapter-scoped
#   $TUP_OVERRIDES/<page>.sh
# where <page> is tried as written (NN-name) and then with the number
# stripped (name). The page an override replaces is handed to it as
# $TUP_PAGE (its path) and $TUP_PAGE_ID (ch/NN-name), so no override needs
# to know a page number either.
#
# Test policy (ruling 2026-08-31, "mathematically useful, zero bullshit"):
# TUP_TESTS names the packages whose suites run; every other suite hit is
# receipted as tests_skipped, never silently dropped.
set -u
LFS=${LFS:-/mnt/lfs}
LOG=$LFS/sources/log
STATE=$LOG/driver.state
RECEIPTS=$LOG/receipts.jsonl
TUP_TESTS=${TUP_TESTS:-"glibc gcc binutils"}
TUP_OVERRIDES=${TUP_OVERRIDES:-/home/lfs/overrides}
case "${TUP_ARCH:-$(uname -m)}" in
  aarch64|arm64) TUP_ARCH=arm64 ;;
  x86_64|amd64)  TUP_ARCH=x86_64 ;;
  *)             TUP_ARCH=${TUP_ARCH:-$(uname -m)} ;;
esac
export TUP_ARCH
CHDIR=$1
CH=$(basename "$CHDIR")
mkdir -p "$LOG"
touch "$STATE"

tup_tests_enabled() {
  for t in $TUP_TESTS; do case "$1" in *"$t"*) return 0;; esac; done
  return 1
}
tup_receipt_skip_tests() {
  echo "{\"ts\":\"$(date -u +%FT%TZ)\",\"page\":\"$1\",\"tests_skipped\":true}" >> "$RECEIPTS"
  echo "    [tests skipped by policy: $1]"
}
export -f tup_tests_enabled tup_receipt_skip_tests
export RECEIPTS

# ORDER is read on fd 3, and every page runs with stdin from /dev/null. A book
# page that reads stdin (createfiles does) would otherwise consume the ORDER
# list off fd 0 and then run the remaining filenames as commands — measured
# 2026-08-31: chapter 7 failed with "07-gettext.sh: command not found" x6.
[ -r "$CHDIR/ORDER" ] || { echo "!!! $CH: no ORDER file at $CHDIR/ORDER — refusing to call an empty run complete"; exit 1; }
[ -s "$CHDIR/ORDER" ] || { echo "!!! $CH: ORDER is empty — refusing to call an empty run complete"; exit 1; }
while read -r script <&3; do
  id="$CH/$script"
  grep -qxF "$id" "$STATE" && continue
  page="${script%.sh}"
  src="$CHDIR/$script"
  # Chapter-qualified first: glibc names a page in BOTH chapter 5 and
  # chapter 8, and they are different builds. A flat name would fire the
  # wrong override on the wrong page, silently. Arch-bound first: the kernel
  # and bootloader pages differ per book.
  stem="${page#[0-9][0-9]-}"
  ov=""
  for cand in "$TUP_OVERRIDES/$TUP_ARCH/${CH%%-*}/$page.sh" "$TUP_OVERRIDES/$TUP_ARCH/${CH%%-*}/$stem.sh" \
              "$TUP_OVERRIDES/$TUP_ARCH/$page.sh"           "$TUP_OVERRIDES/$TUP_ARCH/$stem.sh" \
              "$TUP_OVERRIDES/${CH%%-*}/$page.sh"           "$TUP_OVERRIDES/${CH%%-*}/$stem.sh" \
              "$TUP_OVERRIDES/$page.sh"                     "$TUP_OVERRIDES/$stem.sh"; do
    [ -x "$cand" ] && { ov="$cand"; break; }
  done
  export TUP_PAGE="$CHDIR/$script" TUP_PAGE_ID="$CH/$page"
  if [ -n "$ov" ]; then src="$ov"; echo ">>> $id (OVERRIDE ${ov##*/overrides/})"
  else echo ">>> $id"; fi
  # A page may name one tarball per arch (# TUP_TARBALL_x86_64=..., the
  # prebuilt Node and Lean in the layers do); the arch-specific line wins,
  # the plain one is the fallback.
  pkg=$(sed -n "s/^# TUP_TARBALL_$TUP_ARCH=//p" "$CHDIR/$script" | head -1)
  [ -n "$pkg" ] || pkg=$(sed -n 's/^# TUP_TARBALL=//p' "$CHDIR/$script" | head -1)
  plog="$LOG/$CH-$page.log"
  t0=$SECONDS

  if [ -n "$pkg" ]; then
    tarball="$LFS/sources/$pkg"
    if [ ! -s "$tarball" ]; then
      echo "!!! $id: tarball absent: $pkg" | tee -a "$plog"; exit 1
    fi
    # the top-level dir comes from the tarball's own listing — filename
    # surgery guesses wrong on tcl8.6.17-src and friends
    top=$(tar tf "$tarball" 2>/dev/null | head -1 | cut -d/ -f1)
    dir="$LFS/sources/$top"
    ( set -e; cd "$LFS/sources"
      rm -rf "$dir"; tar xf "$tarball"; cd "$dir"
      bash -e "$src"
    ) > "$plog" 2>&1 < /dev/null
    rc=$?
    [ $rc -eq 0 ] && rm -rf "$dir"
  else
    ( set -e; cd "$LFS/sources"; bash -e "$src" ) > "$plog" 2>&1 < /dev/null
    rc=$?
  fi

  secs=$((SECONDS - t0))
  lhash=$(sha256sum "$plog" | cut -d' ' -f1)
  echo "{\"ts\":\"$(date -u +%FT%TZ)\",\"page\":\"$id\",\"package\":\"${pkg:-null}\",\"seconds\":$secs,\"exit\":$rc,\"log_sha256\":\"$lhash\"}" >> "$RECEIPTS"
  if [ $rc -ne 0 ]; then
    echo "!!! $id FAILED (exit $rc, ${secs}s) — last lines of $plog:"
    tail -15 "$plog"
    exit 1
  fi
  echo "$id" >> "$STATE"
  echo "    ok in ${secs}s"
done 3< "$CHDIR/ORDER"
echo "=== $CH complete"
