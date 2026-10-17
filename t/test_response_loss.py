#!/usr/bin/env python3
"""t/student_sft.py response_loss: the checkpointed-chunk cross-entropy must equal the single
unchunked call -- same loss and same gradients -- or the memory fix changed the training signal.

The chunked path (Cut Cross-Entropy principle, arXiv:2411.09009: do not materialise the full
response-position logit matrix) is only a memory change; the number it returns and the gradient it
produces must match the original `lm_head(hidden[response]).float()` + cross_entropy to float noise.
A small vocabulary keeps the test cheap; the length spans several RESPONSE_LOSS_CHUNK blocks so the
chunking and its checkpointed backward are actually exercised. Run with the training venv's python
(needs torch): /home/t/scratch/venv-train/bin/python t/test_response_loss.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import torch  # noqa: E402
import torch.nn as nn  # noqa: E402
import torch.nn.functional as F  # noqa: E402

import student_sft  # noqa: E402


class _Out:
    def __init__(self, h):
        self.last_hidden_state = h


class _Model(nn.Module):
    def __init__(self, h):
        super().__init__()
        self._h = h

    def forward(self, input_ids=None, attention_mask=None):  # noqa: ARG002
        return _Out(self._h)


class _Base(nn.Module):
    """The two attribute names response_loss branches on: `.model` (backbone) and `.lm_head`."""
    def __init__(self, hidden, vocab):
        super().__init__()
        self.model = _Model(hidden)
        self.lm_head = nn.Linear(hidden.shape[-1], vocab, bias=False)


def _fixture(T=1300, H=32, V=64, n_prompt=7, seed=0):
    torch.manual_seed(seed)
    hidden = torch.randn(1, T, H, dtype=torch.float32, requires_grad=True)
    labels = torch.randint(0, V, (1, T))
    labels[0, :n_prompt] = -100                                  # prompt positions carry no loss
    base = _Base(hidden, V)
    batch = {"input_ids": torch.zeros(1, T, dtype=torch.long),
             "attention_mask": torch.ones(1, T, dtype=torch.long),
             "labels": labels}
    return base, batch, hidden


def _reference(base, batch, num_items_in_batch):
    """The computation response_loss had before chunking (the thing it must still equal)."""
    labels = batch["labels"]
    hidden = base.model(input_ids=batch["input_ids"], attention_mask=batch["attention_mask"]).last_hidden_state
    predicts = labels[:, 1:] != -100
    logits = base.lm_head(hidden[:, :-1][predicts]).float()
    targets = labels[:, 1:][predicts]
    if num_items_in_batch is None:
        return F.cross_entropy(logits, targets)
    return F.cross_entropy(logits, targets, reduction="sum") / num_items_in_batch


def _loss_and_grads(fn):
    base, batch, hidden = _fixture()
    for p in base.parameters():
        if p.grad is not None:
            p.grad = None
    loss = fn(base, batch)
    loss.backward()
    return float(loss.detach()), base.lm_head.weight.grad.detach().clone(), hidden.grad.detach().clone()


def test_chunked_equals_unchunked_mean():
    assert student_sft.RESPONSE_LOSS_CHUNK < 1300, "fixture must span several chunks"
    ref, ref_w, ref_h = _loss_and_grads(lambda b, x: _reference(b, x, None))
    got, got_w, got_h = _loss_and_grads(lambda b, x: student_sft.response_loss(b, x, None))
    assert abs(ref - got) < 1e-4, (ref, got)
    assert torch.allclose(ref_w, got_w, atol=1e-4, rtol=1e-3), (ref_w - got_w).abs().max().item()
    assert torch.allclose(ref_h, got_h, atol=1e-4, rtol=1e-3), (ref_h - got_h).abs().max().item()


def test_chunked_equals_unchunked_accumulation():
    K = 512.0                                                   # the window's target-token count
    ref, ref_w, _ = _loss_and_grads(lambda b, x: _reference(b, x, K))
    got, got_w, _ = _loss_and_grads(lambda b, x: student_sft.response_loss(b, x, K))
    assert abs(ref - got) < 1e-4, (ref, got)
    assert torch.allclose(ref_w, got_w, atol=1e-4, rtol=1e-3), (ref_w - got_w).abs().max().item()


if __name__ == "__main__":
    test_chunked_equals_unchunked_mean()
    test_chunked_equals_unchunked_accumulation()
    print("OK: chunked response_loss equals the unchunked reference (loss + grads), mean and accumulation")
