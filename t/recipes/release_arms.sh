#!/bin/bash
# Generate the registered development parts on an approved GPU host. GitHub grades the completed bundles.
# D is the remote dawnr checkout; L contains the pinned llama-server. No local grading is started here.
#   D=/path/to/dawnr L=/path/to/server release_arms.sh PFX GGUF IDENT
# Sources: the previous release_arms.sh arm order and cache seeding; release_decode_arms.py; laptop_route.sh.
set -euo pipefail
PFX=${1:?prefix}; GGUF=${2:?gguf}; IDENT=${3:?identity}
D=${D:?remote dawnr checkout}; L=${L:?remote llama-server directory}
exec python3 "$D/t/recipes/release_decode_arms.py" --checkout "$D" --server-dir "$L" --prefix "$PFX" \
  --gguf "$GGUF" --identity "$IDENT" --out "$D/t/out/release-decoded/$PFX"
