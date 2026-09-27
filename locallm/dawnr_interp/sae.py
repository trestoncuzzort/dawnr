"""sae.py -- a sparse autoencoder over a language model's residual-stream activations.

Recipe: Cunningham, Ewart, Riggs, Huben, Sharkey, "Sparse Autoencoders Find Highly
Interpretable Features in Language Models" (arXiv:2309.08600), section 2. One hidden
layer, ReLU, encoder and decoder weights tied (the decoder is the encoder's weight
transposed, so the same matrix is both the feature detector and the dictionary), the
dictionary's rows kept unit norm so the L1 term cannot be cheated by growing the
feature vectors instead of shrinking the codes, and

    code = ReLU(M x + b)                                       (their eq. 1)
    x_hat = M^T code = sum_i code_i * dictionary_row_i          (their eq. 2-3)
    loss(x) = ||x - x_hat||_2^2 + alpha * ||code||_1             (their eq. 4)

Their dictionary size is d_hidden = R * d_in for a width multiplier R ("expansion"
below); their alpha is `l1_coefficient`. What is NOT from the paper: their dead-
feature resampling procedure was in a section of the paper this project did not fetch
(see the research-first receipt for this module), so it is not implemented here --
dead_features() below only counts, it never resurrects. Treat that as an open
follow-up, not a design decision.
"""
from __future__ import annotations

from dataclasses import dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F


@dataclass
class SAEConfig:
    d_in: int             # width of the activation vector this SAE reconstructs (the model's n_embd)
    expansion: int = 8    # dictionary size = expansion * d_in (the paper's R)
    l1_coefficient: float = 1e-3   # alpha in the paper's eq. 4; retune per model, their value does not transfer

    def __post_init__(self):
        if self.d_in < 1:
            raise ValueError("d_in must be positive")
        if self.expansion < 1:
            raise ValueError("expansion must be positive")
        if self.l1_coefficient < 0:
            raise ValueError("l1_coefficient must be nonnegative")

    @property
    def d_hidden(self) -> int:
        return self.expansion * self.d_in


class SparseAutoencoder(nn.Module):
    """One dictionary over one activation site. See module docstring for the recipe.

    `encoder.weight` (shape d_hidden x d_in) is M: row i is dictionary feature i.
    There is no separate decoder module -- decode() reuses `encoder.weight` transposed,
    which is what "tied weights" means (halves the parameter count, and removes any
    question of whether a direction is "the encoder's" or "the decoder's": there is
    only one).
    """

    def __init__(self, config: SAEConfig):
        super().__init__()
        self.config = config
        self.encoder = nn.Linear(config.d_in, config.d_hidden, bias=True)
        with torch.no_grad():
            self.normalize_decoder_()

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        return F.relu(self.encoder(x))

    def decode(self, code: torch.Tensor) -> torch.Tensor:
        # code @ M, i.e. x_hat = M^T code for each row -- no decoder bias in the
        # cited recipe (their eq. 2 adds none).
        return F.linear(code, self.encoder.weight.t())

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        code = self.encode(x)
        return self.decode(code), code

    @torch.no_grad()
    def normalize_decoder_(self) -> None:
        """Rescale every dictionary row to unit L2 norm (their footnote 3)."""
        norms = self.encoder.weight.norm(dim=1, keepdim=True).clamp_min(1e-8)
        self.encoder.weight.div_(norms)

    def loss(self, x: torch.Tensor, *, return_components: bool = False):
        """Their eq. 4, per-example squared reconstruction error plus alpha * L1(code),
        both averaged over the batch."""
        if x.ndim != 2 or x.shape[1] != self.config.d_in:
            raise ValueError(f"expected activations shaped (n, {self.config.d_in}); got {tuple(x.shape)}")
        recon, code = self(x)
        reconstruction = (x - recon).pow(2).sum(dim=-1).mean()
        sparsity = code.abs().sum(dim=-1).mean()
        total = reconstruction + self.config.l1_coefficient * sparsity
        if not return_components:
            return total
        components = {
            "reconstruction": reconstruction.detach(),
            "sparsity_l1": sparsity.detach(),
            "l0": (code > 0).float().sum(dim=-1).mean().detach(),
        }
        return total, components


def dead_features(code: torch.Tensor) -> torch.Tensor:
    """Boolean mask, one entry per dictionary feature: True where it never fired
    (activation > 0) on any row of `code`. Counting only -- see the module docstring
    for why resampling is not done here."""
    if code.ndim != 2:
        raise ValueError("code must be (n, d_hidden)")
    return ~(code > 0).any(dim=0)


def train_sae(sae: SparseAutoencoder, activations: torch.Tensor, *, steps: int = 200,
              batch_size: int = 256, lr: float = 1e-3, seed: int = 0,
              normalize_every: int = 1, log_every: int | None = None,
              device: str | torch.device | None = None) -> list[dict]:
    """Adam over random batches of `activations` (n, d_in), one call, one dictionary.

    Returns one metrics dict per step (loss, reconstruction, sparsity_l1, mean L0, and
    the dead-feature fraction accumulated so far -- a feature counts as dead here only
    once it has never fired in any batch seen up to that step). The dictionary is
    row-renormalised every `normalize_every` steps, matching normalize_decoder_'s
    docstring: an optimizer step can grow the rows away from unit norm, so it undoes
    that before the next step reads them, exactly as the paper's footnote 3 requires
    (never skip the very first renormalisation, since Adam's first step is not small).
    """
    if activations.ndim != 2 or activations.shape[1] != sae.config.d_in:
        raise ValueError(f"activations must be (n, {sae.config.d_in}); got {tuple(activations.shape)}")
    n = activations.size(0)
    if n == 0:
        raise ValueError("no activations to train on")
    if steps < 1 or batch_size < 1:
        raise ValueError("steps and batch_size must be positive")
    device = torch.device(device) if device is not None else activations.device
    sae.to(device)
    activations = activations.to(device)
    generator = torch.Generator(device="cpu").manual_seed(seed)
    optimizer = torch.optim.Adam(sae.parameters(), lr=lr)
    ever_fired = torch.zeros(sae.config.d_hidden, dtype=torch.bool, device=device)

    history = []
    draw = min(batch_size, n)
    for step in range(steps):
        batch = activations[torch.randint(0, n, (draw,), generator=generator)]
        optimizer.zero_grad(set_to_none=True)
        loss, parts = sae.loss(batch, return_components=True)
        loss.backward()
        optimizer.step()
        if (step + 1) % normalize_every == 0:
            sae.normalize_decoder_()
        with torch.no_grad():
            ever_fired |= (sae.encode(batch) > 0).any(dim=0)
        record = {
            "step": step,
            "loss": float(loss.detach()),
            "reconstruction": float(parts["reconstruction"]),
            "sparsity_l1": float(parts["sparsity_l1"]),
            "l0": float(parts["l0"]),
            "dead_fraction": float((~ever_fired).float().mean()),
        }
        history.append(record)
        if log_every and (step % log_every == 0 or step == steps - 1):
            print(f"step {step:5d}  loss {record['loss']:.4f}  recon {record['reconstruction']:.4f}  "
                  f"l1 {record['sparsity_l1']:.4f}  l0 {record['l0']:.2f}  dead {record['dead_fraction']:.2%}")
    return history
