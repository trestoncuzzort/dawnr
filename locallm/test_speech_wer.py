"""speech/wer.py: corpus word error rate after Whisper's normaliser (arXiv:2212.04356, appendix D)."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "speech"))

import wer  # noqa: E402


def test_edit_distance_counts_substitutions_insertions_and_deletions():
    assert wer.edits("a b c".split(), "a b c".split()) == 0
    assert wer.edits("a b c".split(), "a x c".split()) == 1
    assert wer.edits("a b c".split(), "a b".split()) == 1
    assert wer.edits("a b".split(), "a b c d".split()) == 2


def test_the_normaliser_makes_case_punctuation_and_spelt_numbers_agree():
    refs = {"u1": "HE SAID TWENTY FIVE DOLLARS", "u2": "COLOUR IT RED"}
    hyps = {"u1": "He said $25.", "u2": "Color it red!"}
    out = wer.corpus_wer(refs, hyps)
    assert out["errors"] == 0 and out["wer"] == 0.0


def test_a_missing_hypothesis_is_all_deletions():
    out = wer.corpus_wer({"u1": "ONE TWO THREE", "u2": "GO"}, {"u2": "go"}, normalise=lambda s: s.lower())
    assert (out["errors"], out["reference words"], out["utterances with no hypothesis"]) == (3, 4, 1)
