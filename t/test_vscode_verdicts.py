"""Behavioral checks of the actual client, without requiring a running editor."""
from pathlib import Path
import shutil
import subprocess
import unittest


@unittest.skipUnless(shutil.which("node"), "Node is required for client behavior tests")
class ClientVerdictTests(unittest.TestCase):
    def test_client_verdict_identity_and_confirmation(self):
        path = Path(__file__).resolve().parent / "editors" / "vscode" / "test_verdicts.js"
        result = subprocess.run(["node", "--test", str(path)], text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
