#!/bin/bash
# emit one line per milestone across the running experiments (new lines only)
S=<scratch>
LOGS="$S/locallm-t/loop.log $S/locallm-t/loop-rawmatched.log $S/volume/locallm-r0.log $S/volume/volume.log"
PAT='round [0-9]+:|LOOP_DONE|stopping|LOCALLM_R0_DONE|kernels, [0-9]+ tasks|set [0-9]+ (generate|kernels)|pass their tests|VOLUME_DONE|Traceback|Error|Killed|REFUSED|No such file'
declare -A seen
for f in $LOGS; do seen[$f]=$(wc -l < "$f" 2>/dev/null || echo 0); done
while true; do
  for f in $LOGS; do
    n=$(wc -l < "$f" 2>/dev/null || echo 0)
    if [ "$n" -gt "${seen[$f]}" ]; then
      tail -n +"$((${seen[$f]} + 1))" "$f" | head -n "$((n - ${seen[$f]}))" | grep -E "$PAT" | sed "s|^|$(basename $(dirname $f))/$(basename $f): |"
      seen[$f]=$n
    fi
  done
  sleep 20
done
