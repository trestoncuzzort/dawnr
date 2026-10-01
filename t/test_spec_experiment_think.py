"""spec_experiment.chat (2026-10-01): Ollama's `think` is a field of the request, not a sampling
option (github.com/ollama/ollama docs/api.md: "think: (for thinking models) should the model think
before responding?"). The answer's options keep it, so sets decoded differently are never mixed;
the request carries it at the top level and not inside options. No server: urlopen is patched."""
from __future__ import annotations

import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import spec_experiment as se  # noqa: E402


class _Reply(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Think(unittest.TestCase):
    def _send(self, options):
        sent = {}

        def fake(req, timeout=None):
            sent["body"] = json.loads(req.data.decode("utf-8"))
            return _Reply(json.dumps({"message": {"content": "ok"}}).encode("utf-8"))
        with patch.object(se.urllib.request, "urlopen", fake):
            se.chat("127.0.0.1:11434", "m", [{"role": "user", "content": "x"}], options, 5.0)
        return sent["body"]

    def test_think_false_is_sent_as_a_request_field_and_not_as_an_option(self):
        options = {"temperature": 0, "seed": 1, "think": False}
        body = self._send(options)
        self.assertIs(body["think"], False)
        self.assertNotIn("think", body["options"])
        self.assertEqual(body["options"], {"temperature": 0, "seed": 1})
        self.assertIn("think", options)                 # the caller's record of the decode is untouched

    def test_without_the_flag_the_request_is_what_it_always_was(self):
        body = self._send({"temperature": 0, "seed": 1})
        self.assertNotIn("think", body)
        self.assertEqual(body["options"], {"temperature": 0, "seed": 1})


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
