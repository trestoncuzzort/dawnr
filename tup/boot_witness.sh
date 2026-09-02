#!/bin/bash
# boot_witness.sh: boot tup ALONE and record what it says.
#
#   bash tup/boot_witness.sh            # boot, capture, verdict
#   bash tup/boot_witness.sh --keep     # leave the VM up for interaction
#   TUP_ARCH=x86_64 bash tup/boot_witness.sh   # the x86_64 disk (see below)
#
# THE WITNESS THIS PRODUCES, and why it is the acceptance test: the build VM
# is stopped first, so nothing of the scaffold (Lima or the QEMU build VM,
# Ubuntu, the host toolchain) is in the loop. QEMU is handed the raw disk and
# firmware and nothing else: no -kernel, no -initrd, no -append. Every byte
# that executes comes off tup's own disk. If a login prompt appears, tup
# booted itself; there is no other explanation available.
#
# Two legs, one rule:
#   arm64  (default) UEFI: EDK2 code + a fresh variable store, so the
#          firmware must find EFI/BOOT/BOOTAA64.EFI on tup's ESP with no
#          prior NVRAM entry. Accelerated by hvf on macOS, tcg elsewhere.
#   x86_64 BIOS: SeaBIOS from the QEMU build (the x86 book installs GRUB to
#          the MBR; the ruling is in X86-FEASIBILITY.md), so there is no
#          firmware file at all, only the disk. kvm when /dev/kvm is
#          openable, else tcg.
#
# Success is the LITERAL `tup login:` prompt on the serial console, and a
# kernel panic anywhere in the transcript outranks it. Recorded to
# tup/receipts/boot-witness-<date>.txt with the disk's PRE-BOOT sha256 (or, for
# a disk too large to hash in reasonable time, an explicit line saying so — the
# receipt never just omits it), the firmware identity, the QEMU version, and
# the console transcript.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
ARCH="${TUP_ARCH:-arm64}"
RECEIPTS="$HERE/receipts"; mkdir -p "$RECEIPTS"
WORK="${TMPDIR:-/tmp}/tup-boot"; mkdir -p "$WORK"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="$WORK/console-$STAMP.log"
KEEP="${1:-}"
QDIR="${TUP_QEMU:-$HOME/.local/opt/qemu-10.1.3}"

case "$ARCH" in
  arm64)
    DISK="${TUP_DISK:-$HOME/.lima/_disks/lfs/datadisk}"
    FW_CODE="${TUP_FW:-/opt/homebrew/share/qemu/edk2-aarch64-code.fd}"
    QEMU=$(command -v qemu-system-aarch64 || echo "$QDIR/bin/qemu-system-aarch64")
    ;;
  x86_64)
    DISK="${TUP_DISK:-$HOME/tup-vm/x86_64/lfs.qcow2}"
    FW_CODE="(SeaBIOS, bundled in the QEMU build; no firmware file)"
    QEMU=$(command -v qemu-system-x86_64 || echo "$QDIR/bin/qemu-system-x86_64")
    ;;
  *) echo "unknown TUP_ARCH $ARCH"; exit 1 ;;
esac
case "$DISK" in *.qcow2) FMT=qcow2 ;; *) FMT=raw ;; esac

[ -f "$DISK" ] || { echo "no disk at $DISK"; exit 1; }
[ -x "$QEMU" ] || { echo "no QEMU for $ARCH ($QEMU)"; exit 1; }
[ "$ARCH" = x86_64 ] || [ -f "$FW_CODE" ] || { echo "no UEFI firmware at $FW_CODE (brew install qemu)"; exit 1; }

# Accelerator: whatever this host can give. hvf on macOS; on Linux, kvm only
# if /dev/kvm opens (group membership, not just existence), else tcg. The
# choice is printed into the witness because it changes the timing claim.
if [ "$(uname -s)" = Darwin ]; then ACCEL=hvf; CPU=host
elif python3 -c 'import os; os.close(os.open("/dev/kvm", os.O_RDWR))' 2>/dev/null; then ACCEL=kvm; CPU=host
else ACCEL=tcg; CPU=$([ "$ARCH" = arm64 ] && echo cortex-a72 || echo max)
fi

# The disk cannot be booted while the build VM holds it, but stopping that VM
# blind would kill a build in progress and lose hours. Check what is running
# BEFORE taking the machine away from it.
if command -v limactl >/dev/null && limactl list 2>/dev/null | grep -q "^lfs-host.*Running"; then
  # The bracket in [r]un-ch0 keeps this check from matching ITS OWN command
  # line: pgrep -f sees the shell that is running the pattern and reports a
  # build that does not exist. Measured 2026-08-31: this refused to boot a
  # finished system, and the only process it had found was itself.
  busy=$(limactl shell lfs-host -- bash -c \
    'pgrep -f "[r]un-ch0|[c]hain-home|[d]river\\.sh" >/dev/null && echo BUSY || echo IDLE' \
    2>/dev/null || echo UNKNOWN)
  if [ "$busy" = "BUSY" ] && [ "${TUP_FORCE_STOP:-}" != "1" ]; then
    echo "REFUSING: a build is still running in lfs-host." >&2
    echo "  Stopping the VM now would discard it. Wait for it to finish, or" >&2
    echo "  set TUP_FORCE_STOP=1 if you are certain." >&2
    exit 1
  fi
  echo "stopping the build VM so tup boots with nothing else attached..."
  limactl stop lfs-host >/dev/null 2>&1
  for _ in $(seq 1 30); do
    limactl list 2>/dev/null | grep -q "^lfs-host.*Running" || break
    sleep 2
  done
  limactl list 2>/dev/null | grep -q "^lfs-host.*Running" \
    && { echo "lfs-host did not stop; refusing to open a disk it still holds" >&2; exit 1; }
fi
# The QEMU build VM (buildvm/vm.sh) holds a write lock on the disk file. Say
# WHO holds it rather than letting qemu print an error that names no process.
holder=$(fuser "$DISK" 2>/dev/null | tr -d ' ')
if [ -n "$holder" ]; then
  echo "REFUSING: $DISK is open by pid(s) $holder:" >&2
  ps -o pid=,lstart=,args= -p $holder 2>/dev/null | cut -c1-120 >&2
  echo "  stop the build VM first (bash tup/buildvm/vm.sh stop); it is not stopped blind." >&2
  exit 1
fi

# UEFI needs a writable variable store; a fresh one each run keeps the boot
# path discovery honest. BIOS needs nothing.
FWARGS=()
if [ "$ARCH" = arm64 ]; then
  VARS="$WORK/edk2-vars-$STAMP.fd"
  if [ -f /opt/homebrew/share/qemu/edk2-arm-vars.fd ]; then
    cp /opt/homebrew/share/qemu/edk2-arm-vars.fd "$VARS"
  elif [ -f "$QDIR/share/qemu/edk2-arm-vars.fd" ]; then
    cp "$QDIR/share/qemu/edk2-arm-vars.fd" "$VARS"
  else
    dd if=/dev/zero of="$VARS" bs=1048576 count=64 2>/dev/null
  fi
  FWARGS=(-M virt -cpu "$CPU" -accel "$ACCEL"
          -drive if=pflash,format=raw,readonly=on,file="$FW_CODE"
          -drive if=pflash,format=raw,file="$VARS")
else
  FWARGS=(-M q35 -cpu "$CPU" -accel "$ACCEL")
fi
INVOCATION="${FWARGS[*]:0:6}, disk + firmware only; no -kernel, no -initrd, no -append"

# The receipt claims a disk hash, so take one BEFORE the boot: QEMU is handed
# this file read-write, and every byte it changes afterwards is a byte the hash
# no longer describes. The build disk measured 128849018880 bytes, which is
# tens of minutes of I/O, so a ceiling decides — and when the ceiling refuses,
# the receipt SAYS SO. An omitted line reads as "no hash was needed"; a stated
# refusal reads as what it is. (stat -c first: GNU stat accepts `-f %z` as a
# FILESYSTEM query and prints a block of filesystem statistics with exit 0, so
# the BSD form must be the fallback, never the probe.)
DISK_BYTES=$(stat -c %s "$DISK" 2>/dev/null || stat -f %z "$DISK" 2>/dev/null || echo 0)
case "$DISK_BYTES" in ''|*[!0-9]*) DISK_BYTES=0;; esac
HASH_MAX=${TUP_HASH_MAX_BYTES:-8589934592}       # 8 GiB; raise it to force one
if [ "$DISK_BYTES" -eq 0 ]; then
  DISK_SHA="not computed (size unknown — stat could not read $DISK)"
elif [ "$DISK_BYTES" -gt "$HASH_MAX" ]; then
  DISK_SHA="not computed (size $DISK_BYTES bytes, over the $HASH_MAX-byte ceiling; set TUP_HASH_MAX_BYTES to force it)"
else
  echo "  hashing the disk before boot ($DISK_BYTES bytes)..."
  DISK_SHA=$( { sha256sum "$DISK" 2>/dev/null || shasum -a 256 "$DISK" 2>/dev/null; } | cut -d' ' -f1 )
  [ -n "$DISK_SHA" ] || DISK_SHA="not computed (no sha256sum or shasum on PATH)"
fi
echo "booting tup ($ARCH) from $DISK (nothing else attached), accel $ACCEL"
echo "  disk sha256 $DISK_SHA (before this boot)"
echo "  console -> $LOG"
set +e
if [ "$KEEP" = "--keep" ]; then
  "$QEMU" "${FWARGS[@]}" -m 4G -smp 4 -nographic \
    -drive file="$DISK",format=$FMT,if=virtio,cache=writeback \
    -netdev user,id=n0 -device virtio-net-pci,netdev=n0
  exit $?
fi
( "$QEMU" "${FWARGS[@]}" -m 4G -smp 4 -nographic \
    -drive file="$DISK",format=$FMT,if=virtio,cache=writeback \
    -netdev user,id=n0 -device virtio-net-pci,netdev=n0 \
    > "$LOG" 2>&1 < /dev/null ) &
QPID=$!
# Wait for a kernel panic, a login prompt, or the timeout — whichever first,
# and the ORDER IS THE POINT. One polling window can hold both a prompt and the
# panic that followed it; the panic is the news. Checking the prompt first, as
# this loop used to, broke out of the loop and filed a dead system as BOOTED.
#
# And the prompt is the LITERAL `tup login:`. A bare "login:" appears in a
# foreign banner ("ubuntu login:"), in the complaint of a userspace that never
# reached a prompt ("login: no shell: /bin/sh: not found"), and inside ordinary
# words ("setup login:") — which is what the leading boundary refuses.
T0=$SECONDS
for i in $(seq 1 120); do
  sleep 2
  grep -qE "Kernel panic|Attempted to kill init|not syncing" "$LOG" 2>/dev/null && { VERDICT="PANIC"; break; }
  grep -qE "(^|[^[:alnum:]_-])tup login:" "$LOG" 2>/dev/null && { VERDICT="BOOTED"; break; }
  kill -0 $QPID 2>/dev/null || { VERDICT="QEMU EXITED"; break; }
done
ELAPSED=$((SECONDS - T0))
VERDICT="${VERDICT:-TIMEOUT (240s, no login prompt)}"
kill $QPID 2>/dev/null; wait $QPID 2>/dev/null

# NO `set -e` here, deliberately. The receipt is this run's only durable
# output, and `set -e` used to be switched on immediately before writing it: a
# single non-zero step inside the block — a `tail` on a console log QEMU never
# managed to create — aborted the script mid-write. The transcript was lost,
# the VERDICT never reached stdout, and the caller got exit 1, which is
# indistinguishable from "it did not boot". Every line below carries its own
# fallback instead, and the exit status is the verdict's, on the last line.
OUT="$RECEIPTS/boot-witness-$ARCH-$STAMP.txt"
{
  echo "tup boot witness ($ARCH), $STAMP"
  echo "VERDICT: $VERDICT (after ${ELAPSED}s)"
  echo
  echo "disk      : $DISK"
  echo "disk bytes: $DISK_BYTES"
  echo "disk sha256: ${DISK_SHA:-not computed (the hash step did not run)} (before this boot; a boot mutates the disk)"
  echo "firmware  : $FW_CODE"
  echo "qemu      : $("$QEMU" --version | head -1)"
  echo "host      : $(uname -sm), accel $ACCEL"
  echo "invocation: $INVOCATION; tup booted itself."
  echo
  echo "--- console transcript (last 60 lines) ---"
  tail -60 "$LOG" 2>/dev/null || echo "(no console log at $LOG — QEMU wrote none)"
} > "$OUT"
echo
echo "VERDICT: $VERDICT"
echo "witness: ${OUT#$HERE/}"
[ "$VERDICT" = "BOOTED" ]
