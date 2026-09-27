"""ctc_decode.py — greedy CTC decoding: argmax, then collapse.

The collapse rule (merge adjacent repeats, then drop every blank) is CTC's
alignment-to-text map, worked through in Hannun, "Sequence Modeling With
CTC" (distill.pub/2017/ctc, fetched 2026-09-27, section "How CTC collapsing
works"): it is what makes an alignment as long as the input decode to a
shorter piece of text, and why a real doubled letter needs a blank between
the two repeats in a *correct* alignment. Greedy (best class per frame, no
search over alignments) is the cheapest decoder that rule admits and the one
a CPU smoke test needs; beam search over the same collapse rule, weighted by
a language model, is future work noted in DAWNR-SPEECH.md and not needed to
measure whether this model has learned anything at all.
"""
from __future__ import annotations

import torch

from .text import CTCVocab


def greedy_ids(log_probs: torch.Tensor, lengths: torch.Tensor) -> list[list[int]]:
    """``log_probs``: ``(B, T, vocab)``. ``lengths``: ``(B,)`` true lengths
    (see ``AcousticModel.forward``'s ``output_lengths``). Returns, per row,
    the collapsed symbol ids (blank id 0 never included) -- CTC ids, not yet
    text; ``decode_text`` below applies a vocabulary on top.
    """
    if log_probs.ndim != 3:
        raise ValueError("log_probs must be (batch, time, vocab)")
    if lengths.shape != (log_probs.size(0),):
        raise ValueError("lengths must hold one length per batch row")
    best = log_probs.argmax(dim=-1)                     # (B, T)
    out = []
    for row, length in zip(best.tolist(), lengths.tolist()):
        row = row[:length]
        collapsed = [sym for i, sym in enumerate(row) if sym != 0 and (i == 0 or sym != row[i - 1])]
        out.append(collapsed)
    return out


def decode_text(log_probs: torch.Tensor, lengths: torch.Tensor, vocab: CTCVocab) -> list[str]:
    """Greedy-decoded text per batch row, through ``vocab.decode``."""
    return [vocab.decode(ids) for ids in greedy_ids(log_probs, lengths)]
