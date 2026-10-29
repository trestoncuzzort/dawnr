"""Keep foreign, incomplete and private content out of public grading submissions."""
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import zipfile

import pytest

sys.path.insert(0, str(Path(__file__).parent / "recipes"))
import release_grading_inputs as inputs


@pytest.fixture
def registration():
    root = Path(__file__).resolve().parents[1]
    return {"seeds": {"1": {"prefix": "fixture-s1", "identity_prefix": "fixture-s1:", "precision_route_args": ["registered-precision"]}},
            "panel_ids": {p["name"]: (root / p["path"]).read_text().split() for p in inputs.PANELS},
            "sources": {"t/pipeline.py": "a" * 64, "t/recipes/v6_server_route.py": "b" * 64},
            "decode_driver_sha256": "c" * 64, "route_driver_sha256": "b" * 64}


def add(tar, name, data=b"", kind=None):
    info = tarfile.TarInfo(name)
    if kind:
        info.type = kind; info.linkname = "/private/key"
    else:
        info.size = len(data)
    tar.addfile(info, None if kind else io.BytesIO(data))


def development(root, registration, extra=None, mutate=None):
    tag = "fixture-s1-dev"
    folder = root / "evaluation/t/out/release-decoded/fixture-s1"; folder.mkdir(parents=True)
    panel = inputs.PANELS[0]; ids = registration["panel_ids"][panel["name"]]
    summary = {"problems": 95, "answered": 0, "per_problem": {i: {} for i in ids}}
    content = {"spec_first.json": inputs.json_bytes(summary), "python.jsonl": b""}
    if mutate:
        mutate(content)
    archive = folder / (tag + ".tar.gz")
    with tarfile.open(archive, "w:gz") as tar:
        for name, data in content.items(): add(tar, tag + "/" + name, data)
        if extra: add(tar, *extra)
    model_sha = "d" * 64
    plan = {"prefix": "fixture-s1", "panels": inputs.PANELS, "settings": inputs.SETTINGS,
            "sources": registration["sources"], "driver_sha256": registration["decode_driver_sha256"],
            "identity": "fixture-s1:" + model_sha + ":llama-" + inputs.SERVER_REVISION, "model_sha256": model_sha}
    (folder / "plan.json").write_bytes(inputs.json_bytes(plan))
    ready = {"plan_sha256": inputs.digest(folder / "plan.json"),
             "arm": {"tag": tag, "panel": "dev-95", "pool": "v5", "offset": 0, "ids_path": panel["path"]},
             "archive": {"filename": archive.name, "sha256": inputs.digest(archive), "bytes": archive.stat().st_size,
                         "summary_sha256": hashlib.sha256(content["spec_first.json"]).hexdigest()}}
    (folder / (tag + ".ready.json")).write_bytes(inputs.json_bytes(ready))
    return folder


def test_zero_answer_arm_is_still_submitted(tmp_path, registration):
    development(tmp_path, registration)
    result = inputs.development_inputs(tmp_path, 1, "fixture-s1-dev", registration)
    assert result["arm"] == {"tag": "fixture-s1-dev", "panel": "dev-95", "pool": "v5"}
    assert result["sha256"] == inputs.digest(result["archive"])


@pytest.mark.parametrize("extra", [
    ("fixture-s1-dev/training-rows.jsonl", b"private"),
    ("fixture-s1-dev/../private.json", b"private"),
    ("fixture-s1-dev/raw/99999999.json", b"{}"),
    ("fixture-s1-dev/raw/1.json", b"", tarfile.SYMTYPE),
])
def test_public_archive_refuses_foreign_private_and_linked_files(tmp_path, registration, extra):
    development(tmp_path, registration, extra=extra)
    with pytest.raises(ValueError): inputs.development_inputs(tmp_path, 1, "fixture-s1-dev", registration)


@pytest.mark.parametrize("change", ["source", "model", "archive", "panel", "summary", "receipt"])
def test_altered_generation_or_completion_is_refused(tmp_path, registration, change):
    folder = development(tmp_path, registration)
    if change == "source": registration["sources"] = {"different": "e" * 64}
    elif change == "model": registration["seeds"]["1"]["identity_prefix"] = "other:"
    elif change == "archive": (folder / "fixture-s1-dev.tar.gz").write_bytes(b"changed")
    elif change == "panel": registration["panel_ids"]["dev-95"][0] = "99999999"
    else:
        p = folder / "fixture-s1-dev.ready.json"; r = json.loads(p.read_text())
        if change == "receipt": r["arm"]["offset"] = 1000
        else: r["archive"]["summary_sha256"] = "f" * 64
        p.write_bytes(inputs.json_bytes(r))
    with pytest.raises(ValueError): inputs.development_inputs(tmp_path, 1, "fixture-s1-dev", registration)


def test_heldout_tag_never_gets_a_public_path(tmp_path, registration):
    with pytest.raises(ValueError, match="development"):
        inputs.development_inputs(tmp_path, 1, "fixture-s1-heldout", registration)


def test_foreign_jsonl_row_is_refused_even_when_no_answers(tmp_path, registration):
    development(tmp_path, registration, mutate=lambda c: c.update({"python.jsonl": b'{"task_id": 99999999}\n'}))
    with pytest.raises(ValueError, match="foreign row"):
        inputs.development_inputs(tmp_path, 1, "fixture-s1-dev", registration)


def test_specs_only_precision_accepts_empty_saved_python(tmp_path, registration):
    tag = "fixture-s1-spec20"; root = tmp_path / "evaluation"
    folder = root / "t/out/spec-experiment" / tag; folder.mkdir(parents=True)
    runs = root / "t/out/laptop-runs"; cache = runs / ("cache-" + tag); cache.mkdir(parents=True)
    panel = inputs.PANELS[0]; ids = registration["panel_ids"]["dev-95"]
    p = root / panel["path"]; p.parent.mkdir(parents=True); p.write_text("\n".join(ids) + "\n")
    (folder / "spec_first.json").write_bytes(inputs.json_bytes({"problems": 95, "per_problem": {i: {} for i in ids}}))
    for name in ("python.jsonl", "scored-specs.jsonl"): (folder / name).write_text("")
    protocol = {"sources": {"t/pipeline.py": "a" * 64}, "driver_sha256": "b" * 64,
                "schema": 1, "decoder": "llama.cpp-Q8_0", "model": "dawnr-route", "route_args": ["registered-precision"],
                "seed_rule": "sha256(canonical_json([stage, messages]))[:8] & 0x7fffffff",
                "identity": "fixture-s1:" + "d" * 64 + ":llama-" + inputs.SERVER_REVISION, "panel_sha256": panel["sha256"]}
    for name in ("protocol.json", "completed.json"): (cache / name).write_bytes(inputs.json_bytes(protocol))
    (runs / (tag + ".done")).write_text("0\n")
    found, sha, files = inputs.precision_inputs(tmp_path, 1, registration)
    assert found == tag and sha == "d" * 64 and len(files) == 5
    protocol["route_args"] = ["different"]
    for name in ("protocol.json", "completed.json"): (cache / name).write_bytes(inputs.json_bytes(protocol))
    with pytest.raises(ValueError, match="arguments"):
        inputs.precision_inputs(tmp_path, 1, registration)


def test_given_specification_panel_and_names_are_complete(tmp_path, registration):
    questions = (Path(__file__).parent / "out/gcp-student-2026-10-11-s1/spec-heldout.jsonl").read_bytes()
    rows = [{"name": q["name"], "model": "fixture-s1", "system": "s1", "reply": ""} for q in inputs.read_jsonl(questions)]
    folder = tmp_path / "evaluation/t/out/spec33-fixture-s1"; folder.mkdir(parents=True)
    path = folder / "spec-answers.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    label, files = inputs.given_spec_inputs(tmp_path, 1, registration, questions)
    assert label == "fixture-s1" and set(files) == {"questions.jsonl", "answers.jsonl", "manifest.json"}
    rows[-1] = deepcopy(rows[0]); path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    with pytest.raises(ValueError, match="missing, duplicate or foreign"):
        inputs.given_spec_inputs(tmp_path, 1, registration, questions)


@pytest.mark.skipif(not shutil.which("openssl"), reason="the sealed-artifact transport needs OpenSSL")
def test_real_seal_and_backup_recovery_refuse_tampering(tmp_path):
    key = tmp_path / "key"; key.write_text("fixture secret\n")
    archive = tmp_path / "inputs.enc"
    inputs.seal_inputs({"manifest.json": b'{}\n', "answers.jsonl": b''}, archive, key)
    plain = tmp_path / "opened.tar.gz"
    subprocess.run(["openssl", "enc", "-d", "-aes-256-cbc", "-pbkdf2", "-iter", "200000", "-in", str(archive),
                    "-out", str(plain), "-pass", "file:" + str(key)], check=True, capture_output=True)
    with tarfile.open(plain) as tar: assert tar.extractfile("manifest.json").read() == b'{}\n'
    private = tmp_path / "private.pem"; public = tmp_path / "public.pem"
    subprocess.run(["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(private)], check=True, capture_output=True)
    subprocess.run(["openssl", "pkey", "-in", str(private), "-pubout", "-out", str(public)], check=True, capture_output=True)
    wrapped = tmp_path / "key.enc"
    subprocess.run(["openssl", "pkeyutl", "-encrypt", "-pubin", "-inkey", str(public), "-pkeyopt", "rsa_padding_mode:oaep",
                    "-pkeyopt", "rsa_oaep_md:sha256", "-in", str(key), "-out", str(wrapped)], check=True, capture_output=True)
    sealed = tmp_path / "backup.zip"
    with zipfile.ZipFile(sealed, "w") as z:
        z.write(archive, "outputs.tar.gz.enc"); z.write(wrapped, "key.enc")
        z.writestr("files.json", json.dumps({"manifest.json": hashlib.sha256(b'{}\n').hexdigest(), "answers.jsonl": hashlib.sha256(b'').hexdigest()}))
    destination = tmp_path / "recovered"
    inputs.open_backup(sealed, inputs.digest(sealed), private, destination)
    assert destination.stat().st_mode & 0o077 == 0
    inputs.open_backup(sealed, inputs.digest(sealed), private, destination)
    (destination / "manifest.json").write_text("tampered")
    with pytest.raises(ValueError, match="recovered files changed"):
        inputs.open_backup(sealed, inputs.digest(sealed), private, destination)
    with pytest.raises(ValueError, match="digest or size"):
        inputs.open_backup(sealed, "0" * 64, private, tmp_path / "other")


def test_dispatch_restart_never_repeats_an_ambiguous_call(tmp_path):
    path = tmp_path / "dispatch.json"; request = {"workflow": "evaluate.yml", "inputs": {"arms": "registered"}}
    assert inputs.claim_dispatch(path, request) is None
    with pytest.raises(ValueError, match="unresolved"):
        inputs.claim_dispatch(path, request)
    inputs.record_dispatch(path, 123)
    assert inputs.claim_dispatch(path, request) == 123
    with pytest.raises(ValueError, match="changed"):
        inputs.claim_dispatch(path, {**request, "inputs": {"arms": "altered"}})
    with pytest.raises(ValueError, match="another run"):
        inputs.record_dispatch(path, 456)
