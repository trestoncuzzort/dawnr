#!/usr/bin/env python3
"""Plan/apply disposable regular-file images with systemd-repart; never disks."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import platform
import re
import stat
import subprocess
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tup.boot.inputs import Refusal, canonical, checked_file, digest, file_hash, inventory, load_json
from tup.boot.assemble import sync_directory

HERE = Path(__file__).resolve().parent
MIB = 1024 * 1024
PATH = "/usr/sbin:/usr/bin:/sbin:/bin"
TYPES = {"esp": "c12a7328-f81f-11d2-ba4b-00a0c93ec93b",
         "root-x86-64": "4f68bce3-e8cd-4db1-96e7-fbcaf984b709"}
TOOLS = {"repart": "/usr/bin/systemd-repart", "sfdisk": "/usr/sbin/sfdisk",
         "mkfs.ext4": "/usr/sbin/mkfs.ext4", "mkfs.vfat": "/usr/sbin/mkfs.vfat",
         "mcopy": "/usr/bin/mcopy"}


def real_path(path):
    path = Path(os.path.abspath(path))
    if path.resolve() != path:
        raise Refusal("symbolic links in input/output paths are not permitted")
    return path


def disjoint(*paths):
    for i, first in enumerate(paths):
        for second in paths[i + 1:]:
            if first == second or first in second.parents or second in first.parents:
                raise Refusal("source, target and state paths must be disjoint")


def unmounted(path):
    # st_dev cannot detect same-filesystem bind mounts. No mounts are performed.
    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        name = re.sub(r"\\([0-7]{3})", lambda m: chr(int(m[1], 8)), line.split()[4])
        mountpoint = Path(name)
        if mountpoint == path or path in mountpoint.parents:
            raise Refusal("mounted input or output refused")


def target_identity(path, fd, *, blank):
    before = path.lstat()
    opened = os.fstat(fd)
    if (not stat.S_ISREG(opened.st_mode) or not stat.S_ISREG(before.st_mode)
            or opened.st_nlink != 1 or before.st_nlink != 1):
        raise Refusal("target must be one regular file, without hardlinks; physical devices refused")
    if not 200 * MIB <= opened.st_size <= 64 * 1024 * MIB or opened.st_size % MIB:
        raise Refusal("fixture image size must be 200 MiB to 64 GiB, in whole MiB")
    fields = lambda st: (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
    if fields(before) != fields(opened):
        raise Refusal("target identity changed while opening")
    h = hashlib.sha256()
    os.lseek(fd, 0, os.SEEK_SET)
    while chunk := os.read(fd, MIB):
        if blank and chunk.count(0) != len(chunk):
            raise Refusal("only an explicitly precreated all-zero fixture image is accepted")
        h.update(chunk)
    if fields(os.fstat(fd)) != fields(opened) or fields(path.lstat()) != fields(before):
        raise Refusal("target changed while hashing")
    # An image attached to a loop device is not an offline target, mounted or not.
    for backing in Path("/sys/block").glob("loop*/loop/backing_file"):
        name = backing.read_text().strip()
        candidate = Path("/" + name.lstrip("/"))
        if candidate.exists() and (candidate.stat().st_dev, candidate.stat().st_ino) == fields(opened)[:2]:
            raise Refusal("target is attached to a loop device")
    return {"path": str(path), "device": opened.st_dev, "inode": opened.st_ino,
            "size": opened.st_size, "mtime_ns": opened.st_mtime_ns,
            "ctime_ns": opened.st_ctime_ns, "sha256": h.hexdigest()}


@contextmanager
def target_file(path, *, write=False):
    # The sidecar serializes this adapter without conflicting with repart's own
    # target flock. Passing the open fd pins the inode used by the subprocess.
    lock = path.with_name("." + path.name + ".tup-install.lock")
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise Refusal("physical devices and other non-regular targets are refused")
    lockfd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        fd = os.open(path, (os.O_RDWR if write else os.O_RDONLY) | os.O_NOFOLLOW)
        try:
            unmounted(path)
            yield fd
        finally:
            os.close(fd)
    finally:
        os.close(lockfd)
        lock.unlink()


def source_inventory(source):
    unmounted(source)
    if sorted(p.name for p in source.iterdir()) != ["esp", "root"]:
        raise Refusal("payload must contain exactly the offline esp/ and root/ directories")
    for name in ("esp", "root"):
        if (source / name).is_symlink() or not (source / name).is_dir():
            raise Refusal("payload roots must be real directories")
    result = inventory(source)
    esp = {name: entry for name, entry in result.items() if name == "esp" or name.startswith("esp/")}
    # FAT silently skips unsupported file types and collapses case aliases.
    folded = set()
    for name, entry in esp.items():
        if entry["type"] not in {"file", "directory"} or name.casefold() in folded:
            raise Refusal("ESP contains an unsupported type or a case-insensitive name collision")
        if (any(c in name for c in ':*?"<>|\\') or any(ord(c) < 32 for c in name)
                or any(p.endswith((" ", ".")) for p in Path(name).parts)):
            raise Refusal("ESP contains a name that FAT cannot preserve")
        folded.add(name.casefold())
    if result.get("esp/EFI/BOOT/BOOTX64.EFI", {}).get("type") != "file":
        raise Refusal("explicit EFI fallback payload is required (bootability is not inferred)")
    return result


def definitions(esp_mib, root_mib):
    if (type(esp_mib) is not int or type(root_mib) is not int
            or not 64 <= esp_mib <= 1024 or not 128 <= root_mib <= 63 * 1024):
        raise Refusal("partition sizes outside the disposable-image policy")
    result = {}
    for name, kind, fs, size, source in (("10-esp.conf", "esp", "vfat", esp_mib, "esp"),
                                       ("20-root.conf", "root-x86-64", "ext4", root_mib, "root")):
        result[name] = (f"[Partition]\nType={kind}\nFormat={fs}\nLabel=TUP-TEST-{source.upper()}\n"
                        f"SizeMinBytes={size}M\nSizeMaxBytes={size}M\nCopyFiles=/{source}/:/\n"
                        "FactoryReset=no\n")
    return result


def tool_identity():
    result = {name: {"path": str(Path(path).resolve()), "sha256": file_hash(Path(path).resolve())}
              for name, path in TOOLS.items()}
    result["mke2fs.conf"] = {"path": "/etc/mke2fs.conf", "sha256": file_hash("/etc/mke2fs.conf")}
    version = subprocess.run([result["repart"]["path"], "--version"], check=True, capture_output=True,
                             text=True, env={"PATH": PATH, "LANG": "C", "LC_ALL": "C"}).stdout
    # This checkpoint has qualified Ubuntu 255 only. The actual target 261
    # binary, mkfs helpers and copying semantics need their own real run.
    if not version.startswith("systemd 255 "):
        raise Refusal("unqualified repart version; this image checkpoint requires systemd 255")
    return {"files": result, "version": version,
            "provenance": "observed host identity; authenticated host package evidence is separate"}


def code_identity():
    files = [HERE / "image.py", HERE.parent / "boot/inputs.py", HERE.parent / "boot/assemble.py"]
    return {str(p.relative_to(HERE.parent)): file_hash(p) for p in files}


def write_json(path, value):
    pending = path.with_name(path.name + ".pending")
    with pending.open("xb") as stream:
        stream.write(canonical(value))
        stream.flush()
        os.fsync(stream.fileno())
    if path.exists():
        raise Refusal("refusing to replace install evidence")
    pending.rename(path)
    sync_directory(path.parent)


def execute(command, state, name, fd):
    env = {"PATH": PATH, "LANG": "C", "LC_ALL": "C", "SYSTEMD_PAGER": "cat",
           "SYSTEMD_COLORS": "0", "MTOOLSRC": "/dev/null", "TMPDIR": str(state / "tmp")}
    with (state / (name + ".stdout")).open("xb") as out, (state / (name + ".stderr")).open("xb") as err:
        result = subprocess.run(command, stdout=out, stderr=err, env=env, pass_fds=(fd,), timeout=600)
        out.flush(); err.flush()
        os.fsync(out.fileno()); os.fsync(err.fileno())
    if result.returncode:
        raise Refusal(f"{name} failed ({result.returncode}); retain its logs and use a new image")
    return load_json(state / (name + ".stdout"))


def command(plan, state, fd, *, apply=False):
    # --empty=create overrides --dry-run=yes upstream; --size can resize before
    # dry-run; --split=yes writes outputs even during dry-run. None belongs here.
    return [plan["tools"]["files"]["repart"]["path"], "--offline=yes", "--empty=require",
            "--factory-reset=no", "--discard=no", "--split=no", "--json=pretty",
            "--definitions=" + str(state / "definitions"), "--copy-source=" + plan["source"],
            "--seed=" + plan["seed"], "--dry-run=" + ("no" if apply else "yes"), f"/proc/self/fd/{fd}"]


def check_platform():
    if platform.system() != "Linux" or platform.machine() != "x86_64" or os.geteuid() != 0:
        raise Refusal("run only in the disposable Linux x86_64 builder as root")


def plan_image(target, source, source_sha256, state, *, esp_mib=64, root_mib=128):
    check_platform()
    target, source, state = map(real_path, (target, source, state))
    disjoint(target, source, state)
    layout = definitions(esp_mib, root_mib)
    current_source = source_inventory(source)
    if digest(canonical(current_source)) != source_sha256:
        raise Refusal("source inventory differs from the caller's reviewed digest")
    if state.exists():
        raise Refusal("plan requires a fresh state directory")
    with target_file(target) as fd:
        identity = target_identity(target, fd, blank=True)
        if identity["size"] < (esp_mib + root_mib + 8) * MIB:
            raise Refusal("target is too small for this layout plus GPT/alignment space")
        plan = {"schema": "tup.install-image-plan.v1", "scope": "regular-file-fixture-only",
                "target": identity, "source": str(source), "source_sha256": source_sha256,
                "definitions": layout, "esp_mib": esp_mib, "root_mib": root_mib,
                "seed": str(uuid.uuid4()), "tools": tool_identity(),
                "code": code_identity(), "release_eligible": False, "boot_tested": False}
        state.mkdir(mode=0o700)
        try:
            (state / "tmp").mkdir(); (state / "definitions").mkdir()
            for name, text in layout.items():
                (state / "definitions" / name).write_text(text, encoding="ascii", newline="\n")
            write_json(state / "SOURCE-INVENTORY.json", current_source)
            plan["partitions"] = execute(command(plan, state, fd), state, "plan", fd)
            if (target_identity(target, fd, blank=True) != identity
                    or source_inventory(source) != current_source or tool_identity() != plan["tools"]):
                raise Refusal("inputs changed during planning")
            write_json(state / "PLAN.json", plan)
            return plan
        except BaseException as error:
            (state / "FAILED.txt").write_text(str(error) + "\n")
            raise


def apply_image(state, plan_sha256, confirmation):
    check_platform()
    state = real_path(state)
    checked_file(state / "PLAN.json", plan_sha256)
    if confirmation != "APPLY-IMAGE " + plan_sha256:
        raise Refusal("exact reviewed plan confirmation required")
    plan = load_json(state / "PLAN.json")
    if plan.get("schema") != "tup.install-image-plan.v1" or plan.get("scope") != "regular-file-fixture-only":
        raise Refusal("unsupported plan; physical disk/USB apply is unavailable")
    if plan["definitions"] != definitions(plan["esp_mib"], plan["root_mib"]):
        raise Refusal("plan contains unsupported partition directives")
    if any(os.path.lexists(state / name) for name in ("APPLYING.json", "RECEIPT.json", "FAILED.txt", "RECEIPT.uncertain.json")):
        raise Refusal("an attempted install cannot be replayed; preserve evidence and use a new image")
    target, source = map(real_path, (plan["target"]["path"], plan["source"]))
    disjoint(target, source, state)
    with target_file(target, write=True) as fd:
        if target_identity(target, fd, blank=True) != plan["target"]:
            raise Refusal("target identity changed since review")
        current_source = source_inventory(source)
        if digest(canonical(current_source)) != plan["source_sha256"]:
            raise Refusal("source changed since review")
        checked_file(state / "SOURCE-INVENTORY.json", plan["source_sha256"])
        defs = real_path(state / "definitions")
        unmounted(defs)
        temporary = real_path(state / "tmp")
        unmounted(temporary)
        if not temporary.is_dir() or any(temporary.iterdir()):
            raise Refusal("temporary directory changed or contains previous work")
        children = list(defs.iterdir())
        if (set(p.name for p in children) != set(plan["definitions"])
                or any(not stat.S_ISREG(p.lstat().st_mode) or p.stat().st_nlink != 1 for p in children)):
            raise Refusal("partition definition paths changed since review")
        actual = {p.name: p.read_text(encoding="ascii") for p in children}
        if actual != plan["definitions"]:
            raise Refusal("partition definitions changed since review")
        if code_identity() != plan["code"] or tool_identity() != plan["tools"]:
            raise Refusal("installer or host tools changed since review")
        try:
            write_json(state / "APPLYING.json", {"plan_sha256": plan_sha256, "automatic_resume": False})
            partitions = execute(command(plan, state, fd, apply=True), state, "apply", fd)
            if partitions != plan["partitions"]:
                raise Refusal("repart's applied layout differs from its reviewed plan")
            os.fsync(fd)
            table = execute([plan["tools"]["files"]["sfdisk"]["path"], "--json", f"/proc/self/fd/{fd}"],
                            state, "partition-table", fd)["partitiontable"]
            if table["label"] != "gpt" or table["unit"] != "sectors" or len(table["partitions"]) != 2:
                raise Refusal("installed GPT does not match the two-partition plan")
            for expected, actual in zip(partitions, table["partitions"]):
                if (actual["type"].lower() != TYPES[expected["type"]]
                        or actual["uuid"].lower() != expected["uuid"]
                        or actual["start"] * table["sectorsize"] != expected["offset"]
                        or actual["size"] * table["sectorsize"] != expected["raw_size"]):
                    raise Refusal("installed GPT partition identity differs from review")
            after = target_identity(target, fd, blank=False)
            if any(after[k] != plan["target"][k] for k in ("path", "device", "inode", "size")):
                raise Refusal("target replaced or resized during install")
            if source_inventory(source) != current_source or tool_identity() != plan["tools"]:
                raise Refusal("source or tools changed during install")
            receipt = {"schema": "tup.install-image-receipt.v1", "status": "populated-unqualified",
                       "scope": plan["scope"], "plan_sha256": plan_sha256, "target": after,
                       "source_sha256": plan["source_sha256"], "gpt_checked": True,
                       "root_contents_attested": False, "boot_tested": False,
                       "physical_install_tested": False, "release_eligible": False,
                       "logs": {p.name: file_hash(p) for p in state.glob("*.std*")}}
            write_json(state / "RECEIPT.json", receipt)
            return receipt
        except BaseException as error:
            receipt = state / "RECEIPT.json"
            if receipt.exists():
                receipt.rename(state / "RECEIPT.uncertain.json")
            (state / "FAILED.txt").write_text(str(error) + "\n")
            raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    plan = sub.add_parser("plan")
    for name in ("target", "source", "state"):
        plan.add_argument("--" + name, type=Path, required=True)
    plan.add_argument("--source-sha256", required=True)
    plan.add_argument("--esp-mib", type=int, default=64)
    plan.add_argument("--root-mib", type=int, default=128)
    apply = sub.add_parser("apply")
    apply.add_argument("--state", type=Path, required=True)
    apply.add_argument("--plan-sha256", required=True)
    apply.add_argument("--confirm", required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == "plan":
            result = plan_image(args.target, args.source, args.source_sha256, args.state,
                                esp_mib=args.esp_mib, root_mib=args.root_mib)
            print(canonical(result).decode(), end="")
            print("Confirmation: APPLY-IMAGE " + digest(canonical(result)))
        else:
            result = apply_image(args.state, args.plan_sha256, args.confirm)
            print(canonical(result).decode(), end="")
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print("image install refused: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
