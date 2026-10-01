"""spec_experiment.chat's OpenAI-shaped request for vLLM and for llama-server (2026-10-01): where the grammar and the
sampler fields go. No server: urlopen is patched."""
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import spec_experiment as se  # noqa: E402


def capture():
    seen = {}

    class R(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake(req, timeout=None):
        seen["body"] = json.loads(req.data.decode())
        return R(json.dumps({"choices": [{"message": {"content": "t"}, "finish_reason": "stop"}], "usage": {}}).encode())
    return seen, fake


OPTS = {"temperature": 0.7, "num_predict": 64, "seed": 3, "grammar": 'root ::= "t"', "top_p": 0.95, "top_k": 0,
        "repeat_penalty": 1.0}


class Flavour(unittest.TestCase):
    def test_vllm_keeps_structured_outputs_and_no_llama_fields(self):
        seen, fake = capture()
        with patch.object(se.urllib.request, "urlopen", fake):
            se.chat("h:1", "m", [{"role": "user", "content": "x"}], dict(OPTS), 5.0, "openai")
        b = seen["body"]
        self.assertEqual(b["structured_outputs"], {"grammar": 'root ::= "t"'})
        self.assertNotIn("grammar", b); self.assertNotIn("min_p", b); self.assertNotIn("top_k", b)

    def test_llamacpp_sends_grammar_and_the_reference_sampler(self):
        seen, fake = capture()
        with patch.object(se.urllib.request, "urlopen", fake):
            se.chat("h:1", "m", [{"role": "user", "content": "x"}], dict(OPTS), 5.0, "openai", "llamacpp")
        b = seen["body"]
        self.assertEqual(b["grammar"], 'root ::= "t"'); self.assertNotIn("structured_outputs", b)
        self.assertEqual((b["top_p"], b["top_k"], b["repeat_penalty"], b["min_p"]), (0.95, 0, 1.0, 0.0))
        self.assertEqual((b["temperature"], b["seed"], b["max_tokens"]), (0.7, 3, 64))



class LlamaGbnf(unittest.TestCase):
    def test_continuation_lines_join_and_nothing_else_changes(self):
        g = 'a ::= "x"\n     | "y"\n\t| "z"\nb ::= ( "p"\n  "q" )'
        self.assertEqual(se.llama_gbnf(g), 'a ::= "x" | "y" | "z"\nb ::= ( "p"\n  "q" )')

    def test_the_real_grammar_keeps_its_rules(self):
        g = "\n".join(l for l in (Path(se.__file__).parent / "t.gbnf").read_text().splitlines() if not l.lstrip().startswith("#"))
        j = se.llama_gbnf(g)
        names = lambda t: [l.split("::=")[0].strip() for l in t.splitlines() if "::=" in l]
        self.assertEqual(names(g), names(j))
        self.assertFalse(any(l.lstrip().startswith("|") for l in j.splitlines()))
        self.assertEqual(g.split(), [w for w in j.split()])

if __name__ == "__main__":
    unittest.main()
