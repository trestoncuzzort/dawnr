"""NextLat-style auxiliary losses (arXiv:2511.05963v1, equations 3–4, 9).

Uses real in-example transitions only, excluding artificial initial states.
Keep ordinary next-token training; this module is discarded at inference.
"""
import torch
from torch import nn
from torch.nn import functional as F


class NextLatent(nn.Module):
    def __init__(self, width, horizon=1):
        super().__init__()
        if type(horizon) is not int or horizon < 1 or width < 1:
            raise ValueError("positive width and integer horizon required")
        self.width, self.horizon = width, horizon
        self.delta = nn.Sequential(nn.LayerNorm(2 * width),
                                   nn.Linear(2 * width, 2 * width), nn.GELU(),
                                   nn.Linear(2 * width, 2 * width), nn.GELU(),
                                   nn.Linear(2 * width, width))

    def transition(self, hidden, token_embedding):
        return hidden + self.delta(torch.cat((hidden, token_embedding), dim=-1))

    def forward(self, hidden, embeddings, segments, output_weight, output_bias=None):
        if hidden.ndim != 3 or hidden.shape[-1] != self.width or embeddings.shape != hidden.shape:
            raise ValueError("hidden and embedding shapes must be [batch,time,width]")
        if segments.shape != hidden.shape[:2] or segments.dtype not in (torch.int32, torch.int64):
            raise ValueError("integer segments must match batch and time")
        if segments.device != hidden.device or embeddings.device != hidden.device:
            raise ValueError("inputs must share a device")
        weight = output_weight.detach().float()
        bias = None if output_bias is None else output_bias.detach().float()
        zero = self.transition(hidden[:, :0], embeddings[:, :0]).sum() * 0
        regression, kl, counts = [], [], []
        predicted = hidden
        for h in range(1, self.horizon + 1):
            if h >= hidden.shape[1]:
                regression.append(zero)
                kl.append(zero)
                counts.append(0)
                continue
            predicted = self.transition(predicted[:, :-1], embeddings[:, h:])
            windows = segments.unfold(1, h + 1, 1)
            valid = (windows[..., 0] >= 0) & (windows == windows[..., :1]).all(-1)
            count = int(valid.sum().item())
            prior = predicted[valid].float()
            posterior = hidden[:, h:][valid].detach().float()
            regression.append(F.smooth_l1_loss(prior, posterior, reduction="sum") /
                              max(count * self.width, 1))
            prior_logp = F.log_softmax(F.linear(prior, weight, bias), dim=-1)
            target_logp = F.log_softmax(F.linear(posterior, weight, bias), dim=-1)
            kl.append(F.kl_div(prior_logp, target_logp, reduction="sum", log_target=True) /
                      max(count, 1))
            counts.append(count)
        return {"regression": sum(regression) / self.horizon,
                "kl": sum(kl) / self.horizon, "pairs": counts}
