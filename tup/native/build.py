#!/usr/bin/env python3
"""Explicit, directory-backed LFS bootstrap; never partitions a device.

Host Python only. The chapter drivers inside chroot remain Bash/coreutils.
See README.md for trust, resource and recovery boundaries.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
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
TUP = Path(__file__).resolve().parents[1]
CH07_ORDER = (
    "01-introduction.sh", "02-changingowner.sh", "03-kernfs.sh", "04-chroot.sh",
    "05-creatingdirs.sh", "06-createfiles.sh", "07-gettext.sh", "08-bison.sh",
    "09-perl.sh", "10-Python.sh", "11-texinfo.sh", "12-util-linux.sh", "13-cleanup.sh",
)


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


def load_lock(path: Path, expected_sha256: str, book: Path) -> dict:
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
    metadata = (book / "BOOK-SOURCE").read_text(encoding="utf-8").splitlines()
    if [line for line in metadata if line.startswith("arch=")] != ["arch=x86_64"]:
        raise Refusal("extracted book metadata is not unambiguously x86_64")
    if [line for line in metadata if line.startswith("base=")] != [
        "base=https://www.linuxfromscratch.org/lfs/view/12.4/"
    ]:
        raise Refusal("unsupported extracted book; this bootstrap currently covers LFS 12.4 only")
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
    required = set()
    for chapter in ("ch05", "ch06", "ch07", "ch08"):
        for page in (book / chapter).glob("*.sh"):
            for line in page.read_text(encoding="utf-8").splitlines():
                if line.startswith(("# TUP_TARBALL=", "# TUP_TARBALL_x86_64=")):
                    required.add(line.split("=", 1)[1])
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


def input_map(source: Path, book: Path) -> dict[str, Path | bytes]:
    files = {"driver.sh": source / "driver.sh"}
    files.update({f"book/{name}": path for name, path in tree_files(book)})
    for relative in ("overrides", "buildlib", "native"):
        files.update({f"{relative}/{name}": path for name, path in tree_files(source / relative)})
    if not any(name.startswith("buildlib/") for name in files):
        raise Refusal("input-aware driver helpers have not been integrated")
    # The native override wins the existing x86_64 lookup before shared overrides.
    native_overrides = source / "native/profiles/x86_64/overrides"
    files.update({f"overrides/{name}": path for name, path in tree_files(native_overrides)})
    order = (book / "ch07/ORDER").read_text(encoding="utf-8").splitlines()
    if tuple(order) != CH07_ORDER:
        raise Refusal("chapter 7 inner selection changed; review the chroot crossing")
    selected = order[4:12]
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


def checked(command: list[str], **kwargs) -> str:
    try:
        result = subprocess.run(command, check=True, text=True, stdout=subprocess.PIPE, timeout=60,
                                stderr=subprocess.STDOUT, **kwargs)
    except (OSError, subprocess.SubprocessError) as exc:
        output = getattr(exc, "stdout", "") or ""
        raise Refusal(f"command failed: {command[0]}: {output[-1500:] or exc}") from exc
    return result.stdout.strip()


def host_identity(workspace: Path, jobs: int, memory_mib: int, free_gib: int) -> dict:
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
                "sha256sum": ["--version"], "sort": ["--version"], "unshare": ["--version"],
                "runuser": ["--version"], "mount": ["--version"], "chroot": ["--version"],
                "python3": ["--version"], "bc": ["--version"]}
    minimums = {"bash": (3, 2), "ld": (2, 13, 1), "bison": (2, 7), "gawk": (4, 0, 1),
                "gcc": (5, 4), "g++": (5, 4), "make": (4, 0), "makeinfo": (5, 0),
                "tar": (1, 22), "gzip": (1, 3, 12), "xz": (5, 0, 0),
                "patch": (2, 5, 4), "m4": (1, 4, 10), "diff": (2, 8, 1),
                "find": (4, 2, 31), "sed": (4, 1, 5), "sort": (8, 1)}
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
        if (name in {"gcc", "g++"} and version > (15, 2, 0)) or (name == "ld" and version > (2, 45, 0)):
            raise Refusal(f"{name} exceeds the LFS 12.4 tested range; review before using")
        tools[name] = {"version": first, "sha256": digest(Path(executable).resolve())}
    if "GNU Awk" not in checked(["awk", "--version"]) or "Bison" not in checked(["yacc", "--version"]):
        raise Refusal("awk/yacc must select gawk/bison")
    kernel = tuple(int(x) for x in re.match(r"(\d+)\.(\d+)", platform.release()).groups())
    if kernel < (5, 4):
        raise Refusal("LFS 12.4 requires host Linux >= 5.4")
    # Compile+link without creating persistent outputs or accepting silence as success.
    checked(["g++", "-x", "c++", "-o", "/dev/null", "-"], input="int main(){}\n")
    checked(["unshare", "--mount", "--pid", "--fork", "--kill-child", "--propagation", "private", "true"])
    return {"kernel": platform.release(), "architecture": "x86_64", "tools": tools,
            "requirements_policy": "LFS-12.4-host-baseline; not production-release approval"}


def verify_host_tools(host: dict) -> None:
    for name, record in host["tools"].items():
        executable = shutil.which(name)
        if executable is None or digest(Path(executable).resolve()) != record["sha256"]:
            raise Refusal(f"host tool changed during build: {name}")


def build_identity(args, files: dict, lock: dict, host: dict) -> dict:
    return {"schema": SCHEMA, "profile": "native-x86_64-core", "architecture": "x86_64",
            "inputs": map_identity(files), "source_lock_sha256": args.lock_sha256,
            "sources": sorted(lock["sources"], key=lambda item: item["name"]), "host": host,
            "policy": {"jobs": args.jobs, "memory_budget_mib": args.memory_mib,
                       "tests": TESTS, "build_user": args.build_user, "last_stage": "ch08"}}


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


def run_stage(state: Path, stage: str, command: list[str], inputs_sha256: str,
              validate_command: list[str] | None = None) -> None:
    if stage_record(state, stage, inputs_sha256):
        if validate_command is not None:
            checked(validate_command, stdin=subprocess.DEVNULL)
        print(f"{stage}: verified prior stage receipt", flush=True)
        return
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
    parser.add_argument("action", choices=("preflight", "prepare", "build"))
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--source-cache", required=True)
    parser.add_argument("--source-lock", required=True)
    parser.add_argument("--lock-sha256", required=True)
    parser.add_argument("--source", default=str(TUP))
    parser.add_argument("--book", help="explicit extracted x86_64 book directory; defaults to source/book-x86_64")
    parser.add_argument("--build-user", default="lfs")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--memory-mib", type=int, default=4096)
    parser.add_argument("--free-gib", type=int, default=40)
    parser.add_argument("--through", choices=("ch06", "ch08"), default="ch08")
    args = parser.parse_args(argv)
    try:
        for name in ("workspace", "source_cache", "source_lock", "source"):
            setattr(args, name, plain_path(getattr(args, name)))
        args.book = plain_path(args.book or str(args.source / "book-x86_64"))
        validate_workspace(args.workspace, args.source, args.source_cache)
        validate_workspace(args.workspace, args.book, args.source_cache)
        if not NAME.fullmatch(args.build_user) or args.build_user == "root":
            raise Refusal("build user must be a dedicated unprivileged account")
        lock = load_lock(args.source_lock, args.lock_sha256, args.book)
        verify_sources(args.source_cache, lock)
        files = input_map(args.source, args.book)
        host = host_identity(args.workspace, args.jobs, args.memory_mib, args.free_gib)
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
            for path in (state, root, args.workspace / "home", root / "sources", root / "tup-build"):
                plain_path(str(path))
                if not path.is_dir():
                    raise Refusal("prepared control paths must remain directories")
            require_identity(read_json(state / "BUILD.json"), inputs)
            if read_json(state / "preparing.json") != {"status": "complete"}:
                raise Refusal("preparation was interrupted")
            inputs_hash = hashlib.sha256(encoded(inputs)).hexdigest()
            for stage in STAGES:
                load_lock(args.source_lock, args.lock_sha256, args.book)
                verify_host_tools(host)
                verify_sources(args.source_cache, lock)
                verify_sources(root / "sources", lock, staged=True)
                require_identity(read_json(state / "BUILD.json"), build_identity(args, input_map(args.source, args.book), lock, host))
                verify_staged(root, inputs)
                runner = str(root / "tup-build/native/run-stage.sh")
                command = ["bash", runner, stage, str(root), args.build_user,
                           str(args.workspace / "home"), str(args.jobs)]
                if stage in ("ch07-inner", "ch08"):
                    command = ["unshare", "--mount", "--pid", "--propagation", "private", "--fork", "--kill-child", *command]
                validation = None if stage == "ownership" else [*command, "--validate"]
                run_stage(state, stage, command, inputs_hash, validation)
                if stage == args.through:
                    break
            print(f"LFS core through {args.through} completed; native boot, installer and networking remain unbuilt")
        finally:
            if lockdir.exists():
                lockdir.rmdir()
        return 0
    except (Refusal, OSError, KeyError, ValueError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
