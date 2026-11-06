#!/usr/bin/env bash
# Build the SAT solver and the proof checker that t/native_case.py can use to certify a `complete` verdict.
#
#   bash t/build_certify_tools.sh DEST
#   python3 t/native_case.py CASE --variant fixed --cadical DEST/cadical --lrat-check DEST/lrat-check --out NEW_DIR
#
# Each is fetched at a pinned commit, and the commit is verified after the checkout. Both are MIT licensed and
# neither is copied into this repository. Needs git, make, a C and a C++ compiler. Run it as an unprivileged user.
set -euo pipefail

CADICAL_COMMIT=c60730422e758ef1cebe7aeddf2dda31c996bf04   # CaDiCaL 3.0.1
DRAT_TRIM_COMMIT=2e3b2dc0ecf938addbd779d42877b6ed69d9a985

dest="${1:?usage: build_certify_tools.sh DEST}"
mkdir -p "$dest"
dest="$(cd "$dest" && pwd)"

fetch() {  # fetch URL COMMIT DIRECTORY
  rm -rf "$3"
  git init -q "$3"
  git -C "$3" fetch -q --depth 1 "$1" "$2"
  git -C "$3" -c advice.detachedHead=false checkout -q FETCH_HEAD
  [ "$(git -C "$3" rev-parse HEAD)" = "$2" ] || { echo "$1: not the pinned commit" >&2; exit 1; }
}

fetch https://github.com/arminbiere/cadical "$CADICAL_COMMIT" "$dest/cadical-src"
(cd "$dest/cadical-src" && ./configure > configure.log 2>&1 && make -j"$(getconf _NPROCESSORS_ONLN)" > make.log 2>&1)
cp "$dest/cadical-src/build/cadical" "$dest/cadical"

fetch https://github.com/marijnheule/drat-trim "$DRAT_TRIM_COMMIT" "$dest/drat-trim-src"
gcc -O2 -w -o "$dest/lrat-check" "$dest/drat-trim-src/lrat-check.c"

"$dest/cadical" --version
(cd "$dest" && sha256sum cadical lrat-check)
