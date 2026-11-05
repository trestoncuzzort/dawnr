#!/bin/sh
# Dracut initqueue/settled hook; the queue loop sources it with $job set
# (dracut 112 init.sh:197-201, dracut-initqueue.sh:42-46). Ventoy starts this
# ISO's own GRUB from a virtual CD that Linux never sees. If, and only if,
# Ventoy's UEFI handoff variable is present and well formed, mount the one
# partition it names read-only, check the named ISO file and attach it to a
# read-only loop device. Dracut's unchanged root=live:LABEL= rule then finds
# the volume label there. Lifted from dracut 112 70dmsquash-live/iso-scan.sh,
# which mounts every filesystem and attaches a writable loop. The structural
# checks mirror ventoy.py. No disk is written. Not yet run under Ventoy.

VL_VARIABLE=VentoyOsParam-77772020-2e77-6576-6e74-6f792e6e6574
VL_SIGNATURE=20207777772e76656e746f792e6e6574
VL_SYS=/sys
VL_DEV=/dev
VL_DIR=/run/initramfs/tup-ventoy

vl_hex() { od -An -v -tx1 -j"$2" -N"$3" -- "$1" 2> /dev/null | tr -d ' \n'; }

# Is $2 one whole line of $1?
vl_has() {
    case "
$1
" in *"
$2
"*) return 0 ;; esac
    return 1
}

# vl_parse FILE: efivarfs bytes, four attribute bytes then ventoy_os_param.
# Sets VL_GUID VL_DISKSIG VL_PARTITION VL_FSTYPE VL_SIZE VL_PATH, or VL_ERROR
# with the wording ventoy.py uses and a nonzero status.
vl_parse() {
    # 516 byte tests would bury an rd.debug serial log (dracut-lib.sh:22-28).
    command -v debug_off > /dev/null 2>&1 && debug_off
    vl_parse_bytes "$1"
    set -- $?
    command -v debug_on > /dev/null 2>&1 && debug_on
    return "$1"
}

vl_parse_bytes() {
    local f="$1" b i=0 sum=0 part=0 fs=0 size=0 huge=0
    local n=-1 pad=0 utf=0 ctl=0 need=0 lo=128 hi=191
    VL_ERROR="efivarfs handoff must have four attribute bytes plus 512 payload bytes"
    # shellcheck disable=SC2046
    set -- $(od -An -v -tu1 -- "$f" 2> /dev/null)
    [ $# -eq 516 ] || return 1
    for b; do
        [ "$i" -lt 4 ] || sum=$((sum + b))
        case $i in
            45) part=$b ;;
            46) part=$((part + b * 256)) ;;
            47) fs=$b ;;
            48) fs=$((fs + b * 256)) ;;
            433 | 434 | 435 | 436 | 437 | 438) size=$((size + (b << (8 * (i - 433))))) ;;
            # POSIX shell arithmetic is signed: no ISO has 2^48 bytes.
            439 | 440) [ "$b" -eq 0 ] || huge=1 ;;
        esac
        if [ "$i" -ge 49 ] && [ "$i" -lt 433 ]; then
            if [ "$n" -ge 0 ]; then
                [ "$b" -eq 0 ] || pad=1
            elif [ "$b" -eq 0 ]; then
                n=$((i - 49))
                [ "$need" -eq 0 ] || utf=1
            else
                if [ "$b" -lt 32 ] || [ "$b" -eq 127 ] || [ "$b" -eq 92 ]; then ctl=1; fi
                if [ "$need" -gt 0 ]; then
                    if [ "$b" -ge "$lo" ] && [ "$b" -le "$hi" ]; then need=$((need - 1)); else utf=1 need=0; fi
                    lo=128 hi=191
                elif [ "$b" -ge 128 ]; then
                    # Strict UTF-8: no overlong forms, surrogates or values past U+10FFFF.
                    case $b in
                        19[4-9] | 2[01][0-9] | 22[0-3]) need=1 ;;
                        224) need=2 lo=160 ;;
                        237) need=2 hi=159 ;;
                        22[5-9] | 23[0-9]) need=2 ;;
                        240) need=3 lo=144 ;;
                        24[1-3]) need=3 ;;
                        244) need=3 hi=143 ;;
                        *) utf=1 ;;
                    esac
                fi
            fi
        fi
        i=$((i + 1))
    done
    VL_ERROR="invalid Ventoy length/signature/checksum"
    [ "$(vl_hex "$f" 4 16)" = "$VL_SIGNATURE" ] && [ $((sum & 255)) -eq 0 ] || return 1
    VL_ERROR="invalid Ventoy disk/partition/filesystem/image identity"
    VL_GUID=$(vl_hex "$f" 21 16)
    VL_DISKSIG=$(vl_hex "$f" 485 4)
    case $fs in
        0) VL_FSTYPE=exfat ;;
        1) VL_FSTYPE=ntfs ;;
        2) VL_FSTYPE=ext ;;
        3) VL_FSTYPE=xfs ;;
        4) VL_FSTYPE=udf ;;
        5) VL_FSTYPE=fat ;;
        *) return 1 ;;
    esac
    [ "$VL_GUID" != 00000000000000000000000000000000 ] && [ "$part" -ge 1 ] && [ "$part" -le 128 ] \
        && [ "$size" -gt 0 ] && [ "$huge" -eq 0 ] || return 1
    VL_PARTITION=$part
    VL_SIZE=$size
    VL_ERROR="unterminated Ventoy path"
    [ "$n" -ge 0 ] || return 1
    VL_ERROR="nonzero bytes after Ventoy path terminator"
    [ "$pad" -eq 0 ] || return 1
    VL_ERROR="invalid UTF-8 Ventoy ISO path"
    [ "$utf" -eq 0 ] || return 1
    VL_ERROR="unsafe Ventoy ISO path"
    [ "$ctl" -eq 0 ] || return 1
    VL_PATH=$(dd if="$f" bs=1 skip=49 count="$n" 2> /dev/null)
    case "$VL_PATH" in /*.[Ii][Ss][Oo]) ;; *) return 1 ;; esac
    case "$VL_PATH/" in *//* | */./* | */../*) return 1 ;; esac
    VL_ERROR=""
}

# One line for the console and journal now (dracut-lib.sh warn/info) and for
# the emergency shell later, as wait_for_dev does (dracut-dev-lib.sh:79-82).
vl_say() {
    local kind="$1"
    shift
    "$kind" "tup-ventoy-live: $*"
    [ -d "$VL_DIR" ] || return 0
    printf '%s\n' "$*" >> "$VL_DIR/status"
    [ -d "${hookdir-}/emergency" ] || return 0
    printf 'while read -r _l; do warn "tup-ventoy-live: $_l"; done < %s\n' "$VL_DIR/status" \
        > "$hookdir/emergency/79-tup-ventoy-live.sh"
}

# Final: leave the queue (iso-scan.sh:27) and let dracut report the missing root.
vl_stop() {
    VL_STATE=stopped
    vl_say warn "$*; live-root discovery is left to dracut alone"
    rm -f -- "$job"
}

# Copy the handoff variable to $VL_DIR/VentoyOsParam. 1: there is none.
vl_variable() {
    local dir="$VL_SYS/firmware/efi/efivars" rc=1
    [ -d "$VL_SYS/firmware/efi" ] || return 1
    if ! ismounted "$dir"; then
        # systemd mounts efivarfs itself; dracut's own init mounts only /proc,
        # /sys, /dev and /run (init.sh:19-77). Look once, read-only, at a
        # private mount point and leave nothing behind.
        dir="$VL_DIR/efivars"
        if ! { mkdir -p "$dir" && mount -n -t efivarfs -o ro,nosuid,nodev,noexec efivarfs "$dir"; }; then
            rmdir "$dir" "$VL_DIR" 2> /dev/null
            return 2
        fi
    fi
    if [ -f "$dir/$VL_VARIABLE" ]; then
        mkdir -p "$VL_DIR" && cat "$dir/$VL_VARIABLE" > "$VL_DIR/VentoyOsParam" && rc=0 || rc=2
    fi
    if [ "$dir" = "$VL_DIR/efivars" ]; then
        umount "$dir"
        rmdir "$dir" 2> /dev/null
        [ "$rc" -eq 0 ] || rmdir "$VL_DIR" 2> /dev/null
    fi
    return "$rc"
}

vl_props() { udevadm info --query=property --name="$VL_DEV/$1" 2> /dev/null; }

# Print the node ventoy.py select_partition would choose. 1: absent, 2: ambiguous.
# Only the udev database is consulted for other disks. Sector 0 is read only
# from a disk that has a partition labelled VTOYEFI, Ventoy's second partition.
vl_select() {
    local sys disk name psys num props fs want found="" count=0
    case $VL_FSTYPE in
        exfat) want=exfat ;;
        fat) want=vfat ;;
        ext) want="ext2 ext3 ext4" ;;
    esac
    for sys in "$VL_SYS"/class/block/*; do
        [ -f "$sys/partition" ] || continue
        vl_has "$(vl_props "${sys##*/}")" ID_FS_LABEL=VTOYEFI || continue
        # The sysfs parent is the kernel's own disk/partition relation: no
        # sdX1 or nvme0n1p1 name arithmetic.
        disk=$(readlink -f "$sys/..") || continue
        name=${disk##*/}
        [ "$(vl_hex "$VL_DEV/$name" 384 16)" = "$VL_GUID" ] \
            && [ "$(vl_hex "$VL_DEV/$name" 440 4)" = "$VL_DISKSIG" ] || continue
        for psys in "$disk"/*/partition; do
            [ -f "$psys" ] && read -r num < "$psys" && [ "$num" = "$VL_PARTITION" ] || continue
            name=${psys%/partition}
            name=${name##*/}
            case $name in *[!A-Za-z0-9._+-]*) continue ;; esac
            [ -e "$VL_DEV/$name" ] || continue
            props=$(vl_props "$name")
            for fs in $want; do
                vl_has "$props" "ID_FS_TYPE=$fs" || continue
                found="$VL_DEV/$name"
                count=$((count + 1))
            done
        done
    done
    [ "$count" -eq 1 ] || {
        [ "$count" -eq 0 ] && return 1
        return 2
    }
    printf '%s\n' "$found"
}

vl_main() {
    local node type opts iso loop
    # A job that could not leave the queue must not mount or attach twice.
    case ${VL_STATE-} in attached | stopped) return 0 ;; esac
    if [ -z "${VL_STATE-}" ]; then
        vl_variable
        case $? in
            0) ;;
            1)
                # Not started by Ventoy: nothing to do, now or later.
                rm -f -- "$job"
                return 0
                ;;
            *)
                vl_stop "efivarfs cannot be read, so a Ventoy handoff cannot be ruled in or out"
                return 0
                ;;
        esac
        if ! vl_parse "$VL_DIR/VentoyOsParam"; then
            vl_stop "ignoring malformed VentoyOsParam: $VL_ERROR"
            return 0
        fi
        case $VL_FSTYPE in
            exfat | ext | fat) ;;
            *)
                vl_stop "the Ventoy partition is $VL_FSTYPE, which this kernel cannot mount"
                return 0
                ;;
        esac
        VL_STATE=searching
        vl_say info "Ventoy handoff names disk $VL_GUID/$VL_DISKSIG $VL_FSTYPE partition $VL_PARTITION, image $VL_PATH ($VL_SIZE bytes)"
    fi

    node=$(vl_select)
    case $? in
        0) ;;
        1)
            [ "$VL_STATE" = waiting ] && return 0
            VL_STATE=waiting
            vl_say warn "no VTOYEFI-marked disk with that identity and partition yet; retrying until rd.retry expires"
            return 0
            ;;
        *)
            vl_stop "more than one partition matches the Ventoy handoff; refusing to guess"
            return 0
            ;;
    esac

    case $VL_FSTYPE in
        exfat) type=exfat opts=ro ;;
        fat) type=vfat opts=ro,utf8 ;;
        # noload: a read-only ext4 mount would otherwise replay the journal.
        ext) type=ext4 opts=ro,noload ;;
    esac
    mkdir -p "$VL_DIR/media"
    if ! mount -n -t "$type" -o "$opts,nosuid,nodev,noexec" "$node" "$VL_DIR/media"; then
        vl_stop "cannot mount $node read-only as $type"
        return 0
    fi
    iso="$VL_DIR/media$VL_PATH"
    if [ ! -f "$iso" ] || [ "$(readlink -f -- "$iso")" != "$iso" ]; then
        umount "$VL_DIR/media"
        vl_stop "$node has no regular file $VL_PATH (symbolic links are not followed)"
    elif [ "$(stat -c %s -- "$iso")" != "$VL_SIZE" ]; then
        umount "$VL_DIR/media"
        vl_stop "$VL_PATH on $node is not the $VL_SIZE bytes Ventoy recorded"
    elif ! loop=$(losetup -r -f --show -- "$iso"); then
        umount "$VL_DIR/media"
        vl_stop "cannot attach $VL_PATH to a read-only loop device"
    else
        # iso-scan.sh:25 re-adds every device; one change event is enough for
        # 99-live-squash.rules to queue dmsquash-live-root for the label.
        udevadm trigger --action=change --name-match="$loop" > /dev/null 2>&1
        VL_STATE=attached
        vl_say info "attached $loop read-only to $VL_PATH on $node"
        rm -f -- "$job"
    fi
    return 0
}

# Only dracut's initqueue loop sets $job; tests source this file for its functions.
[ -z "${job-}" ] || vl_main
