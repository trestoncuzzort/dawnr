#!/bin/bash
# release.sh — package tup as bootable disk images, each one witnessed.
#
#   bash tup/release.sh [outdir]        # default ~/tup-release
#
# Ships qcow2 (KVM/QEMU — witnessed here), vmdk (VMware) and vdi (VirtualBox)
# — the latter two marked UNVERIFIED in RELEASE.md until a human boots one,
# because this machine has no VMware and an unwitnessed claim is not made.
#
# Three lessons are baked in rather than relearned:
#   1. The running Lima VM holds a mandatory lock on the raw disk that even
#      qemu-img -U cannot cross. The disk is therefore quiesced (unmounted in
#      the guest) and an APFS clone taken — instant, lock-free — and the VM
#      goes straight back to work while conversion runs on the clone.
#   2. fstrim first: the raw file carries every deleted build artifact as
#      allocated blocks (53 GB where 5.5 GB is real) until the guest trims.
#   3. No image ships unwitnessed: the qcow2 must reach `tup login:` on a
#      serial console before SHA256SUMS is written. The others are converted
#      FROM the witnessed qcow2, and say so.
set -eu
OUT=${1:-"$HOME/tup-release"}
DISK="$HOME/.lima/_disks/lfs/datadisk"
SCRATCH="${TMPDIR:-/tmp}/tup-release-$$"
FW=$(ls /opt/homebrew/share/qemu/edk2-aarch64-code.fd 2>/dev/null || true)
VER=$(date -u +%Y%m%d)
NAME="tup-0.1-arm64"

[ -r "$DISK" ] || { echo "no disk at $DISK" >&2; exit 1; }
[ -n "$FW" ]   || { echo "no EDK2 firmware (brew install qemu)" >&2; exit 1; }
mkdir -p "$OUT" "$SCRATCH"
trap 'rm -rf "$SCRATCH"' EXIT

echo "=== 1. trim + quiesce + clone (the VM resumes immediately)"
limactl shell lfs-host -- sudo bash -c '
  fstrim /mnt/lfs >/dev/null 2>&1 || true
  umount -R /mnt/lfs 2>/dev/null || true
  mountpoint -q /mnt/lfs && { echo "cannot quiesce /mnt/lfs" >&2; exit 1; }' \
  || { echo "quiesce failed" >&2; exit 1; }
cp -c "$DISK" "$SCRATCH/disk"          # APFS clone: instant, no lock
limactl shell lfs-host -- sudo bash -c \
  'mount /dev/vdb2 /mnt/lfs && mount /dev/vdb1 /mnt/lfs/boot/efi 2>/dev/null || true'
echo "    cloned; build VM remounted"

echo "=== 2. convert (compressed qcow2 is the master)"
qemu-img convert -O qcow2 -c "$SCRATCH/disk" "$OUT/$NAME.qcow2"
ls -lh "$OUT/$NAME.qcow2" | awk '{print "    qcow2:", $5}'

echo "=== 3. witness the qcow2 before anything else happens"
LOG="$SCRATCH/witness.log"
qemu-system-aarch64 -machine virt -accel hvf -cpu host -m 2048 -smp 2 \
  -drive if=pflash,format=raw,readonly=on,file="$FW" \
  -drive file="$OUT/$NAME.qcow2",format=qcow2,if=virtio \
  -display none -serial "file:$LOG" &
QPID=$!
BOOTED=""
for i in $(seq 1 36); do
  grep -q "tup login:" "$LOG" 2>/dev/null && { BOOTED="$((i*5))s"; break; }
  sleep 5
done
kill "$QPID" 2>/dev/null || true
[ -n "$BOOTED" ] || { echo "!!! qcow2 did not reach tup login: in 180s — NOT shipping"
                      tail -5 "$LOG"; exit 1; }
echo "    tup login: after $BOOTED"

echo "=== 4. derived formats (from the witnessed master)"
qemu-img convert -O vmdk "$OUT/$NAME.qcow2" "$OUT/$NAME.vmdk"
qemu-img convert -O vdi  "$OUT/$NAME.qcow2" "$OUT/$NAME.vdi"

echo "=== 5. hashes and the release note"
( cd "$OUT" && shasum -a 256 "$NAME.qcow2" "$NAME.vmdk" "$NAME.vdi" > SHA256SUMS )
KERNEL=$(limactl shell lfs-host -- ls /mnt/lfs/boot 2>/dev/null | grep ^vmlinuz | head -1 || echo unknown)
# Name the inventory. Thirteen INVENTORY files with nothing saying which one
# was the release cost an outside reader a wrong conclusion (2026-09-02); the
# release note now names its inventory by file and hash, and INVENTORIES.md
# is where a human corrects it if the newest one is not the shipped disk.
INV=$(ls -t "$(dirname "$0")/receipts"/INVENTORY-*.txt 2>/dev/null | head -1 || true)
INV_SHA=$([ -n "$INV" ] && shasum -a 256 "$INV" | cut -d' ' -f1 || echo none)
LAYERS=$(ls "$(dirname "$0")/receipts"/LAYER-*.txt "$(dirname "$0")/receipts"/LAYER-*.md 2>/dev/null \
         | xargs -n1 basename 2>/dev/null | tr '\n' ' ' || true)
cat > "$OUT/RELEASE.md" <<EOF
# tup 0.1 ($VER)

- kernel: $KERNEL
- boot witness (this exact qcow2): \`tup login:\` after $BOOTED under QEMU/hvf
- qcow2: **witnessed** · vmdk/vdi: **UNVERIFIED** — converted from the
  witnessed master; boot one and say so before relying on it
- layer diffs shipped in the repo: $LAYERS
- how to boot: tup/RUN-ON-UBUNTU.md (one apt-get, one qemu command)
- verify: \`shasum -a 256 -c SHA256SUMS\`
- inventory of this disk: \`$(basename "$INV")\` sha256 $INV_SHA (the newest
  INVENTORY in receipts/ when this ran; if a layer was built between that
  inventory and this cut, re-inventory the image itself and say so in
  receipts/INVENTORIES.md)

Provenance, not verification: the receipts record what was built, from which
bytes, in what order. Training on the Dell stays on the host OS where CUDA
lives; tup is the pinned verifier and analysis environment.
EOF
echo; echo "release at $OUT:"; ls -lh "$OUT" | tail -n +2 | awk '{print "  " $9, $5}'
