"""The shared GPU route must report a failed decoder and reap the server it started.

Sources: recipes/laptop_route.sh; recipes/v6-gcp-candidate-dev.sh's server cleanup.
The stand-ins require no model, GPU, network request, or prover.
"""
import os
from pathlib import Path
import subprocess

import pytest


@pytest.mark.parametrize("decoder_status", [0, 7])
def test_decoder_status_reaches_the_caller_and_server_is_reaped(tmp_path, decoder_status):
    repo = tmp_path / "repo"
    recipes = repo / "t/recipes"
    recipes.mkdir(parents=True)
    (recipes / "v6_server_route.py").write_text(f"raise SystemExit({decoder_status})\n")
    binaries = tmp_path / "bin"
    binaries.mkdir()
    (binaries / "curl").write_text('#!/bin/sh\ntest -s "$SERVER_PID_FILE"\n')
    (binaries / "llama-server").write_text('#!/bin/sh\nprintf "%s\\n" "$$" > "$SERVER_PID_FILE"\nexec sleep 120\n')
    for path in binaries.iterdir():
        path.chmod(0o755)
    pid_file = tmp_path / "server.pid"
    script = Path(__file__).resolve().parent / "recipes/laptop_route.sh"
    environment = {**os.environ, "PATH": str(binaries) + os.pathsep + os.environ["PATH"],
                   "D": str(repo), "L": str(binaries), "SERVER_PID_FILE": str(pid_file)}
    result = subprocess.run(["bash", str(script), "check", "unused.gguf", "test-model"],
                            env=environment, capture_output=True, text=True, timeout=10)
    assert result.returncode == decoder_status, result.stderr
    assert (repo / "t/out/laptop-runs/check.done").read_text().strip() == str(decoder_status)
    assert pid_file.exists(), "the fake server must have started for the cleanup check"
    with pytest.raises(ProcessLookupError):
        os.kill(int(pid_file.read_text()), 0)
