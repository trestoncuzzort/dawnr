#!/usr/bin/env python3
"""Check two backports and their vulnerable twins on disposable regular files."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    profile = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location("backport_regressions", profile / "python-backport-tests.py")
    tests = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tests)
    patch_file = profile / "python-3.14.10-security-backports.patch"
    review = json.loads((profile / "PYTHON-BACKPORT-REVIEW.json").read_bytes())
    if sha(patch_file) != review["patch_sha256"]:
        raise ValueError("backport patch changed since review")
    with tempfile.TemporaryDirectory(prefix="tup-backport-context-") as temporary:
        root = Path(temporary)
        with tarfile.open(args.archive) as archive:
            for relative, record in review["files"].items():
                member = archive.getmember("Python-3.14.10/" + relative)
                if not member.isfile():
                    raise ValueError("reviewed source must be a regular file")
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.extractfile(member).read())
                if sha(target) != record["original_file_sha256"]:
                    raise ValueError("unreviewed original source bytes")
        outcomes = {}
        for name, test in (("pop3", tests.test_pop3), ("wrealpath", tests.test_wrealpath)):
            try:
                test(root)
            except (AssertionError, subprocess.CalledProcessError):
                outcomes[name + "_vulnerable_twin"] = "rejected"
            else:
                raise ValueError("regression did not reject the vulnerable twin: " + name)
        command = ["patch", "--batch", "--forward", "--fuzz=0", "-Np1", "-i", str(patch_file)]
        applied = subprocess.run(command, cwd=root, check=True, capture_output=True, text=True)
        for relative, record in review["files"].items():
            if sha(root / relative) != record["selected_file_sha256"]:
                raise ValueError("unexpected patched source bytes")
        tests.test_pop3(root)
        tests.test_wrealpath(root)
        outcomes.update(pop3_patched="passed", wrealpath_patched="passed")
    report = {"schema": "tup-python-backport-regression-review-v1", "outcomes": outcomes,
              "archive_sha256": sha(args.archive), "patch_sha256": sha(patch_file),
              "regression_script_sha256": sha(profile / "python-backport-tests.py"),
              "review_sha256": sha(profile / "PYTHON-BACKPORT-REVIEW.json"),
              "patch_stdout": applied.stdout, "patch_stderr": applied.stderr,
              "tools": {}}
    for tool in ("patch", "gcc"):
        executable = Path(shutil.which(tool)).resolve()
        report["tools"][tool] = {"sha256": sha(executable),
            "version": subprocess.check_output([str(executable), "--version"], text=True).splitlines()[0]}
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
