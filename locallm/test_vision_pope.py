"""vision_pope.py: POPE's own answer parsing and metrics (github.com/RUCAIBox/POPE evaluate.py; arXiv:2305.10355)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import vision_pope  # noqa: E402


def test_parse_reads_the_first_sentence_as_pope_does():
    assert vision_pope.parse("Yes, there is a snowboard in the image.") == "yes"
    assert vision_pope.parse("No, there is no snowboard.") == "no"
    assert vision_pope.parse("Based on the image provided, it is not possible to confirm") == "no"
    assert vision_pope.parse("Yes. There is no backpack though.") == "yes"     # only the first sentence counts


def test_metrics_on_a_known_table():
    m = vision_pope.metrics(["yes", "yes", "no", "no"], ["yes", "no", "yes", "no"])
    assert (m["TP"], m["FN"], m["FP"], m["TN"]) == (1, 1, 1, 1)
    assert (m["accuracy"], m["precision"], m["recall"], m["f1"], m["yes ratio"]) == (0.5, 0.5, 0.5, 0.5, 0.5)


def test_ask_inlines_the_image_and_asks_greedily():
    seen = []

    def post(url, body, timeout=0):
        seen.append(body)
        return {"choices": [{"message": {"content": "Yes."}}]}
    assert vision_pope.ask("h:1", b"\xff\xd8jpeg", "Is there a cat in the image?", post=post) == "Yes."
    content = seen[0]["messages"][0]["content"]
    assert content[0]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert content[1]["text"] == "Is there a cat in the image?" and seen[0]["temperature"] == 0
