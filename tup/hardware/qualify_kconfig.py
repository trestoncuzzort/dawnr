#!/usr/bin/env python3
"""Reproduce the README Kconfig qualification out of tree; never build or install a kernel."""
import argparse
from contextlib import nullcontext
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tarfile

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tup.boot.inputs import Refusal, checked_file, file_hash, load_json

TUP = Path(__file__).resolve().parents[1]
LOCK = TUP / "sources" / "source-lock-13.1-build.json"
ENVIRONMENT = {"ARCH": "x86_64", "KCONFIG_WARN_UNKNOWN_SYMBOLS": "1", "KCONFIG_WERROR": "1",
               "LC_ALL": "C", "MAKEFLAGS": "-j1"}
TOOLS = ("bison", "flex", "gcc", "make")


def release_of(source):
    fields = dict(re.findall(r"^(VERSION|PATCHLEVEL|SUBLEVEL|EXTRAVERSION) = ?(.*)$",
                             (source / "Makefile").read_text(encoding="utf-8"), re.M))
    if not all(fields.get(key, "").isdigit() for key in ("VERSION", "PATCHLEVEL", "SUBLEVEL")):
        raise Refusal("source Makefile does not name a kernel release")
    return "{VERSION}.{PATCHLEVEL}.{SUBLEVEL}".format(**fields) + fields.get("EXTRAVERSION", "")


def locked_archive(release, lock):
    name = "linux-" + release + ".tar.xz"
    found = [record["sha256"] for record in load_json(lock)["sources"] if record["name"] == name]
    if len(found) != 1:
        raise Refusal("the source lock does not hold exactly one " + name)
    return found[0]


def snapshot(source):
    """Type, size and mtime of every entry; a directory mtime also exposes a created-then-removed file."""
    entries = {}
    for directory, names, files in os.walk(source):
        for path in [Path(directory)] + [Path(directory, name) for name in names + files]:
            info = path.lstat()
            entries[path.relative_to(source).as_posix()] = (stat.S_IFMT(info.st_mode), info.st_size, info.st_mtime_ns)
    return entries


def check_source(source, archive, release):
    """The tree must be exactly the locked archive: same names, types, link targets and file bytes."""
    before, seen = snapshot(source), set()
    with tarfile.open(archive, "r:xz") as members:
        for member in members:
            top, _, name = member.name.partition("/")
            name = name or "."
            if top != "linux-" + release:
                raise Refusal("unexpected archive member: " + member.name)
            kind = before.get(name, (None,))[0]
            if member.isdir():
                same = kind == stat.S_IFDIR
            elif member.issym():
                same = kind == stat.S_IFLNK and os.readlink(source / name) == member.linkname
            elif member.isreg():
                same = (kind == stat.S_IFREG and before[name][1] == member.size and file_hash(source / name)
                        == hashlib.file_digest(members.extractfile(member), "sha256").hexdigest())
            else:
                same = False
            if not same:
                raise Refusal("kernel source differs from the locked archive: " + name)
            seen.add(name)
    extra = sorted(set(before) - seen)
    if extra:
        raise Refusal("kernel source has entries the locked archive lacks: " + ", ".join(extra[:5]))
    return before


def tool(name, environment):
    found = shutil.which(name, path=environment["PATH"])
    if found is None:
        raise Refusal("required host tool not found: " + name)
    lines = subprocess.run([found, "--version"], env=environment, stdin=subprocess.DEVNULL,
                           capture_output=True, text=True, check=True).stdout.splitlines()
    if not lines:
        raise Refusal("host tool reports no version: " + name)
    return {"sha256": file_hash(Path(found).resolve()), "version": lines[0]}


def qualify(source, archive, output, lock=LOCK):
    source, archive, output = Path(source), Path(archive), Path(os.path.abspath(output))
    if source.is_symlink() or not source.is_dir():
        raise Refusal("--source must be a real extracted kernel source directory")
    source = source.resolve()
    if output.exists() or output.is_symlink():
        raise Refusal("output directory already exists; supply a new one")
    if not output.parent.is_dir() or output.parent.resolve().is_relative_to(source):
        raise Refusal("the output directory needs an existing parent outside the source tree")
    release = release_of(source)
    locked = locked_archive(release, lock)
    checked_file(archive, locked)
    before = check_source(source, archive, release)
    environment = dict(ENVIRONMENT, PATH=os.environ.get("PATH", os.defpath))
    # Identify the host tools before anything is created: a missing tool is a
    # refusal with no partial output directory to clean up.
    tools = {name: tool(name, environment) for name in TOOLS}
    output.mkdir()
    build = output / "build"
    build.mkdir()
    helpers = {"boot": TUP / "boot" / "kernel.py", "hardware": TUP / "hardware" / "kernel.py"}
    steps = []

    def step(action, command, log=None):
        with open(output / log, "xb") if log else nullcontext() as stream:
            code = subprocess.run([str(part) for part in command], cwd=output, env=environment,
                                  stdin=subprocess.DEVNULL, stdout=stream,
                                  stderr=subprocess.STDOUT if log else None).returncode
        steps.append({"action": action, "exit_code": code})
        if code:
            raise Refusal(f"{action} failed with exit code {code}; inspect {output}")

    for name, helper in helpers.items():
        with open(output / (name + ".config"), "xb") as stream:
            if subprocess.run([sys.executable, str(helper), "fragment"], env=environment,
                              stdin=subprocess.DEVNULL, stdout=stream).returncode:
                raise Refusal(name + " fragment helper failed")
    make = ["make", "-C", source, "O=" + str(build)]
    step("x86_64_defconfig", make + ["x86_64_defconfig"], "defconfig.log")
    # merge_config.sh creates its temporary files in the working directory, which
    # is the new output directory here and never the source tree.
    step("merge_config.sh -m", ["bash", source / "scripts/kconfig/merge_config.sh", "-m", "-O", build,
                                build / ".config", output / "boot.config", output / "hardware.config"], "merge.log")
    step("olddefconfig", make + ["olddefconfig"], "olddefconfig.log")
    for name, helper in helpers.items():
        step(name + " required-symbol check", [sys.executable, helper, "check", "--config", build / ".config"])
    if snapshot(source) != before:
        raise Refusal("the kernel source tree changed during qualification")
    record = {
        "architecture": "x86_64",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "config_sha256": file_hash(build / ".config"),
        "device_driver_qualified": False,
        "environment": ENVIRONMENT,
        "firmware_loaded": False,
        "inputs": {
            "boot_fragment_sha256": file_hash(output / "boot.config"),
            "boot_helper_sha256": file_hash(helpers["boot"]),
            "defconfig_sha256": file_hash(source / "arch/x86/configs/x86_64_defconfig"),
            "hardware_fragment_sha256": file_hash(output / "hardware.config"),
            "hardware_helper_sha256": file_hash(helpers["hardware"]),
            "merge_config_sha256": file_hash(source / "scripts/kconfig/merge_config.sh"),
        },
        "jobs": 1,
        "kernel_archive_sha256": locked,
        "kernel_compiled": False,
        "logs": {name: file_hash(output / name) for name in ("defconfig.log", "merge.log", "olddefconfig.log")},
        "schema": "tup-hardware-kconfig-qualification-v1",
        "source_release": release,
        "steps": steps,
        "target_booted": False,
        "tools": tools,
    }
    with open(output / "KCONFIG-QUALIFICATION.json", "x", encoding="ascii", newline="\n") as stream:
        stream.write(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="extracted kernel source; only read")
    parser.add_argument("--archive", type=Path, required=True, help="the locked linux-<release>.tar.xz it came from")
    parser.add_argument("--output", type=Path, required=True, help="new directory for fragments, logs and build/")
    args = parser.parse_args(argv)
    try:
        record = qualify(args.source, args.archive, args.output)
        print(f"Kconfig qualification recorded in {args.output}: config {record['config_sha256']}; "
              "only Kconfig host tools were compiled, no kernel, module or boot")
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print("REFUSED: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
