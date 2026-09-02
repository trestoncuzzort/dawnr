#!/bin/bash
# build-all.sh: launch the whole chain inside the build VM and return.
# Run as root after prepare-host.sh. Each leg waits for the previous leg's
# completion marker in its console file, exactly as the arm64 build did, so
# the four run as independent background processes and a failed leg stops
# every later one by never producing its marker.
#
#   sudo bash /home/lfs/build-all.sh
#   tail -f /mnt/lfs/sources/log/chain*.console
set -u
export LFS=/mnt/lfs
LOG=$LFS/sources/log
mkdir -p "$LOG"
case "$(uname -m)" in x86_64) export TUP_ARCH=x86_64 ;; aarch64) export TUP_ARCH=arm64 ;; esac
for leg in chain56 chain7 chain8 chain-home; do
  if pgrep -f "[b]ash /home/lfs/$leg.sh" >/dev/null; then echo "$leg already running"; continue; fi
  nohup bash /home/lfs/$leg.sh >> "$LOG/$leg.console" 2>&1 &
  echo "$leg started (pid $!)"
done
echo "consoles: $LOG/chain{56,7,8,-home}.console; the last line of the last one is the verdict"
