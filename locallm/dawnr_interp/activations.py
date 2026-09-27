"""activations.py -- cache one layer's residual-stream activations from training text.

Held-out boundary: `training_split_documents` reuses `data.group_split`, the exact
split every locallm trainer already draws its own validation set from, and returns
only the training half. Caching activations through this function rather than a raw
read of a corpus file is what keeps a sparse autoencoder built here from ever seeing
validation or held-out text -- the same rule as training itself, applied to a second
consumer of the corpus (see t/loop_filter.py and t/r12-dev-ids.json for the boundary
this must never cross when a corpus carries pool problems, not just t's own tasks).

The hook point is the output of one `model.transformer.h[layer]` block: exactly the
residual stream after that block, since `model.Block.forward` returns it as a plain
tensor when called without a KV cache (the only way this module calls it).
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import torch

# data.py lives flat in locallm/, one level above this subpackage; every
# cross-boundary import in this codebase reaches it the same way
# (locallm/dawnr_harness/checker.py does the identical insert before `import t_tool`).
LOCALLM = Path(__file__).resolve().parent.parent
if str(LOCALLM) not in sys.path:
    sys.path.insert(0, str(LOCALLM))

import data  # noqa: E402


@dataclass
class CachedActivations:
    """One row per (document, position) the hook fired at, in the order captured."""
    activations: torch.Tensor    # (n, d_in) float32, on cpu
    doc_index: list[int]
    position: list[int]          # token offset within its document's own encoding
    token_id: list[int]
    layer: int
    contexts: list[str] = field(default_factory=list)   # decoded text around each row, for the browser

    def __post_init__(self):
        n = self.activations.size(0)
        for name, values in (("doc_index", self.doc_index), ("position", self.position),
                             ("token_id", self.token_id), ("contexts", self.contexts)):
            if len(values) != n:
                raise ValueError(f"{name} has {len(values)} entries but activations has {n} rows")

    def __len__(self) -> int:
        return self.activations.size(0)


def training_split_documents(corpus_text: str, *, val_frac: float = 0.1, seed: int = 1337,
                             by: str = "order") -> list[str]:
    """The documents inside `corpus_text` that data.group_split assigns to training --
    never validation. Same defaults (val_frac, seed, by) a caller would give
    data.Corpus, so this describes the same split a real training run drew."""
    train_text, _val_text = data.group_split(corpus_text, val_frac=val_frac, seed=seed, by=by)
    return data.documents(train_text)


def _context(tok, chunk: list[int], offset: int, half_width: int) -> str:
    lo, hi = max(0, offset - half_width), min(len(chunk), offset + half_width)
    before = tok.decode(chunk[lo:offset])
    at = tok.decode([chunk[offset]])
    after = tok.decode(chunk[offset + 1:hi])
    return f"{before}<<{at}>>{after}"


@torch.no_grad()
def cache_residual_stream(model, tok, documents: list[str], layer: int, *,
                          context_chars: int = 60, device: str | torch.device = "cpu",
                          max_documents: int | None = None) -> CachedActivations:
    """Run every document through `model` and record the layer-`layer` residual
    stream at every token position, one document at a time (never batched: model.py's
    GPT.forward takes no attention mask, so a shorter row in a batch would attend
    into padding it should not see). A document longer than the model's block_size is
    walked in consecutive, non-overlapping chunks of at most block_size tokens, so
    every position is still read by one real forward pass, never truncated away.

    `max_documents` caps how many documents are read, first-N, for a bounded-time
    smoke run; the default reads all of them.
    """
    if not 0 <= layer < model.config.n_layer:
        raise ValueError(f"layer must be in [0, {model.config.n_layer}); got {layer}")
    if context_chars < 0:
        raise ValueError("context_chars must be nonnegative")
    block = model.config.block_size
    half_width = context_chars // 2

    captured: list[torch.Tensor] = []

    def hook(_module, _inputs, output):
        captured.append((output[0] if isinstance(output, tuple) else output).detach())

    handle = model.transformer.h[layer].register_forward_hook(hook)
    was_training = model.training
    model.eval()
    acts: list[torch.Tensor] = []
    doc_index: list[int] = []
    position: list[int] = []
    token_id: list[int] = []
    contexts: list[str] = []
    try:
        for doc_i, doc in enumerate(documents[:max_documents]):
            ids = tok.encode(doc)
            if not ids:
                continue
            for start in range(0, len(ids), block):
                chunk = ids[start:start + block]
                idx = torch.tensor([chunk], dtype=torch.long, device=device)
                captured.clear()
                model(idx)
                if not captured:
                    raise RuntimeError("the residual-stream hook did not fire; is `layer` inside this model?")
                resid = captured[-1][0]     # drop the batch dim: (1, T, d_in) -> (T, d_in)
                if resid.shape != (len(chunk), model.config.n_embd):
                    raise RuntimeError(
                        f"hook captured shape {tuple(resid.shape)}, expected ({len(chunk)}, {model.config.n_embd})")
                acts.append(resid.to(torch.float32).cpu())
                for offset, tid in enumerate(chunk):
                    doc_index.append(doc_i)
                    position.append(start + offset)
                    token_id.append(int(tid))
                    contexts.append(_context(tok, chunk, offset, half_width))
    finally:
        handle.remove()
        model.train(was_training)

    activations = torch.cat(acts, dim=0) if acts else torch.empty((0, model.config.n_embd))
    return CachedActivations(activations, doc_index, position, token_id, layer, contexts)
