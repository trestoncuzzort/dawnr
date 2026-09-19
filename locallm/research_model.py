"""Opt-in research training wrapper; leaves the core checkpoint schema intact."""
import torch
from torch import nn
from torch.nn import functional as F

from next_latent import NextLatent


class ResearchModel(nn.Module):
    def __init__(self, core, *, latent=False, horizon=1,
                 regression_weight=1.0, kl_weight=0.1, execution_weight=1.0):
        super().__init__()
        if regression_weight < 0 or kl_weight < 0 or execution_weight < 0:
            raise ValueError("loss weights must be nonnegative")
        self.core = core
        self.auxiliary = NextLatent(core.config.n_embd, horizon) if latent else None
        self.regression_weight = regression_weight
        self.kl_weight = kl_weight
        self.execution_weight = execution_weight

    def forward(self, inputs, targets, segments, execution_targets=None):
        if targets.shape != inputs.shape or segments.shape != inputs.shape:
            raise ValueError("batch shapes differ")
        if not torch.any(targets != -1):
            raise ValueError("batch has no supervised targets")
        if torch.any((segments < 0) & (targets != -1)):
            raise ValueError("padding must have ignored targets")
        if execution_targets is not None:
            if execution_targets.shape != targets.shape:
                raise ValueError("execution target shape differs")
            if torch.any((execution_targets != -1) & ((targets != -1) | (segments < 0))):
                raise ValueError("execution supervision overlaps answer or padding")

        def add_execution(logits, losses):
            if execution_targets is not None:
                selected = execution_targets != -1
                execution = (F.cross_entropy(logits[selected], execution_targets[selected])
                             if selected.any() else logits[:, :0].sum())
                losses["execution"] = execution
                losses["total"] = losses["total"] + self.execution_weight * execution
            return logits, losses

        if self.auxiliary is None:
            logits, loss = self.core(inputs, targets)
            return add_execution(logits, {"total": loss, "completion": loss})
        hidden, embeddings = [], []
        handles = [self.core.transformer.ln_f.register_forward_hook(
            lambda module, args, output: hidden.append(output)),
            self.core.transformer.wte.register_forward_hook(
                lambda module, args, output: embeddings.append(output))]
        try:
            logits, completion = self.core(inputs, targets)
        finally:
            for handle in handles:
                handle.remove()
        if len(hidden) != 1 or len(embeddings) != 1:
            raise RuntimeError("unexpected backbone capture count")
        auxiliary = self.auxiliary(hidden[0], embeddings[0], segments,
                                   self.core.lm_head.weight, self.core.lm_head.bias)
        total = (completion + self.regression_weight * auxiliary["regression"]
                 + self.kl_weight * auxiliary["kl"])
        return add_execution(logits, {"total": total, "completion": completion, **auxiliary})

    def inference_state_dict(self):
        """Export only the trained core; resume training with wrapper.state_dict()."""
        return self.core.state_dict()
