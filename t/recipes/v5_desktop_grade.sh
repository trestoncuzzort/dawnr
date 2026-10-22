#!/bin/bash
# The frozen grader (t/recipes/v6-grade.sh) on one generated answer set, inside the desktop's pinned-kernel container
# (image dawnr-kernels, the engine's Dockerfile.kernels: dafny 4.11.0, verus 0.2026.08.30, gnatprove 16.1.0, frama-c 33.0
# with alt-ergo 2.4.3, Lean 4.33.1, Rocq 9.2, F* 2026.08.30, the versions of every grade since v5). The container user is
# prover (uid 1001), so the staged t/out and the output are made writable for it. One answer set at a time: the grader
# takes a lock and the kernels are run one job at a time (14 GB of memory on the desktop; Lean needs about 3 GB).
#   bash t/recipes/v5_desktop_grade.sh TAG          # output under ~/v5-repair/proof-results/TAG, sentinel grade-TAG.done
# Sources: t/recipes/v7_modal_grade.py grade() (the same staging rules: drop grader artifacts, create t/out/v6-20261018).
set -u
TAG=${1:?generation tag}
H=/home/t; D=$H/dawnr; A=$H/v5-repair; OUT=$A/proof-results/$TAG
PANEL=${PANEL:-$H/v7/dev-95.txt}; POOL=${POOL:-v5}; PNAME=$(basename $PANEL)   # PANEL and POOL for the wider 145 (pool v7)
rm -f $A/grade-$TAG.done
# a graded directory left by an interrupted grade (no GRADED sentinel) makes run_par report incomplete kernel coverage
# (2026-10-21, after a GPU reset mid-grade); start it clean
# (the container's user, prover, owns what it wrote, so the host user needs sudo to clear it; tlab has NOPASSWD sudo)
[ -e $OUT/GRADED ] || { rm -rf $OUT 2>/dev/null; [ -e $OUT ] && sudo -n rm -rf $OUT; }
mkdir -p $OUT $D/t/out/v6-20261018
rm -f $D/t/out/spec-experiment/$TAG/kernels.md $D/t/out/spec-experiment/$TAG/extract.json $D/t/out/spec-experiment/$TAG/tests.json
rm -rf $D/t/out/spec-experiment/$TAG/tasks
chmod -R a+rwX $D/t/out $A
echo "$(date -u +%FT%TZ) grade $TAG start" >> $A/grade.log
docker run --rm --name grade-$TAG -v $D:/opt/dawnr -v $A:$A -v $PANEL:/panel/$PNAME:ro -w /opt/dawnr \
  -e POOL=$POOL -e T_MIN_KERNELS=7 -e T_SPARK_JOBS=1 -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 --memory=12g \
  dawnr-kernels bash t/recipes/v6-grade.sh $TAG /panel/$PNAME $OUT > $A/grade-$TAG.log 2>&1
RC=$?
echo "$(date -u +%FT%TZ) grade $TAG rc=$RC graded=$([ -e $OUT/GRADED ] && echo yes || echo no)" >> $A/grade.log
echo $RC > $A/grade-$TAG.done
