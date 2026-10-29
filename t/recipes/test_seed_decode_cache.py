"""Cache reuse must not change the source run or replace existing answers."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import seed_decode_cache as seeder
from v6_server_route import Decoder


def saved_request(directory):
    directory.mkdir(parents=True, exist_ok=True)
    decoder = Decoder("unused", "model", "weights", directory, post=lambda _body: {
        "choices": [{"message": {"content": "saved answer"}, "finish_reason": "stop"}],
        "usage": {"completion_tokens": 3}})
    decoder.one([], 10, 0, .95, 0)
    return next(directory.glob("*.json"))


def test_seed_replays_answer_without_network_and_has_independent_bytes(tmp_path):
    source, target = tmp_path / "source cache", tmp_path / "target cache"
    original = saved_request(source)
    original_bytes = original.read_bytes()
    for name in ("completed.json", "protocol.json", "run.lock", "metadata.json"):
        (source / name).write_text("source metadata")
    assert seeder.seed_cache(source, target) == 1
    assert [p.name for p in target.iterdir()] == [original.name]
    decoder = Decoder("unused", "model", "weights", target,
                      post=lambda _body: pytest.fail("cached answer must not call the model"))
    assert decoder.one([], 10, 0, .95, 0) == ("saved answer", True, 3)
    (target / "completed.json").write_text("target completion")
    (target / original.name).write_text("changed target")
    assert original.read_bytes() == original_bytes
    assert (source / "completed.json").read_text() == "source metadata"


def test_existing_destination_answer_and_same_directory_are_preserved(tmp_path):
    source, target = tmp_path / "source", tmp_path / "target"
    original = saved_request(source)
    target.mkdir()
    existing = target / original.name
    existing.write_text("already saved here")
    assert seeder.seed_cache(source, target) == 0
    assert existing.read_text() == "already saved here"
    before = original.read_bytes()
    assert seeder.seed_cache(source, source) == 0
    assert original.read_bytes() == before


@pytest.mark.parametrize("bad", ["wrong-hash", "wrong-shape", "invalid-json"])
def test_invalid_source_record_is_not_imported(tmp_path, bad):
    source, target = tmp_path / "source", tmp_path / "target"
    path = saved_request(source)
    if bad == "wrong-hash":
        record = json.loads(path.read_text())
        record["identity"] = "different weights"
        path.write_text(json.dumps(record))
    elif bad == "wrong-shape":
        path.write_text("[]")
    else:
        path.write_text("{")
    with pytest.raises(ValueError):
        seeder.seed_cache(source, target)
    assert not list(target.iterdir())


@pytest.mark.parametrize("where", ["source", "destination"])
def test_linked_records_are_refused(tmp_path, where):
    source, target = tmp_path / "source", tmp_path / "target"
    path = saved_request(source)
    target.mkdir()
    linked = path if where == "source" else target / path.name
    if where == "source":
        path.rename(tmp_path / "outside.json")
    else:
        (tmp_path / "outside.json").write_text("do not modify")
    linked.symlink_to(tmp_path / "outside.json")
    with pytest.raises(ValueError):
        seeder.seed_cache(source, target)


@pytest.mark.skipif(os.name != "posix", reason="the route uses Bash on the GPU host")
def test_real_wrapper_removes_legacy_completion_link_before_run(tmp_path):
    root = tmp_path / "checkout with spaces"
    recipes = root / "t/recipes"
    recipes.mkdir(parents=True)
    for name in ("seed_decode_cache.py", "v6_server_route.py"):
        shutil.copyfile(Path(__file__).with_name(name), recipes / name)
    source = tmp_path / "source cache"
    saved_request(source)
    (source / "completed.json").write_text("source completion")
    target = root / "t/out/laptop-runs/cache-target"
    target.mkdir(parents=True)
    os.link(source / "completed.json", target / "completed.json")
    script = Path(__file__).with_name("laptop_route.sh").read_text()
    # Run the actual cache preparation, stopping before the model server starts.
    prefix = script.split('echo "$(date -u +%FT%TZ) start', 1)[0]
    subprocess.run(["bash", "-c", prefix, "route", "target", "unused.gguf", "weights"],
                   env={**os.environ, "D": str(root), "SEED": str(source)}, check=True)
    assert not (target / "completed.json").exists()
    (target / "completed.json").write_text("new completion")
    assert (source / "completed.json").read_text() == "source completion"
