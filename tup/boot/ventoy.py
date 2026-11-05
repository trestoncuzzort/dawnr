"""Validate captured UEFI Ventoy handoff bytes, without reading/mounting devices.

This host-side parser is a fixture-tested interface, not an installed initramfs
implementation or evidence of Ventoy compatibility.
"""
from __future__ import annotations

import struct
from pathlib import PurePosixPath
import re

from .inputs import Refusal

SIGNATURE = bytes.fromhex("20207777772e76656e746f792e6e6574")
EFI_VARIABLE = "VentoyOsParam-77772020-2e77-6576-6e74-6f792e6e6574"
FILESYSTEMS = {0: "exfat", 1: "ntfs", 2: "ext", 3: "xfs", 4: "udf", 5: "fat"}


def parse_handoff(raw, *, efivarfs=False):
    if efivarfs:
        if len(raw) != 516:
            raise Refusal("efivarfs handoff must have four attribute bytes plus 512 payload bytes")
        raw = raw[4:]
    if len(raw) != 512 or raw[:16] != SIGNATURE or sum(raw) & 255:
        raise Refusal("invalid Ventoy length/signature/checksum")
    guid = raw[17:33]
    partition, filesystem = struct.unpack_from("<HH", raw, 41)
    size = struct.unpack_from("<Q", raw, 429)[0]
    if guid == bytes(16) or not 1 <= partition <= 128 or filesystem not in FILESYSTEMS or not size:
        raise Refusal("invalid Ventoy disk/partition/filesystem/image identity")
    field = raw[45:429]
    if b"\0" not in field:
        raise Refusal("unterminated Ventoy path")
    encoded, padding = field.split(b"\0", 1)
    if any(padding):
        raise Refusal("nonzero bytes after Ventoy path terminator")
    try:
        path = encoded.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise Refusal("invalid UTF-8 Ventoy ISO path") from error
    parts = path.split("/")
    if (not path.startswith("/") or any(part in {"", ".", ".."} for part in parts[1:])
            or "\\" in path or any(ord(c) < 32 or ord(c) == 127 for c in path)
            or not path.lower().endswith(".iso") or str(PurePosixPath(path)) != path):
        raise Refusal("unsafe Ventoy ISO path")
    return {"disk_guid": guid.hex(), "disk_signature": raw[481:485].hex(),
            "partition": partition, "filesystem": FILESYSTEMS[filesystem],
            "iso_path": path, "iso_size": size,
            "reported_disk_size": struct.unpack_from("<Q", raw, 33)[0]}


def select_partition(handoff, candidates):
    """Candidates come from a future sysfs enumerator, never name concatenation.

    Each candidate supplies the parent's first sector, actual partition number,
    filesystem and kernel-exported node path. Device size is deliberately not a
    strict key: Ventoy documents firmware/kernel size differences.
    """
    matches = []
    for item in candidates:
        sector = item["parent_sector"]
        if len(sector) != 512:
            raise Refusal("candidate disk identity sector must be 512 bytes")
        if (sector[384:400].hex() == handoff["disk_guid"]
                and sector[440:444].hex() == handoff["disk_signature"]
                and item["partition"] == handoff["partition"]
                and item["filesystem"] == handoff["filesystem"]):
            node = item["node"]
            if not re.fullmatch(r"/dev/[A-Za-z0-9._+-]+", node):
                raise Refusal("unsafe candidate device node")
            matches.append(node)
    if len(matches) != 1:
        raise Refusal("Ventoy partition absent or ambiguous")
    return matches[0]
