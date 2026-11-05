#!/usr/bin/env python3
"""Run the real mount-free repart/metadata fixture in a fresh private directory."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tup.install import image
from tup.boot.inputs import Refusal, canonical, digest, file_hash, inventory


def qualify(directory):
    image.check_platform()
    directory = image.real_path(directory)
    directory.mkdir(mode=0o700)  # Existing work is evidence, never a resume target.
    log_number = 0

    def run(command):
        nonlocal log_number
        log_number += 1
        result = subprocess.run(command, cwd=directory, capture_output=True, timeout=120,
                                env={"PATH": image.PATH, "LANG": "C", "LC_ALL": "C", "MTOOLSRC": "/dev/null"})
        (directory / f"inspect-{log_number:02}.stdout").write_bytes(result.stdout)
        (directory / f"inspect-{log_number:02}.stderr").write_bytes(result.stderr)
        if result.returncode:
            raise Refusal(f"offline inspection command {log_number} failed: {result.returncode}")
        return result.stdout

    def require(condition, message):
        if not condition:
            raise Refusal(message)

    prediction = {"plan_preserves_entire_image": True, "gpt_esp_ext4": True,
                  "metadata": ["bytes", "mode", "numeric_uid_gid", "mtime", "hardlink", "symlink",
                               "user_xattr", "posix_acl", "file_capability"],
                  "efi_file_bytes_preserved": True, "boot_tested": False, "physical_devices_used": False}
    image.write_json(directory / "PREDICTION.json", prediction)
    try:
        source = directory / "source"
        root = source / "root"
        (root / "etc").mkdir(parents=True)
        (source / "esp/EFI/BOOT").mkdir(parents=True)
        payload = root / "etc/payload"
        data = b"tup-repart-offline-fixture\n"
        payload.write_bytes(data)
        os.chown(payload, 12345, 23456)
        payload.chmod(0o4750)
        os.utime(payload, (1700000000, 1700000000))
        os.setxattr(payload, "user.tup-fixture", b"preserved")
        os.link(payload, root / "etc/hardlink")
        (root / "etc/link").symlink_to("payload")
        run(["/usr/bin/setfacl", "-m", "u:12346:r", str(payload)])
        capability = root / "etc/capability"
        capability.write_bytes(b"fixture xattr carrier, not an executable\n")
        run(["/usr/sbin/setcap", "cap_net_bind_service=ep", str(capability)])
        efi = b"fixture-only-not-a-bootable-EFI-program\n"
        (source / "esp/EFI/BOOT/BOOTX64.EFI").write_bytes(efi)
        source_hash = digest(canonical(inventory(source)))
        target = directory / "fixture.raw"
        with target.open("xb") as stream:
            stream.truncate(200 * image.MIB)
        before = file_hash(target)
        state = directory / "state"
        plan = image.plan_image(target, source, source_hash, state)
        require(file_hash(target) == before, "planning wrote to the target image")
        plan_hash = digest(canonical(plan))
        receipt = image.apply_image(state, plan_hash, "APPLY-IMAGE " + plan_hash)
        require(receipt["status"] == "populated-unqualified", "unexpected install receipt")

        # dd extracts already checked GPT extents; no loop devices or mounts.
        # Use existing filesystem tools to inspect their real on-disk metadata.
        for part in plan["partitions"]:
            output = directory / (part["type"] + ".raw")
            run(["/usr/bin/dd", "if=" + str(target), "of=" + str(output), "bs=1M",
                 "iflag=skip_bytes,count_bytes", "skip=" + str(part["offset"]),
                 "count=" + str(part["raw_size"]), "conv=sparse", "status=none"])
            actual = run(["/usr/sbin/blkid", "-p", "-o", "value", "-s", "TYPE", str(output)]).strip()
            require(actual == (b"vfat" if part["type"] == "esp" else b"ext4"), "wrong filesystem type")
        ext4 = directory / "root-x86-64.raw"

        def debug(request):
            return run(["/usr/sbin/debugfs", "-R", request, str(ext4)])

        # debugfs may return zero for nonexistent files: assert its data too.
        observed = debug("stat /etc/payload").decode()
        hardlink = debug("stat /etc/hardlink").decode()
        expected_mode = f"0{payload.stat().st_mode & 0o7777:o}"
        require(re.search(r"Type: regular\s+Mode:\s+" + expected_mode + r"\b", observed), "mode lost")
        require(re.search(r"User:\s+12345\s+Group:\s+23456\b", observed), "numeric ownership lost")
        require("mtime: 0x6553f100:" in observed, "mtime lost")
        require(re.search(r"Links:\s+2\b", observed), "hardlink count lost")
        require(re.search(r"Inode:\s+(\d+)", observed)[1] == re.search(r"Inode:\s+(\d+)", hardlink)[1],
                "hardlink inode differs")
        require(debug("cat /etc/payload") == data, "payload bytes differ")
        require('Fast link dest: "payload"' in debug("stat /etc/link").decode(), "relative symlink lost")
        for name, input_file, input_path, output in (
                ("user.tup-fixture", payload, "/etc/payload", "user-xattr.bin"),
                ("system.posix_acl_access", payload, "/etc/payload", "acl.bin"),
                ("security.capability", capability, "/etc/capability", "capability.bin")):
            debug(f"ea_get -f {output} {input_path} {name}")
            actual = (directory / output).read_bytes()
            if name == "system.posix_acl_access":
                # e2fsprogs returns zero in the unused ID slots of owner/group/
                # mask/other entries; the kernel returns UINT32_MAX. Let the
                # existing kernel ACL implementation validate and canonicalize
                # this representation, without a new ACL parser or any mount.
                normalized = directory / "acl-normalized"
                normalized.touch()
                os.setxattr(normalized, name, actual)
                actual = os.getxattr(normalized, name)
            require(actual == os.getxattr(input_file, name), name + " differs")
        require(run(["/usr/bin/mtype", "-i", str(directory / "esp.raw"), "::/EFI/BOOT/BOOTX64.EFI"]) == efi,
                "EFI fallback bytes differ")
        require(digest(canonical(inventory(source))) == source_hash, "source changed during qualification")
        try:
            image.apply_image(state, plan_hash, "APPLY-IMAGE " + plan_hash)
        except Refusal:
            pass
        else:
            raise Refusal("completed install replay was not refused")
        result = {"schema": "tup.install-image-qualification.v1", "status": "passed",
                  "prediction": prediction, "tool_version": plan["tools"]["version"],
                  "tools": {name: item["sha256"] for name, item in plan["tools"]["files"].items()},
                  "inspection_tools": {name: file_hash(Path(path).resolve()) for name, path in (
                      ("setfacl", "/usr/bin/setfacl"), ("setcap", "/usr/sbin/setcap"),
                      ("dd", "/usr/bin/dd"), ("blkid", "/usr/sbin/blkid"),
                      ("debugfs", "/usr/sbin/debugfs"), ("mtype", "/usr/bin/mtype"))},
                  "adapter_code": plan["code"],
                  "image_bytes": target.stat().st_size, "plan_sha256": plan_hash,
                  "image_sha256": file_hash(target), "source_sha256": source_hash,
                  "recipe_sha256": file_hash(Path(__file__)), "root_contents_attested": False,
                  "release_eligible": False, "physical_install_tested": False, "boot_tested": False,
                  "plan_preserves_entire_image": True, "gpt_esp_ext4": True,
                  "efi_file_bytes_preserved": True,
                  "observed": {key: True for key in prediction["metadata"]}, "replay_refused": True,
                  "logs": {p.name: file_hash(p) for p in directory.glob("inspect-*.std*")}}
        image.write_json(directory / "QUALIFICATION.json", result)
        return result
    except BaseException as error:
        (directory / "FAILED.txt").write_text(str(error) + "\n")
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(qualify(args.workdir), indent=2))
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print("image qualification failed: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
