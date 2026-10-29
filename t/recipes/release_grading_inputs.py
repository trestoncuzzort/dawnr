"""Validate completed model outputs before handing them to frozen cloud graders.

This module never asks a model, runs a reference, grades a proof, or selects weights.
Development panels may be public; precision and given-specification inputs stay sealed.
Sources: release_decode_arms.py, grade_spec33.py, ceiling.yml, teacher_outputs.sh;
https://docs.cloud.google.com/storage/docs/objects
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile
import tempfile
import zipfile

from release_decode_arms import PANELS, SERVER_REVISION, tag_for

MAX_BYTES = 128 * 1024**2
HEX = re.compile(r"[0-9a-f]{64}")
QUESTIONS_SHA = "effc2f4e586e0c4f7638a5a9a2b75515aaf7019de03ca819d46e5aa3d593ab24"
SETTINGS = {"PARALLEL": "4", "CONCURRENCY": "4", "BATCH": "16", "SLOT_CTX": "4096", "PYTHON_ATTEMPTS": "3"}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def json_bytes(value):
    return (json.dumps(value, indent=2) + "\n").encode()


def safe_name(name):
    p = PurePosixPath(name)
    require(bool(name) and not p.is_absolute() and str(p) == name and ".." not in p.parts
            and "\\" not in name and not any(ord(c) < 32 for c in name), "unsafe archive path")
    return p


def read_jsonl(data):
    return [json.loads(line) for line in data.decode().splitlines() if line.strip()]


def open_backup(archive, expected_sha, private_key, destination):
    """Authenticate the complete encrypted ZIP before opening and verify every file."""
    archive, destination = Path(archive), Path(destination)
    require(archive.stat().st_size <= MAX_BYTES and digest(archive) == expected_sha, "backup archive digest or size differs")
    with zipfile.ZipFile(archive) as z:
        require(sorted(z.namelist()) == ["files.json", "key.enc", "outputs.tar.gz.enc"], "unexpected sealed archive entries")
        require(sum(e.file_size for e in z.infolist()) <= MAX_BYTES, "sealed archive expands beyond the limit")
        files = json.loads(z.read("files.json"))
        require(isinstance(files, dict) and 0 < len(files) <= 4096, "invalid file manifest")
        for name, value in files.items():
            safe_name(name)
            require(isinstance(value, str) and HEX.fullmatch(value), "invalid payload digest")
        if destination.exists():
            saved = json.loads((destination / ".verified-backup.json").read_text())
            require(saved == {"archive_sha256": expected_sha, "files": files}, "backup identity changed")
            require(all((destination / name).is_file() and not (destination / name).is_symlink()
                        and digest(destination / name) == value for name, value in files.items()), "recovered files changed")
            return files
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
            work = Path(temporary)
            for name in ("key.enc", "outputs.tar.gz.enc"):
                (work / name).write_bytes(z.read(name))
            subprocess.run(["openssl", "pkeyutl", "-decrypt", "-inkey", str(private_key),
                            "-pkeyopt", "rsa_padding_mode:oaep", "-pkeyopt", "rsa_oaep_md:sha256",
                            "-in", str(work / "key.enc"), "-out", str(work / "key")], check=True, capture_output=True)
            subprocess.run(["openssl", "enc", "-d", "-aes-256-cbc", "-pbkdf2", "-iter", "200000",
                            "-in", str(work / "outputs.tar.gz.enc"), "-out", str(work / "payload.tar.gz"),
                            "-pass", "file:" + str(work / "key")], check=True, capture_output=True)
            payload = work / "payload"; payload.mkdir(mode=0o700)
            with tarfile.open(work / "payload.tar.gz") as tar:
                entries = tar.getmembers()
                require(len(entries) == len(files) and {e.name for e in entries} == set(files), "payload differs from file manifest")
                require(all(e.isfile() for e in entries) and sum(e.size for e in entries) <= MAX_BYTES, "unsafe payload member or size")
                for entry in entries:
                    target = payload / entry.name; target.parent.mkdir(parents=True, exist_ok=True)
                    with tar.extractfile(entry) as source, target.open("wb") as output:
                        shutil.copyfileobj(source, output)
                    require(digest(target) == files[entry.name], "payload file digest differs")
            (payload / ".verified-backup.json").write_bytes(json_bytes({"archive_sha256": expected_sha, "files": files}))
            payload.replace(destination)
    return files


def model_identity(value, seed, registration):
    prefix = registration["seeds"][str(seed)]["identity_prefix"]
    require(isinstance(value, str) and value.startswith(prefix) and value.endswith(":llama-" + SERVER_REVISION), "model identity changed")
    sha = value[len(prefix):].split(":", 1)[0]
    require(HEX.fullmatch(sha), "model identity lacks an exact model digest")
    require(value == prefix + sha + ":llama-" + SERVER_REVISION, "unexpected model identity fields")
    return sha


def panel_ids(panel, registration):
    ids = registration["panel_ids"][panel["name"]]
    data = "".join(x + "\n" for x in ids).encode()
    require(len(ids) == len(set(ids)) == panel["count"] and hashlib.sha256(data).hexdigest() == panel["sha256"], "registered panel changed")
    return set(ids)


def check_summary(data, ids, answers_required=True):
    summary = json.loads(data)
    require(summary["problems"] == len(ids) and set(summary["per_problem"]) == ids, "summary does not cover the exact panel")
    taken = {tid for tid, value in summary["per_problem"].items() if value.get("taken") is not None}
    if answers_required or "answered" in summary:
        require(summary["answered"] == len(taken), "summary answer count differs")
    return summary, taken


def development_inputs(root, seed, tag, registration):
    """Return the exact original public bundle only after complete-panel validation."""
    prefix = registration["seeds"][str(seed)]["prefix"]
    planned = [{"tag": tag_for(prefix, p["name"], offset), "panel": p["name"], "pool": p["pool"],
                "offset": offset, "ids_path": p["path"]} for offset in (0, 1000, 2000) for p in PANELS]
    arm = next((a for a in planned if a["tag"] == tag), None)
    require(arm is not None, "only the registered development arms may be public")
    folder = Path(root) / "evaluation/t/out/release-decoded" / prefix
    plan_path = folder / "plan.json"; plan = json.loads(plan_path.read_text())
    ready = json.loads((folder / (tag + ".ready.json")).read_text())
    require(plan["prefix"] == prefix and plan["panels"] == PANELS and plan["settings"] == SETTINGS, "decode procedure changed")
    require(plan["sources"] == registration["sources"] and plan["driver_sha256"] == registration["decode_driver_sha256"], "decode sources changed")
    model_sha = model_identity(plan["identity"], seed, registration)
    require(plan["model_sha256"] == model_sha, "decode model digest differs")
    require(ready["plan_sha256"] == digest(plan_path) and ready["arm"] == arm, "completion receipt differs")
    meta = ready["archive"]
    require(meta["filename"] == tag + ".tar.gz", "archive filename differs")
    archive = folder / meta["filename"]
    require(archive.stat().st_size == meta["bytes"] and archive.stat().st_size <= MAX_BYTES
            and digest(archive) == meta["sha256"], "decode archive differs")
    panel = next(p for p in PANELS if p["name"] == arm["panel"])
    ids = panel_ids(panel, registration)
    content = {}
    with tarfile.open(archive) as tar:
        entries = tar.getmembers()
        require(len(entries) == len({e.name for e in entries}) and sum(e.size for e in entries) <= MAX_BYTES, "duplicate or oversized public members")
        for entry in entries:
            name = safe_name(entry.name)
            require(name.parts[0] == tag and not entry.issym() and not entry.islnk(), "foreign or linked public member")
            relative = str(name.relative_to(tag))
            if entry.isdir():
                require(relative == "raw", "unexpected public directory")
                continue
            require(entry.isfile() and (relative in ("spec_first.json", "python.jsonl", "kept-specs.jsonl", "scored-specs.jsonl")
                    or re.fullmatch(r"raw/[0-9]+\.json", relative)), "unexpected public file")
            content[relative] = tar.extractfile(entry).read()
    require("spec_first.json" in content, "missing decode summary")
    require(hashlib.sha256(content["spec_first.json"]).hexdigest() == meta["summary_sha256"], "summary digest differs")
    _summary, taken = check_summary(content["spec_first.json"], ids)
    raw_ids = {PurePosixPath(name).stem for name in content if name.startswith("raw/")}
    require(raw_ids == taken and raw_ids <= ids, "raw answers differ from the panel or summary")
    for name, data in content.items():
        if name.endswith(".jsonl"):
            require(all(str(row["task_id"]) in ids for row in read_jsonl(data)), "foreign row in public bundle")
    return {"archive": archive, "sha256": meta["sha256"], "model_sha256": model_sha,
            "arm": {k: arm[k] for k in ("tag", "panel", "pool")}}


def precision_inputs(root, seed, registration):
    prefix = registration["seeds"][str(seed)]["prefix"]; tag = prefix + "-spec20"
    checkout = Path(root) / "evaluation"; runs = checkout / "t/out/laptop-runs"
    cache = runs / ("cache-" + tag)
    protocol = json.loads((cache / "protocol.json").read_text())
    require((runs / (tag + ".done")).read_text().strip() == "0"
            and json.loads((cache / "completed.json").read_text()) == protocol, "precision route is incomplete")
    require(protocol["sources"] == {k: v for k, v in registration["sources"].items() if not k.startswith("t/recipes/")}
            and protocol["driver_sha256"] == registration["route_driver_sha256"], "precision sources changed")
    require(protocol["schema"] == 1 and protocol["decoder"] == "llama.cpp-Q8_0" and protocol["model"] == "dawnr-route", "precision decoder changed")
    require(protocol.get("seed_rule") == "sha256(canonical_json([stage, messages]))[:8] & 0x7fffffff", "precision seed rule changed")
    require(protocol["route_args"] == registration["seeds"][str(seed)]["precision_route_args"], "precision generation arguments changed")
    model_sha = model_identity(protocol["identity"], seed, registration)
    panel = PANELS[0]; ids = panel_ids(panel, registration)
    require(protocol["panel_sha256"] == panel["sha256"], "precision panel changed")
    folder = checkout / "t/out/spec-experiment" / tag
    files = {name: (folder / name).read_bytes() for name in ("spec_first.json", "python.jsonl", "scored-specs.jsonl")}
    files["panel.txt"] = (checkout / panel["path"]).read_bytes()
    require(hashlib.sha256(files["panel.txt"]).hexdigest() == panel["sha256"], "precision panel bytes changed")
    summary, _taken = check_summary(files["spec_first.json"], ids, answers_required=False)
    passing = {tid for tid, state in summary["per_problem"].items() if state.get("python") is not None}
    python_ids = [str(r["task_id"]) for r in read_jsonl(files["python.jsonl"])]
    require(len(python_ids) == len(set(python_ids)) and set(python_ids) == passing, "precision Python evidence differs")
    require(all(str(r["task_id"]) in ids for r in read_jsonl(files["scored-specs.jsonl"])), "foreign precision row")
    files["manifest.json"] = json_bytes({"tag": tag, "files": {k: hashlib.sha256(v).hexdigest() for k, v in files.items()}})
    return tag, model_sha, files


def given_spec_inputs(root, seed, registration, questions):
    prefix = registration["seeds"][str(seed)]["prefix"]
    require(hashlib.sha256(questions).hexdigest() == QUESTIONS_SHA, "given specification panel changed")
    answers = (Path(root) / "evaluation/t/out" / ("spec33-" + prefix) / "spec-answers.jsonl").read_bytes()
    named = [r["name"] for r in read_jsonl(questions)]; rows = read_jsonl(answers)
    require(len(named) == len(set(named)) == len(rows) == 33
            and {r["name"] for r in rows} == set(named), "given specification answers are missing, duplicate or foreign")
    require(all(r.get("model") == prefix and r.get("system") == "s1" and isinstance(r.get("reply"), str) for r in rows), "given specification answer metadata changed")
    files = {"questions.jsonl": questions, "answers.jsonl": answers}
    manifest = {"label": prefix, "answer_model": prefix,
                **{role: {"path": name, "sha256": hashlib.sha256(files[name]).hexdigest()}
                   for role, name in (("questions", "questions.jsonl"), ("answers", "answers.jsonl"))}}
    files["manifest.json"] = json_bytes(manifest)
    return prefix, files


def seal_inputs(files, destination, input_key):
    """Write the existing private-input format; no plaintext publication path exists."""
    destination = Path(destination)
    require(not destination.exists(), "refusing to replace an input asset")
    require(0 < sum(map(len, files.values())) <= MAX_BYTES, "input size outside the limit")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
        plain = Path(temporary) / "inputs.tar.gz"
        with tarfile.open(plain, "w:gz") as tar:
            for name, data in sorted(files.items()):
                require(str(safe_name(name)).count("/") == 0, "private inputs must be flat")
                info = tarfile.TarInfo(name); info.size = len(data); info.mode = 0o600
                tar.addfile(info, io.BytesIO(data))
        sealed = Path(temporary) / "inputs.enc"
        subprocess.run(["openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-iter", "200000", "-salt",
                        "-in", str(plain), "-out", str(sealed), "-pass", "file:" + str(input_key)], check=True, capture_output=True)
        sealed.replace(destination)
    return digest(destination)


def claim_dispatch(path, request):
    """Journal before dispatch; an ambiguous attempt is never repeated automatically."""
    path = Path(path)
    if path.exists():
        record = json.loads(path.read_text())
        require(record["request"] == request, "a submitted input or workflow changed")
        require(record.get("run_id"), "previous dispatch is unresolved; inspect its original attempt")
        return record["run_id"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump({"request": request, "status": "dispatching"}, stream, indent=2)
    return None


def record_dispatch(path, run_id):
    require(type(run_id) is int and run_id > 0, "invalid workflow run ID")
    path = Path(path); record = json.loads(path.read_text())
    require(record.get("run_id", run_id) == run_id, "dispatch already belongs to another run")
    record.update(run_id=run_id, status="submitted")
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_bytes(json_bytes(record)); temporary.replace(path)
