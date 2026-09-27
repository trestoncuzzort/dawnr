"""ctc_model.py — a small, from-scratch CTC acoustic model. Pure PyTorch.

Architecture: a strided Conv1d front end over log-mel frames (cuts the frame
rate so the sequence CTC aligns is shorter, standard in every CTC acoustic
model since Deep Speech 2, arXiv:1512.02595 section 3.1) feeding a
bidirectional GRU stack, then a linear layer to per-frame class scores. The
loss is ``torch.nn.functional.ctc_loss``: CTC's forward-backward recursion
(Graves et al. 2006; worked example read at distill.pub/2017/ctc, fetched
2026-09-27) is a textbook dynamic program that PyTorch already implements and
tests, the same reason ``model.py`` calls ``F.scaled_dot_product_attention``
instead of re-deriving attention -- reimplementing a correct, already-shipped
primitive of a hard dependency this project already has would cost
correctness risk for no capability gained.

Sized for the CPU smoke test in ``test_speech_ctc.py`` (overfit a handful of
one-second synthetic utterances in well under a minute on a laptop CPU) and
for LibriSpeech train-clean-100 on one RTX 4080 at a larger preset; both use
this same class. Kept deliberately smaller than Deep Speech 2 itself (which
targets thousands of GPU-hours): a few million parameters at the default
preset, not tens of millions.
"""
from __future__ import annotations

from dataclasses import dataclass

import torch
import torch.nn as nn
from torch.nn import functional as F
from torch.nn.utils.rnn import pack_padded_sequence, pad_packed_sequence


@dataclass
class AcousticConfig:
    n_mels: int = 40
    vocab_size: int = 30       # text.CTCVocab().vocab_size by default (blank + 29 symbols)
    conv_channels: int = 128
    conv_kernel: int = 5
    conv_stride: int = 2       # frame-rate reduction through the conv front end
    rnn_hidden: int = 128
    rnn_layers: int = 2
    dropout: float = 0.1

    def __post_init__(self):
        if min(self.n_mels, self.conv_channels, self.rnn_hidden, self.rnn_layers) < 1:
            raise ValueError("n_mels, conv_channels, rnn_hidden and rnn_layers must be positive")
        if self.vocab_size < 2:
            raise ValueError("vocab_size must be at least 2 (blank plus one symbol)")
        if self.conv_kernel < 1 or self.conv_kernel % 2 == 0:
            raise ValueError("conv_kernel must be a positive odd number for symmetric padding")
        if self.conv_stride < 1:
            raise ValueError("conv_stride must be positive")
        if not 0 <= self.dropout < 1:
            raise ValueError("dropout must be in [0, 1)")

    @property
    def conv_padding(self) -> int:
        return self.conv_kernel // 2

    def output_length(self, feature_length: int) -> int:
        """Frame count after the conv front end, for one sequence's true
        (unpadded) feature length. Used to build the per-sample lengths CTC
        needs so a padded batch's filler frames are never scored."""
        if feature_length < 1:
            raise ValueError("feature_length must be positive")
        return (feature_length + 2 * self.conv_padding - self.conv_kernel) // self.conv_stride + 1


class AcousticModel(nn.Module):
    def __init__(self, config: AcousticConfig):
        super().__init__()
        self.config = config
        self.conv = nn.Conv1d(config.n_mels, config.conv_channels, config.conv_kernel,
                              stride=config.conv_stride, padding=config.conv_padding)
        self.conv_dropout = nn.Dropout(config.dropout)
        self.rnn = nn.GRU(config.conv_channels, config.rnn_hidden, config.rnn_layers,
                          batch_first=True, bidirectional=True,
                          dropout=config.dropout if config.rnn_layers > 1 else 0.0)
        self.rnn_dropout = nn.Dropout(config.dropout)
        self.head = nn.Linear(2 * config.rnn_hidden, config.vocab_size)

    def total_params(self) -> int:
        return sum(p.numel() for p in self.parameters())

    def forward(self, features: torch.Tensor, feature_lengths: torch.Tensor, *,
                targets: torch.Tensor | None = None, target_lengths: torch.Tensor | None = None):
        """``features``: ``(B, T, n_mels)``, right-zero-padded to the batch's
        longest utterance. ``feature_lengths``: ``(B,)`` true lengths before
        padding. Returns ``(log_probs, output_lengths, loss)``: ``log_probs``
        is ``(B, T', vocab_size)`` log-softmax'd (``T'`` the padded batch's
        longest post-conv length); ``output_lengths`` is each row's true
        length within it; ``loss`` is ``None`` unless both target arguments
        are given, in which case it is the mean per-utterance CTC loss over
        the batch (the same return-loss-from-forward shape as ``GPT``'s in
        ``model.py``, for the same reason: one call computes both, so a
        training loop and an eval loop cannot compute logits one way and the
        loss another and quietly drift apart).
        """
        if features.ndim != 3 or features.size(0) == 0:
            raise ValueError("features must be a nonempty (batch, time, n_mels) tensor")
        if feature_lengths.shape != (features.size(0),):
            raise ValueError("feature_lengths must hold one length per batch row")
        if feature_lengths.min().item() < 1 or feature_lengths.max().item() > features.size(1):
            raise ValueError("feature_lengths must be positive and within the padded time dimension")

        x = self.conv_dropout(F.relu(self.conv(features.transpose(1, 2))))  # (B, C, T')
        x = x.transpose(1, 2)                                              # (B, T', C)
        output_lengths = torch.tensor(
            [self.config.output_length(int(n)) for n in feature_lengths.tolist()],
            dtype=torch.long)
        packed = pack_padded_sequence(x, output_lengths.clamp(max=x.size(1)).cpu(),
                                      batch_first=True, enforce_sorted=False)
        packed_out, _ = self.rnn(packed)
        rnn_out, _ = pad_packed_sequence(packed_out, batch_first=True, total_length=x.size(1))
        logits = self.head(self.rnn_dropout(rnn_out))                      # (B, T', vocab)
        log_probs = F.log_softmax(logits, dim=-1)

        loss = None
        if targets is not None and target_lengths is not None:
            # (T, B, C) is what F.ctc_loss expects; zero_infinity guards the one
            # batch a too-short output length (relative to a target's repeats)
            # would otherwise turn into an infinite loss and a NaN gradient for
            # the whole batch (torch docs, torch.nn.CTCLoss, "zero_infinity").
            loss = F.ctc_loss(log_probs.transpose(0, 1), targets,
                              output_lengths.to(features.device), target_lengths,
                              blank=0, reduction="mean", zero_infinity=True)
        return log_probs, output_lengths, loss
