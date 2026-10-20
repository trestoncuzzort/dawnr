"""Seven-kernel grading on Modal, so the v7 development grade never touches the laptop.

The kernels come from the engine's pinned Dockerfile (t-proof-engine
d13d11d01f8f50687ef645d60aa08c870d664b84/Dockerfile, sha 1483aad0...) truncated to the kernel
installs (lines 1-83, everything before its final COPY of the engine source); Modal's Dockerfile
spec does not implement COPY (modal.com/docs/guide/existing-images), so dawnr's own t/ (engine copy
plus the pipeline scripts) is mounted on top with add_local_dir instead. This is the same toolchain
the GCP prover box built with v6-gcp-proof-bootstrap.sh, moved to the only authenticated cloud.

    modal run --detach t/recipes/v7_modal_grade.py --mode smoke     # build the image, grade 2 tasks
    modal run --detach t/recipes/v7_modal_grade.py --mode grade --tag v7-20261019-dev

Sources: t/recipes/v6-gcp-proof-bootstrap.sh; t/recipes/v6-grade.sh;
modal.com/docs/guide/existing-images (receipt v7modalgrade).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import modal

HERE = Path(__file__).resolve().parent
IMAGE_DIR = HERE.parent / "out/v7-20261019/modal/proof-image"
STAGED_T = Path(os.environ.get("V7_STAGED_T", "/home/t/.claude/jobs/d76813cf/tmp/dawnr-t/t"))
STAGED_NL = Path(os.environ.get("V7_STAGED_NL", "/home/t/.claude/jobs/d76813cf/tmp/dawnr-serve/nl"))

kernels = (
    # add_python gives Modal a Python it can introspect for the function wrapper; the engine's own
    # run_par is invoked as system python3 in a subprocess, so the two never mix.
    modal.Image.from_dockerfile(str(IMAGE_DIR / "Dockerfile.kernels"), add_python="3.12")
    .env({"HOME": "/home/prover", "T_SPARK_JOBS": "1", "PYTHONUNBUFFERED": "1"})
    .add_local_dir(str(STAGED_T), "/opt/dawnr/t", copy=True)
    # The grader's pool (spec_experiment.pool, --pool v5) reads nl/data; without this mount the tests step
    # raised KeyError on the first task id (2026-10-20). The serve image mounts nl/ the same way.
    .add_local_dir(str(STAGED_NL), "/opt/dawnr/nl", copy=True)
)
data = modal.Volume.from_name("dawnr-data")
app = modal.App("dawnr-v7-grade", image=kernels)


@app.function(cpu=8, memory=16384, timeout=2400)
def smoke() -> dict:
    """Grade the committed tasks through every present kernel; assert all seven report."""
    import subprocess
    import sys

    sys.path.insert(0, "/opt/dawnr/t")
    import spec_check
    import spec_experiment as se

    tasks = Path("/tmp/smoke-tasks")
    tasks.mkdir(exist_ok=True)
    for name in ("abs", "gcd", "reverse", "swap_at"):
        src = Path(f"/opt/dawnr/t/tasks/{name}.t")
        if src.exists():
            (tasks / src.name).write_text(src.read_text())
    table = Path("/tmp/kernels.md")
    proc = subprocess.run(
        ["python3", "/opt/dawnr/t/run_par.py", "--tasks", str(tasks),
         "--out", "/tmp/art", "--table", str(table), "--jobs", "2", "--no-cache"],
        capture_output=True, text=True, timeout=2000, cwd="/opt/dawnr",
    )
    columns, rows = se.parse_kernel_table(table) if table.exists() else ([], {})
    return {"returncode": proc.returncode, "columns": columns, "tasks": sorted(rows),
            "all_seven_columns": set(columns) == set(spec_check.KERNELS),
            "stderr_tail": proc.stderr[-800:]}


@app.function(cpu=8, memory=16384, timeout=4 * 3600, volumes={"/data": data})
def grade(tag: str) -> dict:
    """Run the frozen grader (v6-grade.sh) on a generated answer set staged under /data.

    Expects /data/v7-20261019/spec-experiment/<tag> (raw + python/kept/scored/spec_first.json) and
    the 95-id panel at /data/v7-20261019/dev-95.txt. Copies the tag into the image's
    t/out/spec-experiment and grades there. T_SANDBOX is left at the engine default (the GCP
    bootstrap graded with no landlock), not the laptop's landlock, which a container may refuse.
    """
    import shutil
    import subprocess

    src = Path(f"/data/v7-20261019/spec-experiment/{tag}")
    dst = Path(f"/opt/dawnr/t/out/spec-experiment/{tag}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    # v6-grade.sh asserts `test ! -e kernels.md`; the post-step below copies grader outputs back beside the
    # source, so a re-run must start from the generation's files only (attempt 4, 2026-10-20, exited on that guard).
    for name in ("kernels.md", "extract.json", "tests.json"):
        (dst / name).unlink(missing_ok=True)
    if (dst / "tasks").exists():
        shutil.rmtree(dst / "tasks")
    panel = Path("/data/v7-20261019/dev-95.txt")
    out = Path(f"/data/v7-20261019/proof-results/{tag}")
    out.mkdir(parents=True, exist_ok=True)
    # v6-grade.sh takes a flock under t/out/v6-20261018 (its era's run directory); the staged image has no
    # t/out, so the script died there on 2026-10-20 after tests passed. Create it; the frozen script stays as is.
    Path("/opt/dawnr/t/out/v6-20261018").mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "T_MIN_KERNELS": "7", "T_SPARK_JOBS": "1", "PYTHONUNBUFFERED": "1"}
    proc = subprocess.run(
        ["bash", "/opt/dawnr/t/recipes/v6-grade.sh", tag, str(panel), str(out)],
        capture_output=True, text=True, timeout=4 * 3600 - 300, cwd="/opt/dawnr", env=env,
    )
    (out / "grade-stdout.log").write_text(proc.stdout)
    (out / "grade-stderr.log").write_text(proc.stderr)
    # carry the graded answer set's kernels.md/tasks back beside the source so a paired report reads them
    for name in ("kernels.md", "extract.json", "tests.json"):
        if (dst / name).exists():
            shutil.copy2(dst / name, src / name)
    if (dst / "tasks").exists():
        shutil.copytree(dst / "tasks", src / "tasks", dirs_exist_ok=True)
    data.commit()
    return {"returncode": proc.returncode, "graded": (out / "GRADED").exists(),
            "stdout_tail": proc.stdout[-400:], "stderr_tail": proc.stderr[-1000:]}


@app.local_entrypoint()
def main(mode: str = "smoke", tag: str = "v7-20261019-dev"):
    if mode == "smoke":
        print(json.dumps(smoke.remote(), indent=2), flush=True)
    elif mode == "grade":
        print(json.dumps(grade.remote(tag), indent=2), flush=True)
    else:
        raise ValueError("mode must be smoke or grade")
