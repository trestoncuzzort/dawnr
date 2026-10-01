"""t/self_eval.py: P(True) as Kadavath et al. elicit it (arXiv:2207.05221), and their metrics."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import self_eval  # noqa: E402


def test_p_true_reads_a_and_b_from_the_top_tokens_in_either_shape():
    top = [{"token": "A", "logprob": math.log(0.6)}, {"token": "B", "logprob": math.log(0.2)},
           {"token": "C", "logprob": math.log(0.1)}]
    assert abs(self_eval.p_true(top) - 0.75) < 1e-9
    assert self_eval.p_true([{"token": " B)", "prob": 0.3}, {"token": "A)", "prob": 0.1}]) == 0.25
    assert self_eval.p_true([{"token": "x", "prob": 1.0}]) is None


def test_the_conversation_carries_the_shots_with_their_answers_and_ends_on_the_question():
    shots = [{"question": "Q1", "answer": "a1", "right": True}, {"question": "Q2", "answer": "a2", "right": False}]
    msgs = self_eval.conversation("Q", "```t\nx\n```", shots)
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant", "user"]
    assert msgs[1]["content"] == "The proposed answer is: (A) True" and msgs[3]["content"] == "The proposed answer is: (B) False"
    assert msgs[-1]["content"].endswith("Is the proposed answer:\n (A) True\n (B) False")
    assert "Proposed Answer:\n```t\nx\n```" in msgs[-1]["content"]


def test_ask_prefills_the_assistant_turn_and_reads_one_token():
    sent = []

    def post(url, body, timeout=0):
        sent.append((url, body))
        if url.endswith("/apply-template"):
            return {"prompt": "<rendered>"}
        return {"completion_probabilities": [{"top_logprobs": [{"token": "A", "logprob": math.log(0.9)},
                                                               {"token": "B", "logprob": math.log(0.1)}]}]}
    assert abs(self_eval.ask("h:1", [{"role": "user", "content": "q"}], post=post) - 0.9) < 1e-9
    assert sent[1][1]["prompt"] == "<rendered>The proposed answer is: (" and sent[1][1]["n_predict"] == 1


def test_auroc_ece_and_brier_on_known_cases():
    assert self_eval.auroc([0.9, 0.8, 0.1, 0.2], [True, True, False, False]) == 1.0
    assert self_eval.auroc([0.1, 0.9], [True, False]) == 0.0
    assert self_eval.auroc([0.5, 0.5], [True, False]) == 0.5
    assert self_eval.auroc([0.5], [True]) is None
    assert self_eval.ece([1.0, 0.0], [True, False], bins=2) == 0.0
    # two equal-count bins: [0.2, 0.4] predict 0.3 and half are right; [0.6, 0.8] predict 0.7 and all are
    assert abs(self_eval.ece([0.2, 0.4, 0.6, 0.8], [False, True, True, True], bins=2) - 0.25) < 1e-9
    assert self_eval.brier([1.0, 0.0], [True, True]) == 0.5


def test_the_summary_compares_what_it_calls_true_with_the_base_rate():
    s = self_eval.summary([0.9, 0.7, 0.2, 0.1], [True, False, False, False])
    assert (s["base rate"], s["called true (P > 0.5)"], s["right among those"], s["accuracy among those"]) == (0.25, 2, 1, 0.5)
