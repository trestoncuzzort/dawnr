"""metrics.py — word and character error rate, the standard ASR scoreboard.

WER and CER are both an edit distance (substitutions + deletions +
insertions, Levenshtein) over the reference length: this project's own
stdlib implementation, checked against jiwer's published edge cases (Apache
License 2.0; raw.githubusercontent.com/jitsi/jiwer/master/README.md, fetched
2026-09-27) rather than adding jiwer (and its RapidFuzz dependency) for a
computation this small. jiwer's edge case for an EMPTY reference is not the
naive ratio (which divides by zero): it is the raw edit distance with the
denominator floored at 1, so ``wer('', 'silence') == 1`` and
``wer('', 'peaceful silence') == 2`` (an error "rate" that can exceed 1 when
the reference is empty and the model hallucinates words, by construction --
there is no other well-defined number here). That is the rule implemented
below, matching jiwer's four published examples exactly (see
``test_speech_metrics.py``).
"""
from __future__ import annotations


def levenshtein(a: list | str, b: list | str) -> int:
    """Edit distance (substitution, deletion, insertion each cost 1) between
    two sequences, single-row dynamic programming: O(len(a) * len(b)) time,
    O(min(len(a), len(b))) memory. Textbook (Wagner & Fischer, 1974); no
    external library is worth adding for a same-utterance-length comparison.
    """
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, x in enumerate(a, start=1):
        current = [i] + [0] * len(b)
        for j, y in enumerate(b, start=1):
            current[j] = min(previous[j] + 1, current[j - 1] + 1,
                             previous[j - 1] + (x != y))
        previous = current
    return previous[-1]


def _rate(reference: list, hypothesis: list) -> float:
    return levenshtein(reference, hypothesis) / max(len(reference), 1)


def wer(reference: str, hypothesis: str) -> float:
    """Word error rate: whitespace-split word sequences through ``_rate``."""
    return _rate(reference.split(), hypothesis.split())


def cer(reference: str, hypothesis: str) -> float:
    """Character error rate: character sequences (spaces included, since a
    dropped or inserted space is a real error a CTC model can make) through
    ``_rate``."""
    return _rate(list(reference), list(hypothesis))
