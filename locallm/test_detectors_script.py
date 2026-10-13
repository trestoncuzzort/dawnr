import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def test_detectors_script_passes():
    """test_detectors.py is a framework-free script (its tests take the shingle function as a parameter and
    return (ok, note)); run it as the user would and read its exit status."""
    r = subprocess.run([sys.executable, str(HERE / "test_detectors.py")], cwd=str(HERE),
                       capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, (r.stdout[-3000:] + r.stderr[-3000:])
