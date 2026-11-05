#!/bin/bash
# External test host only. No kernel/initrd injection or physical disk. Only the
# *-ssh kinds have a network: one loopback host forward to the guest's port 22.
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd)
TUP=$(cd -- "$HERE/../.." && pwd)
die() { printf '%s\n' "$*" >&2; exit 1; }
usage='usage: uefi.sh KIND MEDIA SHA256 FRESH_OUTPUT [OPTION VALUE]...
  KIND    host-smoke|ventoy-host-smoke|tup-iso|ventoy-tup|installed-disk|tup-iso-ssh|ventoy-tup-ssh
  OPTION  --memory-mib 512-4096  --cpus 1-4  --boot-budget 60-3600   (not for the smoke kinds)
          --ssh-port 1024-65535  --owner NAME  --ssh-wait 30-1800  --poweroff-budget 30-900   (*-ssh only)
          --enroll-keys DIR   (ventoy-tup-ssh only; default: enroll-keys next to the image)'
[ "$#" -ge 4 ] || die "$usage"
kind=$1 media=$2 expected=$3 output=$4
shift 4
memory=4096 cpus=4 budget=600 remote=0 port=2222 owner='' ssh_wait=300 off_budget=180 keys_dir=''
case "$kind" in
    host-smoke|ventoy-host-smoke) memory=256 cpus=1 budget=60;;
    tup-iso|ventoy-tup|installed-disk) ;;
    # The builder has 6 GiB in all; the remote kinds default to a third of it.
    tup-iso-ssh|ventoy-tup-ssh) memory=2048 cpus=2 remote=1;;
    *) die 'unknown test kind';;
esac
number() {
    [[ "$2" =~ ^[1-9][0-9]{0,5}$ ]] && [ "$2" -ge "$3" ] && [ "$2" -le "$4" ] ||
        die "$1 must be an integer from $3 to $4"
}
while [ "$#" -gt 0 ]; do
    [ "$#" -ge 2 ] || die "option $1 needs a value"
    case "$kind:$1" in
        *host-smoke:*) die 'the host smoke kinds are fixed and take no options';;
        *:--memory-mib) number "$1" "$2" 512 4096; memory=$2;;
        *:--cpus) number "$1" "$2" 1 4; cpus=$2;;
        *:--boot-budget) number "$1" "$2" 60 3600; budget=$2;;
        *-ssh:--ssh-port) number "$1" "$2" 1024 65535; port=$2;;
        *-ssh:--owner) owner=$2;; # remote_check.py applies the enrollment account rule.
        *-ssh:--ssh-wait) number "$1" "$2" 30 1800; ssh_wait=$2;;
        *-ssh:--poweroff-budget) number "$1" "$2" 30 900; off_budget=$2;;
        ventoy-tup-ssh:--enroll-keys) keys_dir=$2;;
        *) die "unknown option for $kind: $1";;
    esac
    shift 2
done
[[ "$expected" =~ ^[0-9a-f]{64}$ ]] || die 'expected media SHA256 is required'
[ -f "$media" ] && [ ! -L "$media" ] || die 'media must be a regular file, never a device or symlink'
[ ! -e "$output" ] && [ ! -L "$output" ] || die 'output must be a new directory; earlier runs are preserved'
media=$(realpath -e -- "$media")
[ "$(sha256sum -- "$media" | cut -d' ' -f1)" = "$expected" ] || die 'media digest mismatch'
sha256sum --check --strict "$HERE/host-tools.sha256"
[ "$remote" -eq 0 ] || sha256sum --check --strict "$HERE/remote-tools.sha256"
mkdir -m700 -- "$output" # A new directory is mandatory; preserve earlier runs.
output=$(realpath -e -- "$output")
mkdir -- "$output/tmp"
cp -- /usr/share/OVMF/OVMF_VARS_4M.fd "$output/OVMF_VARS.fd"
serial=$output/serial.log
qpid=
cleanup() {
    if [ -n "$qpid" ]; then
        kill "$qpid" 2>/dev/null || true
        wait "$qpid" 2>/dev/null || true
    fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP
network=(-nic none)
if [ "$remote" -eq 1 ]; then
    # Ephemeral Ed25519 keys, made inside this run's directory, and for the direct
    # ISO the read-only TUP-ENROLL image (MBR, one FAT32 partition). Through Ventoy
    # the enrollment is already on the one stick: its owner key pair comes from the
    # directory the image was built with. This also refuses a path QEMU or ssh
    # would re-parse.
    prepare=(prepare --output "$output" --port "$port")
    [ -z "$owner" ] || prepare+=(--owner "$owner")
    [ "$kind" != ventoy-tup-ssh ] || prepare+=(--keys-from "${keys_dir:-$(dirname -- "$media")/enroll-keys}" --media-sha256 "$expected")
    /usr/bin/python3 "$HERE/remote_check.py" "${prepare[@]}" > "$output/remote-prepare.log" 2>&1 ||
        die "enrollment media refused: $(tail -n 1 "$output/remote-prepare.log")"
    # QEMU 8.2 manual, -netdev user: with restrict=on the guest "will not be able
    # to contact the host and no guest IP packets will be routed over the host to
    # the outside. This option does not affect any explicitly set forwarding
    # rules." libslirp answers DHCP before it applies that restriction. The one
    # forward below is therefore the only way in, and nothing leads out. romfile=
    # keeps an unpinned PXE option ROM out of the firmware's boot path.
    network=(-netdev "user,id=net0,ipv6=off,restrict=on,hostfwd=tcp:127.0.0.1:$port-10.0.2.15:22"
             -device virtio-net-pci,netdev=net0,romfile=
             -qmp "unix:$output/qmp.sock,server=on,wait=off")
    [ "$kind" != tup-iso-ssh ] ||
        network+=(-drive "if=none,id=enroll,format=raw,readonly=on,file=$output/remote/enroll.img")
fi
# KVM was actually probed and returned ENODEV on the qualified host. Do not
# silently switch accelerators: resource/timing claims depend on this choice.
args=(-machine pc-q35-8.2,accel=tcg -cpu max -m "$memory" -smp "$cpus"
      -nodefaults -device VGA -display none -monitor none "${network[@]}" -no-reboot
      -serial "file:$serial"
      -drive if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd
      -drive "if=pflash,format=raw,file=${output//,/,,}/OVMF_VARS.fd")
if [[ "$kind" == ventoy-* ]]; then
    args+=(-device qemu-xhci,id=xhci
           -drive "if=none,id=bootmedia,format=raw,snapshot=on,file=${media//,/,,}"
           -device usb-storage,bus=xhci.0,drive=bootmedia,removable=on,bootindex=1)
    # No second stick: the owner's enrollment is a directory on this one.
elif [ "$kind" = installed-disk ]; then
    args+=(-drive "if=none,id=bootmedia,format=raw,snapshot=on,file=${media//,/,,}"
           -device virtio-blk-pci,drive=bootmedia,bootindex=1)
else
    args+=(-drive "if=none,id=bootmedia,format=raw,media=cdrom,readonly=on,file=${media//,/,,}"
           -device ide-cd,drive=bootmedia,bootindex=1)
    [ "$kind" != tup-iso-ssh ] || args+=(-device virtio-blk-pci,drive=enroll)
fi
{
    printf 'scope: external-%s\nmedia_sha256: %s\n' "$kind" "$expected"
    printf 'accelerator: tcg\nmemory_mib: %s\nvcpus: %s\ntimeout_seconds: %s\n' "$memory" "$cpus" "$budget"
    if [ "$remote" -eq 1 ]; then
        printf 'ssh_forward: 127.0.0.1:%s -> 10.0.2.15:22 (the only host forward; restrict=on)\n' "$port"
        printf 'owner: %s\nssh_wait_seconds: %s\npoweroff_budget_seconds: %s\n' "${owner:-owner (guest default)}" "$ssh_wait" "$off_budget"
    fi
    printf 'argv: '; printf '%q ' /usr/bin/qemu-system-x86_64 "${args[@]}"; printf '\n'
    sha256sum "$HERE/uefi.sh" "$TUP/boot_verdict.sh" "$HERE/host-tools.sha256"
    [ "$remote" -eq 0 ] || sha256sum "$HERE/remote_check.py" "$HERE/remote-tools.sha256"
    [ "$kind" != tup-iso-ssh ] || sha256sum "$output/remote/enroll.img"
    [ "$kind" != ventoy-tup-ssh ] || sha256sum "$output/remote/owner_key.pub"
} > "$output/INPUTS.txt"
export TMPDIR=$output/tmp
/usr/bin/qemu-system-x86_64 "${args[@]}" > "$output/qemu.stdout" 2> "$output/qemu.stderr" &
qpid=$!
start=$SECONDS
ok=0 verify_ran=0
if [[ "$kind" == *host-smoke ]]; then
    while kill -0 "$qpid" 2>/dev/null && [ $((SECONDS - start)) -lt "$budget" ]; do sleep 1; done
    if ! kill -0 "$qpid" 2>/dev/null; then
        if wait "$qpid" && grep -qF 'TUP-HOST-EFI-SMOKE' "$serial"; then ok=1; fi
        qpid=
    fi
    verdict='HOST GRUB EFI SMOKE FAILED (not a TUP boot test)'
    [ "$ok" -ne 1 ] || verdict='HOST GRUB EFI SMOKE PASSED (not a TUP boot test)'
else
    # Reuse the existing prompt/panic/liveness/settle rule without copying it.
    . "$TUP/boot_verdict.sh"
    seen=0 seen_at=0 watched=0
    while [ $((SECONDS - start)) -lt "$budget" ]; do
        sleep 1
        tup_saw_panic "$serial" && break
        if [ "$seen" -eq 0 ] && tup_saw_prompt "$serial"; then
            seen=1; seen_at=$SECONDS
        fi
        [ "$seen" -eq 0 ] || watched=$((SECONDS - seen_at))
        tup_guest_alive "$qpid" || break
        [ "$seen" -eq 0 ] || [ "$watched" -lt 12 ] || break
    done
    if verdict=$(tup_boot_verdict "$serial" "$qpid" "$seen" "$watched" 12 "$budget"); then ok=1; fi
fi
if [ "$remote" -eq 1 ]; then
    # The serial verdict above stays one named check among the others; it is
    # never replaced by a login. A guest that is alive and has not panicked is
    # still examined when the prompt was missed, for the evidence, and still fails.
    boot_verdict=$verdict ok=0 powered_off=0 qemu_exit=-1 off_seconds=0 logged=0
    if tup_guest_alive "$qpid" && ! tup_saw_panic "$serial"; then
        verify_ran=1 requested=0
        /usr/bin/python3 "$HERE/remote_check.py" verify --output "$output" --port "$port" \
            --owner "${owner:-owner}" --wait "$ssh_wait" > "$output/remote-verify.log" 2>&1 || requested=$?
        # 0: all checks passed; 3: some failed. Either way the guest was asked to
        # power off (the owner's sudo, else QMP system_powerdown) and is watched.
        if [ "$requested" -eq 0 ] || [ "$requested" -eq 3 ]; then
            off_start=$SECONDS
            while tup_guest_alive "$qpid" && [ $((SECONDS - off_start)) -lt "$off_budget" ]; do sleep 1; done
            off_seconds=$((SECONDS - off_start))
            if ! tup_guest_alive "$qpid"; then
                qemu_exit=0
                wait "$qpid" || qemu_exit=$?
                qpid=
                powered_off=1
            fi
        fi
    fi
    # -no-reboot makes a guest reset end QEMU as well; only the kernel's own
    # line tells a power-off from a reset.
    ! grep -qF 'reboot: Power down' "$serial" || logged=1
fi
elapsed=$((SECONDS - start))
cleanup
qpid=
# The post-run rechecks come before the machine-readable result is written, and
# their outcome is a required check in it: RESULT.json must never say VERIFIED
# for a run this script then rejects. A failed recheck is recorded, not fatal.
inputs_unchanged=1
{
    if [ "$(sha256sum -- "$media" | cut -d' ' -f1)" = "$expected" ]; then
        printf 'media: unchanged\n'
    else
        printf 'media: CHANGED during the test\n'
        inputs_unchanged=0
    fi
    sha256sum --check --strict "$HERE/host-tools.sha256" 2>&1 || inputs_unchanged=0
    [ "$remote" -eq 0 ] || sha256sum --check --strict "$HERE/remote-tools.sha256" 2>&1 || inputs_unchanged=0
} > "$output/host-recheck.txt"
if [ "$remote" -eq 1 ]; then
    if verdict=$(/usr/bin/python3 "$HERE/remote_check.py" conclude --output "$output" --port "$port" \
            --kind "$kind" --media-sha256 "$expected" --memory-mib "$memory" --cpus "$cpus" \
            --boot-verdict "$boot_verdict" --verify-ran "$verify_ran" --powered-off "$powered_off" \
            --power-down-logged "$logged" --qemu-exit="$qemu_exit" --poweroff-seconds "$off_seconds" \
            --poweroff-budget "$off_budget" --inputs-unchanged "$inputs_unchanged" \
            2> "$output/remote-conclude.log"); then ok=1; fi
    [ -n "$verdict" ] || { ok=0; verdict="TUP REMOTE ACCESS FAILED (no result could be concluded; serial verdict: $boot_verdict)"; }
elif [ "$inputs_unchanged" -ne 1 ]; then
    verdict="$verdict -- REJECTED: the media or a pinned tool changed during the test (see host-recheck.txt)"
fi
[ "$inputs_unchanged" -eq 1 ] || { ok=0; printf '%s\n' 'media or a pinned tool changed during the test' >&2; }
evidence=("$serial" "$output/qemu.stdout" "$output/qemu.stderr" "$output/INPUTS.txt" "$output/OVMF_VARS.fd")
for extra in RESULT.json remote/CHECKS.json remote/PREPARED.json remote/enroll.img remote-verify.log host-recheck.txt; do
    [ ! -f "$output/$extra" ] || evidence+=("$output/$extra")
done
{
    printf 'verdict: %s\nelapsed_seconds: %s\n' "$verdict" "$elapsed"
    if [ "$remote" -eq 1 ]; then
        printf 'serial_boot_verdict: %s\nenvironment: external VM (QEMU, OVMF)\naccelerator: tcg\n' "$boot_verdict"
        printf 'hardware_tested: false\nmachine_readable: RESULT.json\n'
    fi
    printf 'scope: %s\nremote_access_tested: %s\n' "$kind" "$([ "$verify_ran" -eq 1 ] && echo true || echo false)"
    printf 'physical_boot_tested: false\nrelease_eligible: false\n'
    sha256sum "${evidence[@]}"
} > "$output/RESULT.txt.pending"
sync "$output/RESULT.txt.pending"
mv -- "$output/RESULT.txt.pending" "$output/RESULT.txt"
if ! sync "$output"; then
    mv -- "$output/RESULT.txt" "$output/RESULT.uncertain.txt"
    die 'result durability failed'
fi
printf '%s\n' "$verdict"
[ "$ok" -eq 1 ]
