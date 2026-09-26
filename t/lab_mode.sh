# t/lab_mode.sh -- one driver, two grading machines (2026-09-26).
#
# Sourced by t/grade_lab.sh and t/r12_data_queue.sh once LAB is set. T_LAB=user@host
# names a workstation reached over ssh and rsync, as before; T_LAB=local names this
# machine, where the same steps run in a login shell and every transfer is a local
# copy, or nothing at all when both ends are the same tree. GNU parallel does the
# same with its login names: "There are 3 names with special meaning: ':' Means 'no
# ssh' and will therefore run on the local computer" (gnu.org/software/parallel/
# parallel.html, --sshlogin). rsync copies locally whenever neither path names a
# host: "If neither the source or destination path specify a remote host, the copy
# occurs locally" (download.samba.org/pub/rsync/rsync.1, GENERAL), with the same
# trailing-slash rules, so a transfer written for the lab needs only its host
# dropped. With a user@host every function below is exactly the ssh or rsync it
# replaced; the lab path is unchanged.
#
# The seven kernels have to be installed here for local grading (t/RUN-ON-LINUX.md);
# run_par refuses to write a table otherwise.

lab_is_local() { [ "${LAB:-}" = local ]; }

# ~/$REPO on the workstation is this checkout here, a worktree included, so a command
# or a path written for the lab is rewritten once, in one place: `~/tup/...`, `~/tup`
# at the end of a word, and a leading `local:` host. `~/tup-grade` is left alone.
ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
localize() {
  printf '%s' "$1" | sed -e "s|^local:||" -e "s#~/${REPO:-tup}\(/\|$\| \|'\|\"\)#$ROOT\1#g"
}

# remote CMD: run CMD on the grading machine. stdin passes through either way, so
# `_py name | remote "python3 -"` works on both.
remote() {
  if lab_is_local; then bash -lc "$(localize "$*")"; else $SSH "$LAB" "$@"; fi
}

# xfer RSYNC-OPTIONS... SRC... DST: rsync between here and the grading machine, or a
# local rsync with the host dropped, or nothing when every SRC already sits in DST
# (the queue stores a chunk's table "on the lab" from the directory it is in here).
xfer() {
  if ! lab_is_local; then rsync "$@"; return; fi
  local args=() a n dst src same=1
  for a in "$@"; do args+=("$(localize "$a")"); done
  n=${#args[@]}; dst=$(readlink -f "${args[n-1]%/}")
  for src in "${args[@]:0:n-1}"; do
    case "$src" in -*) continue ;; esac
    if [ "$(readlink -f "${src%/}")" != "$dst" ] && [ "$(readlink -f "$(dirname "$src")")" != "$dst" ]; then same=0; fi
  done
  [ "$same" = 1 ] && return 0
  rsync "${args[@]}"
}
fetch() { xfer "$@"; }   # grading machine -> here
store() { xfer "$@"; }   # here -> grading machine

reachable() { if lab_is_local; then true; else $SSH "$LAB" true 2>/dev/null; fi; }

# The RAM disk when it has room (the lab's is 252 GB; this desktop's /dev/shm is a few
# GB), else a directory on disk; T_LAB_WORK still overrides.
default_work_dir() {
  local free
  if lab_is_local; then
    free=$(df -Pk /dev/shm 2>/dev/null | awk 'NR==2 {print $4}')
    if [ -z "$free" ] || [ "$free" -lt 4194304 ]; then echo "$HOME/tup-grade"; return; fi
  fi
  echo /dev/shm/tup-grade
}
# Cells at once: 32 on the lab's 120 threads; 8 on a 24-core desktop, where a SPARK
# cell is several gnatprove processes. Answer sets at once: one here, four there.
default_jobs() { if lab_is_local; then echo 8; else echo 32; fi; }
default_sets() { if lab_is_local; then echo 1; else echo 4; fi; }
