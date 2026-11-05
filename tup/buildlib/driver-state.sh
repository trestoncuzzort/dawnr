# Sourced only by driver.sh. Bash + temporary LFS coreutils/findutils suffice;
# Python and util-linux flock do not exist at the start of chapter 7.
#
# Resume is deliberately refusal-based, not an incremental package uninstall.
# A changed input, failed/interrupted attempt, old unbound state, or damaged
# ledger requires a fresh target or a reviewed restoration of BOTH target and
# evidence. Deleting state/intent files is not recovery of an installed root.
#
# driver.v2/<digest>/ is an immutable snapshot of receipts, completion state,
# input identities and build identity. Its checksums hash names the snapshot.
# One same-filesystem rename of driver.v2/current commits the whole result.
# driver.state and receipts.jsonl are checked compatibility copies, published
# AFTER the canonical commit. A durable pending directory precedes execution
# and survives any failure, including publication of either copy. A crash can
# therefore require recovery, but cannot authorize replay or partial success.
# This relies on local-filesystem rename/fsync guarantees and cooperative
# writers; neither a malicious root nor broken storage is in that contract.
# See https://www.sqlite.org/atomiccommit.html and GNU coreutils sync/mv docs.

tup_die() { printf '!!! driver: %s\n' "$*" >&2; exit 1; }

tup_regular() {
  [ -f "$1" ] && [ ! -L "$1" ] && [ -r "$1" ] || tup_die "not a readable regular file: $1"
}

tup_digest_stream() {
  local result
  result=$(sha256sum) || tup_die 'sha256sum failed'
  result=${result%% *}
  [[ $result =~ ^[0-9a-f]{64}$ ]] || tup_die 'invalid sha256sum output'
  printf '%s' "$result"
}

tup_sha256() {
  tup_regular "$1"
  tup_digest_stream < "$1"
}

tup_flush() {
  # Named-file sync uses fsync, including directory entries; a bare sync does
  # not provide the same per-file error reporting. Never ignore this status.
  sync -- "$@" || tup_die "cannot durably flush $*; refusing completion verdict"
}

tup_tree_digest() {
  # Relative names and executable bits survive the chroot crossing. Include
  # shared override helpers as well as the selected page; reject symlinks and
  # special files rather than hashing a path while reading untracked bytes.
  local tree=$1
  [ -d "$tree" ] && [ ! -L "$tree" ] || tup_die "input tree missing or symlinked: $tree"
  (
    cd -- "$tree" || exit 1
    find . -mindepth 1 -print0 | LC_ALL=C sort -z | while IFS= read -r -d '' entry; do
      [ ! -L "$entry" ] || tup_die "input symlink is not tracked: $tree/$entry"
      if [ -d "$entry" ]; then
        printf 'directory\0%s\0' "$entry"
      else
        tup_regular "$entry"
        executable=0; [ ! -x "$entry" ] || executable=1
        digest=$(tup_sha256 "$entry") || exit 1
        printf 'file\0%s\0%s\0%s\0' "$entry" "$executable" "$digest"
      fi
    done
  ) | tup_digest_stream
}

tup_context_digest() {
  local chapter_hash overrides_hash manifest_hash name
  chapter_hash=$(tup_tree_digest "$CHDIR") || exit 1
  overrides_hash=$(tup_tree_digest "$TUP_OVERRIDES") || exit 1
  manifest_hash=$(tup_sha256 "$TUP_BUILD_INPUTS") || exit 1
  {
    printf 'tup-driver-context-v2\0%s\0%s\0%s\0%s\0' "$BUILD_ID" "$manifest_hash" "$chapter_hash" "$overrides_hash"
    # Other build inputs must be declared in TUP_BUILD_INPUTS by the caller;
    # an opaque manifest is an identity, not authentication or a sandbox.
    for name in TUP_ARCH TUP_PROFILE TUP_TESTS MAKEFLAGS TESTSUITEFLAGS LFS_TGT CC CXX AR AS LD \
                CFLAGS CXXFLAGS CPPFLAGS LDFLAGS CONFIG_SITE LANG LC_ALL TZ SOURCE_DATE_EPOCH; do
      printf '%s\0%s\0%s\0' "$name" "${!name+x}" "${!name-}"
    done
  } | tup_digest_stream
}

tup_snapshot_manifest() {
  local dir=$1 name digest
  for name in build-id driver.state inputs.tsv receipts.jsonl; do
    digest=$(tup_sha256 "$dir/$name") || exit 1
    printf '%s  %s\n' "$digest" "$name"
  done
}

tup_projection_check() {
  local name path
  for name in driver.state receipts.jsonl; do
    path=$LOG/$name
    if [ -e "$path" ] || [ -L "$path" ]; then
      tup_regular "$path"
      [ -w "$path" ] || tup_die "ledger is not writable: $path"
    fi
    if [ -n "${GENERATION:-}" ]; then
      [ -f "$path" ] && cmp -s -- "$path" "$GENERATION/$name" || tup_die "ledger copy differs from committed snapshot: $path"
    elif [ -s "$path" ]; then
      tup_die "legacy receipts/state have no input identity; preserved, but cannot authorize resume. Use a fresh target or reviewed target+ledger restoration"
    fi
  done
}

tup_publish_copies() {
  local name path temp
  # Old readers see evidence before its completion line, but must still check
  # the canonical snapshot/pending state (or run TUP_VALIDATE_ONLY) for a gate.
  for name in receipts.jsonl driver.state; do
    path=$LOG/$name
    if [ -e "$path" ] || [ -L "$path" ]; then
      tup_regular "$path"
      [ -w "$path" ] || tup_die "ledger is not writable: $path"
    fi
    temp=$DRIVER_LOCK/$name
    cp -- "$GENERATION/$name" "$temp" || tup_die "cannot stage $name"
    tup_flush "$temp"
    mv -T -- "$temp" "$path" || tup_die "cannot publish $name; canonical result and pending intent retained"
    tup_flush "$LOG"
  done
}

tup_publish_snapshot() {
  local candidate=$1 digest next
  tup_snapshot_manifest "$candidate" > "$candidate/checksums" || tup_die 'cannot write snapshot checksums'
  digest=$(tup_sha256 "$candidate/checksums") || exit 1
  tup_flush "$candidate/build-id" "$candidate/driver.state" "$candidate/inputs.tsv" "$candidate/receipts.jsonl" "$candidate/checksums" "$candidate"
  [ ! -e "$DRIVER_STORE/$digest" ] || tup_die 'duplicate snapshot destination'
  mv -T -- "$candidate" "$DRIVER_STORE/$digest" || tup_die 'cannot publish immutable snapshot'
  tup_flush "$DRIVER_STORE"
  # Keep the pointer's temporary file beside its destination, even if someone
  # places the snapshot store on its own filesystem. mv must use rename here,
  # never its cross-device copy fallback. A failed staging file is evidence.
  next=$(mktemp "$DRIVER_STORE/.current.XXXXXX") || tup_die 'cannot stage commit pointer'
  printf '%s\n' "$digest" > "$next" || tup_die 'cannot stage commit pointer'
  tup_flush "$next"
  mv -T -- "$next" "$DRIVER_STORE/current" || tup_die 'cannot commit snapshot'
  tup_flush "$DRIVER_STORE"
  GENERATION=$DRIVER_STORE/$digest
  tup_publish_copies
}

tup_unlock() {
  # Never recursively remove a possibly unfamiliar lock directory. SIGKILL
  # leaves a stale lock; there is deliberately no PID-based automatic steal.
  local name
  for name in owner current driver.state receipts.jsonl expected-state expected-checksums; do
    rm -f -- "$DRIVER_LOCK/$name" 2>/dev/null || return
  done
  rmdir -- "$DRIVER_LOCK" 2>/dev/null || true
}

tup_ledger_init() {
  local candidate current canonical page identity log_hash extra line
  DRIVER_LOCK=$LOG/.driver.lock
  DRIVER_STORE=$LOG/driver.v2
  DRIVER_PENDING=$DRIVER_STORE/pending
  mkdir -- "$DRIVER_LOCK" 2>/dev/null || tup_die "build locked: $DRIVER_LOCK (active or interrupted owner; never automatically stolen)"
  trap tup_unlock EXIT
  trap 'exit 130' INT
  trap 'exit 143' TERM HUP
  printf '%s\n' "$$" > "$DRIVER_LOCK/owner" || tup_die 'cannot record lock owner'
  [ ! -L "$DRIVER_STORE" ] || tup_die 'snapshot store is a symlink'
  GENERATION=
  if [ -e "$DRIVER_STORE" ]; then
    [ -d "$DRIVER_STORE" ] || tup_die 'snapshot store is not a directory'
    [ ! -e "$DRIVER_PENDING" ] && [ ! -L "$DRIVER_PENDING" ] || tup_die "unfinished/failed page intent at $DRIVER_PENDING; target may be partially modified. Refusing replay; restore a reviewed target+ledger checkpoint or rebuild in a fresh target"
    tup_regular "$DRIVER_STORE/current"
    current=$(cat -- "$DRIVER_STORE/current") || tup_die 'cannot read commit pointer'
    [[ $current =~ ^[0-9a-f]{64}$ ]] || tup_die 'corrupt commit pointer'
    printf '%s\n' "$current" > "$DRIVER_LOCK/expected-checksums"
    cmp -s -- "$DRIVER_LOCK/expected-checksums" "$DRIVER_STORE/current" || tup_die 'noncanonical commit pointer'
    GENERATION=$DRIVER_STORE/$current
    [ -d "$GENERATION" ] && [ ! -L "$GENERATION" ] || tup_die 'committed snapshot is missing or symlinked'
    tup_regular "$GENERATION/checksums"
    canonical=$(tup_sha256 "$GENERATION/checksums") || exit 1
    [ "$canonical" = "$current" ] || tup_die 'snapshot checksum manifest is corrupt'
    tup_snapshot_manifest "$GENERATION" > "$DRIVER_LOCK/expected-checksums" || tup_die 'cannot verify snapshot'
    cmp -s -- "$DRIVER_LOCK/expected-checksums" "$GENERATION/checksums" || tup_die 'committed ledger is corrupt'
    printf '%s\n' "$BUILD_ID" > "$DRIVER_LOCK/expected-checksums"
    cmp -s -- "$DRIVER_LOCK/expected-checksums" "$GENERATION/build-id" || tup_die 'build inputs or driver changed; refusing stale state and unsafe incremental replay'
    tup_projection_check
  else
    tup_projection_check
    if [ "${TUP_VALIDATE_ONLY:-0}" = 1 ]; then tup_die 'no completed build to validate'; fi
    # An old driver could die after opening its log but before either append.
    # Empty ledgers cannot turn that potentially modified root into a fresh
    # build. Native preparation uses a fresh target; preserve orphan evidence.
    for line in "$LOG"/*.log; do
      [ ! -e "$line" ] && [ ! -L "$line" ] || tup_die "unbound pre-existing page log: $line; refusing legacy interrupted-target adoption"
    done
    mkdir -- "$DRIVER_STORE" || tup_die 'cannot create snapshot store'
    candidate=$(mktemp -d "$DRIVER_STORE/.next.XXXXXX") || tup_die 'cannot stage initial snapshot'
    printf '%s\n' "$BUILD_ID" > "$candidate/build-id" || tup_die 'cannot write build identity'
    : > "$candidate/driver.state" || tup_die 'cannot stage initial state'
    : > "$candidate/inputs.tsv" || tup_die 'cannot stage initial identities'
    : > "$candidate/receipts.jsonl" || tup_die 'cannot stage initial receipts'
    tup_publish_snapshot "$candidate"
  fi
  : > "$DRIVER_LOCK/expected-state" || tup_die 'cannot stage state validation'
  while IFS=$'\t' read -r page identity log_hash extra || [ -n "$page$identity$log_hash$extra" ]; do
    [[ $page =~ ^[a-zA-Z0-9][a-zA-Z0-9_.+-]*/[a-zA-Z0-9][a-zA-Z0-9_.+-]*\.sh$ ]] || tup_die 'invalid completed page identity'
    [[ $identity =~ ^[0-9a-f]{64}$ && $log_hash =~ ^[0-9a-f]{64}$ && -z $extra ]] || tup_die 'invalid completed input/log digest'
    [ -z "${DONE[$page]+x}" ] || tup_die "duplicate completed page: $page"
    DONE[$page]=$identity
    printf '%s\n' "$page" >> "$DRIVER_LOCK/expected-state" || tup_die 'cannot stage state validation'
    line=$LOG/${page%%/*}-${page#*/}; line=${line%.sh}.log
    [ -z "${LOG_OWNER[$line]+x}" ] || tup_die 'completed page log names collide'
    LOG_OWNER[$line]=$page
    canonical=$(tup_sha256 "$line") || exit 1
    [ "$canonical" = "$log_hash" ] || tup_die "completed page log changed: $line"
  done < "$GENERATION/inputs.tsv"
  cmp -s -- "$DRIVER_LOCK/expected-state" "$GENERATION/driver.state" || tup_die 'completion state and input identities disagree'
}

tup_begin_page() {
  mkdir -- "$DRIVER_PENDING" || tup_die 'cannot create page intent'
  printf 'tup-driver-intent-v2\n%s\n%s\n%s\n' "$id" "$input_hash" "${GENERATION##*/}" > "$DRIVER_PENDING/intent" || tup_die 'cannot write page intent'
  : > "$DRIVER_PENDING/events.jsonl" || tup_die 'cannot stage page events'
  tup_flush "$DRIVER_PENDING/intent" "$DRIVER_PENDING/events.jsonl" "$DRIVER_PENDING" "$DRIVER_STORE"
  # Export a private buffer, not the published ledger. Existing overrides that
  # append test judgments retain their JSONL contract without partial commits.
  export RECEIPTS=$DRIVER_PENDING/events.jsonl
}

tup_finish_page() {
  local receipt=$1 candidate
  tup_regular "$DRIVER_PENDING/events.jsonl"
  tup_projection_check
  candidate=$(mktemp -d "$DRIVER_STORE/.next.XXXXXX") || tup_die 'cannot stage page result'
  cp -- "$GENERATION/build-id" "$GENERATION/driver.state" "$GENERATION/inputs.tsv" "$GENERATION/receipts.jsonl" "$candidate/" || tup_die 'cannot copy committed evidence'
  cat -- "$DRIVER_PENDING/events.jsonl" >> "$candidate/receipts.jsonl" || tup_die 'cannot persist page test receipts'
  printf '%s\n' "$receipt" >> "$candidate/receipts.jsonl" || tup_die 'cannot persist page receipt'
  if [ "$rc" -eq 0 ]; then
    printf '%s\n' "$id" >> "$candidate/driver.state" || tup_die 'cannot persist completed state'
    printf '%s\t%s\t%s\n' "$id" "$input_hash" "$lhash" >> "$candidate/inputs.tsv" || tup_die 'cannot persist completed input identity'
  fi
  tup_publish_snapshot "$candidate"
  if [ "$rc" -eq 0 ]; then
    rm -- "$DRIVER_PENDING/intent" "$DRIVER_PENDING/events.jsonl" || tup_die 'cannot retire committed page intent'
    rmdir -- "$DRIVER_PENDING" || tup_die 'cannot retire committed page directory'
    tup_flush "$DRIVER_STORE"
    DONE[$id]=$input_hash
    LOG_OWNER[$plog]=$id
  fi
}
