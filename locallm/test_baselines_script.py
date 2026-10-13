import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def test_baselines_script_passes():
    """test_baselines.py is a framework-free script; run it as the user would and read its exit status."""
    r = subprocess.run([sys.executable, str(HERE / "test_baselines.py")], cwd=str(HERE),
                       capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, (r.stdout[-3000:] + r.stderr[-3000:])
