#!/bin/bash
# Fetch and open the sealed outputs of a teacher workflow run (.github/workflows/teacher.yml): each job's artifact holds
# its outputs encrypted with a random AES key, and that key encrypted to .github/teacher-outputs.pub.pem; the private
# key is ~/.config/dawnr/teacher-outputs.key on the laptop alone. Cohere's text is never published (its terms forbid
# distributing it; the permission of 2026-10-24 covers training on what passes our checks).
#   bash t/recipes/teacher_outputs.sh RUN_ID [DEST]       -> DEST/<artifact>/ with the job's out/ and t/out/ files
set -eu
RUN=${1:?run id}; DEST=${2:-out/r61/teacher-runs/$RUN}; KEY=${KEY:-$HOME/.config/dawnr/teacher-outputs.key}
mkdir -p "$DEST/sealed"
gh run download "$RUN" -D "$DEST/sealed"
for d in "$DEST"/sealed/*/; do
  name=$(basename "$d"); mkdir -p "$DEST/$name"
  if [ -f "$d/key.enc" ]; then
    k=$(mktemp); trap 'rm -f "$k"' EXIT
    openssl pkeyutl -decrypt -inkey "$KEY" -pkeyopt rsa_padding_mode:oaep -pkeyopt rsa_oaep_md:sha256 -in "$d/key.enc" -out "$k"
    openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -in "$d/outputs.tar.gz.enc" -pass "file:$k" | tar -xzf - -C "$DEST/$name"
    rm -f "$k"
  else
    cp -r "$d"/. "$DEST/$name/"        # an unsealed artifact from before the seal (the smoke run of 2026-10-24)
  fi
  echo "$name: $(find "$DEST/$name" -name '*strict-kept.jsonl' -exec cat {} + 2>/dev/null | wc -l) problems strictly kept"
done
rm -rf "$DEST/sealed"
