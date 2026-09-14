#!/bin/bash
# vm.sh: the x86_64 build VM, on a Linux host, from QEMU and nothing else.
#
#   bash tup/buildvm/vm.sh create      # cloud image -> scaffold overlay, LFS disk, seed
#   bash tup/buildvm/vm.sh start       # boot headless; serial console to console.log
#   bash tup/buildvm/vm.sh ssh [cmd]   # shell or command in the guest (user tup, sudo)
#   bash tup/buildvm/vm.sh push        # copy this repo's tup/ into the guest
#   bash tup/buildvm/vm.sh status | stop | destroy
#
# The arm64 leg used Lima on macOS; the Dell has no sudo and no Lima, so the
# scaffolding is made by hand and every step records what it used. The
# design is the same: Ubuntu as a DISPOSABLE HOST (the LFS two-pass
# toolchain exists precisely to sever the result from it), the LFS disk as
# the VM's SECOND virtio disk (/dev/vdb in the guest, /dev/vda at final
# boot), and nothing of the scaffold ends up on tup's disk.
#
# Accelerator: KVM when /dev/kvm is openable, else TCG. On this host
# (2026-09-02) the account is not in the kvm group, so the build runs under
# TCG, measured at roughly 14x per thread (X86-FEASIBILITY.md) and recovered
# across vcpus by MTTCG. The choice is printed and written to PROVENANCE.txt
# so the receipt says which one built the system.
#
# State lives OUTSIDE the repo in $TUP_VM (default ~/tup/tup-vm/x86_64):
#   noble-server-cloudimg-amd64.img   the pristine scaffold image (hashed)
#   scaffold.qcow2                    overlay the VM actually boots
#   lfs.qcow2                         the LFS disk: this becomes tup
#   seed.iso                          cloud-init NoCloud seed (user, ssh key)
#   id_ed25519[.pub]                  the key the host uses to reach the guest
#   console.log qemu.pid PROVENANCE.txt
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
TUP="$(cd "$HERE/.." && pwd)"
VM="${TUP_VM:-$HOME/tup/tup-vm/x86_64}"
Q="${TUP_QEMU:-$HOME/.local/opt/qemu-10.1.3}"
QEMU="$Q/bin/qemu-system-x86_64"; QIMG="$Q/bin/qemu-img"
IMG="$VM/noble-server-cloudimg-amd64.img"
IMG_URL="https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img"
SCAFFOLD="$VM/scaffold.qcow2"; LFSDISK="$VM/lfs.qcow2"; SEED="$VM/seed.iso"
KEY="$VM/id_ed25519"; PIDFILE="$VM/qemu.pid"; CONSOLE="$VM/console.log"
SSH_PORT="${TUP_SSH_PORT:-2322}"
SMP="${TUP_SMP:-64}"; MEM="${TUP_MEM:-96G}"; LFS_SIZE="${TUP_LFS_SIZE:-80G}"
SSH_OPTS=(-i "$KEY" -p "$SSH_PORT" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null
          -o LogLevel=ERROR -o ConnectTimeout=10)

die() { echo "vm.sh: $*" >&2; exit 1; }
[ -x "$QEMU" ] || die "no $QEMU (build QEMU per RUN-ON-UBUNTU.md)"
mkdir -p "$VM"

accel() {
  if python3 -c 'import os; os.close(os.open("/dev/kvm", os.O_RDWR))' 2>/dev/null; then
    echo kvm
  else
    echo tcg
  fi
}

running() { [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; }

cmd_create() {
  [ -f "$KEY" ] || ssh-keygen -q -t ed25519 -N '' -C tup-buildvm -f "$KEY"
  if [ ! -f "$IMG" ]; then
    echo "fetching the scaffold image"
    curl -fsSL -o "$IMG.part" "$IMG_URL" && mv "$IMG.part" "$IMG"
  fi
  # The scaffold's hash is recorded before first use and checked against the
  # publisher's list when that list is present. It is scaffolding, not tup,
  # but a build whose host image is unknown is a build with a hole in it.
  local sum; sum=$(sha256sum "$IMG" | cut -d' ' -f1)
  if [ -f "$VM/SHA256SUMS.ubuntu" ]; then
    grep -q "^$sum " "$VM/SHA256SUMS.ubuntu" \
      || die "scaffold image sha256 $sum is not in SHA256SUMS.ubuntu"
    echo "scaffold image sha256 $sum (matches the publisher's list)"
  else
    echo "scaffold image sha256 $sum (publisher's list not present; recorded, not checked)"
  fi
  if [ ! -f "$SCAFFOLD" ]; then
    "$QIMG" create -q -f qcow2 -b "$IMG" -F qcow2 "$SCAFFOLD"
    "$QIMG" resize -q "$SCAFFOLD" 40G
    echo "scaffold overlay created (40G, cloud-init grows the root)"
  fi
  if [ ! -f "$LFSDISK" ]; then
    "$QIMG" create -q -f qcow2 "$LFSDISK" "$LFS_SIZE"
    echo "LFS disk created ($LFS_SIZE, empty)"
  fi
  if [ ! -f "$SEED" ]; then
    local d; d=$(mktemp -d)
    printf 'instance-id: tup-buildvm\nlocal-hostname: lfs-host\n' > "$d/meta-data"
    cat > "$d/user-data" <<UD
#cloud-config
hostname: lfs-host
users:
  - name: tup
    shell: /bin/bash
    sudo: ALL=(ALL) NOPASSWD:ALL
    lock_passwd: true
    ssh_authorized_keys:
      - $(cat "$KEY.pub")
ssh_pwauth: false
growpart: {mode: auto, devices: ["/"]}
UD
    genisoimage -quiet -output "$SEED" -volid cidata -joliet -rock "$d/user-data" "$d/meta-data"
    rm -rf "$d"
    echo "cloud-init seed written"
  fi
  {
    echo "# tup x86_64 build VM, created $(date -u +%FT%TZ) on $(hostname)"
    echo "scaffold image: $(basename "$IMG") sha256 $sum"
    echo "qemu: $("$QEMU" --version | head -1)"
    echo "accelerator: $(accel)"
    echo "vcpus: $SMP  memory: $MEM  lfs disk: $LFS_SIZE"
  } > "$VM/PROVENANCE.txt"
  cat "$VM/PROVENANCE.txt"
}

cmd_start() {
  running && { echo "already running, pid $(cat "$PIDFILE")"; return 0; }
  [ -f "$SCAFFOLD" ] && [ -f "$LFSDISK" ] && [ -f "$SEED" ] || die "run create first"
  local acc cpu; acc=$(accel)
  case "$acc" in kvm) cpu=host ;; *) cpu=max ;; esac
  echo "starting: -accel $acc -cpu $cpu -smp $SMP -m $MEM, ssh on 127.0.0.1:$SSH_PORT"
  "$QEMU" -M q35 -accel "$acc" -cpu "$cpu" -smp "$SMP" -m "$MEM" \
    -drive file="$SCAFFOLD",format=qcow2,if=virtio,discard=unmap \
    -drive file="$LFSDISK",format=qcow2,if=virtio,discard=unmap \
    -drive file="$SEED",format=raw,media=cdrom,if=ide,readonly=on \
    -netdev user,id=n0,hostfwd=tcp:127.0.0.1:"$SSH_PORT"-:22 -device virtio-net-pci,netdev=n0 \
    -display none -serial "file:$CONSOLE" -daemonize -pidfile "$PIDFILE"
  echo "pid $(cat "$PIDFILE"); console -> $CONSOLE"
}

cmd_wait() {
  # until sshd answers (cloud-init has run the user block by then)
  local i
  for i in $(seq 1 "${1:-120}"); do
    if ssh "${SSH_OPTS[@]}" tup@127.0.0.1 true 2>/dev/null; then echo "guest is up"; return 0; fi
    running || die "qemu exited; see $CONSOLE"
    sleep 10
  done
  die "guest did not answer ssh in time; see $CONSOLE"
}

cmd_ssh() { ssh "${SSH_OPTS[@]}" tup@127.0.0.1 "$@"; }

cmd_push() {
  # Everything the guest needs, nothing it does not: books, overrides, the
  # driver, the chains, the layers, this directory. Receipts stay on the host.
  cmd_ssh mkdir -p /home/tup/tup
  tar -C "$TUP" -cf - book book-x86_64 overrides driver.sh chain7.sh chain8.sh chain-home.sh \
      inventory.sh layers buildvm 2>/dev/null \
    | cmd_ssh "tar -C /home/tup/tup -xf -"
  echo "pushed tup/ to the guest"
}

cmd_status() {
  if running; then echo "running, pid $(cat "$PIDFILE"), accel $(accel)"; else echo "not running"; fi
  [ -f "$CONSOLE" ] && tail -3 "$CONSOLE"
  return 0
}

cmd_stop() {
  running || { echo "not running"; return 0; }
  cmd_ssh sudo poweroff 2>/dev/null || true
  local i
  for i in $(seq 1 60); do running || { echo "stopped"; return 0; }; sleep 2; done
  echo "guest did not power off; killing qemu"; kill "$(cat "$PIDFILE")" 2>/dev/null || true
}

cmd_destroy() {
  running && die "stop it first"
  rm -f "$SCAFFOLD" "$SEED" "$PIDFILE"
  echo "scaffold removed; the LFS disk $LFSDISK is kept (delete it yourself)"
}

case "${1:-}" in
  create|start|wait|ssh|push|status|stop|destroy) c=$1; shift; "cmd_$c" "$@" ;;
  *) sed -n '2,12p' "$0"; exit 1 ;;
esac
