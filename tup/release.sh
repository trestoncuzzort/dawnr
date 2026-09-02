#!/bin/bash
# release.sh: package tup as bootable disk images, each one witnessed.
#
#   bash tup/release.sh [outdir]                    # arm64, from the Lima disk (macOS)
#   TUP_ARCH=x86_64 bash tup/release.sh [outdir]    # x86_64, from the QEMU build VM's disk
#
# Ships qcow2 (KVM/QEMU, witnessed here), vmdk (VMware) and vdi (VirtualBox),
# the latter two marked UNVERIFIED in RELEASE.md until a human boots one,
# because this machine has no VMware and an unwitnessed claim is not made.
#
# Three lessons are baked in rather than relearned:
#   1. A running build VM holds a lock on the disk. On macOS the disk is
#      quiesced (unmounted in the guest) and an APFS clone taken, instant and
#      lock-free, and the VM goes straight back to work. On Linux there is no
#      clone primitive without root, so the x86_64 leg requires the build VM
#      to be STOPPED (buildvm/vm.sh stop, after a guest-side fstrim); the
#      script refuses a disk any process still holds open.
#   2. fstrim first: the disk carries every deleted build artifact as
#      allocated blocks (53 GB where 5.5 GB is real) until the guest trims.
#   3. No image ships unwitnessed: the qcow2 must reach `tup login:` on a
#      serial console before SHA256SUMS is written. The others are converted
#      FROM the witnessed qcow2, and say so.
set -eu
OUT=${1:-"$HOME/tup-release"}
ARCH="${TUP_ARCH:-arm64}"
SCRATCH="${TMPDIR:-/tmp}/tup-release-$$"
VER=$(date -u +%Y%m%d)
NAME="tup-0.1-$ARCH"
HERE="$(cd "$(dirname "$0")" && pwd)"
QDIR="${TUP_QEMU:-$HOME/.local/opt/qemu-10.1.3}"
QIMG=$(command -v qemu-img || echo "$QDIR/bin/qemu-img")
SHA=$(command -v sha256sum >/dev/null && echo "sha256sum" || echo "shasum -a 256")

case "$ARCH" in
  arm64)
    DISK="${TUP_DISK:-$HOME/.lima/_disks/lfs/datadisk}"
    FW=$(ls /opt/homebrew/share/qemu/edk2-aarch64-code.fd 2>/dev/null || true)
    QEMU=$(command -v qemu-system-aarch64 || echo "$QDIR/bin/qemu-system-aarch64")
    [ -n "$FW" ] || { echo "no EDK2 firmware (brew install qemu)" >&2; exit 1; }
    ;;
  x86_64)
    DISK="${TUP_DISK:-$HOME/tup-vm/x86_64/lfs.qcow2}"
    FW=""
    QEMU=$(command -v qemu-system-x86_64 || echo "$QDIR/bin/qemu-system-x86_64")
    ;;
  *) echo "unknown TUP_ARCH $ARCH" >&2; exit 1 ;;
esac
[ -r "$DISK" ] || { echo "no disk at $DISK" >&2; exit 1; }
[ -x "$QEMU" ] || { echo "no QEMU for $ARCH" >&2; exit 1; }
if [ "$(uname -s)" = Darwin ]; then ACCEL=hvf; CPU=host
elif python3 -c 'import os; os.close(os.open("/dev/kvm", os.O_RDWR))' 2>/dev/null; then ACCEL=kvm; CPU=host
else ACCEL=tcg; CPU=$([ "$ARCH" = arm64 ] && echo cortex-a72 || echo max)
fi
mkdir -p "$OUT" "$SCRATCH"
trap 'rm -rf "$SCRATCH"' EXIT

echo "=== 1. the source disk"
SRC="$SCRATCH/disk"; SRCFMT=raw
if [ "$ARCH" = arm64 ] && command -v limactl >/dev/null; then
  echo "    trim + quiesce + clone (the VM resumes immediately)"
  limactl shell lfs-host -- sudo bash -c '
    fstrim /mnt/lfs >/dev/null 2>&1 || true
    umount -R /mnt/lfs 2>/dev/null || true
    mountpoint -q /mnt/lfs && { echo "cannot quiesce /mnt/lfs" >&2; exit 1; }' \
    || { echo "quiesce failed" >&2; exit 1; }
  cp -c "$DISK" "$SRC"          # APFS clone: instant, no lock
  limactl shell lfs-host -- sudo bash -c \
    'mount /dev/vdb2 /mnt/lfs && mount /dev/vdb1 /mnt/lfs/boot/efi 2>/dev/null || true'
  echo "    cloned; build VM remounted"
  KERNEL=$(limactl shell lfs-host -- ls /mnt/lfs/boot 2>/dev/null | grep ^vmlinuz | head -1 || echo unknown)
else
  holder=$(fuser "$DISK" 2>/dev/null | tr -d ' ')
  [ -z "$holder" ] || { echo "!!! $DISK is open by pid(s) $holder; stop the build VM first" >&2; exit 1; }
  SRC="$DISK"; case "$DISK" in *.qcow2) SRCFMT=qcow2 ;; esac
  # The kernel name is read from the disk at build time by the orchestrator
  # (buildvm/build-x86_64.sh writes KERNEL.txt beside the disk); there is no
  # rootless way to list a stopped disk's /boot from here.
  KERNEL=${TUP_KERNEL:-$(cat "$(dirname "$DISK")/KERNEL.txt" 2>/dev/null || echo unknown)}
  echo "    $DISK ($SRCFMT), not held by any process"
fi

echo "=== 2. convert (compressed qcow2 is the master)"
"$QIMG" convert -f "$SRCFMT" -O qcow2 -c "$SRC" "$OUT/$NAME.qcow2"
ls -lh "$OUT/$NAME.qcow2" | awk '{print "    qcow2:", $5}'

echo "=== 3. witness the qcow2 before anything else happens (accel $ACCEL)"
# Boot an OVERLAY of the master, never the master: a boot remounts rw and
# changes the file (measured 2026-08-31; it is why RUN-ON-UBUNTU.md prescribes
# an overlay). What ships is the exact bytes the overlay was backed by.
LOG="$SCRATCH/witness.log"
"$QIMG" create -q -f qcow2 -b "$OUT/$NAME.qcow2" -F qcow2 "$SCRATCH/witness.qcow2"
if [ "$ARCH" = arm64 ]; then
  "$QEMU" -machine virt -accel "$ACCEL" -cpu "$CPU" -m 2048 -smp 2 \
    -drive if=pflash,format=raw,readonly=on,file="$FW" \
    -drive file="$SCRATCH/witness.qcow2",format=qcow2,if=virtio \
    -display none -serial "file:$LOG" &
else
  "$QEMU" -M q35 -accel "$ACCEL" -cpu "$CPU" -m 2048 -smp 2 \
    -drive file="$SCRATCH/witness.qcow2",format=qcow2,if=virtio \
    -display none -serial "file:$LOG" &
fi
QPID=$!
BOOTED=""
for i in $(seq 1 60); do
  grep -q "tup login:" "$LOG" 2>/dev/null && { BOOTED="$((i*5))s"; break; }
  sleep 5
done
kill "$QPID" 2>/dev/null || true
[ -n "$BOOTED" ] || { echo "!!! qcow2 did not reach tup login: in 300s; NOT shipping"
                      tail -5 "$LOG"; exit 1; }
echo "    tup login: after $BOOTED"

echo "=== 4. derived formats (from the witnessed master)"
"$QIMG" convert -O vmdk "$OUT/$NAME.qcow2" "$OUT/$NAME.vmdk"
"$QIMG" convert -O vdi  "$OUT/$NAME.qcow2" "$OUT/$NAME.vdi"

echo "=== 5. hashes and the release note"
( cd "$OUT" && $SHA "$NAME.qcow2" "$NAME.vmdk" "$NAME.vdi" > SHA256SUMS )
# Name the inventory. Thirteen INVENTORY files with nothing saying which one
# was the release cost an outside reader a wrong conclusion (2026-09-02); the
# release note now names its inventory by file and hash, and INVENTORIES.md
# is where a human corrects it if the newest one is not the shipped disk.
# Inventories are per arch: arm64 ones are INVENTORY-<stamp>.txt, x86_64 ones
# INVENTORY-x86_64-<stamp>.txt (buildvm/build-x86_64.sh), so each leg names
# only its own, and a leg with none yet says so rather than borrowing one.
case "$ARCH" in
  arm64)  INV=$(ls -t "$HERE/receipts"/INVENTORY-*.txt 2>/dev/null | grep -v '/INVENTORY-x86_64-' | head -1 || true) ;;
  x86_64) INV=$(ls -t "$HERE/receipts"/INVENTORY-x86_64-*.txt 2>/dev/null | head -1 || true) ;;
esac
INV_SHA=$([ -n "$INV" ] && $SHA "$INV" | cut -d' ' -f1 || echo none)
INV_NAME=$([ -n "$INV" ] && basename "$INV" || echo "none yet for this arch")
LAYERS=$(ls "$HERE/receipts"/LAYER-*.txt "$HERE/receipts"/LAYER-*.md 2>/dev/null \
         | xargs -n1 basename 2>/dev/null | tr '\n' ' ' || true)
case "$ARCH" in
  arm64)  BOOTHOW="tup/RUN-ON-UBUNTU.md (one apt-get, one qemu command)" ;;
  x86_64) BOOTHOW="tup/RUN-ON-UBUNTU.md, x86_64 section (BIOS GRUB; no firmware file needed)" ;;
esac
cat > "$OUT/RELEASE.md" <<EOF
# tup 0.1 $ARCH ($VER)

- kernel: $KERNEL
- boot witness (this exact qcow2): \`tup login:\` after $BOOTED under QEMU/$ACCEL on $(uname -sm)
- qcow2: **witnessed**; vmdk/vdi: **UNVERIFIED**, converted from the
  witnessed master; boot one and say so before relying on it
- layer diffs shipped in the repo: ${LAYERS:-none yet for this arch}
- how to boot: $BOOTHOW
- verify: \`sha256sum -c SHA256SUMS\`
- inventory of this disk: \`$INV_NAME\` sha256 $INV_SHA (the newest
  INVENTORY for this arch in receipts/ when this ran; if a layer was built
  between that inventory and this cut, re-inventory the image itself and say
  so in receipts/INVENTORIES.md)

Provenance, not verification: the receipts record what was built, from which
bytes, in what order. Training on the Dell stays on the host OS where CUDA
lives; tup is the pinned verifier and analysis environment.
EOF
echo; echo "release at $OUT:"; ls -lh "$OUT" | tail -n +2 | awk '{print "  " $9, $5}'
