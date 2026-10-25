#!/usr/bin/env python3
"""Generate six registered public-panel parts on a GPU host and checkpoint grading inputs.

Sources: release_arms.sh's tags and cache seeding; laptop_route.sh;
v6_server_route.py's complete-panel checks; evaluate.yml's input archive format.
https://github.com/trestoncuzzort/dawnr/blob/main/t/recipes/v6_server_route.py
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile

PANELS = [
    {"name": "dev-95", "pool": "v5", "path": "t/out/v6-20261018/dev-95.txt", "count": 95,
     "sha256": "f807aec7e6b89e524ded720d9ccfb670c1d504a5a5717966a4b870516701daf7"},
    {"name": "wider-145", "pool": "v7", "path": "t/out/v6-20261018/wider-145.txt", "count": 145,
     "sha256": "ba3f9e023b0a8d458989be9419dd016d26a35727eaf3c1cacc3a935f65f9ede7"},
]
SERVER_REVISION = "f1cee9941b0e843ea260bf8dd9a090fbd9711b6a"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def atomic_json(path, value):
    temporary = path.with_name(path.name + ".part")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def tag_for(prefix, panel, offset):
    if panel == "dev-95":
        return prefix + ("-dev" if offset == 0 else f"-seedoff{offset}")
    return prefix + f"-wider-off{offset}"


def bundle(checkout, tag, ids, destination):
    directory = checkout / "t/out/spec-experiment" / tag
    if directory.is_symlink():
        raise ValueError("a public grading bundle cannot follow a symbolic link")
    summary = json.loads((directory / "spec_first.json").read_text())
    if summary["problems"] != len(ids) or set(summary["per_problem"]) != set(ids):
        raise ValueError("the route did not account for the exact registered panel")
    taken = {tid for tid, state in summary["per_problem"].items() if state.get("taken") is not None}
    raw_ids = {p.stem for p in (directory / "raw").glob("*.json")}
    if summary["answered"] != len(taken) or raw_ids != taken:
        raise ValueError("the saved answers are incomplete or foreign to the panel")
    names = ["spec_first.json", "raw", "python.jsonl", "kept-specs.jsonl", "scored-specs.jsonl"]
    selected = [directory / name for name in names if (directory / name).exists()]
    for path in selected:
        if path.is_symlink() or (path.is_dir() and any(p.is_symlink() for p in path.rglob("*"))):
            raise ValueError("a public grading bundle cannot follow a symbolic link")
        if path.suffix == ".jsonl":
            for line in path.read_text().splitlines():
                if line.strip() and str(json.loads(line)["task_id"]) not in ids:
                    raise ValueError("a saved row is foreign to the panel")
    archive = destination / (tag + ".tar.gz")
    temporary = archive.with_name(archive.name + ".part")
    with tarfile.open(temporary, "w:gz") as tar:
        for path in selected:
            tar.add(path, arcname=tag + "/" + path.name)
    temporary.replace(archive)
    return {"filename": archive.name, "sha256": digest(archive), "bytes": archive.stat().st_size,
            "summary_sha256": digest(directory / "spec_first.json")}


def generate(checkout, server_dir, prefix, gguf, identity, destination, panels=None):
    import fcntl  # The GPU host is POSIX; importing the module alone stays portable for CI.
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", prefix):
        raise ValueError("use a simple release tag prefix")
    checkout, server_dir, gguf = checkout.resolve(), server_dir.resolve(), gguf.resolve()
    if not (server_dir / "llama-server").is_file():
        raise ValueError("the configured llama-server is missing")
    model_sha = digest(gguf)
    if model_sha not in identity.split(":") or not identity.endswith(":llama-" + SERVER_REVISION):
        raise ValueError("identity must bind this GGUF and the registered server revision")
    panels = panels or PANELS
    if [p["name"] for p in panels] != ["dev-95", "wider-145"]:
        raise ValueError("only the registered development panel pair is supported")
    planned, panel_ids = [], {}
    for panel in panels:
        path = checkout / panel["path"]
        ids = path.read_text().split()
        if digest(path) != panel["sha256"] or len(ids) != len(set(ids)) or len(ids) != panel["count"]:
            raise ValueError("a development panel differs from its registered digest or count")
        panel_ids[panel["name"]] = set(ids)
    for offset in (0, 1000, 2000):
        for panel in panels:
            planned.append({"tag": tag_for(prefix, panel["name"], offset), "panel": panel["name"],
                            "pool": panel["pool"], "offset": offset, "ids_path": panel["path"]})
    sources = set((checkout / "t").glob("*.py")) | set((checkout / "t/verifiers").rglob("*.py"))
    sources |= set((checkout / "nl/data").glob("*.gz"))
    sources |= {checkout / "t/recipes/laptop_route.sh", checkout / "t/recipes/v6_server_route.py"}
    source_hashes = {str(p.relative_to(checkout)): digest(p) for p in sorted(sources)}
    settings = {"PARALLEL": "4", "CONCURRENCY": "4", "BATCH": "16", "SLOT_CTX": "4096",
                "PYTHON_ATTEMPTS": "3"}
    plan = {"prefix": prefix, "model_sha256": model_sha, "identity": identity, "panels": panels,
            "settings": settings, "sources": source_hashes, "driver_sha256": digest(Path(__file__))}
    destination.mkdir(parents=True, exist_ok=True)
    with (destination / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        plan_path = destination / "plan.json"
        if plan_path.exists():
            if json.loads(plan_path.read_text()) != plan:
                raise ValueError("model or generation procedure changed; use a fresh prefix and output")
        else:
            if any((checkout / "t/out/spec-experiment" / p["tag"]).exists() for p in planned):
                raise ValueError("unreceipted generation already exists under this prefix")
            atomic_json(plan_path, plan)
        plan_sha, ready = digest(plan_path), []
        for item in planned:
            tag = item["tag"]
            receipt = destination / (tag + ".ready.json")
            if receipt.exists():
                saved = json.loads(receipt.read_text())
                if saved["plan_sha256"] != plan_sha or saved["arm"] != item or digest(
                        destination / saved["archive"]["filename"]) != saved["archive"]["sha256"]:
                    raise ValueError("a completed grading bundle differs from its receipt")
            else:
                env = {**os.environ, **settings, "D": str(checkout), "L": str(server_dir),
                       "IDS": str(checkout / item["ids_path"]), "POOL": item["pool"],
                       "SEED": str(checkout / "t/out/laptop-runs" /
                                   ("cache-" + tag_for(prefix, item["panel"], 0)))}
                subprocess.run(["bash", str(checkout / "t/recipes/laptop_route.sh"), tag, str(gguf), identity,
                                "--seed-offset", str(item["offset"])], cwd=checkout, env=env, check=True)
                done = checkout / "t/out/laptop-runs" / (tag + ".done")
                if done.read_text().strip() != "0":
                    raise ValueError("the decoder did not write a successful completion marker")
                archive = bundle(checkout, tag, panel_ids[item["panel"]], destination)
                atomic_json(receipt, {"plan_sha256": plan_sha, "arm": item, "archive": archive})
            ready.append({key: item[key] for key in ("tag", "panel", "pool")})
            atomic_json(destination / "arms.json", ready)
            print(f"ready {tag}", flush=True)
        atomic_json(destination / "COMPLETE.json", {"plan_sha256": plan_sha, "arms": ready})
    return ready


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--server-dir", type=Path, required=True)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--gguf", type=Path, required=True)
    parser.add_argument("--identity", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    generate(args.checkout, args.server_dir, args.prefix, args.gguf, args.identity, args.out)


if __name__ == "__main__":
    main()
