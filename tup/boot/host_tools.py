#!/usr/bin/env python3
"""Build and qualify the three offline, separately authenticated boot host tools.

This is a trusted-source builder, not a sandbox. It never consumes a TUP root,
mounts a filesystem, installs a firmware entry, or writes a block device.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import sys
import tarfile

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tup.boot.inputs import Refusal, canonical, checked_file, digest, file_hash, load_json, tree_hash
from tup.boot.assemble import GRUB_TEXT_OPTIONS, check_tools, execute, sync_directory, sync_tree
from tup.sources import source_lock

RECIPES = {
    "dracut": ("dracut-112.tar.gz", "dracut-112"),
    "grub": ("grub-2.14.tar.xz", "grub-2.14"),
    "squashfs": ("squashfs-tools-4.7.5.tar.gz", "squashfs-tools-4.7.5"),
}
PATH = "/usr/sbin:/usr/bin:/sbin:/bin"


def authenticated_sources(catalog, expected, cache, evidence):
    """Reuse the core verifier without altering its 94-source inventory/lock."""
    checked_file(catalog, expected)
    data = load_json(catalog)
    if data.get("schema") != "tup.boot-source-catalog.v1":
        raise Refusal("unsupported boot source catalog")
    records = data.get("sources", [])
    names = [r.get("name") for r in records]
    required = {item[0] for item in RECIPES.values()}
    if len(names) != len(set(names)) or set(names) != required:
        raise Refusal("host catalog must contain exactly the three selected host sources")
    context = {"requested": {}}
    for record in records:
        auth = record.get("authentication", {})
        if record.get("disposition") != "retain" or not auth.get("approval", auth.get("reviewed_exception")):
            raise Refusal("each host source needs a retained, reviewed authentication policy")
        for item in (auth, auth.get("corroboration", {})):
            if item.get("method") == "distributor-openpgp-manifest":
                identity = digest(source_lock.encoded(item.get("snapshot", {})))
                context["requested"].setdefault(identity, set()).add(item.get("manifest_member"))
    verified = []
    for record in records:
        result = source_lock.verify_record(record, cache, evidence, Path("/usr/bin/gpg"), context)
        if result.get("status") != "verified":
            raise Refusal("boot host sources cannot use a provenance exception")
        verified.append(result)
    return {"catalog_sha256": expected, "sources": verified,
            "verifier_sha256": file_hash(Path(source_lock.__file__)),
            "checked_at": datetime.now(timezone.utc).isoformat()}


def fresh_workspace(path):
    path = Path(path).absolute()
    if (len(path.parts) < 4 or path.exists() or path.is_symlink() or
            not re.fullmatch(r"/[A-Za-z0-9_./+-]+", str(path)) or path != path.resolve()):
        raise Refusal("choose a fresh absolute workspace without links, whitespace or shell metacharacters")
    if path.parts[1] in {"usr", "etc", "bin", "sbin", "boot", "dev", "proc", "sys", "run"}:
        raise Refusal("system directories cannot be host build workspaces")
    path.mkdir()  # Exclusive creation is the concurrent-invocation boundary.
    return path


def unpack(archive, destination, top):
    destination.mkdir()
    with tarfile.open(archive) as source:
        members = source.getmembers()
        seen = set()
        for member in members:
            name = PurePosixPath(member.name)
            if (name.is_absolute() or ".." in name.parts or not name.parts or
                    name.parts[0] != top or str(name) in seen or
                    not (member.isdir() or member.isfile() or member.issym() or member.islnk())):
                raise Refusal("source archive has unsafe, duplicate or unexpected members")
            seen.add(str(name))
        # Python's data filter additionally rejects escaping link targets and
        # extraction through previously created symlinks. Require Python >=3.12.
        source.extractall(destination, members=members, filter="data")
    result = destination / top
    if not result.is_dir() or result.is_symlink():
        raise Refusal("source archive lacks its selected top-level directory")
    return result


def commands(component, source, prefix, staging, jobs):
    """Every install is staged, including upstream absolute directory defaults."""
    if component == "dracut":
        return [(source, ["./configure", f"--prefix={prefix}", f"--sysconfdir={prefix}/etc",
                          f"--systemdsystemunitdir={prefix}/lib/systemd/system",
                          f"--bashcompletiondir={prefix}/share/bash-completion/completions",
                          f"--pkgconfigdatadir={prefix}/share/pkgconfig",
                          "--disable-documentation", "--disable-dracut-cpio", "--configprofile=generic"]),
                (source, ["make", f"-j{jobs}"]),
                (source, ["make", "install", f"DESTDIR={staging}"])]
    if component == "grub":
        return [(source, ["./configure", f"--prefix={prefix}", f"--sysconfdir={prefix}/etc",
                          "--target=x86_64", "--with-platform=efi", "--disable-efiemu", "--disable-werror"]),
                (source, ["make", f"-j{jobs}"]),
                (source, ["make", "install", f"DESTDIR={staging}"])]
    if component == "squashfs":
        directory = source / "squashfs-tools"
        return [(directory, ["make", f"-j{jobs}", "XATTR_SUPPORT=1", "ZSTD_SUPPORT=1"]),
                (directory, ["make", "install", f"INSTALL_PREFIX={staging}{prefix}",
                             "XATTR_SUPPORT=1", "ZSTD_SUPPORT=1"])]
    raise Refusal("unknown host component")


def publish_staged(staging, prefix):
    staged_prefix = staging / prefix.relative_to("/")
    if not staged_prefix.is_dir() or staged_prefix.is_symlink():
        raise Refusal("upstream install did not produce the dedicated prefix")
    for path in staging.rglob("*"):
        if path in staged_prefix.parents:
            continue
        if path != staged_prefix and staged_prefix not in path.parents:
            raise Refusal("upstream install attempted a path outside its dedicated prefix")
        if path.is_symlink():
            resolved = path.resolve()
            if resolved != staged_prefix and staged_prefix not in resolved.parents:
                raise Refusal("installed symlink escapes the dedicated prefix")
    for path in staged_prefix.rglob("*"):
        target = prefix / path.relative_to(staged_prefix)
        if (target.exists() or target.is_symlink()) and not (path.is_dir() and target.is_dir() and not target.is_symlink()):
            raise Refusal("host components collide in the installation prefix")
    shutil.copytree(staged_prefix, prefix, dirs_exist_ok=True, symlinks=True)


def qualify(prefix, directory, jobs, env, run=execute):
    """Real, mount-free tests: metadata roundtrip and an unbooted EFI smoke ISO."""
    directory.mkdir()
    log = directory / "qualification.log"
    def call(argv):
        return run(argv, cwd=directory, env=env, log=log)
    versions = {}
    for name, flag, expected in (("dracut", "--version", r"\b112\b"),
                                 ("grub-mkrescue", "--version", r"\b2\.14\b"),
                                 ("mksquashfs", "-version", r"\b4\.7\.5\b")):
        versions[name] = call([prefix / "bin" / name, flag]).strip()
        if not re.search(expected, versions[name]):
            raise Refusal(f"built {name} version does not match the selected source")
    fixture = directory / "input"
    fixture.mkdir(mode=0o750)
    payload = fixture / "payload"
    payload.write_bytes(bytes(range(256)) * 100)
    payload.chmod(0o4750)
    os.chown(payload, 12345, 23456)
    # chown clears set-ID bits; the exact intended mode is applied afterwards.
    payload.chmod(0o4750)
    os.setxattr(payload, "user.tup-qualification", b"preserved")
    os.link(payload, fixture / "hardlink")
    (fixture / "relative-link").symlink_to("payload")
    for path in (fixture, payload, fixture / "relative-link"):
        os.utime(path, (1700000000, 1700000000), follow_symlinks=False)
    squash = directory / "fixture.squashfs"
    call([prefix / "bin/mksquashfs", fixture, squash, "-noappend", "-comp", "zstd",
          "-processors", str(jobs), "-mem", "128M", "-no-progress", "-one-file-system"])
    details = call([prefix / "bin/unsquashfs", "-s", squash])
    if not re.search(r"Compression\s+zstd", details):
        raise Refusal("SquashFS fixture is not zstd-compressed")
    restored = directory / "restored"
    call([prefix / "bin/unsquashfs", "-processors", str(jobs), "-no-progress", "-d", restored, squash])
    output = restored / "payload"
    status = output.stat()
    if (file_hash(output) != file_hash(payload) or status.st_mode & 0o7777 != 0o4750 or
            (status.st_uid, status.st_gid, int(status.st_mtime)) != (12345, 23456, 1700000000) or
            os.getxattr(output, "user.tup-qualification") != b"preserved" or
            status.st_ino != (restored / "hardlink").stat().st_ino or
            os.readlink(restored / "relative-link") != "payload"):
        raise Refusal("SquashFS roundtrip changed content, ownership, mode, xattr, time or links")
    iso_tree = directory / "iso-tree"
    (iso_tree / "boot/grub").mkdir(parents=True)
    config = iso_tree / "boot/grub/grub.cfg"
    config.write_text("serial --unit=0 --speed=115200\nterminal_output serial\necho TUP-HOST-EFI-SMOKE\nhalt\n")
    call([prefix / "bin/grub-script-check", config])
    iso = directory / "host-efi-smoke.iso"
    call([prefix / "bin/grub-mkrescue", *GRUB_TEXT_OPTIONS, f"--directory={prefix}/lib/grub/x86_64-efi",
          f"--output={iso}", f"--label-font={prefix}/share/grub/themes/starfield/dejavu_12.pf2",
          "--xorriso=/usr/bin/xorriso", iso_tree, "-volid", "TUP_HOST_SMOKE"])
    report = call(["/usr/bin/xorriso", "-indev", iso, "-report_el_torito", "plain"])
    if not re.search(r"El Torito boot img\s*:.*UEFI", report):
        raise Refusal("GRUB smoke ISO has no UEFI El Torito image")
    return {"versions": versions, "squashfs_metadata_roundtrip": "passed",
            "squashfs_sha256": file_hash(squash), "efi_iso_sha256": file_hash(iso),
            "efi_el_torito": "present", "booted": False,
            "dracut_target_sysroot": "not-tested-with-TUP", "log_sha256": file_hash(log)}


def build(args):
    if platform.system() != "Linux" or platform.machine() != "x86_64" or os.geteuid() != 0:
        raise Refusal("this metadata-qualification recipe requires root in an isolated Linux x86_64 builder")
    if sys.version_info < (3, 12) or not 1 <= args.jobs <= 16:
        raise Refusal("Python >=3.12 and an explicit 1..16 job budget are required")
    verification = authenticated_sources(args.catalog, args.catalog_sha256, args.cache, args.evidence)
    workspace = fresh_workspace(args.workspace)
    prefix = workspace / "prefix"
    logs = workspace / "logs"
    logs.mkdir()
    env = {"PATH": PATH, "LANG": "C", "LC_ALL": "C", "TZ": "UTC", "HOME": str(workspace),
           "CFLAGS": "", "CPPFLAGS": "", "CXXFLAGS": "", "LDFLAGS": "", "MAKEFLAGS": ""}
    try:
        (workspace / "SOURCES.json").write_bytes(canonical(verification))
        packages = execute(["dpkg-query", "-W", "-f=${binary:Package} ${Version} ${Architecture}\n"],
                           cwd=workspace, env=env, log=logs / "host-packages.log")
        (workspace / "HOST-PACKAGES.txt").write_text(packages)
        for component, (archive_name, top) in RECIPES.items():
            print(f"building {component}; log: {logs / (component + '.log')}", flush=True)
            archive = args.cache / archive_name
            expected = next(r["sha256"] for r in verification["sources"] if r["name"] == archive_name)
            checked_file(archive, expected)
            source = unpack(archive, workspace / (component + "-source"), top)
            staging = workspace / (component + "-install")
            staging.mkdir()
            for cwd, command in commands(component, source, prefix, staging, args.jobs):
                execute(command, cwd=cwd, env=env, log=logs / (component + ".log"))
            publish_staged(staging, prefix)
            checked_file(archive, expected)
        env["PATH"] = f"{prefix}/bin:{prefix}/sbin:" + PATH
        env["dracutbasedir"] = str(prefix / "lib/dracut")
        qualification = qualify(prefix, workspace / "qualification", args.jobs, env)
        checked_file(args.catalog, args.catalog_sha256)
        for record in verification["sources"]:
            checked_file(args.cache / record["name"], record["sha256"])
        font = prefix / "share/grub/themes/starfield/dejavu_12.pf2"
        lock = {"schema": "tup.boot-tools.v1", "versions": {"dracut": "112", "grub": "2.14"},
                "commands": {}, "path": [str(prefix / "bin"), "/usr/sbin", "/usr/bin", "/sbin", "/bin"],
                "support_trees": [], "grub_modules": str(prefix / "lib/grub/x86_64-efi"),
                "dracut_base": str(prefix / "lib/dracut"),
                "grub_label_font": {"path": str(font), "sha256": file_hash(font)},
                "provenance": {"source_verification": str(workspace / "SOURCES.json"),
                               "source_verification_sha256": file_hash(workspace / "SOURCES.json"),
                               "host_packages_sha256": file_hash(workspace / "HOST-PACKAGES.txt"),
                               "host_package_authentication": "builder distribution APT trust; inventory is not a signature",
                               "qualification": qualification}}
        for name in ("mksquashfs", "dracut", "lsinitrd", "grub-mkrescue", "grub-script-check", "xorriso"):
            path = Path("/usr/bin/xorriso") if name == "xorriso" else prefix / "bin" / name
            lock["commands"][name] = {"path": str(path), "sha256": file_hash(path)}
        for path in (prefix, prefix / "lib/dracut", prefix / "lib/grub/x86_64-efi"):
            lock["support_trees"].append({"path": str(path), "sha256": tree_hash(path)})
        tool_lock = workspace / "TOOLS.json"
        tool_lock.write_bytes(canonical(lock))
        check_tools(tool_lock, file_hash(tool_lock))
        receipt = {"schema": "tup.boot-host-build.v1", "status": "complete", "scope": "host-tools-only",
                   "catalog_sha256": args.catalog_sha256, "recipe_sha256": file_hash(Path(__file__)),
                   "inputs_helper_sha256": file_hash(Path(__file__).with_name("inputs.py")),
                   "assemble_helper_sha256": file_hash(Path(__file__).with_name("assemble.py")),
                   "tools_sha256": file_hash(tool_lock), "qualification": qualification,
                   "logs": {p.name: file_hash(p) for p in sorted(logs.glob("*.log"))},
                   "jobs": args.jobs, "booted": False, "release_eligible": False}
        sync_tree(workspace)
        pending = workspace / "HOST-BUILD.pending.json"
        pending.write_bytes(canonical(receipt))
        with pending.open("rb") as stream:
            os.fsync(stream.fileno())
        pending.rename(workspace / "HOST-BUILD.json")
        sync_directory(workspace)
        print(f"host tools qualified; tool lock SHA256 {receipt['tools_sha256']}")
    except BaseException as exc:
        receipt = workspace / "HOST-BUILD.json"
        if receipt.exists():
            receipt.rename(workspace / "HOST-BUILD.uncertain.json")
        (workspace / "FAILED.txt").write_text(str(exc) + "\n")
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--catalog-sha256", required=True)
    parser.add_argument("--cache", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--jobs", required=True, type=int)
    args = parser.parse_args(argv)
    try:
        build(args)
    except (Refusal, source_lock.Refusal, OSError, ValueError, tarfile.TarError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
