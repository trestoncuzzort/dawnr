"""dense.py: optional dense-embedding retrieval from dawnr's own model. Off by default, and never
imported by index.py unless the operator's config turns it on (retrieval.dense in the harness
configuration) -- AMBITION.md: "optional dense embeddings from dawnr's own model (torch, off by
default)". torch and locallm.checkpoint are imported lazily, inside the functions that need them,
so importing this module, or running the BM25-only path anywhere in dawnr_retrieval, never requires
torch (DAWNR-HARNESS.md: "the harness is standard-library Python 3.10+ ... starts offline").

No one else's embedding model is used: "dawnr's own model" means the same checkpoint
locallm/checkpoint.load_checkpoint already loads for chat and generation, which is built from
random weights on this project's own data (README.md, "It is built, not borrowed"), never a
downloaded sentence-embedding model.

model.GPT.forward (locallm/model.py) returns only logits, never hidden states, so `_hidden_states`
below re-runs the same sequence forward() does -- embed, add positions if the architecture has a
learned table, dropout, every block, final norm -- stopping one step earlier, right before
lm_head. It calls forward()'s own public submodules (transformer.wte, .wpe, .drop, .h, .ln_f)
rather than copying their internals, so a change inside any block is picked up here unchanged;
only the *order* of these calls (mirrored from model.py's forward) would need to move if that
order ever changes there.

Fusing a dense ranking with BM25's is Reciprocal Rank Fusion, in index.py, not here: see index.py's
docstring and this track's research receipt for why (BM25 scores and cosine similarities are not on
the same scale, so they are never blended by raw value).
"""
from __future__ import annotations

import math

from . import _paths


def _hidden_states(model, idx):
    """[B, T, C] final hidden states of `model` on token ids `idx` [B, T], before lm_head."""
    import torch  # noqa: F401  -- imported for its side effect of being on sys.modules; idx is already a tensor

    transformer = model.transformer
    x = transformer.wte(idx)
    if "wpe" in transformer:
        pos = torch.arange(idx.size(1), dtype=torch.long, device=idx.device)
        x = x + transformer.wpe(pos)
    x = transformer.drop(x)
    for block in transformer.h:
        x = block(x)
    return transformer.ln_f(x)


def mean_pool(vectors) -> list[float]:
    """Unweighted mean over token positions: every position is real passage or query text here
    (unlike a chat transcript's tool spans), so nothing needs masking before pooling."""
    vectors = list(vectors)
    if not vectors:
        return []
    n, dim = len(vectors), len(vectors[0])
    return [sum(v[i] for v in vectors) / n for i in range(dim)]


def cosine(a, b) -> float:
    num = sum(x * y for x, y in zip(a, b))
    da = math.sqrt(sum(x * x for x in a))
    db = math.sqrt(sum(y * y for y in b))
    return num / (da * db) if da and db else 0.0


def encode(model, tok, text: str, device: str = "cpu", max_tokens: int = 512) -> list[float]:
    """One passage or query -> one pooled vector. cosine() only needs direction, so no length
    normalisation is applied here."""
    import torch

    ids = tok.encode(text)[:max_tokens] if text else []
    if not ids:
        return [0.0] * model.config.n_embd
    with torch.no_grad():
        hidden = _hidden_states(model, torch.tensor([ids], dtype=torch.long, device=device))
    return mean_pool(hidden[0].tolist())


class DenseIndex:
    """Cosine search over passages embedded once with `encode`. Built only when the operator's
    config asks for it and a trained checkpoint is on disk; CPU by default (the desktop's one GPU
    is shared with pretraining -- see the repository's run-anywhere rules -- and a handful of
    short passages embed in well under a second on CPU regardless)."""

    def __init__(self, model, tok, device: str = "cpu"):
        self.model, self.tok, self.device = model, tok, device
        self._ids: list = []
        self._vecs: list = []

    @classmethod
    def build(cls, passages, *, model_dir: str, device: str = "cpu") -> "DenseIndex":
        _paths.ensure_repo_paths()
        from checkpoint import load_checkpoint

        model, tok, _cfg = load_checkpoint(model_dir, device=device)
        self = cls(model, tok, device)
        for p in passages:
            self.add(p.id, (p.title + "\n" + p.text) if p.title else p.text)
        return self

    def add(self, doc_id, text: str) -> None:
        self._ids.append(doc_id)
        self._vecs.append(encode(self.model, self.tok, text, self.device))

    def search(self, query: str, k: int = 5) -> list[tuple]:
        if not self._ids:
            return []
        qv = encode(self.model, self.tok, query, self.device)
        scored = [(doc_id, cosine(qv, v)) for doc_id, v in zip(self._ids, self._vecs)]
        scored.sort(key=lambda kv: (-kv[1], str(kv[0])))
        return scored[:k]
