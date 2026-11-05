#!/bin/bash
# Native profile deviation: preserve book commands and lock root. Owner-key
# enrollment belongs to installation; this core has no shared root password.
set -euo pipefail
[ -s "$TUP_PAGE" ] || { echo 'shadow override: missing book page' >&2; exit 1; }
[ "$(grep -c '^passwd root$' "$TUP_PAGE")" = 1 ] || {
  echo 'shadow override: expected exactly one root password prompt' >&2; exit 1;
}
sed 's|^passwd root$|passwd -l root|' "$TUP_PAGE" | bash -e
