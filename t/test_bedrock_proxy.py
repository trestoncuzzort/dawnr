"""The Bedrock proxy's two mappings (t/recipes/bedrock_proxy.py): the route's request to Converse, and a Converse
result to the reply the route checks. Source: docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "recipes"))
import bedrock_proxy as bp  # noqa: E402


class MappingTest(unittest.TestCase):
    def test_system_goes_to_system_blocks_and_roles_alternate(self):
        body = {"messages": [{"role": "system", "content": "be brief"}, {"role": "user", "content": "q1"},
                             {"role": "assistant", "content": "a1"}, {"role": "user", "content": "q2"}],
                "max_tokens": 64, "temperature": 0.8, "top_p": 0.95}
        system, messages, config = bp.to_converse(body)
        self.assertEqual(system, [{"text": "be brief"}])
        self.assertEqual([m["role"] for m in messages], ["user", "assistant", "user"])
        self.assertEqual(messages[0]["content"], [{"text": "q1"}])
        self.assertEqual(config, {"maxTokens": 64, "temperature": 0.8, "topP": 0.95})

    def test_consecutive_same_role_messages_are_merged(self):
        _, messages, _ = bp.to_converse({"messages": [{"role": "user", "content": "a"}, {"role": "user", "content": "b"}]})
        self.assertEqual(len(messages), 1) and self.assertEqual(len(messages[0]["content"]), 2)

    def test_reply_has_exactly_what_the_route_checks(self):
        result = {"output": {"message": {"role": "assistant", "content": [{"reasoningContent": {"text": "hmm"}},
                                                                            {"text": "```t\nt 1\n```"}]}},
                  "stopReason": "end_turn", "usage": {"inputTokens": 100, "outputTokens": 20, "totalTokens": 120}}
        reply = bp.from_converse(result, 1024, "deepseek.v3.2")
        self.assertEqual(len(reply["choices"]), 1)
        self.assertEqual(reply["choices"][0]["message"]["content"], "```t\nt 1\n```")
        self.assertEqual(reply["choices"][0]["finish_reason"], "stop")
        self.assertEqual(reply["usage"]["completion_tokens"], 20)

    def test_max_tokens_stop_is_length_and_the_count_is_capped(self):
        result = {"output": {"message": {"content": [{"text": "x"}]}}, "stopReason": "max_tokens",
                  "usage": {"inputTokens": 1, "outputTokens": 1030, "totalTokens": 1031}}
        reply = bp.from_converse(result, 1024, "m")
        self.assertEqual(reply["choices"][0]["finish_reason"], "length")
        self.assertEqual(reply["usage"]["completion_tokens"], 1024)


if __name__ == "__main__":
    unittest.main()
