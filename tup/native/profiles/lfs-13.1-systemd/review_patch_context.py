#!/usr/bin/env python3
"""Check approved patch application on isolated file copies, never run packages.

Source authentication is separate. This produces PATCH-APPLICATION.json with
observed source hashes and exact GNU patch statuses. It includes deleted-file
inputs and preserves the source archive; only its selected regular files are
copied into a bounded disposable temporary directory.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile
import tempfile


HERE = Path(__file__).resolve().parent
CHECKS = (
    ("bzip2-1.0.8.tar.gz", ("bzip2-1.0.8-install_docs-1.patch",)),
    ("coreutils-9.11.tar.xz", ("coreutils-9.11-i18n-1.patch",)),
    ("expect5.45.4.tar.gz", ("expect-5.45.4-gcc15-1.patch",)),
    ("glibc-2.44.tar.xz", ("glibc-fhs-1.patch", "glibc-2.44-upstream_fixes-3.patch")),
    ("kbd-2.10.0.tar.xz", ("kbd-2.10.0-backspace-1.patch",)),
    ("Python-3.14.10.tar.xz", ("Python-3.14.7-openssl_4-1.patch",)),
    ("tar-1.35.tar.xz", ("tar-1.35-acl_fix-1.patch",)),
)


def module(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + ".py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def sha(data):
    return hashlib.sha256(data).hexdigest()


def changed_lines(data):
    return [line for line in data.splitlines() if line.startswith((b"+", b"-")) and not line.startswith((b"+++", b"---"))]


def patch_paths(data):
    result = set()
    for raw in re.findall(rb"^(?:---|\+\+\+) ([^\t\n ]+)", data, re.M):
        if raw == b"/dev/null":
            continue
        path = PurePosixPath(raw.decode("utf-8"))
        if path.is_absolute() or len(path.parts) < 2 or ".." in path.parts or "\\" in str(path):
            raise ValueError("unsafe patch path")
        result.add(PurePosixPath(*path.parts[1:]).as_posix())
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bash", default=shutil.which("bash"))
    args = parser.parse_args()
    patch_version = subprocess.check_output([args.bash, "--noprofile", "--norc", "-c", "patch --version"], text=True, timeout=30).splitlines()[0]
    patch_digest = subprocess.check_output([args.bash, "--noprofile", "--norc", "-c", 'sha256sum "$(command -v patch)"'], text=True, timeout=30).split()[0]
    if not re.fullmatch(r"[0-9a-f]{64}", patch_digest):
        raise ValueError("invalid host patch identity")
    python_adapter, context_adapter = module("adapt-python-openssl"), module("adapt-patch-context")
    rows = []
    for archive, names in CHECKS:
        original = {name: (args.cache / name).read_bytes() for name in names}
        selected = dict(original)
        for name, data in original.items():
            if name.startswith("Python-"):
                selected[name] = python_adapter.adapt(data)
            elif name in context_adapter.PINS:
                selected[name] = context_adapter.adapt(name, data)
            if changed_lines(data) != changed_lines(selected[name]):
                raise ValueError("context adaptation changed an added/deleted source line")
        paths = set().union(*(patch_paths(data) for data in selected.values()))
        archive_path = args.cache / archive
        with tempfile.TemporaryDirectory(prefix="tup-patch-context-") as temporary:
            target = Path(temporary).resolve()
            if target.parent != Path(tempfile.gettempdir()).resolve() or not target.name.startswith("tup-patch-context-"):
                raise ValueError("temporary patch target escaped its intended parent")
            with tarfile.open(archive_path) as source:
                members = source.getmembers()
                top = PurePosixPath(members[0].name).parts[0]
                # Read in archive order to avoid repeatedly decompressing xz.
                for member in members:
                    rel = str(PurePosixPath(member.name).relative_to(top))
                    if rel not in paths:
                        continue
                    if not member.isfile():
                        raise ValueError("changed archive member is not a regular file")
                    output = target / rel
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_bytes(source.extractfile(member).read())
            for name in names:
                (target / "input.patch").write_bytes(selected[name])
                result = subprocess.run([args.bash, "--noprofile", "--norc", "-c",
                                         "patch --batch --forward --fuzz=0 -p1 -i input.patch"],
                                        cwd=target, capture_output=True, timeout=60)
                output = result.stdout + result.stderr
                row = {"archive": archive, "patch": name, "exit_code": result.returncode,
                       "archive_sha256": sha(archive_path.read_bytes()), "original_patch_sha256": sha(original[name]),
                       "applied_patch_sha256": sha(selected[name]), "context_adapted": selected[name] != original[name],
                       "added_deleted_lines_unchanged": True, "patch_output_sha256": sha(output),
                       "failed_hunks": [line for line in output.decode("utf-8", "replace").splitlines()
                                        if "FAILED" in line or "ignored" in line or "fuzz" in line]}
                rows.append(row)
                print(f"{archive}: {name}: exit {result.returncode}", flush=True)
                if result.returncode:
                    print(output.decode("utf-8", "replace"), flush=True)
                    break
    report = {"schema": "tup-patch-context-review-v1", "reviewed_at": "2026-11-05",
              "patch_tool_sha256": patch_digest,
              "method": patch_version + " --batch --forward --fuzz=0 on isolated regular-file copies; no package commands",
              "scope": "context applicability only; source authentication and runtime behavior remain separate gates",
              "results": rows}
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    return 0 if len(rows) == 8 and all(row["exit_code"] == 0 for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
