#!/bin/bash
# build-x86_64.sh: the whole x86_64 leg, host side, resumable.
#
#   bash tup/buildvm/build-x86_64.sh            # run every stage not yet done
#   bash tup/buildvm/build-x86_64.sh status     # where is it
#
# Stages, each skipped when its evidence already exists:
#   1 create+start the build VM        (buildvm/vm.sh)
#   2 push tup/ and prepare the host   (buildvm/prepare-host.sh: chapters 2-4)
#   3 launch the chain                 (buildvm/build-all.sh: ch05..ch11)
#   4 wait for the verdict, polling the consoles; a FAILED marker stops here
#   5 collect: log dir + manifest -> ~/tup/tup-vm/x86_64/log/, BUILD receipt,
#     inventory of the built tree, kernel name, guest-side fstrim
#   6 stop the VM and boot tup alone   (boot_witness.sh)
#   7 release images                   (release.sh)
#
# Nothing here is clever; it is the arm64 leg's sequence of hand-run steps
# written down so the x86_64 leg is a record instead of a memory.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
TUP="$(cd "$HERE/.." && pwd)"
VM="${TUP_VM:-$HOME/tup/tup-vm/x86_64}"
VMSH="bash $HERE/vm.sh"
LOGDIR="$VM/log"          # per-page logs stay outside the repo; receipts/ gets the bundle
GLOG=/mnt/lfs/sources/log
export TUP_ARCH=x86_64

say() { echo; echo "=== [$(date -u +%FT%TZ)] $*"; }
guest() { $VMSH ssh "$@"; }

if [ "${1:-}" = status ]; then
  $VMSH status
  guest "for c in $GLOG/chain*.console; do echo \"--- \$c\"; tail -2 \$c; done; tail -1 $GLOG/driver.state" 2>/dev/null
  exit 0
fi

say "1. build VM"
$VMSH create >/dev/null
$VMSH start
$VMSH wait 120

if guest "test -s $GLOG/PREPARED.txt" 2>/dev/null; then
  say "2. host already prepared: $(guest cat $GLOG/PREPARED.txt | head -1)"
else
  say "2. push tup/ and prepare the host (chapters 2-4)"
  $VMSH push
  guest "sudo bash /home/tup/tup/buildvm/prepare-host.sh" 2>&1 | tee "$VM/prepare.log" | tail -5
  guest "test -s $GLOG/PREPARED.txt" || { echo "!!! prepare-host did not finish; see $VM/prepare.log"; exit 1; }
fi

say "3. launch the chain"
guest "sudo bash /home/lfs/build-all.sh"

say "4. wait for the verdict"
while :; do
  v=$(guest "tail -qn1 $GLOG/chain56.console $GLOG/chain7.console $GLOG/chain8.console $GLOG/chain-home.console 2>/dev/null" 2>/dev/null || true)
  case "$v" in
    *"TUP BUILT"*) echo "$v" | tail -1; break ;;
    *FAILED*) echo "!!! a leg failed:"; echo "$v"; guest "tail -20 $GLOG/chain*.console" ; exit 1 ;;
  esac
  echo "  $(date -u +%H:%M) $(guest "tail -qn1 $GLOG/driver.state 2>/dev/null" 2>/dev/null)"
  sleep 300
done

say "5. collect the evidence"
mkdir -p "$LOGDIR"
guest "sudo tar -C $GLOG -cf - ." | tar -C "$LOGDIR" -xf -
guest "cat /mnt/lfs/sources/SHA256-MANIFEST-*.txt" > "$LOGDIR/SHA256-MANIFEST-x86_64.txt"
guest "ls /mnt/lfs/boot | grep ^vmlinuz | head -1" > "$VM/KERNEL.txt"
echo "kernel: $(cat "$VM/KERNEL.txt")"
python3 "$TUP/bundle_receipts.py" --local "$LOGDIR"
guest "sudo bash /home/tup/tup/inventory.sh /mnt/lfs" | tail -3
guest "ls -t /home/tup/tup/receipts/INVENTORY-*.txt | head -1 | xargs cat" > "$TUP/receipts/INVENTORY-x86_64-$(date -u +%Y%m%dT%H%M%SZ).txt"
guest "sudo fstrim -v /mnt/lfs; sudo sync"

say "6. stop the VM; boot tup alone"
$VMSH stop
bash "$TUP/boot_witness.sh" || { echo "!!! boot witness did not pass"; exit 1; }

say "7. release"
bash "$TUP/release.sh" "$HOME/tup-release-x86_64"
say "done"
