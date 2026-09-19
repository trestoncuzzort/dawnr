"""model.py — a from-scratch GPT you own. Pure PyTorch, no pretrained base, no API.

Based on the standard decoder-only Transformer (the architecture you sent), made
training-ready: proper init, dropout, flash attention when available, and a forward
pass that returns a loss so you can train it from random weights.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import torch
import torch.nn as nn
from torch.nn import functional as F
from torch.utils.checkpoint import checkpoint


KVCache = tuple[tuple[torch.Tensor, torch.Tensor], ...]


@dataclass
class GPTConfig:
    vocab_size: int = 256   # set from your corpus's tokenizer
    block_size: int = 256   # context window
    n_layer: int = 6
    n_head: int = 8
    n_embd: int = 256
    dropout: float = 0.0
    bias: bool = True
    architecture: str = "gpt"  # old checkpoints retain their exact topology
    gradient_checkpointing: bool = False
    rope_theta: float = 10000.0
    norm_eps: float = 1e-5
    ffn_hidden_size: int | None = None

    def __post_init__(self):
        if self.architecture not in ("gpt", "modern"):
            raise ValueError("architecture must be gpt or modern")
        if min(self.vocab_size, self.block_size, self.n_layer, self.n_head, self.n_embd) < 1:
            raise ValueError("model dimensions must be positive")
        if self.n_embd % self.n_head:
            raise ValueError("n_embd must be divisible by n_head")
        if self.architecture == "modern" and (self.n_embd // self.n_head) % 2:
            raise ValueError("rotary attention requires an even head dimension")
        if not 0 <= self.dropout < 1 or self.rope_theta <= 0 or self.norm_eps <= 0:
            raise ValueError("invalid dropout, rope_theta, or norm_eps")
        if self.ffn_hidden_size is not None and self.ffn_hidden_size < 1:
            raise ValueError("ffn_hidden_size must be positive")


class RMSNorm(nn.Module):
    """RMS normalization with float32 reduction under mixed precision."""
    def __init__(self, width: int, eps: float):
        super().__init__()
        self.weight = nn.Parameter(torch.ones(width))
        self.eps = eps

    def forward(self, x):
        value = x.float()
        value = value * torch.rsqrt(value.square().mean(dim=-1, keepdim=True) + self.eps)
        return value.to(x.dtype) * self.weight.to(x.dtype)


class RotaryEmbedding(nn.Module):
    """Rotate adjacent query/key coordinates; no learned position table."""
    def __init__(self, head_dim: int, block_size: int, theta: float):
        super().__init__()
        frequency = theta ** (-torch.arange(0, head_dim, 2, dtype=torch.float32) / head_dim)
        angles = torch.outer(torch.arange(block_size, dtype=torch.float32), frequency)
        self.register_buffer("cos", angles.cos()[None, None, :, :], persistent=False)
        self.register_buffer("sin", angles.sin()[None, None, :, :], persistent=False)

    def forward(self, x, position_offset=0):
        end = position_offset + x.size(-2)
        if position_offset < 0 or end > self.cos.size(-2):
            raise ValueError("rotary positions exceed the current context window")
        cos = self.cos[:, :, position_offset:end].to(x.dtype)
        sin = self.sin[:, :, position_offset:end].to(x.dtype)
        even, odd = x[..., 0::2], x[..., 1::2]
        return torch.stack((even * cos - odd * sin, even * sin + odd * cos), dim=-1).flatten(-2)


class CausalSelfAttention(nn.Module):
    def __init__(self, config: GPTConfig):
        super().__init__()
        assert config.n_embd % config.n_head == 0
        self.c_attn = nn.Linear(config.n_embd, 3 * config.n_embd, bias=config.bias)
        self.c_proj = nn.Linear(config.n_embd, config.n_embd, bias=config.bias)
        self.attn_dropout = nn.Dropout(config.dropout)
        self.resid_dropout = nn.Dropout(config.dropout)
        self.n_head, self.n_embd, self.dropout = config.n_head, config.n_embd, config.dropout
        self.rotary = (RotaryEmbedding(config.n_embd // config.n_head, config.block_size,
                                       config.rope_theta) if config.architecture == "modern" else None)
        self.flash = hasattr(F, "scaled_dot_product_attention")
        if not self.flash:
            self.register_buffer("mask", torch.tril(torch.ones(config.block_size, config.block_size))
                                 .view(1, 1, config.block_size, config.block_size))

    def forward(self, x, *, past_key_value=None, use_cache=False, position_offset=0):
        B, T, C = x.size()
        q, k, v = self.c_attn(x).split(self.n_embd, dim=2)
        k = k.view(B, T, self.n_head, C // self.n_head).transpose(1, 2)
        q = q.view(B, T, self.n_head, C // self.n_head).transpose(1, 2)
        v = v.view(B, T, self.n_head, C // self.n_head).transpose(1, 2)
        if self.rotary is not None:
            q, k = self.rotary(q, position_offset), self.rotary(k, position_offset)
        if past_key_value is not None:
            if past_key_value[0].dtype != k.dtype or past_key_value[1].dtype != v.dtype:
                raise ValueError("cache precision changed; rebuild it under the current precision")
            k = torch.cat((past_key_value[0], k), dim=-2)
            v = torch.cat((past_key_value[1], v), dim=-2)
        present = (k, v) if use_cache else None
        # Non-square is_causal uses an upper-left triangle. Cached queries
        # instead start after the prefix, so chunk decoding needs this offset.
        mask = None
        if position_offset and T > 1:
            keys = torch.arange(k.size(-2), device=x.device)
            queries = torch.arange(position_offset, position_offset + T, device=x.device)
            mask = keys[None, :] <= queries[:, None]
        # Apple's MPS backend has no fused attention with dropout (torch 2.14:
        # "scaled_dot_product_attention for MPS does not support dropout"), so
        # a training step on a Mac takes the plain path; same math, no fusion.
        fused = self.flash and not (x.device.type == "mps" and self.training and self.dropout > 0)
        if fused:
            y = F.scaled_dot_product_attention(
                q, k, v, attn_mask=mask, is_causal=position_offset == 0,
                dropout_p=self.dropout if self.training else 0.0)
        else:
            att = (q @ k.transpose(-2, -1)) * (1.0 / math.sqrt(k.size(-1)))
            if mask is None:
                if position_offset:
                    mask = torch.ones(T, k.size(-2), dtype=torch.bool, device=x.device)
                else:
                    stored_mask = getattr(self, "mask", None)
                    mask = (stored_mask[:, :, :T, :T] if stored_mask is not None else
                            torch.ones(T, T, dtype=torch.bool, device=x.device).tril())
            att = att.masked_fill(mask == 0, float("-inf"))
            y = self.attn_dropout(F.softmax(att, dim=-1)) @ v
        y = y.transpose(1, 2).contiguous().view(B, T, C)
        output = self.resid_dropout(self.c_proj(y))
        return (output, present) if use_cache else output


class MLP(nn.Module):
    def __init__(self, config: GPTConfig):
        super().__init__()
        self.c_fc = nn.Linear(config.n_embd, 4 * config.n_embd, bias=config.bias)
        self.gelu = nn.GELU()
        self.c_proj = nn.Linear(4 * config.n_embd, config.n_embd, bias=config.bias)
        self.dropout = nn.Dropout(config.dropout)

    def forward(self, x):
        return self.dropout(self.c_proj(self.gelu(self.c_fc(x))))


class SwiGLU(nn.Module):
    def __init__(self, config: GPTConfig):
        super().__init__()
        # Three matrices at 8/3 width approximately match the old two at 4x.
        hidden = config.ffn_hidden_size or math.ceil((8 * config.n_embd / 3) / 64) * 64
        self.gate_up = nn.Linear(config.n_embd, 2 * hidden, bias=config.bias)
        self.c_proj = nn.Linear(hidden, config.n_embd, bias=config.bias)
        self.dropout = nn.Dropout(config.dropout)

    def forward(self, x):
        gate, value = self.gate_up(x).chunk(2, dim=-1)
        return self.dropout(self.c_proj(F.silu(gate) * value))


def normalization(config: GPTConfig):
    if config.architecture == "modern":
        return RMSNorm(config.n_embd, config.norm_eps)
    return nn.LayerNorm(config.n_embd)


class Block(nn.Module):
    def __init__(self, config: GPTConfig):
        super().__init__()
        self.ln_1 = normalization(config)
        self.attn = CausalSelfAttention(config)
        self.ln_2 = normalization(config)
        self.mlp = SwiGLU(config) if config.architecture == "modern" else MLP(config)

    def forward(self, x, *, past_key_value=None, use_cache=False, position_offset=0):
        attention = self.attn(self.ln_1(x), past_key_value=past_key_value,
                              use_cache=use_cache, position_offset=position_offset)
        if use_cache:
            attention, present = attention
        x = x + attention
        x = x + self.mlp(self.ln_2(x))
        return (x, present) if use_cache else x


class GPT(nn.Module):
    def __init__(self, config: GPTConfig):
        super().__init__()
        self.config = config
        modules = dict(wte=nn.Embedding(config.vocab_size, config.n_embd))
        if config.architecture == "gpt":
            modules["wpe"] = nn.Embedding(config.block_size, config.n_embd)
        modules.update(
            drop=nn.Dropout(config.dropout),
            h=nn.ModuleList([Block(config) for _ in range(config.n_layer)]),
            ln_f=normalization(config),
        )
        self.transformer = nn.ModuleDict(modules)
        self.lm_head = nn.Linear(config.n_embd, config.vocab_size, bias=False)
        self.transformer.wte.weight = self.lm_head.weight  # weight tying

        self.apply(self._init_weights)
        # GPT-2 scaled init on residual projections
        for name, p in self.named_parameters():
            if name.endswith("c_proj.weight"):
                nn.init.normal_(p, mean=0.0, std=0.02 / math.sqrt(2 * config.n_layer))

    @staticmethod
    def _init_weights(m):
        if isinstance(m, nn.Linear):
            nn.init.normal_(m.weight, mean=0.0, std=0.02)
            if m.bias is not None:
                nn.init.zeros_(m.bias)
        elif isinstance(m, nn.Embedding):
            nn.init.normal_(m.weight, mean=0.0, std=0.02)

    def num_params(self) -> int:
        """Historical count excluding learned positions, for old run comparisons."""
        positions = self.transformer.wpe.weight.numel() if "wpe" in self.transformer else 0
        return self.total_params() - positions

    def total_params(self) -> int:
        """All trainable parameters, counting the tied embedding only once."""
        return sum(p.numel() for p in self.parameters())

    def forward(self, idx, targets=None, *, only_last=False):
        B, T = idx.size()
        assert T <= self.config.block_size, f"seq len {T} > block_size {self.config.block_size}"
        x = self.transformer.wte(idx)
        if "wpe" in self.transformer:
            pos = torch.arange(0, T, dtype=torch.long, device=idx.device)
            x = x + self.transformer.wpe(pos)
        x = self.transformer.drop(x)
        for block in self.transformer.h:
            if self.config.gradient_checkpointing and self.training and torch.is_grad_enabled():
                x = checkpoint(block, x, use_reentrant=False)
            else:
                x = block(x)
        x = self.transformer.ln_f(x)
        if only_last:
            if targets is not None:
                raise ValueError("only_last cannot be used with training targets")
            x = x[:, -1:, :]
        logits = self.lm_head(x)
        loss = None
        if targets is not None:
            loss = F.cross_entropy(logits.view(-1, logits.size(-1)),
                                   targets.view(-1), ignore_index=-1)
        return logits, loss

    @torch.no_grad()
    def forward_cached(self, idx, cache: KVCache | None = None, *, only_last=False):
        """Decode a new chunk after an external cache; return its logits and cache.

        Positions start at the cached prefix length for both learned embeddings
        and RoPE. This inference-only API never stores state on the model. When
        the context shifts, the caller must rebuild from the retained token IDs:
        dropping old keys would preserve hidden states that attended to them.
        """
        if self.training:
            raise ValueError("cached decoding requires eval mode")
        if idx.ndim != 2 or idx.size(1) == 0:
            raise ValueError("cached decoding requires a nonempty batch of token sequences")
        batch, length = idx.shape
        offset = 0
        if cache is not None:
            if len(cache) != self.config.n_layer:
                raise ValueError("cache must contain one key/value pair per layer")
            if not cache or len(cache[0]) != 2 or cache[0][0].ndim != 4:
                raise ValueError("invalid cache tensor shape")
            offset = cache[0][0].size(-2)
            expected = (batch, self.config.n_head, offset,
                        self.config.n_embd // self.config.n_head)
            for pair in cache:
                if len(pair) != 2 or any(t.shape != expected or t.device != idx.device for t in pair):
                    raise ValueError("cache batch, heads, length, or device does not match this input")
        if offset + length > self.config.block_size:
            raise ValueError("cache exceeds context window; rebuild from the retained token IDs")
        x = self.transformer.wte(idx)
        if "wpe" in self.transformer:
            pos = torch.arange(offset, offset + length, dtype=torch.long, device=idx.device)
            x = x + self.transformer.wpe(pos)
        x = self.transformer.drop(x)
        next_cache = []
        for i, block in enumerate(self.transformer.h):
            x, present = block(x, past_key_value=cache[i] if cache is not None else None,
                               use_cache=True, position_offset=offset)
            next_cache.append(present)
        x = self.transformer.ln_f(x)
        if only_last:
            x = x[:, -1:, :]
        return self.lm_head(x), tuple(next_cache)

    @torch.no_grad()
    def generate(self, idx, max_new_tokens, temperature=1.0, top_k=None, *, use_cache=False):
        """Sample tokens; caching is opt-in because small prefixes can run faster without it."""
        if temperature < 0 or not math.isfinite(temperature):
            raise ValueError("temperature must be finite and nonnegative")
        if max_new_tokens < 0 or (top_k is not None and top_k < 1):
            raise ValueError("max_new_tokens must be nonnegative and top_k positive")
        if idx.ndim != 2 or idx.size(1) == 0:
            raise ValueError("generation requires a nonempty batch of token sequences")
        was_training = self.training
        self.eval()
        cache = None
        try:
            for _ in range(max_new_tokens):
                if use_cache:
                    if cache is None or cache[0][0].size(-2) == self.config.block_size:
                        logits, cache = self.forward_cached(idx[:, -self.config.block_size:], only_last=True)
                    else:
                        logits, cache = self.forward_cached(idx[:, -1:], cache, only_last=True)
                else:
                    logits, _ = self(idx[:, -self.config.block_size:], only_last=True)
                logits = logits[:, -1, :]
                if temperature == 0:
                    idx_next = logits.argmax(dim=-1, keepdim=True)
                else:
                    logits = logits / temperature
                    if top_k is not None:
                        v, _ = torch.topk(logits, min(top_k, logits.size(-1)))
                        logits = logits.masked_fill(logits < v[:, [-1]], -float("Inf"))
                    idx_next = torch.multinomial(F.softmax(logits, dim=-1), num_samples=1)
                idx = torch.cat((idx, idx_next), dim=1)
            return idx
        finally:
            self.train(was_training)
