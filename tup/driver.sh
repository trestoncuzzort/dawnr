#!/bin/bash
# driver.sh: run one extracted chapter of the tup build, with receipts.
#
#   bash driver.sh <chapter-dir>
#   TUP_VALIDATE_ONLY=1 bash driver.sh <chapter-dir>
#
# Reads <chapter-dir>/ORDER and executes each page script in order. State
# lives in $LFS/sources/log/driver.v2 as atomically committed snapshots.
# driver.state (one line per completed script) and receipts.jsonl retain their
# old reader formats as checked compatibility copies. Identical inputs resume;
# changed, legacy, interrupted or failed state REFUSES automatic replay. A page
# can already have modified the target before failing. Preserve its evidence
# and rebuild a fresh target or restore a reviewed target+ledger checkpoint.
# Every committed page adds one JSON line to log/receipts.jsonl: page,
# package, seconds, exit status, the sha256 of its own log, and, because an
# override REPLACES the page body, which body actually ran (`override`), the
# sha256 of that body (`script_sha256`) and of the tarball it was handed
# (`tarball_sha256`), both measured BEFORE the page runs, so they name the
# inputs and not whatever the page left in their place. That ledger, not this
# script's stdout, is the record.
#
# TUP_BUILD_INPUTS must name the native caller's immutable input manifest and
# TUP_PROFILE its selected profile. The caller must validate its versioned
# manifest schema and recompute ALL transitive source, patch, configuration,
# profile and toolchain identities before EVERY invocation, including resume.
# This driver hashes its exact bytes (no Python is available in early chroot)
# and additionally checks chapter/ORDER, original pages, overrides including
# shared helpers, selected archives and material build environment. Manifest
# authentication and completeness remain the caller's responsibility. A hash
# of an unchecked, stale manifest does not make it valid. Driver and buildlib
# must be copied together and kept byte-identical across the chroot crossing.
# Requires Bash >= 4.4 and GNU coreutils with named-file sync and sync -f
# (>= 8.24), provided by the book's temporary toolchain inside chroot.
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
set -euo pipefail
shopt -s inherit_errexit
[ "$#" -eq 1 ] || { echo "usage: bash driver.sh <chapter-dir>" >&2; exit 2; }
LFS=${LFS-/mnt/lfs}
LOG=$LFS/sources/log
STATE=$LOG/driver.state
RECEIPTS=$LOG/receipts.jsonl
TUP_TESTS=${TUP_TESTS-"glibc gcc binutils"}
TUP_OVERRIDES=${TUP_OVERRIDES:-/home/lfs/overrides}
case "${TUP_ARCH:-$(uname -m)}" in
  aarch64|arm64) TUP_ARCH=arm64 ;;
  x86_64|amd64)  TUP_ARCH=x86_64 ;;
  *)             TUP_ARCH=${TUP_ARCH:-$(uname -m)} ;;
esac
export LFS TUP_ARCH TUP_TESTS TUP_OVERRIDES
CHDIR=$(cd -- "$1" && pwd -P)
CH=$(basename "$CHDIR")
DRIVER_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
source "$DRIVER_DIR/buildlib/driver-state.sh"
[[ $CH =~ ^[a-zA-Z0-9][a-zA-Z0-9_.+-]*$ ]] || tup_die 'invalid chapter name'
case "${TUP_VALIDATE_ONLY:-0}" in 0|1) ;; *) tup_die 'TUP_VALIDATE_ONLY must be 0 or 1';; esac
[ -n "${TUP_BUILD_INPUTS:-}" ] && [ -s "$TUP_BUILD_INPUTS" ] || tup_die 'TUP_BUILD_INPUTS must name a validated, nonempty immutable manifest'
[ -n "${TUP_PROFILE:-}" ] || tup_die 'TUP_PROFILE must name the selected profile'
TUP_OVERRIDES=$(cd -- "$TUP_OVERRIDES" && pwd -P)
BUILD_INPUTS_HASH=$(tup_sha256 "$TUP_BUILD_INPUTS")
DRIVER_HASH=$(tup_sha256 "$DRIVER_DIR/driver.sh")
HELPER_HASH=$(tup_sha256 "$DRIVER_DIR/buildlib/driver-state.sh")
BUILD_ID=$(printf 'tup-driver-build-v2\0native-caller-revalidates-schema-and-inputs-v1\0%s\0%s\0%s\0' "$BUILD_INPUTS_HASH" "$DRIVER_HASH" "$HELPER_HASH" | tup_digest_stream)
if [ "${TUP_VALIDATE_ONLY:-0}" != 1 ]; then mkdir -p -- "$LOG"; fi
[ -d "$LOG" ] && [ ! -L "$LOG" ] || tup_die 'log must be a real directory'
declare -A DONE=() PLANNED_INPUTS=() ORDER_SEEN=() LOG_OWNER=()
declare -a PAGES=()

tup_tests_enabled() {
  for t in $TUP_TESTS; do case "$1" in *"$t"*) return 0;; esac; done
  return 1
}
# Every string this script puts in the ledger is a filename or a path, and a
# filename may hold a double quote, a backslash or a control character. Pasting
# one between \" and \" by hand does not produce JSON: a single override path
# with a quote in it made json.loads refuse the WHOLE line, so a reader lost
# that page's digests, seconds and exit status too, not just the field it could
# not read. These are RFC 8259's escapes -- backslash and quote first, then the
# C0 range, which has no literal form in a JSON string at all.
tup_json_str() {
  local s=$1 out='"' i ch code
  for ((i = 0; i < ${#s}; i++)); do
    ch=${s:i:1}
    case "$ch" in
      '"')   out=$out'\"' ;;
      '\')   out=$out'\\' ;;
      $'\n') out=$out'\n' ;;
      $'\r') out=$out'\r' ;;
      $'\t') out=$out'\t' ;;
      $'\b') out=$out'\b' ;;
      $'\f') out=$out'\f' ;;
      *)
        printf -v code '%d' "'$ch"
        if [ "$code" -lt 32 ]; then out=$out$(printf '\\u%04x' "$code")
        else out=$out$ch; fi ;;
    esac
  done
  printf '%s"' "$out"
}
tup_receipt_skip_tests() {
  printf '%s\n' "{\"ts\":$(tup_json_str "$(date -u +%FT%TZ)"),\"page\":$(tup_json_str "$1"),\"tests_skipped\":true}" >> "$RECEIPTS" || return 1
  echo "    [tests skipped by policy: $1]"
}
export -f tup_tests_enabled tup_receipt_skip_tests tup_json_str
export RECEIPTS

tup_resolve_page() {
  local script=$1 cand line fallback='' arch_pkg=''
  id="$CH/$script"
  page="${script%.sh}"
  src="$CHDIR/$script"
  tup_regular "$src"
  book_hash=$(tup_sha256 "$src") || exit 1
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
  [ -z "$ov" ] || src=$ov
  # A page may name one tarball per arch (# TUP_TARBALL_x86_64=..., the
  # prebuilt Node and Lean in the layers do); the arch-specific line wins,
  # the plain one is the fallback.
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      "# TUP_TARBALL_$TUP_ARCH="*) [ -n "$arch_pkg" ] || arch_pkg=${line#*=} ;;
      '# TUP_TARBALL='*) [ -n "$fallback" ] || fallback=${line#*=} ;;
    esac
  done < "$CHDIR/$script"
  pkg=${arch_pkg:-$fallback}
  shash=$(tup_sha256 "$src") || exit 1
  thash=''; tb_json=null
  if [ -n "$pkg" ]; then
    [[ $pkg =~ ^[a-zA-Z0-9][a-zA-Z0-9._+-]*$ ]] || tup_die "unsafe tarball name: $pkg"
    tarball=$LFS/sources/$pkg
    [ -s "$tarball" ] || tup_die "$id: tarball absent: $pkg"
    thash=$(tup_sha256 "$tarball") || exit 1
    tb_json=$(tup_json_str "$thash")
  fi
  plog="$LOG/$CH-$page.log"
  [ -z "${LOG_OWNER[$plog]+x}" ] || [ "${LOG_OWNER[$plog]}" = "$id" ] || tup_die "page log name collides with ${LOG_OWNER[$plog]}"
  input_hash=$(printf 'tup-driver-page-v2\0%s\0%s\0%s\0%s\0%s\0%s\0%s\0' \
    "$CONTEXT_HASH" "$id" "$book_hash" "$shash" "${ov#"$TUP_OVERRIDES"}" "$pkg" "$thash" | tup_digest_stream) || exit 1
}

# Parse and fingerprint the WHOLE requested chapter before executing anything,
# so a later stale completed page cannot be discovered only after new writes.
tup_regular "$CHDIR/ORDER"
[ -s "$CHDIR/ORDER" ] || tup_die "$CH: ORDER is empty"
while IFS= read -r script || [ -n "$script" ]; do
  [[ $script =~ ^[a-zA-Z0-9][a-zA-Z0-9_.+-]*\.sh$ ]] || tup_die "invalid ORDER page: $script"
  [ -z "${ORDER_SEEN[$script]+x}" ] || tup_die "duplicate ORDER page: $script"
  ORDER_SEEN[$script]=1
  PAGES+=("$script")
done < "$CHDIR/ORDER"
CONTEXT_HASH=$(tup_context_digest)
for script in "${PAGES[@]}"; do
  tup_resolve_page "$script"
  PLANNED_INPUTS[$script]=$input_hash
done
tup_ledger_init
if [ "${TUP_VALIDATE_ONLY:-0}" != 1 ]; then
  # Discover unsupported syncfs/permissions before any package can mutate the
  # target, rather than only after the first expensive build has completed.
  sync -f -- "${LFS:-/}" || tup_die 'target filesystem flush is unavailable'
fi
missing=0
for script in "${PAGES[@]}"; do
  id="$CH/$script"
  if [ -n "${DONE[$id]+x}" ]; then
    [ "$missing" -eq 0 ] || tup_die 'completed pages are not a prefix of ORDER'
    [ "${DONE[$id]}" = "${PLANNED_INPUTS[$script]}" ] || tup_die "$id: inputs changed; refusing stale state and unsafe incremental replay"
  else
    missing=1
  fi
done
if [ "${TUP_VALIDATE_ONLY:-0}" = 1 ] && [ "$missing" -ne 0 ]; then
  tup_die "$CH is incomplete; validation never executes missing pages"
fi

for script in "${PAGES[@]}"; do
  [ "$(tup_context_digest)" = "$CONTEXT_HASH" ] || tup_die 'chapter inputs changed during this invocation'
  tup_resolve_page "$script"
  [ "$input_hash" = "${PLANNED_INPUTS[$script]}" ] || tup_die "$id: input changed after preflight"
  [ -z "${DONE[$id]+x}" ] || continue
  [ ! -e "$plog" ] && [ ! -L "$plog" ] || tup_die "$id: unbound page log already exists; refusing to overwrite evidence"
  if [ -n "$ov" ]; then echo ">>> $id (OVERRIDE ${ov##*/overrides/})"
  else echo ">>> $id"; fi
  tup_begin_page
  # THE PAGE LOG IS CREATED HERE, AND EVERY WRITER AFTER THIS ONE APPENDS. It
  # used to be truncated by the redirect on the page's own subshell, a long way
  # further down, and everything written to it before that point went with it.
  # Extraction runs first and sends tar's stderr here (`2>>"$plog"`), so a
  # tarball that WARNS and still exits 0, an implausible timestamp or an unknown
  # pax header, had its warnings appended and then wiped, and the log_sha256
  # in the receipt described the page's own output alone. Measured 2026-09-02:
  # `tar: pkg-1.0/configure: time stamp ... is 357619170 s in the future`, one
  # line, gone from the record, on the one path where nothing failed loudly and
  # a reader would therefore never go looking. Each intent has exactly one log;
  # failed intents are never retried automatically over the same evidence.
  ( set -C; : > "$plog" ) || {
    echo "!!! $id: cannot open the page log $plog for writing"
    echo "    refusing: the receipt names that log's digest."
    exit 1; }
  # THE INPUT DIGESTS ARE ALREADY HELD, BEFORE ANYTHING RUNS. They used
  # to be taken beside the log hash, after the page had returned, so a page
  # that modified its own inputs while it built had the receipt record the bytes
  # it LEFT BEHIND under the name of the bytes that RAN. Neither input is out of
  # the page's reach: the build directory's parent is $LFS/sources, so the
  # tarball is ../$pkg from the page's own cwd, and a page can rewrite its own
  # file. Measured 2026-09-02: a page appending one byte to its archive and one
  # line to its body produced a receipt naming both POST-run digests, "ok in
  # 0s", exit 0: the ledger absorbed the change instead of showing it. Held
  # here and written unchanged below, the receipt states what went IN, and a
  # mismatch against what is on disk afterwards is exactly what it now exposes.
  t0=$SECONDS

  if [ -n "$pkg" ]; then
    # Before extraction, for the reason given above: this is the archive that is
    # about to be unpacked and handed to the page, not whatever stands at that
    # path once the page has had its turn with it.
    # ISOLATED EXTRACTION, because the archive names the directory an `rm -rf`
    # is about to be aimed at. Nothing is aimed at a name the archive chose:
    # extract into a fresh directory of OUR naming, look at what actually came
    # out, and move it into place only once it is one real directory whose name
    # is not reserved. Trusting the tarball's own listing failed open three
    # ways, each of them measured:
    #   * a truncated or non-tarball file lists nothing, $top came back empty,
    #     and $dir became "$LFS/sources/", every tarball plus log/receipts.jsonl
    #   * a perfectly good archive made with `tar cf x ./dir` lists "./dir/",
    #     `cut -d/ -f1` gives ".", and $dir became "$LFS/sources/.", the same
    #     deletion, with the page then reporting "ok"
    #   * an archive whose first entry is `log/` gave $dir = "$LFS/sources/log",
    #     so the build deleted driver.state and receipts.jsonl, its own ledger,
    #     and then printed "ok in 0s" and "complete" (measured 2026-09-01)
    # After this, the only paths rm -rf can ever see are the staging directory
    # this script made and the package directory it checked.
    stage=$(mktemp -d "$LFS/sources/.tup-extract-XXXXXX") || {
      echo "!!! $id: cannot make an extraction directory under $LFS/sources" | tee -a "$plog"; exit 1; }
    if ! tar xf "$tarball" -C "$stage" 2>>"$plog"; then
      rm -rf "$stage"
      echo "!!! $id: tar xf $tarball failed, refusing to continue" | tee -a "$plog"; exit 1
    fi
    top=""; n=0
    for e in "$stage"/* "$stage"/.[!.]* "$stage"/..?*; do
      { [ -e "$e" ] || [ -L "$e" ]; } || continue
      n=$((n + 1)); top="${e##*/}"
    done
    # One top-level directory is the book's own per-package shape, and it is
    # what makes the rm -rf below a bounded statement. Each refusal below says
    # what is true where it fires, because that is all it knows.
    if [ "$n" -ne 1 ]; then
      echo "!!! $id: $tarball extracts to $n top-level entries, not one directory" | tee -a "$plog"
      [ "$n" -gt 0 ] && echo "    (the last one seen is \"$top\")" | tee -a "$plog"
      echo "    refusing: the page contract is to cd into the package tree," | tee -a "$plog"
      echo "    and the next step after that is rm -rf on it." | tee -a "$plog"
      rm -rf "$stage"; exit 1
    fi
    # A symlink is not a directory however -d answers it: cd through one would
    # run the page somewhere else entirely, and the rm -rf afterwards would
    # remove the link and leave the tree.
    if [ ! -d "$stage/$top" ] || [ -L "$stage/$top" ]; then
      echo "!!! $id: $tarball's one top-level entry \"$top\" is not a directory" | tee -a "$plog"
      echo "    refusing: the page contract is to cd into the package tree," | tee -a "$plog"
      echo "    and the next step after that is rm -rf on it." | tee -a "$plog"
      rm -rf "$stage"; exit 1
    fi
    case "$top" in
      log|.|..|*/*|.tup-extract-*)
        echo "!!! $id: $tarball extracts to \"$top\", a name reserved in \$LFS/sources" | tee -a "$plog"
        echo "    (log/ is this build's ledger: driver.state and receipts.jsonl;" | tee -a "$plog"
        echo "    .tup-extract-* is this script's own staging.) The next step" | tee -a "$plog"
        echo "    after moving it into place is rm -rf, so: refused." | tee -a "$plog"
        rm -rf "$stage"; exit 1;;
    esac
    dir="$LFS/sources/$top"
    if { [ -e "$dir" ] || [ -L "$dir" ]; } && { [ ! -d "$dir" ] || [ -L "$dir" ]; }; then
      echo "!!! $id: $dir already exists and is not a package directory" | tee -a "$plog"
      echo "    refusing to rm -rf it." | tee -a "$plog"
      rm -rf "$stage"; exit 1
    fi
    rm -rf "$dir"                 # a previous run's tree of that name, and only that
    if ! mv "$stage/$top" "$dir" 2>>"$plog"; then
      echo "!!! $id: cannot move the extracted tree to $dir" | tee -a "$plog"
      rm -rf "$stage"; exit 1
    fi
    rmdir "$stage" 2>/dev/null
    if ( cd "$dir" && bash -e -o pipefail "$src" ) >> "$plog" 2>&1 < /dev/null; then
      rc=0
      rm -rf -- "$dir" || tup_die "$id: cannot clean completed package tree"
    else rc=$?; fi
  else
    if ( cd "$LFS/sources" && bash -e -o pipefail "$src" ) >> "$plog" 2>&1 < /dev/null; then
      rc=0
    else rc=$?; fi
  fi

  page_rc=$rc
  # Catch inputs changed by the page (or another writer) without replacing the
  # before-run hashes in its receipt. No false success or automatic replay.
  if after_hash=$(CONTEXT_HASH=$(tup_context_digest) && tup_resolve_page "$script" && printf '%s' "$input_hash"); then
    if [ "$after_hash" != "$input_hash" ]; then
      printf '%s\n' '!!! inputs changed during the page; refusing completion' >> "$plog"
      rc=125
    fi
  else
    printf '%s\n' '!!! cannot validate inputs after the page; refusing completion' >> "$plog"
    rc=125
  fi
  secs=$((SECONDS - t0))
  # A digest this script could not compute is not a digest the receipt may
  # claim. `sha256sum X | cut -d' ' -f1` reports the status of `cut`, which is
  # 0 whatever sha256sum did, so an unreadable log wrote "log_sha256":"" into
  # the ledger while the page printed "ok in 0s" and the run exited 0; the
  # tarball hash had its own `2>/dev/null` and went to null the same way. Every
  # digest the receipt names is checked here, and a page whose own evidence
  # cannot be hashed fails as loudly as a page that will not build.
  if ! lhash=$(tup_sha256 "$plog"); then
    echo "!!! $id: cannot sha256 the page log $plog (the page itself exited $rc)"
    echo "    refusing: the receipt would name a digest it does not have."
    exit 1
  fi
  # LFS installs onto one target filesystem. Flush those writes before making
  # its page completion durable; the log may be on a separate sources mount.
  # Builders using additional target filesystems must flush them themselves.
  sync -f -- "${LFS:-/}" || tup_die "$id: target filesystem flush failed"
  tup_flush "$plog" "$LOG"
  # A page name is not a body. An executable override replaces the book's text
  # entirely, and the old receipt recorded only the page, so the ledger could
  # not say whether the book built this system or we did, let alone from which
  # bytes. $src is whichever body actually ran; the tarball is its other input.
  # Both were hashed above, before the page could touch either. These keys are
  # ADDED, never renamed: a reader of the old five still parses.
  ov_json=null;  [ -n "$ov" ]  && ov_json=$(tup_json_str "$ov")
  receipt="{\"ts\":$(tup_json_str "$(date -u +%FT%TZ)"),\"page\":$(tup_json_str "$id"),\"package\":$(tup_json_str "${pkg:-null}"),\"seconds\":$secs,\"exit\":$rc,\"page_exit\":$page_rc,\"log_sha256\":$(tup_json_str "$lhash"),\"override\":$ov_json,\"script_sha256\":$(tup_json_str "$shash"),\"tarball_sha256\":$tb_json,\"receipt_version\":2,\"book_sha256\":$(tup_json_str "$book_hash"),\"build_inputs_sha256\":$(tup_json_str "$BUILD_INPUTS_HASH"),\"context_sha256\":$(tup_json_str "$CONTEXT_HASH"),\"input_sha256\":$(tup_json_str "$input_hash") }"
  tup_finish_page "$receipt"
  if [ $rc -ne 0 ]; then
    echo "!!! $id FAILED (exit $rc, ${secs}s), last lines of $plog:"
    tail -15 "$plog"
    echo '    target may be partially modified; refusing automatic retry (intent retained).'
    exit 1
  fi
  echo "    ok in ${secs}s"
done
echo "=== $CH complete"
