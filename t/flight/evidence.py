"""Pinned flight source bytes and optional, path-free identities for bounded comparison runs.

Atomic installation follows t/cache.py and t/cli.py. Expected source hashes are reviewed data, never learned from
the cache being checked. Receipts identify a replay's inputs; they are not self-contained proof certificates.
"""
from __future__ import annotations

import contextlib
import contextvars
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
import urllib.request

MANIFEST = Path(__file__).with_name("source-manifest.json")
ACTIVE = contextvars.ContextVar("flight_receipt", default=None)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def object_digest(value) -> str:
    return digest(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8"))


def atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix="." + path.name + ".", suffix=".tmp", dir=path.parent,
                                         delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def identity(repository: str, revision: str, path: str) -> tuple[str, str, str]:
    if (not isinstance(repository, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository)
            or any(part in (".", "..") for part in repository.split("/"))):
        raise ValueError("invalid source repository")
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("source revision must be a full commit hash")
    if (not isinstance(path, str) or not path or PurePosixPath(path).is_absolute()
            or any(part in ("", ".", "..") for part in path.split("/")) or "\\" in path):
        raise ValueError("source path must be a normalized relative path")
    return repository, revision, path


class SourceCache:
    def __init__(self, root: Path, manifest: Path = MANIFEST):
        self.root = Path(root)
        self.manifest_bytes = Path(manifest).read_bytes()
        document = json.loads(self.manifest_bytes)
        if not isinstance(document, dict) or document.get("schema") != 1 or not isinstance(document.get("sources"), list):
            raise ValueError("invalid flight source manifest")
        self.records = {}
        for record in document["sources"]:
            key = identity(record["repository"], record["revision"], record["path"])
            if (key in self.records or not re.fullmatch(r"[0-9a-f]{64}", record["sha256"])
                    or type(record["bytes"]) is not int or record["bytes"] <= 0):
                raise ValueError("invalid or duplicate flight source manifest record")
            self.records[key] = record

    def get(self, repository: str, revision: str, path: str, *, legacy: Path | None = None) -> Path:
        key = identity(repository, revision, path)
        if key not in self.records:
            raise ValueError(f"source has no reviewed digest: {repository}@{revision}:{path}")
        expected = self.records[key]
        destination = self.root / repository / revision / path
        if destination.is_symlink():
            raise ValueError("source cache entry is a symbolic link")
        candidate = destination if destination.exists() else legacy if legacy and legacy.exists() else None
        if candidate is not None:
            with candidate.open("rb") as handle:
                data = handle.read(expected["bytes"] + 1)
        else:
            url = f"https://raw.githubusercontent.com/{repository}/{revision}/{path}"
            with urllib.request.urlopen(url, timeout=60) as response:
                data = response.read(expected["bytes"] + 1)
        if len(data) != expected["bytes"] or digest(data) != expected["sha256"]:
            origin = "cached" if candidate is not None else "downloaded"
            raise ValueError(f"{origin} source digest mismatch: {repository}@{revision}:{path}")
        if candidate != destination:
            atomic_bytes(destination, data)
        receipt = ACTIVE.get()
        if receipt is not None:
            receipt.data["manifest_sha256"] = digest(self.manifest_bytes)
            receipt.sources[key] = dict(expected, identity_scope="reviewed_pinned_source")
        return destination


def generated_source(name: str, data: bytes) -> None:
    receipt = ACTIVE.get()
    if receipt is not None:
        receipt.generated[name] = {"name": name, "sha256": digest(data), "bytes": len(data)}


def observed_tree(root: Path, files: list[str]) -> None:
    receipt = ACTIVE.get()
    if receipt is None:
        return
    receipt.data["fixed_tree_scope"] = "observed listed files; not authenticated as a pinned upstream revision"
    for name in files:
        data = (root / name).read_bytes()
        receipt.sources[("working-tree", "unverified", name)] = {
            "repository": "working-tree", "revision": "unverified", "path": name,
            "sha256": digest(data), "bytes": len(data), "identity_scope": "observed_working_tree_bytes"}


def wrapper_source(text: str) -> None:
    receipt = ACTIVE.get()
    if receipt is not None and receipt.current is not None:
        receipt.current["wrapper_sha256"] = digest(text.encode("utf-8"))


def start_case(name: str, task: dict, inputs: list, wrapper: str, *, role: str = "function",
               task_bytes: bytes | None = None, flags: list[str] | None = None) -> None:
    receipt = ACTIVE.get()
    if receipt is not None:
        case = {"name": name, "role": role, "task_ast_sha256": object_digest(task),
                "wrapper_sha256": digest(wrapper.encode("utf-8")), "inputs_sha256": object_digest(inputs),
                "planned_inputs": len(inputs), "compiler_flags": flags or [], "processes": []}
        if task_bytes is not None:
            case["task_source_sha256"] = digest(task_bytes)
        receipt.data["cases"].append(case)
        receipt.current = case


def finish_case(result: dict) -> None:
    receipt = ACTIVE.get()
    if receipt is not None and receipt.current is not None:
        # Keep only stable summary fields, not exception messages that can contain machine paths.
        receipt.current["result"] = {key: result[key] for key in
            ("status", "points", "inputs", "agree", "narrowed_points", "skipped_inputs", "returned_rows")
            if key in result}
        if "status" in receipt.current["result"]:
            status = receipt.current["result"]["status"]
            if "error:" in status:
                receipt.current["result"]["status"] = status.split(":", 1)[0]
        receipt.current = None


def process_result(phase: str, command: list[str], *, result=None, error: Exception | None = None,
                   stdin: str | None = None) -> None:
    receipt = ACTIVE.get()
    if receipt is None or receipt.current is None:
        return
    event = {"phase": phase, "outcome": "error" if error is not None else "completed" if result.returncode == 0 else "failed",
             "exit_code": result.returncode if result is not None else None}
    if result is not None:
        event.update(stdout_sha256=digest(result.stdout.encode("utf-8")),
                     stderr_sha256=digest(result.stderr.encode("utf-8")),
                     stdout_lines=len(result.stdout.splitlines()))
    if error is not None:
        event["error_kind"] = type(error).__name__
    if stdin is not None:
        event["stdin_sha256"] = digest(stdin.encode("utf-8"))
    receipt.current["processes"].append(event)
    if phase == "compile" and "compiler" not in receipt.data:
        tool = command[0]
        compiler = {"driver": Path(tool).name}
        for name, option in (("version", "-dumpfullversion"), ("target", "-dumpmachine")):
            try:
                probe = subprocess.run([tool, option], capture_output=True, text=True, timeout=10)
                value = probe.stdout.strip()
                compiler[name] = value if probe.returncode == 0 and re.fullmatch(r"[A-Za-z0-9_.+:-]+", value) else "unavailable"
            except (OSError, subprocess.TimeoutExpired):
                compiler[name] = "unavailable"
        receipt.data["compiler"] = compiler


class Receipt:
    def __init__(self, kind: str):
        self.data = {"schema": 1, "kind": kind, "scope": "bounded_native_correspondence",
                     "standalone_replay_bundle": False,
                     "limitations": ["Hashes identify inputs; source and tool artifacts are not embedded.",
                                     "System headers, linked libraries and compiler executable bytes are not recorded.",
                                     "No claim about untested inputs or whole-module behavior."],
                     "cases": [], "skips": []}
        self.sources, self.generated, self.current = {}, {}, None

    def write(self, path: Path) -> None:
        self.data["sources"] = [self.sources[key] for key in sorted(self.sources)]
        self.data["generated_sources"] = [self.generated[key] for key in sorted(self.generated)]
        atomic_bytes(path, (json.dumps(self.data, sort_keys=True, indent=2, allow_nan=False) + "\n").encode())


@contextlib.contextmanager
def recording(path: Path | None, kind: str):
    if path is None:
        yield None
        return
    receipt = Receipt(kind)
    token = ACTIVE.set(receipt)
    try:
        yield receipt
    except BaseException as error:
        receipt.data["run_outcome"] = "error"
        receipt.data["error_kind"] = type(error).__name__
        raise
    finally:
        ACTIVE.reset(token)
        receipt.write(Path(path))
