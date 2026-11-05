#!/usr/bin/env python3
"""Build the target layers once in a fresh export of a validated core; no enrollment.

The original core workspace is only validated and read. Layer chapters run
through the unchanged driver.sh in private namespaces inside a separate export.
Every disposable input and the layer ledger are moved out of that export before
it is inventoried and receipted. See README.md for boundaries and evidence.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys

TUP = Path(__file__).resolve().parents[1]
# boot/ modules import "tup.boot...", the remote and source verifiers "boot..."/"sources...".
sys.path[:0] = [str(TUP.parent), str(TUP)]
from tup.boot.assemble import check_completion, check_core_spec, completion_path, stamp
from tup.boot.inputs import (Refusal, canonical, check_kernel, check_offline_root, checked_file,
                             digest, file_hash, inventory, load_json, root_path)
from remote.verify_sources import verify as verify_remote
from sources import source_lock as verifier

HERE = Path(__file__).resolve().parent
PROFILE = "native-x86_64-lfs-13.1-systemd-layers"
KERNEL_RELEASE = "6.18.60-tup"
KERNEL_ARCHIVE = "linux-6.18.60.tar.xz"
DEVICE_MAPPER_ARCHIVE = "LVM2.2.03.42.tgz"
# Chapter name -> repository directory holding ORDER and its pages.
CHAPTERS = {"remote": "remote/pages", "boot": "boot/pages", "system": "system/pages"}
HELPERS = ("boot", "hardware", "remote", "system")
EXCLUDED = ("sources", "tools", "tup-build", "dev", "proc", "sys", "run", "tmp")
STAGE = "tup-layer"


def write_json(path, value):
    with Path(path).open("xb") as stream:
        stream.write(canonical(value))
        stream.flush()
        os.fsync(stream.fileno())


def chapter_pages(source: Path, chapter: str) -> list[str]:
    directory = source / CHAPTERS[chapter]
    names = (directory / "ORDER").read_text(encoding="utf-8").splitlines()
    present = sorted(path.name for path in directory.iterdir())
    if not names or sorted([*names, "ORDER"]) != present:
        raise Refusal("layer chapter ORDER and page files disagree: " + chapter)
    return names


def chapter_archives(source: Path, chapters: list[str]) -> list[str]:
    """Archives named by the selected pages' driver headers, in page order."""
    names = []
    for chapter in chapters:
        for page in chapter_pages(source, chapter):
            lines = (source / CHAPTERS[chapter] / page).read_text(encoding="utf-8").splitlines()
            headers = [line for line in lines if line.startswith("# TUP_TARBALL")]
            if len(headers) > 1 or any(not line.startswith("# TUP_TARBALL=") for line in headers):
                raise Refusal("layer pages name at most one architecture-independent archive: " + page)
            if headers:
                names.append(headers[0].split("=", 1)[1])
    if len(names) != len(set(names)):
        raise Refusal("a layer archive is built by more than one page")
    return names


def verify_sources(cache: Path, gpg: Path, core_lock: Path, wanted: list[str], source: Path = TUP) -> dict:
    """Re-authenticate every archive the selected pages consume; never trust an old receipt."""
    results = {}
    remote = verify_remote(cache, gpg, source / "remote")
    for row in remote["sources"]:
        results[row["name"]] = row
    for record in load_json(source / "boot/target-sources.json")["sources"]:
        if record["name"] == DEVICE_MAPPER_ARCHIVE:
            results[record["name"]] = verifier.verify_record(record, cache, source / "boot/evidence", gpg)
    firmware = load_json(source / "hardware/firmware-source.json")
    results[firmware["name"]] = verifier.verify_record(firmware, cache, source / "hardware/evidence", gpg)
    # The kernel archive is a core-lock input; reuse that authentication and pin.
    kernel = [row for row in load_json(core_lock)["sources"] if row["name"] == KERNEL_ARCHIVE]
    if len(kernel) != 1 or kernel[0]["authentication"].get("status") != "verified":
        raise Refusal("core lock does not authenticate the selected kernel archive")
    checked_file(cache / KERNEL_ARCHIVE, kernel[0]["sha256"])
    results[KERNEL_ARCHIVE] = {"name": KERNEL_ARCHIVE, "status": "verified", "sha256": kernel[0]["sha256"],
                               "size": (cache / KERNEL_ARCHIVE).stat().st_size,
                               "authentication": dict(kernel[0]["authentication"], origin="core-source-lock")}
    missing = [name for name in wanted if results.get(name, {}).get("status") != "verified"]
    if missing:
        raise Refusal("layer page archive has no verified source record: " + ", ".join(missing))
    return {"schema": "tup-layer-source-verification-v1", "status": "verified", "release_eligible": False,
            "verifier_sha256": verifier.digest(Path(verifier.__file__)),
            "remote_advisory_review_sha256": remote["advisory_review_sha256"],
            "core_source_lock_sha256": file_hash(core_lock),
            "sources": [results[name] for name in wanted],
            "limitations": ["Source verification does not establish target compilation, boot or remote access",
                            "LVM2 and linux-firmware have no separate advisory review yet"]}


def check_export(root: Path):
    for name in EXCLUDED:
        path = root_path(root, name)
        if path.exists() and (not path.is_dir() or any(path.iterdir())):
            raise Refusal("build export contains retained core build/runtime state: " + name)
    for name in ("etc/tup/owner-enrolled.json", STAGE):
        if root_path(root, name).exists():
            raise Refusal("build export is already enrolled or has a layer build")
    ssh = root_path(root, "etc/ssh")
    if ssh.exists() and list(ssh.glob("ssh_host_*_key")):
        raise Refusal("build export contains a cloned private SSH host key")
    for binary in ("usr/bin/python3", "usr/bin/gcc", "usr/bin/make", "usr/bin/su"):
        # These tools may use in-root version symlinks; their final targets must
        # remain inside the export. The complete initial inventory binds them.
        path = root / binary
        if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
            raise Refusal("target core tool is absent or outside the export: " + binary)


def export_core(original: Path, root: Path, run) -> None:
    root.mkdir(mode=0o755)
    run("export", ["rsync", "-aHAX", "--numeric-ids", "--one-file-system",
                   *("--exclude=/" + name + "/***" for name in EXCLUDED), str(original) + "/", str(root) + "/"])
    check_export(root)


def stage_inputs(root: Path, cache: Path, verified: dict, chapters: list[str], source: Path = TUP) -> tuple[Path, dict]:
    """Copy the driver, pages, read-only helpers and verified archives into the export."""
    stage = root / STAGE
    stage.mkdir()
    shutil.copyfile(source / "driver.sh", stage / "driver.sh")
    shutil.copyfile(HERE / "common.sh", stage / "common.sh")
    shutil.copyfile(HERE / "run.sh", stage / "run.sh")
    shutil.copytree(source / "buildlib", stage / "buildlib")
    (stage / "overrides").mkdir()
    for chapter in chapters:
        shutil.copytree(source / CHAPTERS[chapter], stage / "chapters" / chapter)
    skip = shutil.ignore_patterns("__pycache__", "*.pyc", "evidence", "tests-runtime", "pages")
    for name in HELPERS:
        if (source / name).is_dir():
            shutil.copytree(source / name, stage / "tup" / name, ignore=skip)
    for path in stage.rglob("*"):
        if path.is_symlink():
            raise Refusal("symlink in staged layer inputs: " + path.name)
        if path.is_file():
            path.chmod(0o755 if path.suffix == ".sh" else 0o644)
    sources = root / "sources"
    sources.mkdir(exist_ok=True)
    for row in verified["sources"]:
        shutil.copyfile(cache / row["name"], sources / row["name"])
        checked_file(sources / row["name"], row["sha256"])
    return stage, inventory(stage)


def staged_unchanged(stage: Path, frozen: dict) -> bool:
    current = inventory(stage)
    current.pop("BUILD-INPUTS.json", None)
    current["."] = frozen["."]  # Adding the manifest changes only the stage directory's own mtime.
    return current == frozen


def run_chapters(root: Path, stage: Path, jobs: int, chapters: list[str], run) -> None:
    parent = [os.readlink("/proc/self/ns/" + name) for name in ("net", "mnt", "pid", "uts")]
    run("target-build", ["unshare", "--mount", "--net", "--pid", "--uts", "--fork", "--kill-child=KILL",
                         "--mount-proc", "/bin/bash", str(stage / "run.sh"), str(root), str(jobs), *parent, *chapters],
        timeout=4 * 3600)


def detach_inputs(workspace: Path, root: Path, stage: Path) -> Path:
    """Move this export's disposable inputs and ledger out; never touch the original core."""
    shutil.move(str(root / "sources"), str(workspace / "sources-and-ledger"))
    shutil.move(str(stage), str(workspace / "execution-inputs"))
    for name in ("dev", "proc", "sys", "run", "tmp"):
        path = root_path(root, name)
        if not path.is_dir() or any(path.iterdir()):
            raise Refusal("target build left runtime state in the export: " + name)
    return workspace / "sources-and-ledger/log"


def build(workspace: Path, core_validator: Path, cache: Path, gpg: Path, jobs: int, chapters: list[str]):
    if sys.platform != "linux" or os.geteuid() != 0:
        raise Refusal("target build requires root on Linux")
    if type(jobs) is not int or not 1 <= jobs <= 4:
        raise Refusal("layer jobs must be 1 through 4")
    if not chapters or len(set(chapters)) != len(chapters) or any(name not in CHAPTERS for name in chapters):
        raise Refusal("unknown or repeated layer chapter")
    if [name for name in CHAPTERS if name in chapters] != chapters:
        raise Refusal("layer chapters run in their fixed order: " + ", ".join(CHAPTERS))
    workspace = workspace.absolute()
    parent = workspace.parent
    if (workspace.resolve() != workspace or not parent.is_dir() or
            parent.stat().st_uid != os.geteuid() or stat.S_IMODE(parent.stat().st_mode) & 0o022):
        raise Refusal("workspace must be new under a real caller-owned private parent")
    if workspace.exists() or workspace.is_symlink():
        raise Refusal("layer builds never reuse a partial workspace")
    spec = check_core_spec(core_validator)
    options = dict(zip(spec["args"][1::2], spec["args"][2::2]))
    original = Path(options["--workspace"]).resolve() / "root"
    if workspace.is_relative_to(original) or original.is_relative_to(workspace):
        raise Refusal("layer workspace must be separate from the original core")
    for tool in ("rsync", "unshare", "mount", "chroot", "ip"):
        if shutil.which(tool) is None:
            raise Refusal("missing host build tool: " + tool)
    wanted = chapter_archives(TUP, chapters)
    workspace.mkdir(mode=0o700)

    def run(name, command, timeout=7200):
        with (workspace / (name + ".log")).open("xb") as log:
            result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                    timeout=timeout)
        if result.returncode:
            raise Refusal(name + " failed; preserve this workspace and its log")

    previous = stamp(completion_path(spec))
    run("core-validation", [sys.executable, spec["script"], *spec["args"]])
    completion = check_completion(spec, previous)
    shutil.copyfile(completion, workspace / "CORE-COMPLETION.json")
    core = load_json(completion)
    verified = verify_sources(cache, gpg, Path(options["--source-lock"]), wanted)
    write_json(workspace / "SOURCE-VERIFICATION.json", verified)
    root = workspace / "root"
    export_core(original, root, run)
    before = inventory(root)
    write_json(workspace / "before.json", before)
    stage, frozen = stage_inputs(root, cache, verified, chapters)
    manifest = {"schema": "tup-layer-build-inputs-v1", "profile": PROFILE, "chapters": chapters,
                "core_completion_sha256": file_hash(workspace / "CORE-COMPLETION.json"),
                "core_inputs_sha256": core["inputs_sha256"], "core_source_lock_sha256": core["source_lock_sha256"],
                "core_source_policy": {name: core[name] for name in
                    ("source_lock_purpose", "source_release_eligible", "release_gates", "advisory_review_sha256")},
                "source_verification_sha256": file_hash(workspace / "SOURCE-VERIFICATION.json"),
                "sources": verified["sources"], "jobs": jobs,
                "initial_tree_sha256": file_hash(workspace / "before.json"), "staged_inputs": frozen}
    write_json(workspace / "BUILD-INPUTS.json", manifest)
    shutil.copyfile(workspace / "BUILD-INPUTS.json", stage / "BUILD-INPUTS.json")
    # Check the copied execution tree immediately before use.
    if not staged_unchanged(stage, frozen):
        raise Refusal("staged layer inputs changed before execution")
    run_chapters(root, stage, jobs, chapters, run)
    for row in verified["sources"]:
        checked_file(root / "sources" / row["name"], row["sha256"])
    checked_file(stage / "BUILD-INPUTS.json", file_hash(workspace / "BUILD-INPUTS.json"))
    if not staged_unchanged(stage, frozen):
        raise Refusal("staged layer inputs changed during the build")
    if root_path(root, "etc/tup/owner-enrolled.json").exists() or list(root_path(root, "etc/ssh").glob("ssh_host_*_key")):
        raise Refusal("layer build unexpectedly enrolled the generic image")
    log = detach_inputs(workspace, root, stage)
    after = inventory(root)
    write_json(workspace / "after.json", after)
    changed = {name: {"before": before.get(name), "after": after.get(name)}
               for name in sorted(before.keys() | after.keys()) if before.get(name) != after.get(name)}
    write_json(workspace / "changes.json", changed)
    complete = chapters == list(CHAPTERS)
    receipt = {"schema": "tup-target-layers-v1", "status": "built-unenrolled" if complete else "partial-chapters",
               "release_eligible": False, "chapters": chapters,
               "core_completion_sha256": file_hash(workspace / "CORE-COMPLETION.json"),
               "core_inputs_sha256": core["inputs_sha256"], "build_inputs_sha256": file_hash(workspace / "BUILD-INPUTS.json"),
               "source_verification_sha256": file_hash(workspace / "SOURCE-VERIFICATION.json"),
               "initial_tree_sha256": file_hash(workspace / "before.json"), "root_tree_sha256": file_hash(workspace / "after.json"),
               "changes_sha256": file_hash(workspace / "changes.json"),
               "driver_receipts_sha256": file_hash(log / "receipts.jsonl"),
               "driver_state_sha256": file_hash(log / "driver.state"),
               "driver_snapshot": (log / "driver.v2/current").read_text().strip(),
               "retained_page_evidence": {path.name: file_hash(path) for path in sorted(log.iterdir()) if path.is_file()},
               "target_build_log_sha256": file_hash(workspace / "target-build.log"),
               "release_gates": core["release_gates"],
               "pending": ["owner enrollment and real policy authentication tests", "booted target kernel and firewall",
                           "service boot ordering", "physical network/private transport/Mac login",
                           "resource stress and recovery"]}
    write_json(workspace / "TARGET-LAYERS.json", receipt)
    if complete:
        # The packager's contract: only a root that passed every chapter and its
        # own offline checks gets the receipt boot/assemble.py requires.
        check_offline_root(root)
        check_kernel(root, KERNEL_RELEASE)
        write_json(workspace / "BOOT-LAYER.json", {
            "schema": "tup.boot-layer.v1", "architecture": "x86_64", "status": "complete",
            "core_inputs_sha256": core["inputs_sha256"],
            "source_lock_sha256": receipt["source_verification_sha256"],
            "recipe_sha256": receipt["build_inputs_sha256"],
            "root_tree_sha256": receipt["root_tree_sha256"],
            "target_layers_sha256": file_hash(workspace / "TARGET-LAYERS.json")})
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--core-validator", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--gpg", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--chapters", default=",".join(CHAPTERS),
                        help="comma-separated subset in fixed order; only the full set yields BOOT-LAYER.json")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(build(args.workspace, args.core_validator, args.cache, args.gpg, args.jobs,
                               args.chapters.split(",")), indent=2))
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print("REFUSED: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
