"""Experimental training-only future-state prediction, not a HiLP reproduction.

This bounded prototype predicts detached future backbone states from a causal
current state. It omits HiLP's hierarchical aggregation, KL and combined head.
Keep next-token loss active: this auxiliary loss alone admits collapsed states.
"""
import torch
from torch import nn
from torch.nn import functional as F


class FutureStateObjective(nn.Module):
    def __init__(self, width, horizons=(1, 4)):
        super().__init__()
        if width < 1 or not horizons or any(type(h) is not int or h < 1 for h in horizons):
            raise ValueError("positive width and integer horizons required")
        if len(set(horizons)) != len(horizons):
            raise ValueError("duplicate horizons")
        self.width = width
        self.horizons = tuple(horizons)
        self.heads = nn.ModuleDict({str(h): nn.Sequential(
            nn.Linear(width, width), nn.GELU(), nn.Linear(width, width)) for h in horizons})

    def forward(self, hidden, segments):
        """Return per-horizon losses and eligible counts.

        hidden: [batch,time,width] causal backbone states.
        segments: [batch,time] integer example IDs; -1 means padding.
        All positions in a prediction interval must belong to one example.
        Attention isolation across packed examples is the caller's responsibility.
        """
        if hidden.ndim != 3 or hidden.shape[-1] != self.width:
            raise ValueError("invalid hidden shape")
        if segments.shape != hidden.shape[:2] or segments.device != hidden.device:
            raise ValueError("segments must match hidden batch, time and device")
        if segments.dtype not in (torch.int32, torch.int64):
            raise ValueError("integer segment IDs required")
        losses, counts = {}, {}
        for h in self.horizons:
            head = self.heads[str(h)]
            if hidden.shape[1] <= h:
                # Preserve zero gradients for all head parameters under DDP.
                losses[h] = head(hidden[:, :0]).sum() * 0
                counts[h] = 0
                continue
            windows = segments.unfold(1, h + 1, 1)
            valid = (windows[..., 0] >= 0) & (windows == windows[..., :1]).all(-1)
            prediction = head(hidden[:, :-h])
            target = hidden[:, h:].detach()
            # Select before reduction: invalid pairs contribute no gradient.
            error = F.smooth_l1_loss(prediction[valid].float(), target[valid].float(),
                                     reduction="sum")
            count = int(valid.sum().item())
            losses[h] = error / max(count * self.width, 1)
            counts[h] = count
        return losses, counts
