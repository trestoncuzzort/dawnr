import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

import pytest

sys.path.insert(0, str(Path(__file__).parent / "recipes"))
import release_decode_arms as driver

pytestmark = pytest.mark.skipif(os.name != "posix", reason="the GPU host uses POSIX")


@pytest.fixture
def host(tmp_path):
    root = tmp_path / "GPU checkout"
    recipes = root / "t/recipes"
    recipes.mkdir(parents=True)
    mock = recipes / "mock_route.py"
    mock.write_text('''import fcntl,json,os,sys
from pathlib import Path
root=Path(os.environ['D']); tag=sys.argv[1]
(root/'t/out').mkdir(parents=True,exist_ok=True)
with (root/'t/out/.laptop-gpu.lock').open('a') as gpu:
 try:fcntl.flock(gpu,fcntl.LOCK_EX | fcntl.LOCK_NB)
 except BlockingIOError:pass
 else:sys.exit(91)
with (root/'calls.txt').open('a') as stream:stream.write(tag+'\\n')
if tag==os.environ.get('FAKE_FAIL'):sys.exit(7)
ids=Path(os.environ['IDS']).read_text().split()
out=root/'t/out/spec-experiment'/tag; (out/'raw').mkdir(parents=True,exist_ok=True)
(out/'spec_first.json').write_text(json.dumps({'problems':len(ids),'per_problem':{i:{'taken':None} for i in ids},'answered':0}))
if os.environ.get('FAKE_FOREIGN'):(out/'raw/999999.json').write_text('{}')
runs=root/'t/out/laptop-runs';runs.mkdir(parents=True,exist_ok=True)
(runs/(tag+'.done')).write_text('0')
''')
    route = recipes / "laptop_route.sh"
    route.write_text('#!/bin/bash\nexec "' + sys.executable + '" "' + str(mock) + '" "$@"\n')
    (recipes / "v6_server_route.py").write_text("# stand-in; no server or model is started\n")
    (recipes / "seed_decode_cache.py").write_text("# stand-in cache seeder\n")
    panels = []
    for name, pool, ids in [("dev-95", "v5", "1\n2\n"), ("wider-145", "v7", "3\n4\n")]:
        path = root / (name + ".txt")
        path.write_text(ids)
        panels.append({"name": name, "pool": pool, "path": path.name, "count": 2, "sha256": driver.digest(path)})
    server = root / "server"
    server.mkdir()
    (server / "llama-server").write_text("stand-in")
    model = root / "model.gguf"
    model.write_bytes(b"model fixture")
    output = root / "ready"
    return root, server, model, output, panels


def run(host):
    root, server, model, output, panels = host
    identity = "fixture:" + driver.digest(model) + ":llama-" + driver.SERVER_REVISION
    return driver.generate(root, server, "candidate", model, identity, output, panels)


def test_failure_stops_and_completed_bundle_is_reused(host, monkeypatch):
    root, _, _, output, _ = host
    monkeypatch.setenv("FAKE_FAIL", "candidate-wider-off0")
    with pytest.raises(subprocess.CalledProcessError) as error:
        run(host)
    assert error.value.returncode == 7
    assert (output / "candidate-dev.ready.json").exists()
    assert not (output / "COMPLETE.json").exists()
    monkeypatch.delenv("FAKE_FAIL")
    arms = run(host)
    assert len(arms) == 6
    calls = (root / "calls.txt").read_text().splitlines()
    assert calls.count("candidate-dev") == 1
    assert calls.count("candidate-wider-off0") == 2
    assert len(list(output.glob("*.ready.json"))) == 6
    with tarfile.open(output / "candidate-dev.tar.gz") as tar:
        assert "candidate-dev/spec_first.json" in tar.getnames()
        assert all(name.startswith("candidate-dev/") for name in tar.getnames())


def test_changed_model_cannot_reuse_finished_outputs(host):
    root, _, model, _, _ = host
    run(host)
    calls = (root / "calls.txt").read_bytes()
    model.write_bytes(b"different model")
    with pytest.raises(ValueError, match="procedure changed"):
        run(host)
    assert (root / "calls.txt").read_bytes() == calls


def test_changed_cache_seeder_cannot_reuse_finished_outputs(host):
    root, _, _, _, _ = host
    run(host)
    calls = (root / "calls.txt").read_bytes()
    (root / "t/recipes/seed_decode_cache.py").write_text("# changed procedure\n")
    with pytest.raises(ValueError, match="procedure changed"):
        run(host)
    assert (root / "calls.txt").read_bytes() == calls


def test_foreign_raw_answer_is_not_bundled(host, monkeypatch):
    _, _, _, output, _ = host
    monkeypatch.setenv("FAKE_FOREIGN", "1")
    with pytest.raises(ValueError, match="foreign"):
        run(host)
    assert not list(output.glob("*.tar.gz"))
    assert not (output / "COMPLETE.json").exists()
