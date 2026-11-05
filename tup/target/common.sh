# Sourced by every layer page inside the exported TUP target; see README.md.
# Bash and the completed core's coreutils only.
set -euo pipefail
[ "${TUP_LAYER_CHROOT:-}" = 1 ] && [ -s /tup-layer/BUILD-INPUTS.json ] || {
  echo 'layer page requires the validated exported-target runner' >&2; exit 1;
}
[ -n "${TUP_LAYER_PARENT_NETNS:-}" ] &&
  [ "$(readlink /proc/self/ns/net)" != "$TUP_LAYER_PARENT_NETNS" ] || {
  echo 'layer pages require a private network namespace' >&2; exit 1;
}
[[ ${TUP_JOBS:-} =~ ^[1-4]$ ]] || { echo 'layer jobs must be 1 through 4' >&2; exit 1; }
umask 022
