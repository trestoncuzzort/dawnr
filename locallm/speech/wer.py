"""wer.py: word error rate the way Whisper's paper computes it (2026-10-01).

    python3 locallm/speech/wer.py REFERENCE.txt HYPOTHESIS.txt [--ids IDS.txt]

Both files hold one utterance a line, "<id> <text>" (LibriSpeech's own *.trans.txt format). Each side is
passed through Whisper's EnglishTextNormalizer (openai/whisper whisper/normalizers, MIT, vendored in
third_party/whisper_normalizer with its licence; Radford et al., arXiv:2212.04356, appendix D reports
LibriSpeech word error rates after this normaliser), then the corpus word error rate is the total
word-level edit distance over the total number of reference words. An utterance with no hypothesis
counts as all deletions.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "third_party"))


def edits(ref: list[str], hyp: list[str]) -> int:
    """Levenshtein distance over words (substitutions, insertions, deletions, each cost 1)."""
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h))
        prev = cur
    return prev[-1]


def read(path: Path) -> dict[str, str]:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            uid, _, text = line.strip().partition(" ")
            out[uid] = text
    return out


def corpus_wer(refs: dict[str, str], hyps: dict[str, str], ids: list[str] | None = None, normalise=None) -> dict:
    if normalise is None:
        from whisper_normalizer import EnglishTextNormalizer
        normalise = EnglishTextNormalizer()
    ids = ids if ids is not None else sorted(refs)
    total = errors = missing = 0
    for uid in ids:
        r = normalise(refs[uid]).split()
        h = normalise(hyps.get(uid, "")).split()
        missing += uid not in hyps or not hyps[uid].strip()
        total += len(r)
        errors += edits(r, h)
    return {"utterances": len(ids), "reference words": total, "errors": errors,
            "wer": round(100 * errors / total, 2) if total else None, "utterances with no hypothesis": missing}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("reference", type=Path)
    ap.add_argument("hypothesis", type=Path)
    ap.add_argument("--ids", type=Path, help="score only these utterance ids (one a line or space separated)")
    a = ap.parse_args(argv)
    ids = a.ids.read_text(encoding="utf-8").split() if a.ids else None
    print(json.dumps(corpus_wer(read(a.reference), read(a.hypothesis), ids)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
