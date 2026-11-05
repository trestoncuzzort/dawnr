#!/usr/bin/env python3
"""Explicit, directory-backed LFS bootstrap; never partitions a device.

Host Python only. The chapter drivers inside chroot remain Bash/coreutils.
See README.md for trust, resource and recovery boundaries.
"""
from __future__ import annotations

import argparse
from collections.abc import Callable
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import stat
import subprocess
import sys
import time


class Refusal(RuntimeError):
    pass


SCHEMA = "tup-native-inputs-v1"
STAGES = ("ch05", "ch06", "ownership", "ch07-inner", "ch08")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]*\Z")
TESTS = "glibc gcc binutils"
NATIVE13_TESTS = "glibc gcc binutils gmp mpfr expect coreutils Python tar kbd bzip2 tcl sqlite"
# Required receipt keys bind each distinct phase to its exact audited block.
NATIVE13_SUITES = {
    "glibc": ("ch08/05-glibc.sh", "006"),
    "gcc": ("ch08/32-gcc.sh", "006"),
    "binutils": ("ch08/22-binutils.sh", "004"),
    "gmp": ("ch08/23-gmp.sh", "005"),
    "mpfr": ("ch08/24-mpfr.sh", "003"),
    "expect": ("ch08/18-expect.sh", "005"),
    "coreutils-root": ("ch08/61-coreutils.sh", "004"),
    "coreutils-user": ("ch08/61-coreutils.sh", "007"),
    "Python": ("ch08/54-Python.sh", "004"),
    "python-temporary": ("ch07/12-Python.sh", "002"),
    "tar": ("ch08/72-tar.sh", "004"),
    "kbd": ("ch08/68-kbd.sh", "005"),
    "bzip2": ("ch08/07-bzip2.sh", "005"),
    "tcl": ("ch08/17-tcl.sh", "003"),
    "sqlite": ("ch08/52-sqlite.sh", "003"),
}
TUP = Path(__file__).resolve().parents[1]
# Suites whose harness names every non-pass result; required-suite.sh accepts
# reviewed suite-exceptions/<package>.allow lists for these and no others.
REVIEWED_EXCEPTION_SUITES = ("glibc", "gcc", "binutils")

# Exact lower-assurance exceptions approved in the committed provenance review.
LFS_PATCH_POLICY = "85c9b35612c90dc4936acdfdf20e36f1b9f3939a49f5f79ef2bd195f14539ea7"
LFS_PATCH_CORROBORATION = "fb2162be4fe417b6f24f423d6ce3e32878646c80335152e6245c0e5c1df0ec6a"
LFS_PATCH_COMMIT = "73171803a34ba79742605e7c4ed31fbdc6cedc07"
REMAINING_SOURCE_POLICY = "536e77f61dd24a3269888645aa33fb4d55dfe5aa3fa0bcf4ac79915da42f33d1"
LFS_PATCH_EXCEPTIONS = {
    'bzip2-1.0.8-install_docs-1.patch': ('35e3bbd9642af51fef2a8a83afba040d272da42d7e3a251d8e43255a7b496702', 'c3b0230c9887bf9617bd358616f5f23b64f423a6'),
    'coreutils-9.11-i18n-1.patch': ('7c2aecf9ae24b87b019595e382b9f41d2c96de7f95abe95ad8cacc7e2ce1bbcc', '18c83d50fd22a4feea0de296b8c38ce4ca45af39'),
    'expect-5.45.4-gcc15-1.patch': ('ab5fc0af9e2e0f80d7623c1a3a3dbeb1da3d8c9134276792199df401f9eb2cec', '7838746c6d94ee9f1ddc9b98965ada7f9b35b7a4'),
    'glibc-2.44-upstream_fixes-3.patch': ('cd3245887c9c2564ef18b8e9ed4046093a575fc91bce00fd82eb931102e4a30e', 'ac8dfe4b2a74d7652256f2d5c90961696786be20'),
    'glibc-fhs-1.patch': ('643552db030e2f2d7ffde4f558e0f5f83d3fabf34a2e0e56ebdb49750ac27b0d', '4ac8d106bbd57efd44e0d507442ab58121baaa99'),
    'kbd-2.10.0-backspace-1.patch': ('8be28dcb11420624a500f2ea4fe975f771174bffee50e54ec8cd295a2dec104e', '8fec17180e17d2e5021b35992a063c0f697c4e57'),
    'Python-3.14.7-openssl_4-1.patch': ('707a0c457192ac2f3b5b8a51481bc5ebd12db22d57c1dbe0256138ee6e070792', '0ab47088abf326d2be8c9273c6a94be1d5c03f88'),
    'tar-1.35-acl_fix-1.patch': ('51cadccfcb2f29cfdb4ec18015360100aa167179a72ece040a6a8612aeec5081', 'ac5d2b703b0df2451a9f98c8c11fb23e64dfa54b'),
}

CH07_ORDER = (
    "01-introduction.sh", "02-changingowner.sh", "03-kernfs.sh", "04-chroot.sh",
    "05-creatingdirs.sh", "06-createfiles.sh", "07-gettext.sh", "08-bison.sh",
    "09-perl.sh", "10-Python.sh", "11-texinfo.sh", "12-util-linux.sh", "13-cleanup.sh",
)
CH07_ORDER_13 = (
    "01-introduction.sh", "02-changingowner.sh", "03-kernfs.sh", "04-chroot.sh",
    "05-creatingdirs.sh", "06-createfiles.sh", "07-gettext.sh", "08-bison.sh",
    "09-perl.sh", "10-zlib.sh", "11-mpdecimal.sh", "12-Python.sh", "13-texinfo.sh",
    "14-util-linux.sh", "15-cleanup.sh",
)
PROFILES = {
    "lfs-12.4-sysv": {"version": "12.4", "init": "sysv", "base": "https://www.linuxfromscratch.org/lfs/view/12.4/",
                       "book": "book-x86_64", "chapter7": CH07_ORDER, "tests": TESTS,
                       "gcc_max": (15, 2, 0), "ld_max": (2, 45, 0), "kernel_min": (5, 4)},
    "lfs-13.1-systemd": {"version": "13.1", "init": "systemd", "base": "https://www.linuxfromscratch.org/lfs/view/13.1-systemd/",
                          "book": "book-x86_64-13.1-systemd", "chapter7": CH07_ORDER_13, "tests": NATIVE13_TESTS,
                          "gcc_max": (16, 2, 0), "ld_max": (2, 47, 0), "kernel_min": (5, 10)},
}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def encoded(value) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode()


def atomic_json(path: Path, value) -> None:
    """A failed fsync/rename is an error, even if the new file is visible."""
    temporary = path.with_name(path.name + ".new")
    with temporary.open("xb") as stream:
        stream.write(encoded(value))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    if os.name == "posix":
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def read_json(path: Path):
    try:
        return json.loads(path.read_bytes().decode("utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise Refusal(f"invalid or missing JSON evidence {path.name}: {exc}") from exc


def plain_path(value: str, *, must_exist=True) -> Path:
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        raise Refusal("paths must be absolute and must not contain '..'")
    if str(path.resolve(strict=must_exist)) != str(path.absolute()):
        raise Refusal("symlink/redirected paths are not supported")
    # Bash book commands contain unquoted $LFS; refuse instead of misrouting them.
    if re.search(r"[\s\x00-\x1f'\"`$\\;|&<>*?{}()]", str(path)):
        raise Refusal("build paths must not contain whitespace or shell metacharacters")
    return path


def validate_workspace(workspace: Path, source: Path, cache: Path) -> None:
    if len(workspace.parts) < 4:
        raise Refusal("choose a dedicated build workspace below a parent directory")
    if os.name == "posix" and workspace.parts[1] in {
        "dev", "proc", "sys", "boot", "etc", "usr", "bin", "sbin", "lib", "lib64"
    }:
        raise Refusal("system paths cannot be build workspaces")
    for other in (source, cache):
        if workspace == other or workspace in other.parents or other in workspace.parents:
            raise Refusal("workspace, source checkout and source cache must be disjoint")
    if not workspace.is_dir():
        raise Refusal("create an empty dedicated workspace directory first")


def validate_control_paths(workspace: Path, *, prepared=False) -> None:
    """Keep the writer lock and stage control paths outside unprivileged reach."""
    for path in (workspace, *workspace.parents):
        plain_path(str(path))
        mode = path.stat()
        if os.name == "posix" and (mode.st_uid != 0 or stat.S_IMODE(mode.st_mode) & 0o022):
            raise Refusal("workspace and its ancestors must be root-owned and not group/world writable")
    if prepared:
        for relative in ("state", "root", "home", "root/tup-build", "root/sources", "root/sources/log"):
            path = plain_path(str(workspace / relative))
            if not path.is_dir():
                raise Refusal("prepared control paths must remain directories")
        for relative in ("state", "root", "root/tup-build"):
            mode = (workspace / relative).stat()
            if os.name == "posix" and (mode.st_uid != 0 or stat.S_IMODE(mode.st_mode) & 0o022):
                raise Refusal("prepared control directories must remain root-owned and protected")


def metadata_for_book(book: Path, profile: str) -> dict:
    policy = PROFILES[profile]
    metadata = {}
    for line in (book / "BOOK-SOURCE").read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            raise Refusal("malformed extracted book metadata")
        key, value = line.split("=", 1)
        if key in metadata:
            raise Refusal("ambiguous extracted book metadata")
        metadata[key] = value
    if metadata.get("arch") != "x86_64":
        raise Refusal("extracted book metadata is not unambiguously x86_64")
    if metadata.get("base") != policy["base"]:
        raise Refusal("unsupported extracted book for the explicitly selected native profile")
    if profile == "lfs-13.1-systemd":
        for key, value in (("version", "13.1"), ("init", "systemd"), ("profile", profile)):
            if metadata.get(key) != value:
                raise Refusal(f"book/profile identity mismatch: {key}")
        for key in ("snapshot_sha256", "audit_profile_sha256"):
            if not SHA256.fullmatch(metadata.get(key, "")):
                raise Refusal(f"missing exact book input digest: {key}")
    return metadata


def archive_metadata(data: bytes) -> str:
    values = {}
    for line in data.decode("utf-8").splitlines():
        if line.startswith("# TUP_TARBALL"):
            match = re.fullmatch(r"# TUP_TARBALL(_[A-Za-z0-9_]+)?=([A-Za-z0-9][A-Za-z0-9._+-]*)", line)
            if not match or match.group(1) in values:
                raise Refusal("duplicate, malformed or unsafe archive metadata")
            values[match.group(1)] = match.group(2)
    return values.get("_x86_64", values.get(None, ""))


def validate_distributor_auth(entry: dict) -> None:
    """Require the exported signed-snapshot linkage, not a bare 'verified'.

    Cryptographic verification belongs to sources/source_lock.py. The caller's
    independently reviewed lock digest authenticates that report to this host.
    """
    auth = entry["authentication"]
    material = entry.get("verification_material", {})
    try:
        snapshot = material["snapshot"]
        signature = snapshot["authentication"]
        fingerprint = "DCD05B71EAB94199527F44ACDB6B8C1F96D8BF6D"
        valid = (material["method"] == "distributor-openpgp-manifest"
                 and material["distributor"] == auth["distributor"] == "Gentoo"
                 and signature["method"] == "openpgp"
                 and signature["primary_fingerprint"] == auth["primary_fingerprint"] == fingerprint
                 and re.fullmatch(r"[A-F0-9]{40}", auth["signing_fingerprint"])
                 and auth["snapshot_sha256"] == snapshot["material"]["sha256"]
                 and auth["manifest_sha256"] == material["manifest"]["sha256"]
                 and auth["manifest_member"] == material["manifest_member"]
                 and re.fullmatch(r"gentoo-[0-9]{8}/[A-Za-z0-9+_.-]+/[A-Za-z0-9+_.-]+/Manifest", auth["manifest_member"])
                 and auth["source_digest_algorithm"] == "sha512"
                 and re.fullmatch(r"[0-9a-f]{128}", auth["source_digest"])
                 and type(auth["source_size"]) is int and auth["source_size"] > 0
                 and signature["approval"]["material"]["url"] == "https://www.gentoo.org/downloads/signatures/"
                 and bool(signature["approval"]["reviewed_at"]) and bool(signature["approval"]["basis"])
                 and bool(material["reviewed_exception"]["reviewed_at"]) and bool(material["reviewed_exception"]["reason"]))
        for item in (snapshot["material"], signature["key"], signature["signature"],
                     signature["approval"]["material"], material["manifest"]):
            valid = valid and SHA256.fullmatch(item["sha256"]) and item["url"].startswith("https://") and bool(item["path"])
        valid = valid and all(SHA256.fullmatch(auth[key]) for key in ("verifier_sha256", "status_sha256"))
    except (KeyError, TypeError, AttributeError):
        valid = False
    if not valid:
        raise Refusal(f"incomplete distributor signature/snapshot/Manifest linkage: {entry['name']}")


def validate_patch_exception(entry: dict) -> None:
    expected = LFS_PATCH_EXCEPTIONS.get(entry["name"])
    auth = entry["authentication"]
    material = entry.get("verification_material", {})
    try:
        valid = (expected is not None and entry["sha256"] == expected[0]
                 and auth["status"] == "accepted-exception"
                 and auth["policy_sha256"] == material["policy"]["sha256"] == LFS_PATCH_POLICY
                 and auth["corroboration_sha256"] == material["corroboration"]["sha256"] == LFS_PATCH_CORROBORATION
                 and auth["git_commit"] == LFS_PATCH_COMMIT and auth["git_blob"] == expected[1]
                 and auth["required_gates"] == ["selected-version-patch-application", "required-package-tests"]
                 and isinstance(auth["assurance"], str) and bool(auth["assurance"].strip())
                 and material["method"] == "reviewed-lfs-patch-exception"
                 and material["policy"]["path"] == "lfs-patch-provenance-review.json"
                 and material["corroboration"]["path"] == "lfs-patch-corroboration-13.1.json")
    except (KeyError, TypeError):
        valid = False
    if not valid:
        raise Refusal(f"patch provenance exception is not an exact approved input: {entry['name']}")


def validate_tar_equivalence(entry: dict) -> None:
    """The one reviewed Make recompression path must retain its signed reference."""
    auth = entry["authentication"]
    material = entry.get("verification_material", {})
    try:
        reference = material["reference_archive"]
        nested = auth["reference_authentication"]
        valid = (entry["name"] == "make-4.4.1.tar.gz"
                 and material["method"] == "distributor-openpgp-tar-equivalence"
                 and reference["path"] == auth["reference_name"] == "make-4.4.1.tar.lz"
                 and reference["sha256"] == auth["reference_sha256"]
                 and SHA256.fullmatch(reference["sha256"])
                 and reference["url"].startswith("https://")
                 and SHA256.fullmatch(auth["uncompressed_sha256"])
                 and type(auth["uncompressed_size"]) is int and auth["uncompressed_size"] > 0
                 and SHA256.fullmatch(auth["decompressor"]["sha256"])
                 and type(auth["source_size"]) is int and auth["source_size"] > 0
                 and nested["status"] == "verified"
                 and nested["trust_class"] == "distributor-openpgp-manifest"
                 and SHA256.fullmatch(nested["evidence_sha256"]))
        validate_distributor_auth({"name": reference["path"], "authentication": nested,
                                   "verification_material": material["reference_authentication"]})
    except (KeyError, TypeError, AttributeError, Refusal):
        valid = False
    if not valid:
        raise Refusal("incomplete or unapproved signed tar equivalence linkage")


def validate_remaining_exception(entry: dict) -> None:
    policy_path = TUP / "native/profiles/lfs-13.1-systemd/REMAINING-SOURCE-PROVENANCE.json"
    if digest(policy_path) != REMAINING_SOURCE_POLICY:
        raise Refusal("reviewed source-exception policy changed")
    records = {item["name"]: item for item in read_json(policy_path)["sources"]}
    auth, material = entry["authentication"], entry.get("verification_material", {})
    try:
        selected = records[entry["name"]]
        valid = (entry["sha256"] == selected["sha256"]
                 and auth["status"] == "accepted-exception"
                 and auth["trust_class"] == material["method"] == selected["proposed_class"]
                 and auth["policy_sha256"] == REMAINING_SOURCE_POLICY
                 and material["policy"] == {"path": "remaining-source-provenance-review.json", "sha256": REMAINING_SOURCE_POLICY}
                 and auth["source_size"] == selected["size"]
                 and isinstance(auth["assurance"], str) and bool(auth["assurance"].strip()))
        if selected["proposed_class"] == "reviewed-distributor-https-exception":
            valid = (valid and auth["distributor"] == "NetBSD pkgsrc"
                     and auth["source_digest_algorithm"] == "sha512"
                     and auth["source_digest"] == selected["published_sha512"]
                     and auth["material_sha256"] == selected["material"]["sha256"]
                     and material["material"] == selected["material"]
                     and auth["required_gates"] == ["required-package-tests"])
        else:
            valid = (valid and auth["inventory_sha256"] == selected["inventory"]["sha256"]
                     and material["inventory"] == selected["inventory"]
                     and material["book_material"] == selected["book_material"]
                     and auth["install_destination"] == "/usr/share/man"
                     and auth["required_gates"] == ["documentation-install-confinement", "documentation-inventory"])
    except (KeyError, TypeError):
        valid = False
    if not valid:
        raise Refusal("source provenance exception is not an exact approved input")


def validate_native_patch_dispositions(dispositions: list, inputs: dict) -> None:
    records = [item for item in dispositions if item.get("disposition") == "fixed-by-native-patch"]
    if {item.get("id") for item in records} != {"sa-13.1-088", "sa-13.1-089"} or len(records) != 2:
        raise Refusal("both reviewed Python backport advisory dispositions are required")
    for item in records:
        if item.get("package") != "python" or item.get("selected_sources") != ["Python-3.14.10.tar.xz"]:
            raise Refusal("unknown native advisory backport selection")
        for field, name in (("native_patch", "python-3.14.10-security-backports.patch"),
                            ("native_review", "PYTHON-BACKPORT-REVIEW.json")):
            relative = "native/profiles/lfs-13.1-systemd/" + name
            record = item.get(field, {})
            value = inputs.get(relative)
            if value is None:
                raise Refusal("native advisory backport input is missing")
            actual = hashlib.sha256(value).hexdigest() if isinstance(value, bytes) else digest(value)
            if record != {"path": "tup/" + relative, "sha256": actual}:
                raise Refusal("native advisory backport review or patch digest changed")


def validate_release_policy(lock: dict) -> None:
    dispositions = lock["advisory_review"]["dispositions"]
    deferred = [item for item in dispositions if item.get("disposition") == "deferred-release-gate"]
    gates = lock.get("release_gates")
    if not deferred:
        if lock.get("lock_purpose") != "production" or lock.get("release_eligible") is not True or gates != []:
            raise Refusal("source lock without deferrals requires explicit production source eligibility")
        return
    if (len(deferred) != 1 or lock.get("lock_purpose") != "build-only"
            or lock.get("release_eligible") is not False or not isinstance(gates, list) or len(gates) != 1):
        raise Refusal("deferred advisory requires the exact build-only release gate")
    item, gate = deferred[0], gates[0]
    if (item.get("id") != "upstream-expat-CVE-2025-66382" or item.get("package") != "expat"
            or item.get("gate_id") != "H55" or item.get("selected_sources") != ["expat-2.10.0.tar.xz"]
            or not isinstance(item.get("reason"), str) or not item["reason"].strip()
            or not isinstance(item.get("evidence"), list) or not item["evidence"]
            or not isinstance(gate, dict) or gate.get("id") != "H55" or gate.get("status") != "open"
            or gate.get("advisories") != ["CVE-2025-66382"]
            or gate.get("required_evidence") != ["host XML exposure review", "workload CPU/time containment demonstrated or qualified upstream fix"]):
        raise Refusal("unknown or incomplete deferred advisory; only the reviewed H55 build gate is supported")


def load_lock(path: Path, expected_sha256: str, book: Path, *,
              profile="lfs-12.4-sysv", effective_inputs=None) -> dict:
    if not SHA256.fullmatch(expected_sha256):
        raise Refusal("an independently authenticated source-lock SHA256 is required")
    if not path.is_file() or path.is_symlink() or digest(path) != expected_sha256:
        raise Refusal("source-lock SHA256 mismatch or missing lock")
    lock = read_json(path)
    if not isinstance(lock, dict) or lock.get("schema") != "tup-source-lock-v1":
        raise Refusal("unsupported source-lock schema")
    if lock.get("architecture") != "x86_64":
        raise Refusal("source lock is not for x86_64")
    if lock.get("book_source_sha256") != digest(book / "BOOK-SOURCE"):
        raise Refusal("source lock belongs to a different book")
    metadata_for_book(book, profile)
    if not isinstance(lock.get("provenance"), str) or not lock["provenance"].strip():
        raise Refusal("source lock must describe its authentication evidence")
    entries = lock.get("sources")
    if not isinstance(entries, list) or not entries:
        raise Refusal("source lock has no sources")
    names = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise Refusal("invalid source record")
        name = entry.get("name", "")
        if not isinstance(name, str) or not NAME.fullmatch(name) or name in names:
            raise Refusal("duplicate or unsafe source basename")
        if not isinstance(entry.get("sha256"), str) or not SHA256.fullmatch(entry["sha256"]):
            raise Refusal(f"invalid pinned SHA256 for {name}")
        if not isinstance(entry.get("url"), str) or not entry["url"].startswith("https://"):
            raise Refusal(f"source URL must use HTTPS: {name}")
        names.add(name)
    if profile == "lfs-13.1-systemd":
        verification = lock.get("source_verification", {})
        if (not isinstance(verification, dict) or verification.get("schema") != "tup-source-verification-v1" or verification.get("status") != "complete"
                or verification.get("source_count") != len(entries)
                or not SHA256.fullmatch(verification.get("report_sha256", ""))):
            raise Refusal("native13 requires a complete exported source-verification report")
        for entry in entries:
            auth = entry.get("authentication", {})
            if not isinstance(auth, dict) or not SHA256.fullmatch(auth.get("evidence_sha256", "")):
                raise Refusal(f"unverified source authentication: {entry['name']}")
            if auth.get("trust_class") == "reviewed-lfs-patch-exception":
                validate_patch_exception(entry)
            elif auth.get("trust_class") in {"reviewed-distributor-https-exception", "reviewed-lfs-documentation-exception"}:
                validate_remaining_exception(entry)
            elif auth.get("status") != "verified" or auth.get("trust_class") not in {"publisher-openpgp", "https-published-sha256", "https-published-sha512", "distributor-openpgp-manifest", "distributor-openpgp-tar-equivalence"}:
                raise Refusal(f"unverified source authentication: {entry['name']}")
            elif auth["trust_class"] == "distributor-openpgp-manifest":
                validate_distributor_auth(entry)
            elif auth["trust_class"] == "distributor-openpgp-tar-equivalence":
                validate_tar_equivalence(entry)
            elif auth["trust_class"] == "https-published-sha512":
                if auth.get("source_digest_algorithm") != "sha512" or not re.fullmatch(r"[0-9a-f]{128}", auth.get("source_digest", "")):
                    raise Refusal("missing published SHA512 source identity")
        advisory = lock.get("advisory_review", {})
        if not isinstance(advisory, dict):
            raise Refusal("native13 advisory review must be a structured object")
        dispositions = advisory.get("dispositions")
        if (advisory.get("status") != "reviewed" or not SHA256.fullmatch(advisory.get("material_sha256", ""))
                or not isinstance(dispositions, list) or not dispositions
                or any(not isinstance(item, dict) or item.get("disposition") not in {"fixed-by-selection", "fixed-by-native-patch", "not-affected", "not-in-base", "deferred-release-gate"}
                       for item in dispositions)):
            raise Refusal("native13 requires a complete reviewed advisory disposition")
        validate_release_policy(lock)
        if effective_inputs is None:
            raise Refusal("native13 source validation requires audited effective recipes")
        validate_native_patch_dispositions(dispositions, effective_inputs)
        audit_input = effective_inputs.get("native/profiles/lfs-13.1-systemd/AUDIT.json")
        if audit_input is None:
            raise Refusal("native13 source validation requires its full reviewed source inventory")
        audit = json.loads(audit_input if isinstance(audit_input, bytes) else audit_input.read_bytes())
        expected_names = audit.get("source_names")
        if (not isinstance(expected_names, list) or len(expected_names) != len(set(expected_names))
                or set(expected_names) != names):
            raise Refusal("source lock differs from the full reviewed native13 source inventory")
    required = set()
    for chapter in ("ch05", "ch06", "ch07", "ch08"):
        for page in (book / chapter).glob("*.sh"):
            archive = archive_metadata(page.read_bytes())
            if effective_inputs is not None:
                key = f"overrides/x86_64/{chapter}/{page.name}"
                override = effective_inputs.get(key)
                if override is not None:
                    replacement = archive_metadata(override if isinstance(override, bytes) else override.read_bytes())
                    archive = replacement or archive
            if archive:
                required.add(archive)
    missing = required - names
    if missing:
        raise Refusal("source lock omits book archives: " + ", ".join(sorted(missing)))
    return lock


def manifest_bytes(lock: dict) -> bytes:
    return "".join(f"{item['sha256']}  {item['name']}\n"
                   for item in sorted(lock["sources"], key=lambda item: item["name"])).encode("ascii")


def verify_sources(directory: Path, lock: dict, *, staged=False) -> None:
    for entry in lock["sources"]:
        path = directory / entry["name"]
        if path.is_symlink() or not path.is_file() or digest(path) != entry["sha256"]:
            raise Refusal(f"missing or mismatched source archive: {entry['name']}")
    if staged:
        allowed = {entry["name"] for entry in lock["sources"]} | {"log", "SHA256-MANIFEST-NATIVE.txt"}
        if {path.name for path in directory.iterdir()} != allowed:
            raise Refusal("unlisted or missing staged source entries; no unpinned patches are accepted")
        manifest = directory / "SHA256-MANIFEST-NATIVE.txt"
        if manifest.is_symlink() or manifest.read_bytes() != manifest_bytes(lock):
            raise Refusal("staged source manifest changed")
        if not (directory / "log").is_dir() or (directory / "log").is_symlink():
            raise Refusal("staged log directory changed")


def tree_files(directory: Path):
    if not directory.is_dir() or directory.is_symlink():
        raise Refusal(f"required input directory missing or redirected: {directory.name}")
    for path in sorted(directory.rglob("*")):
        if "__pycache__" in path.parts:
            continue
        if path.is_symlink():
            raise Refusal(f"symlink in build inputs: {path.name}")
        if path.is_file():
            yield path.relative_to(directory).as_posix(), path
        elif not path.is_dir():
            raise Refusal(f"special file in build inputs: {path.name}")


def raw_blocks(page: bytes) -> dict[str, bytes]:
    """Read only delimiter-bound original commands, never extractor wrappers."""
    blocks = {}
    active = None
    body = []
    for line in page.splitlines(keepends=True):
        start = re.fullmatch(rb"# TUP_BLOCK_BEGIN=([0-9]{3})\n", line)
        end = re.fullmatch(rb"# TUP_BLOCK_END=([0-9]{3})\n", line)
        if start:
            key = start.group(1).decode("ascii")
            if active is not None or key in blocks:
                raise Refusal("ambiguous native book block delimiters")
            active, body = key, []
        elif end:
            if active != end.group(1).decode("ascii"):
                raise Refusal("mismatched native book block delimiters")
            rendered = b"".join(body)
            if not rendered.endswith(b"\n"):
                raise Refusal("native book block lacks its formatter newline")
            # Extraction hashes the displayed command text, then adds exactly
            # one newline before END. Remove that separator only; preserve all
            # actual command whitespace to match EXTRACTION.json block hashes.
            blocks[active] = rendered[:-1]
            active = None
        elif active is not None:
            body.append(line)
        elif line.startswith((b"# TUP_BLOCK_BEGIN", b"# TUP_BLOCK_END")):
            raise Refusal("malformed native book block delimiter")
    if active is not None:
        raise Refusal("unterminated native book block")
    return blocks


def render_native_page(key: str, original: bytes, plan: dict) -> bytes:
    """Compile an explicit reviewed block plan into a named Bash override."""
    if not isinstance(plan, dict):
        raise Refusal(f"native13 page audit must be a structured object: {key}")
    if hashlib.sha256(original).hexdigest() != plan.get("page_sha256"):
        raise Refusal(f"native13 page changed since block audit: {key}")
    blocks = raw_blocks(original)
    decisions = plan.get("blocks")
    if (not isinstance(decisions, list) or any(not isinstance(item, dict) for item in decisions)
            or [item.get("id") for item in decisions] != list(blocks)):
        raise Refusal(f"native13 audit does not cover each block in order: {key}")
    archive = plan.get("archive")
    if archive is not None and (not isinstance(archive, str) or not NAME.fullmatch(archive)):
        raise Refusal(f"invalid native13 archive selection: {key}")
    expected_profile = "native-x86_64-lfs-13.1-systemd-core"
    lines = ["#!/bin/bash", "# Generated from the versioned native13 block audit; original book is unchanged.",
             *([f"# TUP_TARBALL_x86_64={archive}"] if archive else []),
             "set -eEuo pipefail", "umask 022",
             f'[ "${{TUP_PROFILE:-}}" = {shlex.quote(expected_profile)} ] || exit 96',
             '[[ "${TUP_JOBS:-}" =~ ^[1-9][0-9]*$ ]] || exit 96',
             'declare -F tup_json_str >/dev/null || exit 96',
             'native_page_hash=$(sha256sum -- "$TUP_PAGE")',
             f'[ "${{native_page_hash%% *}}" = {shlex.quote(plan["page_sha256"])} ] || exit 96']
    if key.startswith(("ch05/", "ch06/")):
        lines += ['[ "${TUP_NATIVE_CHROOT:-}" = 0 ] && [[ "$LFS" = /* && "$LFS" != / ]] || exit 96',
                  '[ "$(readlink -f -- "$LFS")" = "$LFS" ] || exit 96',
                  '[ "$CONFIG_SITE" = "$LFS/usr/share/config.site" ] || exit 96']
    else:
        lines += ['[ "${TUP_NATIVE_CHROOT:-}" = 1 ] && [ "$LFS" = "" ] || exit 96',
                  '[ -s /tup-build/BUILD-INPUTS.json ] || exit 96']
    if plan.get("required_suite"):
        if plan["required_suite"] not in {*NATIVE13_TESTS.split(), "python-temporary"}:
            raise Refusal(f"unknown required suite policy: {key}")
        lines += ['source /tup-build/native/profiles/lfs-13.1-systemd/required-suite.sh']
    lines += [
        'native_block=none; native_suite=0',
        'native_event() {',
        '  printf \'{"page":%s,"native_block":%s,"native_status":%s,"reason":%s}\\n\' \\',
        '    "$(tup_json_str "$TUP_PAGE_ID")" "$(tup_json_str "$native_block")" \\',
        '    "$(tup_json_str "$1")" "$(tup_json_str "$2")" >> "${RECEIPTS:?}"',
        '}',
        'native_failed() {',
        '  local rc=$?; trap - ERR',
        '  [ "$native_suite" = 0 ] || native_event suite-failed "exit=$rc" || exit 125',
        '  exit "$rc"',
        '}',
        'trap native_failed ERR',
    ]
    for item in decisions:
        block = blocks[item["id"]]
        if hashlib.sha256(block).hexdigest() != item.get("sha256"):
            raise Refusal(f"native13 block changed: {key}/{item['id']}")
        action, reason = item.get("action"), item.get("reason")
        if action not in {"run", "run-suite", "run-build-test", "skip-suite", "omit", "replace", "replace-suite", "delegate"}:
            raise Refusal(f"unclassified native13 block: {key}/{item['id']}")
        if not isinstance(reason, str) or not reason:
            raise Refusal(f"native13 block has no review reason: {key}/{item['id']}")
        kind = item.get("classification")
        if kind not in {"command", "test", "build-test", "diagnostic", "test-setup", "test-cleanup", "optional", "interactive", "example", "platform"}:
            raise Refusal(f"native13 block has no reviewed classification: {key}/{item['id']}")
        if kind == "test" and action not in {"run-suite", "replace-suite", "skip-suite"}:
            raise Refusal(f"native13 test block has no explicit suite disposition: {key}/{item['id']}")
        if kind == "build-test" and action not in {"run-build-test", "replace-suite"}:
            raise Refusal(f"native13 combined build/test cannot be skipped: {key}/{item['id']}")
        lines += [f"native_block={item['id']}; native_suite=0"]
        if action in {"skip-suite", "omit", "delegate"}:
            status = {"skip-suite": "suite-skipped", "omit": "omitted", "delegate": "delegated"}[action]
            lines += [f"native_event {status} {shlex.quote(reason)}"]
            if action == "skip-suite":
                lines += ['tup_receipt_skip_tests "$TUP_PAGE_ID"']
            if action == "delegate":
                lines += ["echo 'native stage belongs to host orchestration; refusing page execution' >&2", "exit 97"]
            continue
        if action in {"run-suite", "run-build-test", "replace-suite"}:
            status = "build-test-started" if kind == "build-test" else "suite-started"
            lines += ["native_suite=1", f"native_event {status} {shlex.quote(reason)}"]
        if action in {"replace", "replace-suite"}:
            replacement = item.get("replacement")
            if not isinstance(replacement, str) or not replacement.strip():
                raise Refusal(f"native13 replacement body missing: {key}/{item['id']}")
            lines += [f"native_event changed {shlex.quote(reason)}", replacement.rstrip("\n")]
        else:
            lines += [block.decode("utf-8")]
        if action in {"run-suite", "run-build-test", "replace-suite"}:
            status = "build-test-complete" if kind == "build-test" else "suite-passed"
            lines += [f"native_event {status} 'command exited zero'", "native_suite=0"]
    return ("\n".join(lines) + "\n").encode("utf-8")


def native13_overrides(source: Path, book: Path) -> dict[str, bytes]:
    path = source / "native/profiles/lfs-13.1-systemd/AUDIT.json"
    audit = read_json(path)
    if (audit.get("schema") != "tup-native-block-audit-v1" or audit.get("profile") != "lfs-13.1-systemd"
            or audit.get("book_source_sha256") != digest(book / "BOOK-SOURCE")):
        raise Refusal("native13 block audit does not match the selected book snapshot")
    orders, plans = audit.get("orders", {}), audit.get("pages", {})
    expected_pages = set()
    result = {}
    for chapter in ("ch05", "ch06", "ch07", "ch08"):
        names = (book / chapter / "ORDER").read_text(encoding="utf-8").splitlines()
        if orders.get(chapter) != names or any(not NAME.fullmatch(name) for name in names):
            raise Refusal(f"native13 chapter order differs from reviewed profile: {chapter}")
        for name in names:
            key = f"{chapter}/{name}"
            expected_pages.add(key)
            if key not in plans:
                raise Refusal(f"missing native13 page audit: {key}")
            result[f"overrides/x86_64/{key}"] = render_native_page(key, (book / key).read_bytes(), plans[key])
    if set(plans) != expected_pages:
        raise Refusal("native13 page audit includes unselected or missing pages")
    required_suites = audit.get("required_suites")
    if required_suites != list(NATIVE13_SUITES):
        raise Refusal("native13 critical suite policy changed without implementation review")
    for package, (page, block_id) in NATIVE13_SUITES.items():
        selected = [item for item in plans[page]["blocks"] if item["id"] == block_id]
        if (not plans[page].get("required_suite") or len(selected) != 1
                or selected[0]["classification"] not in {"test", "build-test"}
                or selected[0]["action"] != "replace-suite"
                or f"native_required_suite {package} " not in selected[0].get("replacement", "")):
            raise Refusal(f"native13 required suite omitted: {package}")
    return result


def input_map(source: Path, book: Path, *, profile="lfs-12.4-sysv") -> dict[str, Path | bytes]:
    files = {"driver.sh": source / "driver.sh"}
    files.update({f"book/{name}": path for name, path in tree_files(book)})
    for relative in (("overrides", "buildlib", "native") if profile == "lfs-12.4-sysv" else ("buildlib", "native")):
        files.update({f"{relative}/{name}": path for name, path in tree_files(source / relative)})
    if not any(name.startswith("buildlib/") for name in files):
        raise Refusal("input-aware driver helpers have not been integrated")
    # The native override wins the existing x86_64 lookup before shared overrides.
    if profile == "lfs-12.4-sysv":
        native_overrides = source / "native/profiles/x86_64/overrides"
        files.update({f"overrides/{name}": path for name, path in tree_files(native_overrides)})
    else:
        files.update(native13_overrides(source, book))
    order = (book / "ch07/ORDER").read_text(encoding="utf-8").splitlines()
    if tuple(order) != PROFILES[profile]["chapter7"]:
        raise Refusal("chapter 7 inner selection changed; review the chroot crossing")
    selected = order[4:12] if profile == "lfs-12.4-sysv" else order[4:]
    for name in selected:
        if not NAME.fullmatch(name):
            raise Refusal("unsafe book page name")
        files[f"book/ch07-inner/{name}"] = book / "ch07" / name
    files["book/ch07-inner/ORDER"] = ("\n".join(selected) + "\n").encode()
    return files


def map_identity(files: dict[str, Path | bytes]) -> dict:
    result = {}
    for name, item in sorted(files.items()):
        if isinstance(item, bytes):
            data = item
        else:
            if not item.is_file() or item.is_symlink():
                raise Refusal(f"missing or redirected input: {name}")
            data = item.read_bytes()
        if name.endswith((".sh", "ORDER")) and b"\r" in data:
            raise Refusal(f"CRLF build input: {name}; use a Linux/LF checkout")
        result[name] = hashlib.sha256(data).hexdigest()
    return result


def checked(command: list[str], *, timeout: int = 60, **kwargs) -> str:
    try:
        result = subprocess.run(command, check=True, text=True, stdout=subprocess.PIPE, timeout=timeout,
                                stderr=subprocess.STDOUT, **kwargs)
    except (OSError, subprocess.SubprocessError) as exc:
        output = getattr(exc, "stdout", "") or ""
        raise Refusal(f"command failed: {command[0]}: {output[-1500:] or exc}") from exc
    return result.stdout.strip()


def host_identity(workspace: Path, jobs: int, memory_mib: int, free_gib: int, *, profile="lfs-12.4-sysv") -> dict:
    policy = PROFILES[profile]
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise Refusal("native LFS requires a Linux x86_64 host; Git Bash is not a build host")
    if os.geteuid() != 0:
        raise Refusal("preflight/prepare/build require root in the disposable Linux builder")
    if not 1 <= jobs <= (os.cpu_count() or 1) or memory_mib < 4096 or jobs * 1024 > memory_mib:
        raise Refusal("jobs exceed CPU count or the 1024 MiB-per-job planning floor")
    mem = dict(re.findall(r"^(MemTotal|MemAvailable):\s+(\d+)",
                          Path("/proc/meminfo").read_text(), re.M))
    if int(mem.get("MemAvailable", 0)) < (memory_mib + 512) * 1024:
        raise Refusal("available host memory is below build budget plus 512 MiB reserve")
    if free_gib < 20 or shutil.disk_usage(workspace).free < free_gib * 1024**3:
        raise Refusal("insufficient free workspace space (minimum reservation is 20 GiB)")
    filesystem = checked(["findmnt", "-n", "-o", "FSTYPE", "-T", str(workspace)])
    if filesystem != "ext4":
        raise Refusal("first native builder supports ext4 workspaces only")
    if Path("/bin/sh").resolve() != Path("/bin/bash").resolve():
        raise Refusal("LFS requires /bin/sh to resolve to bash; configure the disposable host")
    tools = {}
    commands = {"bash": ["--version"], "ld": ["--version"], "bison": ["--version"],
                "gawk": ["--version"], "gcc": ["--version"], "g++": ["--version"],
                "make": ["--version"], "makeinfo": ["--version"], "tar": ["--version"],
                "gzip": ["--version"], "xz": ["--version"], "patch": ["--version"],
                "m4": ["--version"], "perl": ["-v"], "diff": ["--version"],
                "find": ["--version"], "grep": ["--version"], "sed": ["--version"],
                "sha256sum": ["--version"], "sort": ["--version"], "sync": ["--version"],
                "unshare": ["--version"],
                "runuser": ["--version"], "mount": ["--version"], "chroot": ["--version"],
                "python3": ["--version"], "bc": ["--version"], "awk": ["--version"], "yacc": ["--version"],
                "findmnt": ["--version"], "mountpoint": ["--version"], "id": ["--version"],
                "readlink": ["--version"], "chown": ["--version"], "tee": ["--version"],
                "cmp": ["--version"], "mktemp": ["--version"], "mv": ["--version"],
                "cp": ["--version"], "install": ["--version"], "stat": ["--version"]}
    # The transaction driver adds requirements beyond the historical book:
    # inherit_errexit needs Bash 4.4; named-file sync and sync -f need coreutils 8.24.
    minimums = {"bash": (4, 4), "ld": (2, 13, 1), "bison": (2, 7), "gawk": (4, 0, 1),
                "gcc": (5, 4), "g++": (5, 4), "make": (4, 0), "makeinfo": (5, 0),
                "tar": (1, 22), "gzip": (1, 3, 12), "xz": (5, 0, 0),
                "patch": (2, 5, 4), "m4": (1, 4, 10), "diff": (2, 8, 1),
                "find": (4, 2, 31), "sed": (4, 1, 5), "sort": (8, 24),
                "sha256sum": (8, 24), "sync": (8, 24)}
    for name, args in commands.items():
        executable = shutil.which(name)
        if executable is None:
            raise Refusal(f"missing host dependency: {name}")
        output = checked([executable, *args])
        first = next((line for line in output.splitlines() if line.strip()), "")
        match = re.search(r"\b(\d+)\.(\d+)(?:\.(\d+))?", first)
        version = tuple(int(value or 0) for value in match.groups()) if match else ()
        if name in minimums and version < minimums[name]:
            raise Refusal(f"host dependency too old or unrecognized: {name}")
        if name in {"sort", "sha256sum", "sync"} and "GNU coreutils" not in first:
            raise Refusal(f"GNU coreutils implementation required: {name}")
        if (name in {"gcc", "g++"} and version > policy["gcc_max"]) or (name == "ld" and version > policy["ld_max"]):
            raise Refusal(f"{name} exceeds the {profile} tested range; review before using")
        tools[name] = {"version": first, "sha256": digest(Path(executable).resolve())}
    if "GNU Awk" not in checked(["awk", "--version"]) or "Bison" not in checked(["yacc", "--version"]):
        raise Refusal("awk/yacc must select gawk/bison")
    if Path(shutil.which("bash")).resolve() != Path("/bin/bash").resolve():
        raise Refusal("PATH bash must be the /bin/bash used by the stage runner")
    kernel = tuple(int(x) for x in re.match(r"(\d+)\.(\d+)", platform.release()).groups())
    if kernel < policy["kernel_min"]:
        raise Refusal(f"{profile} requires host Linux >= {'.'.join(map(str, policy['kernel_min']))}")
    # Compile+link without creating persistent outputs or accepting silence as success.
    checked(["g++", "-x", "c++", "-o", "/dev/null", "-"], input="int main(){}\n")
    checked(["unshare", "--mount", "--pid", "--fork", "--kill-child", "--propagation", "private", "true"])
    return {"kernel": platform.release(), "architecture": "x86_64", "tools": tools,
            "requirements_policy": profile + "; native Bash/coreutils transaction requirements; not production-release approval"}


def verify_host_tools(host: dict) -> None:
    for name, record in host["tools"].items():
        executable = shutil.which(name)
        if executable is None or digest(Path(executable).resolve()) != record["sha256"]:
            raise Refusal(f"host tool changed during build: {name}")


def build_identity(args, files: dict, lock: dict, host: dict) -> dict:
    profile = getattr(args, "profile", "lfs-12.4-sysv")
    return {"schema": SCHEMA, "profile": profile, "architecture": "x86_64",
            "inputs": map_identity(files), "source_lock_sha256": args.lock_sha256,
            "sources": sorted(lock["sources"], key=lambda item: item["name"]), "host": host,
            "source_policy": {"lock_purpose": lock.get("lock_purpose", "historical"),
                              "release_eligible": lock.get("release_eligible", False),
                              "release_gates": lock.get("release_gates", []),
                              "advisory_review": lock.get("advisory_review", {})},
            "policy": {"jobs": args.jobs, "memory_budget_mib": args.memory_mib,
                       "test_jobs": min(args.jobs, 4), "tests": PROFILES[profile]["tests"],
                       "build_user": args.build_user, "last_stage": "ch08"}}


def require_identity(actual: dict, expected: dict) -> None:
    if actual != expected:
        raise Refusal("build inputs changed; use a fresh workspace after reviewing the change")


def verify_staged(root: Path, inputs: dict) -> None:
    staged = root / "tup-build"
    names = {name for name, _ in tree_files(staged)} - {"BUILD-INPUTS.json"}
    if names != set(inputs["inputs"]):
        raise Refusal("staged input file set changed")
    for name, expected in inputs["inputs"].items():
        if digest(staged / name) != expected:
            raise Refusal(f"staged build input changed: {name}")
        expected_mode = 0o755 if name.endswith(".sh") else 0o644
        if os.name == "posix" and ((staged / name).stat().st_mode & 0o777) != expected_mode:
            raise Refusal(f"staged input permissions changed: {name}")
    if (staged / "BUILD-INPUTS.json").read_bytes() != encoded(inputs):
        raise Refusal("staged build identity changed")


def stage_record(state: Path, stage: str, inputs_sha256: str) -> bool:
    receipt = state / f"{stage}.json"
    if receipt.is_symlink():
        raise Refusal(f"{stage} receipt is redirected")
    if not receipt.exists():
        return False
    record = read_json(receipt)
    if not isinstance(record, dict) or record.get("status") != "complete":
        raise Refusal(f"{stage} has an interrupted/failed attempt; inspect evidence and use a fresh workspace")
    if record.get("inputs_sha256") != inputs_sha256:
        raise Refusal(f"{stage} belongs to changed inputs")
    log = state / f"{stage}.log"
    if record.get("exit_code") != 0 or log.is_symlink() or not log.is_file() or digest(log) != record.get("log_sha256"):
        raise Refusal(f"{stage} log is missing or changed")
    return True


def verify_suite_evidence(root: Path, *, require_complete=False) -> dict:
    """Recheck the retained files referenced by committed per-page receipts."""
    receipts = root / "sources/log/receipts.jsonl"
    if not receipts.exists():
        if require_complete:
            raise Refusal("critical suite receipts are missing")
        return {}
    if receipts.is_symlink():
        raise Refusal("critical suite receipts are redirected")
    suites = {}
    for line in receipts.read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        record = event.get("native_suite_evidence")
        if record is None:
            continue
        package = record.get("package")
        if (package not in NATIVE13_SUITES or package in suites
                or record.get("status") != "passed" or record.get("exit_code") != 0):
            raise Refusal("invalid, failed or duplicate required suite evidence")
        relative = record.get("directory", "")
        page, block = NATIVE13_SUITES[package]
        receipt_page = page.replace("ch07/", "ch07-inner/").removesuffix(".sh")
        expected_directory = "native-suites/" + receipt_page.replace("/", "-") + "-" + block
        if relative != expected_directory:
            raise Refusal("unsafe required suite evidence directory")
        directory = root / "sources/log" / relative
        files = dict(tree_files(directory))
        manifest = files.pop("files.sha256", None)
        if manifest is None or digest(manifest) != record.get("manifest_sha256"):
            raise Refusal("required suite evidence manifest changed")
        expected = {}
        for row in manifest.read_text(encoding="utf-8").splitlines():
            match = re.fullmatch(r"([0-9a-f]{64})  (.+)", row)
            if not match or match[2] in expected:
                raise Refusal("invalid required suite file manifest")
            expected[match[2]] = match[1]
        if set(expected) != set(files) or any(digest(files[name]) != value for name, value in expected.items()):
            raise Refusal("retained required suite files are missing, changed or unlisted")
        # Named non-pass results are acceptable only as the exact reviewed list
        # staged with this build; a failed command needs at least one of them.
        reviewed, command_exit = record.get("reviewed_exceptions", 0), record.get("command_exit_code", 0)
        if type(reviewed) is not int or type(command_exit) is not int or reviewed < 0:
            raise Refusal("invalid required suite exception record")
        if reviewed:
            allow = root / "tup-build/native/profiles/lfs-13.1-systemd/suite-exceptions" / (package + ".allow")
            observed, unexplained = files.get("nonpass.observed"), files.get("nonpass.unexplained")
            if (package not in REVIEWED_EXCEPTION_SUITES or allow.is_symlink() or not allow.is_file()
                    or record.get("exceptions_sha256") != digest(allow) or observed is None or unexplained is None
                    or len(observed.read_text(encoding="utf-8").splitlines()) != reviewed
                    or unexplained.stat().st_size):
                raise Refusal("required suite exceptions differ from the reviewed staged list")
        elif command_exit != 0 or record.get("exceptions_sha256") is not None:
            raise Refusal("required suite command failed without reviewed exceptions")
        suites[package] = record
    if require_complete and set(suites) != set(NATIVE13_SUITES):
        raise Refusal("not every required native13 suite has retained passing evidence")
    return suites


def export_core_completion(state: Path, root: Path, inputs_hash: str, profile: str) -> dict:
    """Called only after fresh validation of every completed core stage."""
    stages = {}
    for stage in STAGES:
        if not stage_record(state, stage, inputs_hash):
            raise Refusal("cannot export an incomplete core")
        stages[stage] = {"receipt_sha256": digest(state / f"{stage}.json"),
                         "log_sha256": digest(state / f"{stage}.log")}
    suites = verify_suite_evidence(root, require_complete=True) if profile == "lfs-13.1-systemd" else {}
    inputs = read_json(state / "BUILD.json")
    if hashlib.sha256(encoded(inputs)).hexdigest() != inputs_hash:
        raise Refusal("core export input identity changed")
    source_policy = inputs["source_policy"]
    log = root / "sources/log"
    evidence = {"schema": "tup-native-core-completion-v1", "scope": "ch05-ch08-core-only",
                "profile": profile, "inputs_sha256": inputs_hash, "stages": stages,
                "driver_receipts_sha256": digest(log / "receipts.jsonl"),
                "driver_state_sha256": digest(log / "driver.state"),
                "driver_snapshot": (log / "driver.v2/current").read_text().strip(),
                "required_suites": suites, "validated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "source_lock_sha256": inputs["source_lock_sha256"],
                "source_lock_purpose": source_policy["lock_purpose"],
                "source_release_eligible": source_policy["release_eligible"],
                "release_eligible": False, "release_gates": source_policy["release_gates"],
                "advisory_review_sha256": hashlib.sha256(encoded(source_policy["advisory_review"])).hexdigest(),
                "source_assurance": {
                    "verified_sources": sum(entry.get("authentication", {}).get("status") == "verified" for entry in inputs["sources"]),
                    "accepted_patch_exceptions": sum(entry.get("authentication", {}).get("trust_class") == "reviewed-lfs-patch-exception" for entry in inputs["sources"]),
                    "accepted_other_source_exceptions": sum(entry.get("authentication", {}).get("trust_class") in {"reviewed-distributor-https-exception", "reviewed-lfs-documentation-exception"} for entry in inputs["sources"]),
                    "patch_exception_policy_sha256": LFS_PATCH_POLICY if profile == "lfs-13.1-systemd" else None,
                    "remaining_source_exception_policy_sha256": REMAINING_SOURCE_POLICY if profile == "lfs-13.1-systemd" else None},
                "root_identity": {"device": root.stat().st_dev, "inode": root.stat().st_ino},
                "claims": {"bootable": False, "remote_access": False, "root_contents_attested": False}}
    atomic_json(state / "CORE-COMPLETION.json", evidence)
    return evidence


def run_stage(state: Path, stage: str, command: list[str], inputs_sha256: str,
              validate_command: list[str] | None = None, *,
              postcondition: Callable[[], None] | None = None, validation_only=False) -> None:
    if stage_record(state, stage, inputs_sha256):
        if validate_command is not None:
            # Validation hashes a complete chapter's sources and retained logs.
            # Keep it bounded without imposing the short host-tool probe limit.
            checked(validate_command, timeout=900, stdin=subprocess.DEVNULL)
        if postcondition is not None:
            postcondition()
        print(f"{stage}: verified prior stage receipt", flush=True)
        return
    if validation_only:
        raise Refusal(f"{stage} is incomplete; validation never executes package commands")
    receipt = state / f"{stage}.json"
    started = time.monotonic()
    record = {"stage": stage, "status": "running", "inputs_sha256": inputs_sha256,
              "started_utc": dt.datetime.now(dt.timezone.utc).isoformat()}
    atomic_json(receipt, record)
    log = state / f"{stage}.log"
    print(f"{stage}: running; log {log}", flush=True)
    with log.open("xb") as stream:
        try:
            result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=stream,
                                    stderr=subprocess.STDOUT, check=False)
            code = result.returncode
        except OSError as exc:
            stream.write((str(exc) + "\n").encode())
            code = 127
        stream.flush()
        os.fsync(stream.fileno())
    if code == 0 and postcondition is not None:
        # Leave the durable running intent intact if the full source/input
        # check fails. A child's zero exit cannot authorize stage completion.
        postcondition()
    record.update({"status": "complete" if code == 0 else "failed", "exit_code": code,
                   "seconds": round(time.monotonic() - started, 3), "log_sha256": digest(log)})
    atomic_json(receipt, record)
    if code:
        raise Refusal(f"{stage} failed with exit {code}; later stages were not started")


def prepare(args, files, lock, inputs, uid, gid):
    workspace = args.workspace
    if set(workspace.iterdir()) != {workspace / ".native-lock"}:
        raise Refusal("prepare requires an empty workspace; never infer ownership from a marker")
    state = workspace / "state"
    state.mkdir(mode=0o700)
    atomic_json(state / "preparing.json", {"status": "running", "inputs": inputs})
    root = workspace / "root"
    root.mkdir(mode=0o755)
    for name in ("etc", "var", "usr/bin", "usr/lib", "usr/sbin", "lib64", "tools", "sources/log"):
        (root / name).mkdir(parents=True, exist_ok=True)
    for name in ("bin", "lib", "sbin"):
        (root / name).symlink_to(f"usr/{name}")
    for name in ("usr", "usr/bin", "usr/lib", "usr/sbin", "var", "etc", "lib64", "tools", "sources/log"):
        os.chown(root / name, uid, gid)
    (root / "sources").chmod(0o1777)
    home = workspace / "home"
    home.mkdir(mode=0o755)
    os.chown(home, uid, gid)
    for entry in lock["sources"]:
        shutil.copyfile(args.source_cache / entry["name"], root / "sources" / entry["name"])
        (root / "sources" / entry["name"]).chmod(0o644)
    (root / "sources/SHA256-MANIFEST-NATIVE.txt").write_bytes(manifest_bytes(lock))
    staged = root / "tup-build"
    for name, item in files.items():
        target = staged / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(item if isinstance(item, bytes) else item.read_bytes())
        target.chmod(0o755 if name.endswith(".sh") else 0o644)
    atomic_json(staged / "BUILD-INPUTS.json", inputs)
    verify_sources(root / "sources", lock, staged=True)
    verify_staged(root, inputs)
    atomic_json(state / "BUILD.json", inputs)
    atomic_json(state / "preparing.json", {"status": "complete"})
    print("prepared explicit target root; no build or device operation has run")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "prepare", "build", "validate"))
    parser.add_argument("--profile", choices=tuple(PROFILES), required=True,
                        help="explicit book/init and reviewed native recipe policy")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--source-cache", required=True)
    parser.add_argument("--source-lock", required=True)
    parser.add_argument("--lock-sha256", required=True)
    parser.add_argument("--source", default=str(TUP))
    parser.add_argument("--book", help="explicit extracted book directory; must match the selected profile")
    parser.add_argument("--build-user", default="lfs")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--memory-mib", type=int, default=4096)
    parser.add_argument("--free-gib", type=int, default=40)
    parser.add_argument("--through", choices=("ch06", "ch08"), default="ch08")
    args = parser.parse_args(argv)
    try:
        if platform.system() == "Linux":
            # The host runner and early chroot use system tools, so inventory
            # those exact tools regardless of the invoking shell or venv.
            os.environ["PATH"] = "/usr/sbin:/usr/bin:/sbin:/bin"
            os.environ["LC_ALL"] = "C"
            os.environ["LANG"] = "C"
        for name in ("workspace", "source_cache", "source_lock", "source"):
            setattr(args, name, plain_path(getattr(args, name)))
        args.book = plain_path(args.book or str(args.source / PROFILES[args.profile]["book"]))
        validate_workspace(args.workspace, args.source, args.source_cache)
        validate_workspace(args.workspace, args.book, args.source_cache)
        if not NAME.fullmatch(args.build_user) or args.build_user == "root":
            raise Refusal("build user must be a dedicated unprivileged account")
        files = input_map(args.source, args.book, profile=args.profile)
        lock = load_lock(args.source_lock, args.lock_sha256, args.book, profile=args.profile, effective_inputs=files)
        verify_sources(args.source_cache, lock)
        host = host_identity(args.workspace, args.jobs, args.memory_mib, args.free_gib, profile=args.profile)
        validate_control_paths(args.workspace)
        import pwd
        account = pwd.getpwnam(args.build_user)
        if account.pw_uid == 0:
            raise Refusal("build user cannot have UID 0")
        checked(["runuser", "-u", args.build_user, "--", "test", "-x", str(args.workspace)])
        os.umask(0o022)
        inputs = build_identity(args, files, lock, host)
        if args.action == "preflight":
            print(json.dumps({"status": "ready-for-prepare", "inputs_sha256": hashlib.sha256(encoded(inputs)).hexdigest(),
                              "memory_budget_enforcement": "external Linux builder limit required",
                              "last_supported_stage": "ch08; not a bootable or remotely accessible OS"}, indent=2))
            return 0
        # Single writer, including prepare. Never remove another process's lock.
        lockdir = args.workspace / ".native-lock"
        lockdir.mkdir(mode=0o700)
        try:
            if args.action == "prepare":
                # prepare's emptiness check excludes only the lock we just created.
                if set(args.workspace.iterdir()) != {lockdir}:
                    raise Refusal("prepare requires an empty dedicated workspace")
                prepare(args, files, lock, inputs, account.pw_uid, account.pw_gid)
                return 0
            state, root = args.workspace / "state", args.workspace / "root"
            validate_control_paths(args.workspace, prepared=True)
            require_identity(read_json(state / "BUILD.json"), inputs)
            if read_json(state / "preparing.json") != {"status": "complete"}:
                raise Refusal("preparation was interrupted")
            inputs_hash = hashlib.sha256(encoded(inputs)).hexdigest()

            def validate_all_inputs():
                validate_control_paths(args.workspace, prepared=True)
                current_files = input_map(args.source, args.book, profile=args.profile)
                load_lock(args.source_lock, args.lock_sha256, args.book, profile=args.profile, effective_inputs=current_files)
                verify_host_tools(host)
                verify_sources(args.source_cache, lock)
                verify_sources(root / "sources", lock, staged=True)
                require_identity(read_json(state / "BUILD.json"), build_identity(args, current_files, lock, host))
                verify_staged(root, inputs)
                if args.profile == "lfs-13.1-systemd":
                    verify_suite_evidence(root)

            for stage in STAGES:
                validate_all_inputs()
                runner = str(root / "tup-build/native/run-stage.sh")
                command = ["bash", runner, stage, str(root), args.build_user,
                           str(args.workspace / "home"), str(args.jobs), args.profile]
                if stage in ("ch07-inner", "ch08"):
                    command = ["unshare", "--mount", "--pid", "--propagation", "private", "--fork", "--kill-child", *command]
                validation = None if stage == "ownership" else [*command, "--validate"]
                run_stage(state, stage, command, inputs_hash, validation,
                          postcondition=validate_all_inputs, validation_only=args.action == "validate")
                if stage == args.through:
                    break
            if args.through == "ch08":
                export_core_completion(state, root, inputs_hash, args.profile)
            print(f"LFS core through {args.through} validated; native boot, installer and networking remain unbuilt")
        finally:
            if lockdir.exists():
                lockdir.rmdir()
        return 0
    except (Refusal, OSError, KeyError, ValueError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
