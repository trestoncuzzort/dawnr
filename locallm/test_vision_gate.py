"""vision_gate.py: a 'yes' is shown only when the detector agrees (Woodpecker's validation, arXiv:2310.16045)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import vision_gate  # noqa: E402


def test_the_object_is_read_from_popes_question():
    assert vision_gate.object_of("Is there a dining table in the image?") == "dining table"
    assert vision_gate.object_of("Is there an apple in the image?") == "apple"


def test_the_gate_shows_yes_only_when_both_agree():
    rows = [{"label": "yes", "parsed": "yes", "evidence": 0.5},   # shown, right
            {"label": "no", "parsed": "yes", "evidence": 0.05},   # model hallucinates, detector refuses: withheld
            {"label": "yes", "parsed": "yes", "evidence": 0.05},  # right but unconfirmed: withheld
            {"label": "no", "parsed": "no", "evidence": 0.9}]     # model says no: no claim to show
    m = vision_gate.gate_metrics(rows, 0.1)
    assert (m["the gate"]["TP"], m["the gate"]["FP"]) == (1, 0)
    assert (m["the model"]["TP"], m["the model"]["FP"]) == (2, 1)
    assert m["the gate keeps of the model's true yes"] == 0.5
