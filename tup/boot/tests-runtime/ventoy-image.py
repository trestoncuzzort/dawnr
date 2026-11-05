#!/usr/bin/env python3
"""Build a Ventoy 1.1.18 test stick image with Ventoy's own installer, on a disposable loop only.

The installer runs with its defaults (MBR, secure-boot support on). Partition 1
is the exFAT filesystem the installer creates; this program then mounts it on
the builder's kernel driver and copies the ISO as an ordinary non-sparse file,
the way the owner will. Every write-capable command is preceded by a check that
the device is the loop whose backing file is the new image.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tarfile

import loop_guard
import remote_check

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))
from tup.boot.inputs import Refusal, canonical, checked_file, digest, file_hash
from tup.remote.policy import owner_name, public_keys
sys.path.insert(0, str(HERE.parents[1] / "sources"))
from source_lock import verify_record

ISO_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,60}\.iso")
FIBMAP, FIGETBSZ = 1, 2  # <linux/fs.h>: _IO(0, 1) and _IO(0, 2)


def fibmap(path):
    """(block size, physical block of every logical block; 0 is a hole). FIBMAP needs root.

    exfat has no FIEMAP, so `filefrag -v` prints no extent table and its FIBMAP mode does not
    say whether a hole sits inside an apparently contiguous run. This asks block by block.
    """
    import fcntl  # Linux only; the module must still import for the Windows unit tests.
    fd = os.open(path, os.O_RDONLY)
    try:
        size = os.fstat(fd).st_size
        block = struct.unpack("i", fcntl.ioctl(fd, FIGETBSZ, bytes(4)))[0]
        return block, [struct.unpack("i", fcntl.ioctl(fd, FIBMAP, struct.pack("i", n)))[0]
                       for n in range(-(-size // block))]
    finally:
        os.close(fd)


def extents(blocks):
    """(extent count, hole count) of a block map: an extent is a run of consecutive physical blocks."""
    runs, holes, last = 0, 0, None
    for physical in blocks:
        if physical == 0:
            holes, last = holes + 1, None
        elif last is None or physical != last + 1:
            runs, last = runs + 1, physical
        else:
            last = physical
    return runs, holes


def populate(partition, mountpoint, iso, name, small_files, guard, run, block_map=fibmap):
    """Mount partition 1 read-write, copy the files, unmount, mount read-only and read everything back.

    guard(mounted) must raise unless the device is the verified loop; `run` runs one external program.
    Returns the filefrag report, the SHA256 of each file read back, the commands run and (block size, extents, holes).
    """
    mountpoint = Path(mountpoint)
    steps = []

    def command(argv, **keywords):
        steps.append(argv)
        return run(argv, **keywords)

    def mount(mode):
        guard(None)
        command(["/usr/bin/mount", "-t", "exfat", "-o", mode + ",nosuid,nodev,noexec", partition, str(mountpoint)])

    mount("rw")
    try:
        guard((partition, str(mountpoint)))
        command(["/usr/bin/cp", "--sparse=never", "--", str(iso), str(mountpoint / name)])
        for relative, data in small_files.items():
            target = mountpoint / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        guard((partition, str(mountpoint)))
        command(["/usr/bin/sync", "-f", str(mountpoint)])
        # While the kernel can still answer for the file: how it is laid out, and whether it has holes.
        report = command(["/usr/sbin/filefrag", "-v", str(mountpoint / name)])
        block, mapped = block_map(mountpoint / name)
    finally:
        guard((partition, str(mountpoint)))
        command(["/usr/bin/umount", str(mountpoint)])
    mount("ro")
    try:
        guard((partition, str(mountpoint)))
        back = {name: file_hash(mountpoint / name)}
        back.update({relative: file_hash(mountpoint / relative) for relative in small_files})
    finally:
        guard((partition, str(mountpoint)))
        command(["/usr/bin/umount", str(mountpoint)])
    guard(None)
    return report, back, steps, (block, *extents(mapped))


def stick_files(iso_name, keys=None, owner=None):
    """What goes on the data partition besides the ISO, as {path relative to the partition: bytes}.

    The ISO itself sits at the top level under iso_name. Headless boot needs no key press: Ventoy's
    documented control plugin names the image to start. The owner's key is at tup-enroll/authorized_keys.
    """
    files = {"ventoy/ventoy.json": canonical({"control": [
        {"VTOY_DEFAULT_IMAGE": "/" + iso_name}, {"VTOY_MENU_TIMEOUT": "2"}, {"VTOY_SECONDARY_TIMEOUT": "2"}]})}
    if keys is not None:
        files["tup-enroll/authorized_keys"] = keys
        if owner is not None:
            files["tup-enroll/owner"] = (owner + "\n").encode()
    return files


def enroll_record(image_sha256, owner, keys, fingerprint):
    """The ENROLL.json dictionary that remote_check.adopt_ventoy_keys reads back beside the image."""
    return {"schema": "tup.runtime-ventoy-enroll.v1", "image_sha256": image_sha256, "owner": owner,
            "authorized_keys_sha256": digest(keys), "owner_key_fingerprint": fingerprint}


def require_whole_file(count, holes):
    """Refuse a block map (see extents) with a hole or no extent at all: Ventoy's GRUB cannot read such a file."""
    if holes or not count:
        raise Refusal("the ISO on the data partition has holes (block map: %d extents, %d holes)" % (count, holes))


def real_run(argv, **keywords):
    done = subprocess.run(argv, check=True, capture_output=True, text=True, timeout=600, **keywords)
    return done.stdout


def build(cache, iso, expected, output, prefix, size_gib, workspace, authorized_keys=None, generate_key=False,
          owner=None):
    # Argument refusals come before the privilege check so they hold for every caller.
    if type(size_gib) is not int or not 1 <= size_gib <= 16:
        raise Refusal("a 1-16 GiB image is required")
    if authorized_keys is not None and generate_key:
        raise Refusal("give an authorized_keys file or ask for a generated test key, not both")
    if owner is not None:
        owner = owner_name(owner)
        if authorized_keys is None and not generate_key:
            raise Refusal("an owner name is only written together with enrollment keys")
    output, iso, prefix = map(lambda p: Path(os.path.abspath(p)), (output, iso, prefix))
    keys = None
    if authorized_keys is not None:
        keys, _ = public_keys(Path(authorized_keys).read_bytes())
    if output.is_symlink() or output.exists():
        raise Refusal("output must be a new directory; earlier images are preserved")
    checked_file(iso, expected)  # A device node or symlink is not a regular file and refuses here.
    if not ISO_NAME.fullmatch(iso.name):
        raise Refusal("the ISO file name must be letters, digits, . _ - and end in .iso")
    if not hasattr(os, "geteuid") or os.geteuid() != 0:
        raise Refusal("root in the disposable builder is required")
    if "exfat" not in Path("/proc/filesystems").read_text().split():
        raise Refusal("the kernel has no exfat driver loaded (modprobe exfat as root first)")
    workspace = loop_guard.workspace_root(workspace)
    if output.resolve() != output or workspace not in output.parents:
        raise Refusal("output must be a fresh directory under the named workspace")
    if iso.stat().st_size + 512 * 1024 * 1024 > size_gib * 1024**3:
        raise Refusal("ISO does not fit the bounded fixture image")
    for name in ("parted", "partprobe"):
        if not (prefix / "usr/sbin" / name).is_file():
            raise Refusal("private, authenticated parted/partprobe prefix is required")
    private = json.loads((HERE / "private-parted.json").read_bytes())
    for name, sha in private["files"].items():
        checked_file(prefix / name, sha)
    if (prefix / "usr/lib/x86_64-linux-gnu/libparted.so.2").resolve() != prefix / "usr/lib/x86_64-linux-gnu/libparted.so.2.0.5":
        raise Refusal("private libparted library link changed")
    record = json.loads((HERE / "ventoy-source.json").read_bytes())
    verified = verify_record(record, cache, HERE / "evidence", None)
    output.mkdir(mode=0o700)
    image = output / "ventoy.raw"
    with image.open("xb") as stream:
        stream.truncate(size_gib * 1024**3)
    st = image.stat()
    identity = [st.st_dev, st.st_ino, st.st_size]
    wrappers = output / "wrappers"; wrappers.mkdir()
    for name in ("parted", "partprobe"):
        shutil.copyfile(HERE / "loop_guard.py", wrappers / name)
        (wrappers / name).chmod(0o700)
    with tarfile.open(cache / record["name"]) as archive:
        archive.extractall(output / "upstream", filter="data")
    upstream = output / "upstream/ventoy-1.1.18"
    enrollment = None
    if generate_key:
        folder = output / "enroll-keys"
        folder.mkdir(mode=0o700)
        remote_check.generate_key(remote_check.TOOLS, remote_check.execute, folder / "owner_key")
        keys = public_keys((folder / "owner_key.pub").read_bytes())[0]
    files = stick_files(iso.name, keys, owner)
    if keys is not None:
        enrollment = {"files": sorted(f for f in files if f.startswith("tup-enroll/")),
                      "authorized_keys_sha256": digest(keys), "owner": owner,
                      "keys": "generated test key" if generate_key else "supplied public keys"}
    env = {"PATH": str(wrappers) + ":" + str(prefix / "usr/sbin") + ":/usr/sbin:/usr/bin:/sbin:/bin",
           "LANG": "C", "LC_ALL": "C", "TUP_LOOP_BACKING": str(image),
           "TUP_LOOP_IDENTITY": json.dumps(identity), "TUP_PARTED_PREFIX": str(prefix),
           "TUP_LOOP_WORKSPACE": str(workspace)}
    loop = None
    try:
        # No caller-supplied device argument exists. The only writable device
        # is allocated here from the fresh, checked regular file.
        if image.resolve() != image or image.stat().st_nlink != 1 or image.stat().st_size != identity[2]:
            raise Refusal("new image identity changed")
        loop = subprocess.run(["/usr/sbin/losetup", "--find", "--show", "--partscan", "--nooverlap", str(image)],
                              check=True, capture_output=True, text=True).stdout.strip()
        env["TUP_LOOP"] = loop
        loop_guard.check(loop, image, identity, workspace)
        (output / "INPUTS.json").write_bytes(canonical({"scope": "disposable-loop-image-only",
            "source": verified, "iso_sha256": expected, "backing_identity": identity,
            "loop": loop, "size_gib": size_gib, "tup_boot_tested": False}))
        # Ventoy2Disk.sh -i: install. Its other options stay at their defaults, which the source
        # (tool/VentoyWorker.sh) states: MBR partition style (-g would make GPT) and secure-boot
        # support enabled (-S would turn it off). The two "y" answers are its two confirmations.
        with (output / "ventoy-install.log").open("wb") as log:
            subprocess.run(["/bin/bash", "Ventoy2Disk.sh", "-i", loop], cwd=upstream,
                           env=env, input=b"y\ny\n", stdout=log, stderr=subprocess.STDOUT,
                           check=True, timeout=180)
        loop_guard.check(loop, image, identity, workspace)
        table = subprocess.run(["/usr/sbin/sfdisk", "--json", str(image)], check=True, capture_output=True).stdout
        (output / "partition-table.json").write_bytes(table)
        partition_table = json.loads(table)["partitiontable"]
        parts = partition_table["partitions"]
        if (partition_table["label"] != "dos" or partition_table["sectorsize"] != 512
                or len(parts) != 2 or parts[0]["start"] != 2048
                or [p["type"].lower() for p in parts] != ["7", "ef"] or not parts[0].get("bootable")
                or parts[1]["size"] != 65536 or parts[1]["start"] != parts[0]["start"] + parts[0]["size"]):
            raise Refusal("upstream did not create its expected MBR layout (NTFS-type data partition, EF 32 MiB partition)")
        first, second = loop + "p1", loop + "p2"
        for part, kind, label in ((first, b"exfat", b"Ventoy"), (second, b"vfat", b"VTOYEFI")):
            found = [subprocess.run(["/usr/sbin/blkid", "-p", "-o", "value", "-s", tag, part],
                                    check=True, capture_output=True).stdout.strip() for tag in ("TYPE", "LABEL")]
            if found != [kind, label]:
                raise Refusal(f"{part} is {found}, not {kind!r} labelled {label!r}")
        efi = subprocess.run(["/usr/bin/mtools", "-c", "mtype", "-i", second, "::/EFI/BOOT/BOOTX64.EFI"],
                             check=True, capture_output=True, env=remote_check.host_environment()).stdout
        if not efi.startswith(b"MZ"):
            raise Refusal("VTOYEFI lacks its EFI fallback program")
        (output / "BOOTX64.EFI").write_bytes(efi)
        for part, number in ((first, "1"), (second, "2")):
            sysfs = Path("/sys/class/block") / Path(part).name
            if sysfs.resolve().parent.name != Path(loop).name or (sysfs / "partition").read_text().strip() != number:
                raise Refusal(f"{part} does not belong to the verified loop")
        mountpoint = output / "mnt"
        mountpoint.mkdir()
        def guard(mounted):
            loop_guard.check(loop, image, identity, workspace, mounted)
        report, back, steps, (block, count, holes) = populate(first, mountpoint, iso, iso.name, files, guard, real_run)
        (output / "filefrag.txt").write_text(report)
        (output / "populate-steps.json").write_bytes(canonical(steps))
        (output / "iso-block-map.json").write_bytes(canonical({"block_bytes": block, "extents": count, "holes": holes}))
        require_whole_file(count, holes)
        expect = {iso.name: expected, **{name: digest(data) for name, data in files.items()}}
        if back != expect:
            raise Refusal("files read back from the data partition differ from what was written")
        loop_guard.check(loop, image, identity, workspace)
        subprocess.run(["/usr/sbin/losetup", "--detach", loop], check=True)
        loop = None
        result = {"scope": "disposable-ventoy-image", "status": "created-unbooted", "version": "1.1.18",
                  "installer_options": ["-i"], "partition_style": "mbr", "secure_boot_support": True,
                  "image_sha256": file_hash(image), "iso_sha256": expected, "size_bytes": image.stat().st_size,
                  "data_partition": "exfat, created by Ventoy's mkexfatfs, written through the builder kernel exfat driver",
                  "payload_path": "/" + iso.name, "iso_extents": count, "iso_holes": holes, "iso_block_bytes": block,
                  "payload_bytes_checked": True, "files_read_back": dict(sorted(back.items())),
                  "enrollment": enrollment, "bootx64_efi_sha256": digest(efi),
                  "mounts_performed": "partition 1 of the new loop only, read-write then read-only, both unmounted",
                  "physical_devices_written": False, "tup_boot_tested": False, "release_eligible": False}
        (output / "RESULT.json").write_bytes(canonical(result))
        if generate_key:
            (output / "enroll-keys/ENROLL.json").write_bytes(canonical(enroll_record(
                result["image_sha256"], owner, keys,
                public_keys((output / "enroll-keys/owner_key.pub").read_bytes())[1][0])))
        return result
    except BaseException as error:
        (output / "FAILED.txt").write_text(str(error) + "\n")
        raise
    finally:
        if loop:
            # Only a mount this program made on its own mountpoint can exist; unmount it, then detach.
            mounted = [line.split()[:2] for line in Path("/proc/mounts").read_text().splitlines()
                       if line.split()[0].startswith(loop)]
            ours = [loop + "p1", str(output / "mnt")]
            if mounted and mounted != [ours]:
                raise Refusal("unexpected mounts on the fixture loop; nothing was unmounted or detached")
            if mounted:
                subprocess.run(["/usr/bin/umount", str(output / "mnt")], check=True)
            loop_guard.check(loop, image, identity, workspace)
            subprocess.run(["/usr/sbin/losetup", "--detach", loop], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    for name in ("cache", "iso", "output", "parted-prefix", "workspace"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--iso-sha256", required=True)
    parser.add_argument("--size-gib", type=int, default=1)
    parser.add_argument("--authorized-keys", type=Path,
                        help="public keys to place at tup-enroll/authorized_keys on the data partition")
    parser.add_argument("--generate-test-key", action="store_true",
                        help="make an Ed25519 test key in OUTPUT/enroll-keys and enroll it, as the SSH test needs")
    parser.add_argument("--owner", help="also write tup-enroll/owner (the guest default account is used without it)")
    args = parser.parse_args()
    try:
        print(json.dumps(build(args.cache, args.iso, args.iso_sha256, args.output, args.parted_prefix,
                               args.size_gib, args.workspace, args.authorized_keys, args.generate_test_key,
                               args.owner), indent=2))
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print("Ventoy fixture refused: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
