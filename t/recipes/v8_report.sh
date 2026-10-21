#!/bin/bash
# After t/recipes/v8_desktop_finish.sh: copy the two v8 arms back, pair them against their controls, and print the numbers
# that decide t/PREDICT-2026-10-21-v8-spec-rows.md (P1 frozen route vs control-r2; P3 oracle route vs v5 O39; P2 the
# ceiling instrument). Run on the laptop. Sources: t/recipes/v7_local_pair.py, t/recipes/spec_ceiling.py.
set -u
cd "$(dirname "$0")/../.." || exit 1
D=t/out/v5-repair-20261021; H=t@10.42.0.2
for tag in v8-20261021-dev v8-20261021-oracle39; do
  rsync -a $H:~/v5-repair/proof-results/$tag $D/proof-results/ || exit 1
  rsync -a --exclude raw $H:~/dawnr/t/out/spec-experiment/$tag $D/spec-experiment/ || exit 1
  [ -e t/out/spec-experiment/$tag ] || ln -s ../v5-repair-20261021/spec-experiment/$tag t/out/spec-experiment/$tag
done
rsync -a $H:~/v5-repair/v8-ceiling.json $D/ 2>/dev/null; cp t/out/v8-export/export.json t/out/v8-export/inputs.json $D/v8-export/ 2>/dev/null
mkdir -p $D/v8-export
echo "--- P1: v8 frozen route vs the v5 control (same tree) ---"
python3 t/recipes/v7_local_pair.py --panel t/out/v6-20261018/dev-95.txt --baseline "v5-20261021-dev-desktop-r2:$D/proof-results/v5-20261021-dev-desktop-r2" --candidate "v8-20261021-dev:$D/proof-results/v8-20261021-dev" --out release/evidence/v8-development-2026-10-21.json | tail -1 | cut -c1-400
echo "--- P3: v8 oracle route vs v5 oracle route ---"
python3 t/recipes/v7_local_pair.py --panel t/out/v6-20261018/dev-95.txt --baseline "v5-20261021-oracle39:$D/proof-results/v5-20261021-oracle39" --candidate "v8-20261021-oracle39:$D/proof-results/v8-20261021-oracle39" --out release/evidence/v8-oracle39-2026-10-21.json | tail -1 | cut -c1-400
echo "--- P2: the ceiling instrument (reference-correct specification within 5 and 20 candidates; v5: 18 and 29 of 63) ---"
python3 -c "
import json; r=json.load(open('$D/v8-ceiling.json')); k=r['spec_pass_at_k']['reference']; print('with_python', r['with_python'], '| within 5:', k.get('5'), '| within 20:', k.get('20'), '| SAFE precision', round(r['safe_precision'] or 0,3))"
