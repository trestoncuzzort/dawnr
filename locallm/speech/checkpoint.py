"""checkpoint.py — save and load a trained AcousticModel. One implementation.

The same shape and the same safety rule as ``locallm/checkpoint.py`` (the GPT
checkpoint loader, read for this): a plain dict of tensors plus config
primitives, loaded with ``weights_only=True`` so a checkpoint file can never
unpickle arbitrary code, and a consistency check at load time (here: the
saved alphabet must match ``CTCVocab``'s) rather than a silent mismatch that
only shows up as garbage decoding later.
"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import torch

from .ctc_model import AcousticConfig, AcousticModel
from .text import CTCVocab


def save_checkpoint(path: str | Path, model: AcousticModel, vocab: CTCVocab | None = None) -> None:
    vocab = vocab or CTCVocab()
    torch.save({"config": asdict(model.config), "model": model.state_dict(),
               "vocab_symbols": list(vocab.symbols)}, path)


def load_checkpoint(path: str | Path, device: str | None = None):
    """Return ``(model, vocab, config)`` in eval mode on ``device`` (default
    CPU). Raises ``ValueError`` naming the file when its saved alphabet does
    not match this codebase's ``CTCVocab`` -- a model trained under a
    different alphabet would otherwise decode to wrong or empty text with no
    signal beyond "the numbers look off"."""
    ck = torch.load(path, map_location="cpu", weights_only=True)
    vocab = CTCVocab()
    if ck["vocab_symbols"] != list(vocab.symbols):
        raise ValueError(f"{path}: saved alphabet does not match this codebase's CTCVocab")
    config = AcousticConfig(**ck["config"])
    model = AcousticModel(config).to(device or "cpu")
    model.load_state_dict(ck["model"])
    model.eval()
    return model, vocab, config
