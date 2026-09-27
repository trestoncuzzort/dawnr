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

    @staticmethod
    def _validate_sampling(temperature, top_k, max_new_tokens):
        if temperature < 0 or not math.isfinite(temperature):
            raise ValueError("temperature must be finite and nonnegative")
        if max_new_tokens < 0 or (top_k is not None and top_k < 1):
            raise ValueError("max_new_tokens must be nonnegative and top_k positive")

    @torch.no_grad()
    def generate(self, idx, max_new_tokens, temperature=1.0, top_k=None, *, use_cache=False,
                 stop=None, generator=None):
        """Sample tokens; caching is opt-in because small prefixes can run faster without it.

        ``stop(row, new_tokens) -> bool`` is asked after every token for each row that
        has not stopped yet, with that row's new token ids so far. The loop ends when
        every row has stopped or the budget is spent. Stopped rows stay in the batch and
        keep sampling until then, as HF's StoppingCriteria and nanochat's engine do
        (github.com/huggingface/transformers src/transformers/generation/stopping_criteria.py,
        github.com/karpathy/nanochat nanochat/engine.py), so every row is bitwise the
        unstopped row cut at the step the loop ended, at any temperature, cached or not.
        The return type does not change with ``stop``: the (batch, prompt + generated)
        tensor, so ``out[0, n:]`` keeps working for every caller. A caller that wants a
        row cut at its own stop re-applies its boundary to the text; ``sample_many``
        below returns per-row lengths instead.

        ``generator`` seeds the multinomial draws; ``None`` uses torch's global state.
        """
        self._validate_sampling(temperature, top_k, max_new_tokens)
        if idx.ndim != 2 or idx.size(1) == 0:
            raise ValueError("generation requires a nonempty batch of token sequences")
        was_training = self.training
        self.eval()
        cache = None
        live = [True] * idx.size(0) if stop is not None else None
        new = [[] for _ in range(idx.size(0))] if stop is not None else None
        try:
            for _ in range(max_new_tokens):
                if use_cache:
                    if cache is None or cache[0][0].size(-2) == self.config.block_size:
                        logits, cache = self.forward_cached(idx[:, -self.config.block_size:], only_last=True)
                    else:
                        logits, cache = self.forward_cached(idx[:, -1:], cache, only_last=True)
                else:
                    logits, _ = self(idx[:, -self.config.block_size:], only_last=True)
                idx_next = _next_token(logits[:, -1, :], temperature, top_k, generator)
                idx = torch.cat((idx, idx_next), dim=1)
                if stop is not None:
                    column = idx_next[:, 0].tolist()
                    for row, token in enumerate(column):
                        if live[row]:
                            new[row].append(token)
                            if stop(row, new[row]):
                                live[row] = False
                    if not any(live):
                        break
            return idx
        finally:
            self.train(was_training)

    @torch.no_grad()
    def sample_many(self, prompt, num_samples, max_new_tokens, *, temperature, top_k,
                    stop=None, generator=None):
        """k completions of one prompt, decoded together with the KV cache.

        ``prompt`` is a 1-D tensor of token ids. Returns a list of ``Sampled`` in row
        order: each row's new tokens (through its stop token when it stopped), the
        log-probability of every new token under the untempered fp32 distribution,
        and whether its stop fired.

        The prompt is prefilled once at batch 1 and the cache and last logits are
        expanded to k rows (nanochat engine.py, github.com/karpathy/nanochat). Rows
        decode in lockstep; a row whose ``stop(row, new_tokens)`` returns True leaves
        the batch (index_select on the cache), the iteration-level scheduling of vLLM,
        arXiv:2309.06180, because one long row would otherwise keep every other row
        decoding to the budget. The price is stated plainly: kernels are not
        batch-invariant (thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference),
        so a run is bitwise reproducible only for the same seed, k and departure
        pattern; at k=1 it is bitwise ``generate(use_cache=True)`` with the same
        generator, which the tests check.

        Log-probabilities are taken before temperature and top-k, because ranking by
        mean token log-probability under the model's own distribution is the heuristic
        Codex measured (arXiv:2107.03374, figure 7); the caller decides which tokens to
        average over.
        """
        self._validate_sampling(temperature, top_k, max_new_tokens)
        if prompt.ndim != 1 or prompt.numel() == 0:
            raise ValueError("sample_many takes one nonempty 1-D prompt")
        if num_samples < 1:
            raise ValueError("num_samples must be positive")
        was_training = self.training
        self.eval()
        try:
            block = self.config.block_size
            idx = prompt[None, :]
            logits, cache = self.forward_cached(idx[:, -block:], only_last=True)
            logits = logits[:, -1, :].expand(num_samples, -1).contiguous()
            cache = tuple((k.expand(num_samples, -1, -1, -1).contiguous(),
                           v.expand(num_samples, -1, -1, -1).contiguous()) for k, v in cache)
            idx = idx.expand(num_samples, -1).contiguous()
            rows = list(range(num_samples))                    # original row of each live batch row
            results = [Sampled([], [], False) for _ in range(num_samples)]
            for _ in range(max_new_tokens):
                logp = F.log_softmax(logits.float(), dim=-1)
                idx_next = _next_token(logits, temperature, top_k, generator)
                chosen = logp.gather(1, idx_next)[:, 0].tolist()
                column = idx_next[:, 0].tolist()
                idx = torch.cat((idx, idx_next), dim=1)
                keep = []
                for b, row in enumerate(rows):
                    results[row].tokens.append(column[b])
                    results[row].logprobs.append(chosen[b])
                    if stop is not None and stop(row, results[row].tokens):
                        results[row].stopped = True
                    else:
                        keep.append(b)
                if not keep:
                    break
                if len(keep) < len(rows):
                    select = torch.tensor(keep, device=idx.device)
                    idx = idx.index_select(0, select)
                    cache = tuple((k.index_select(0, select), v.index_select(0, select)) for k, v in cache)
                    rows = [rows[b] for b in keep]
                if cache[0][0].size(-2) == block:                 # the window is full: rebuild, as generate does
                    logits, cache = self.forward_cached(idx[:, -block:], only_last=True)
                else:
                    logits, cache = self.forward_cached(idx[:, -1:], cache, only_last=True)
                logits = logits[:, -1, :]
            return results
        finally:
            self.train(was_training)


def _next_token(logits, temperature, top_k, generator=None):
    """One sampling step over (batch, vocab) logits: greedy at temperature 0, else
    temperature, then top-k, then a multinomial draw. Shared by generate and
    sample_many so the two cannot drift."""
    if temperature == 0:
        return logits.argmax(dim=-1, keepdim=True)
    logits = logits / temperature
    if top_k is not None:
        v, _ = torch.topk(logits, min(top_k, logits.size(-1)))
        logits = logits.masked_fill(logits < v[:, [-1]], -float("Inf"))
    return torch.multinomial(F.softmax(logits, dim=-1), num_samples=1, generator=generator)


@dataclass
class Sampled:
    """One row of sample_many: new tokens (through the stop token if it stopped),
    the log-probability of each under the untempered distribution, and whether the
    stop fired. The mean here is over every new token; a caller that knows which
    tokens the reply keeps (checkpoint.sample_batch) averages over those."""
    tokens: list
    logprobs: list
    stopped: bool

    @property
    def logprob_sum(self) -> float:
        return float(sum(self.logprobs))

    @property
    def mean_logprob(self):
        return self.logprob_sum / len(self.tokens) if self.tokens else None


# ------------------------------------------------------------------ LoRA --
# Low-rank adapters, off unless add_lora is called (dawnr's per-person learning,
# DAWNR-LEARNING.md). LoRA (Hu et al., arXiv:2106.09685): the pretrained weight
# W0 is frozen and a trainable update B A of rank r is added beside it,
# h = W0 x + (alpha / r) B A x, with A random and B zero so the adapted model
# starts exactly where the base is. The layer follows microsoft/LoRA's
# loralib/layers.py Linear (github.com/microsoft/LoRA): lora_A is (r, in),
# lora_B is (out, r), A is initialised as nn.Linear initialises its weight
# (kaiming_uniform, a = sqrt(5)), dropout acts on the input to A. The paper
# adapts the attention projections only and leaves the MLP to future work; the
# repo's own peft recipe for the Phi student adapts attention and MLP
# (t/loop_train.py), and so does this one.
#
# Two things differ from loralib, on purpose. loralib merges B A into the base
# weight as a side effect of .eval() and unmerges on .train(); here merging is
# an explicit call (merge_lora), because dawnr swaps one person's adapter for
# another's on the same base and must be able to show the base never changed
# (base_fingerprint before add_lora and after remove_lora). And an adapter can
# be switched off in place (set_lora_enabled), which gives the frozen base's
# own predictions without unloading anything: the reference a measurement
# compares against.

LORA_TARGETS = {"gpt": ("attn.c_attn", "attn.c_proj", "mlp.c_fc", "mlp.c_proj"),
                "modern": ("attn.c_attn", "attn.c_proj", "mlp.gate_up", "mlp.c_proj")}


class LoRALinear(nn.Module):
    """A frozen nn.Linear with a trainable rank-r update beside it."""

    def __init__(self, base: nn.Linear, r: int, alpha: float, dropout: float = 0.0):
        super().__init__()
        if not isinstance(base, nn.Linear):
            raise TypeError(f"LoRA wraps an nn.Linear, not {type(base).__name__}")
        if r < 1 or alpha <= 0 or not 0 <= dropout < 1:
            raise ValueError(f"LoRA needs r >= 1, alpha > 0 and dropout in [0, 1); got {r}, {alpha}, {dropout}")
        self.base = base
        for p in base.parameters():
            p.requires_grad_(False)
        self.r, self.alpha, self.scaling = int(r), float(alpha), float(alpha) / r
        self.lora_A = nn.Parameter(base.weight.new_zeros((r, base.in_features)))
        self.lora_B = nn.Parameter(base.weight.new_zeros((base.out_features, r)))
        nn.init.kaiming_uniform_(self.lora_A, a=math.sqrt(5))
        self.lora_dropout = nn.Dropout(dropout) if dropout > 0 else nn.Identity()
        self.enabled = True

    @property
    def in_features(self) -> int:
        return self.base.in_features

    @property
    def out_features(self) -> int:
        return self.base.out_features

    def delta_weight(self) -> torch.Tensor:
        """The update this adapter adds to the base weight: (alpha / r) B A, shaped like it."""
        return (self.lora_B @ self.lora_A) * self.scaling

    def forward(self, x):
        out = self.base(x)
        if not self.enabled:
            return out
        return out + F.linear(F.linear(self.lora_dropout(x), self.lora_A), self.lora_B) * self.scaling


def _lora_slots(model, targets):
    """(block index, dotted path, parent module, attribute name) for every target Linear."""
    for i, block in enumerate(model.transformer.h):
        for path in targets:
            parent_path, _, leaf = path.rpartition(".")
            parent = block.get_submodule(parent_path) if parent_path else block
            yield i, path, parent, leaf


def has_lora(model) -> bool:
    return any(isinstance(m, LoRALinear) for m in model.modules())


def lora_modules(model) -> list[tuple[str, LoRALinear]]:
    return [(name, m) for name, m in model.named_modules() if isinstance(m, LoRALinear)]


def add_lora(model, r: int = 8, alpha: float | None = None, dropout: float = 0.0, targets=None) -> dict:
    """Freeze every parameter of the model and wrap each block's target Linears in a LoRALinear.

    Returns the adapter's configuration, which is also kept as model.lora_config
    and saved with the adapter (lora_state), so a load can refuse a mismatch.
    alpha defaults to r (scaling 1): the LoRA paper sets alpha to the first r it
    tries and does not tune it. remove_lora restores the model exactly.
    """
    if has_lora(model):
        raise ValueError("this model already carries a LoRA adapter; remove_lora first")
    targets = tuple(targets or LORA_TARGETS[model.config.architecture])
    alpha = float(r if alpha is None else alpha)
    slots = list(_lora_slots(model, targets))
    for _i, path, parent, leaf in slots:
        if not isinstance(getattr(parent, leaf, None), nn.Linear):
            raise ValueError(f"LoRA target {path!r} is not an nn.Linear in this model")
    model._lora_requires_grad = {name: p.requires_grad for name, p in model.named_parameters()}
    for p in model.parameters():
        p.requires_grad_(False)
    for _i, _path, parent, leaf in slots:
        setattr(parent, leaf, LoRALinear(getattr(parent, leaf), r, alpha, dropout))
    model.lora_config = {"r": int(r), "alpha": alpha, "dropout": float(dropout), "targets": list(targets),
                         "n_layer": model.config.n_layer, "architecture": model.config.architecture}
    return dict(model.lora_config)


def remove_lora(model) -> None:
    """Unwrap every LoRALinear back to its frozen base and restore each parameter's requires_grad."""
    for name, m in lora_modules(model):
        parent_path, _, leaf = name.rpartition(".")
        setattr(model.get_submodule(parent_path) if parent_path else model, leaf, m.base)
    for name, p in model.named_parameters():
        p.requires_grad_(getattr(model, "_lora_requires_grad", {}).get(name, True))
    model.__dict__.pop("_lora_requires_grad", None)
    model.__dict__.pop("lora_config", None)


def merge_lora(model) -> None:
    """Fold every adapter into its base weight (W0 + (alpha / r) B A) and unwrap it.

    The result is a plain GPT whose state_dict loads like any checkpoint; the
    adapter's own tensors are gone, so this is an export, never a step in a
    session (a merged base can no longer be shown untouched)."""
    with torch.no_grad():
        for _name, m in lora_modules(model):
            m.base.weight += m.delta_weight().to(m.base.weight.dtype)
    remove_lora(model)


def set_lora_enabled(model, enabled: bool) -> None:
    """Switch every adapter on or off in place; off, the model computes exactly the frozen base."""
    for _name, m in lora_modules(model):
        m.enabled = bool(enabled)


def lora_parameters(model) -> list[nn.Parameter]:
    return [p for _name, m in lora_modules(model) for p in (m.lora_A, m.lora_B)]


def lora_state(model) -> dict:
    """The adapter alone, on the CPU: its configuration and every lora_A / lora_B tensor by module name."""
    if not has_lora(model):
        raise ValueError("this model carries no LoRA adapter")
    tensors = {}
    for name, m in lora_modules(model):
        tensors[name + ".lora_A"] = m.lora_A.detach().to("cpu", torch.float32).clone()
        tensors[name + ".lora_B"] = m.lora_B.detach().to("cpu", torch.float32).clone()
    return {"config": dict(model.lora_config), "tensors": tensors}


def load_lora_state(model, state: dict) -> dict:
    """Wrap the model with the saved adapter's configuration and load its tensors, refusing any mismatch."""
    config = dict(state["config"])
    if config.get("architecture") != model.config.architecture or config.get("n_layer") != model.config.n_layer:
        raise ValueError(f"this adapter was made for a {config.get('architecture')} model of "
                         f"{config.get('n_layer')} layers, not {model.config.architecture} of {model.config.n_layer}")
    if not has_lora(model):
        add_lora(model, r=config["r"], alpha=config["alpha"], dropout=config["dropout"], targets=config["targets"])
    elif model.lora_config != config:
        raise ValueError("the model carries a different adapter configuration; remove_lora first")
    modules = dict(lora_modules(model))
    expected = {name + suffix for name in modules for suffix in (".lora_A", ".lora_B")}
    if set(state["tensors"]) != expected:
        raise ValueError("the adapter's tensors do not name this model's adapted modules")
    with torch.no_grad():
        for key, tensor in state["tensors"].items():
            name, _, which = key.rpartition(".")
            target = getattr(modules[name], which)
            if tuple(target.shape) != tuple(tensor.shape):
                raise ValueError(f"{key} is {tuple(tensor.shape)}, the model's is {tuple(target.shape)}")
            target.copy_(tensor.to(target.device, target.dtype))
    return config


def base_fingerprint(model) -> str:
    """sha256 over every non-LoRA tensor in the model, by name: equal before and after an adapter's life."""
    import hashlib
    h = hashlib.sha256()
    for name, tensor in sorted(model.state_dict().items()):
        if ".lora_" in name:
            continue
        name = name.replace(".base.", ".")          # a wrapped Linear names its weight <module>.base.weight
        h.update(name.encode())
        h.update(tensor.detach().to("cpu").contiguous().numpy().tobytes() if tensor.dtype != torch.bfloat16
                 else tensor.detach().to("cpu", torch.float32).contiguous().numpy().tobytes())
    return h.hexdigest()
