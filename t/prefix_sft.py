"""prefix_sft.py: a batch of rows that share a long prefix, with the prefix computed once per step, exactly.

    python3 t/prefix_sft.py --check            # a tiny random model, CPU, double precision: the loss and every gradient
                                               # against the plain per-row loss, with and without checkpointing

Every training row of the assistant is the same 2,200-token system-and-tools prefix and then a task of some hundreds
of tokens; a step of sixteen rows runs the prefix forward and backward sixteen times. Here the prefix runs once: its
state after the last prefix token (the attention layers' keys and values, the linear-attention layers' recurrent
state and conv window) is kept on the autograd graph, expanded over the batch, and the suffixes run as one batch from
it; the loss's gradient flows back through the shared state into the single prefix pass, which is the sum over the
rows, as the per-row computation would give. The schedule is the one of arXiv:2606.01143 (prefix forward once,
suffixes reading its K/V, prefix backward once on the accumulated gradient; exact over real arithmetic) and the
reuse of arXiv:2511.00413, written here for a hybrid model whose state is not only K/V: fla's chunked gated delta
rule returns the gradient of its initial state (dh0), so the path exists.

What the model's own cache would not let through: its linear-attention cache layer writes new states into static
tensors in place (`copy_`), which autograd rejects once those tensors have been read into the graph; `GradLinearLayer`
assigns instead. And checkpointing: a layer that mutates a cache cannot be recomputed, so each layer runs as a pure
function of (hidden states, its incoming state) that builds a throwaway cache, under torch's checkpoint.
"""
from __future__ import annotations

import argparse
import sys

import torch
from torch.utils.checkpoint import checkpoint


class GradLinearLayer:
    """A linear-attention cache layer whose updates assign (autograd-safe) instead of copying in place."""

    def __init__(self, base_class, conv_kernel_size: int):
        self._base = base_class
        self.layer = base_class(number_of_states=1)
        self.layer.conv_kernel_size[0] = conv_kernel_size
        self.layer.update_conv_state = self.update_conv_state
        self.layer.update_recurrent_state = self.update_recurrent_state

    def update_conv_state(self, conv_states, state_idx: int = 0, conv_kernel_size=None, **_kw):
        lay, k = self.layer, conv_kernel_size or self.layer.conv_kernel_size[0]
        lay.conv_kernel_size[state_idx] = k
        if lay.has_previous_state[state_idx]:
            full = torch.cat([lay.conv_states[state_idx], conv_states], dim=-1)
        else:
            full = conv_states
            lay.has_previous_state[state_idx] = True
        lay.conv_states[state_idx] = full[..., -k:]
        lay.is_conv_states_initialized[state_idx] = True
        return full

    def update_recurrent_state(self, recurrent_states, state_idx: int = 0, **_kw):
        self.layer.recurrent_states[state_idx] = recurrent_states
        self.layer.is_recurrent_states_initialized[state_idx] = True
        return recurrent_states


class Shared:
    """The backbone run layer by layer, states in and out as plain tensors. `base` is the causal LM (its `.model` the
    text backbone with `embed_tokens`, `layers`, `norm`, `rotary_emb`; its `lm_head` the output layer)."""

    def __init__(self, base, checkpointing: bool = True):
        from transformers.cache_utils import DynamicCache, LinearAttentionLayer
        self.base, self.text = base, base.model
        self.config = self.text.config
        self.kinds = list(self.config.layer_types)
        self.conv_k = self.config.linear_conv_kernel_dim
        self.checkpointing = checkpointing
        self._DynamicCache, self._LinearLayer = DynamicCache, LinearAttentionLayer

    # ---- caches as plain tensors ---------------------------------------------------------------------------------
    def _cache(self, states, batch: int | None):
        """A cache holding `states` (per layer: (keys, values) or (conv, recurrent), or None), each expanded to `batch`."""
        cache = self._DynamicCache(config=self.config)
        for i, kind in enumerate(self.kinds):
            if kind == "linear_attention":
                cache.layers[i] = GradLinearLayer(self._LinearLayer, self.conv_k).layer
            st = states[i] if states is not None else None
            if st is None:
                continue
            lay = cache.layers[i]
            if kind == "full_attention":
                k, v = st
                if batch is not None and k.shape[0] != batch:
                    k, v = k.expand(batch, *k.shape[1:]), v.expand(batch, *v.shape[1:])
                lay.keys, lay.values, lay.is_initialized = k, v, True
                lay.dtype, lay.device = k.dtype, k.device
            else:
                conv, rec = st
                if batch is not None and conv.shape[0] != batch:
                    conv = conv.expand(batch, *conv.shape[1:]).contiguous()
                    rec = rec.expand(batch, *rec.shape[1:]).contiguous()
                lay.conv_states[0], lay.recurrent_states[0] = conv, rec
                lay.is_conv_states_initialized[0] = lay.is_recurrent_states_initialized[0] = lay.has_previous_state[0] = True
                lay.dtype, lay.device = conv.dtype, conv.device
        return cache

    def _state_of(self, cache, i: int):
        lay = cache.layers[i]
        if self.kinds[i] == "full_attention":
            return lay.keys, lay.values
        return lay.conv_states[0], lay.recurrent_states[0]

    # ---- one pass -------------------------------------------------------------------------------------------------
    def run(self, input_ids, attention_mask, start: int, states=None):
        """Hidden states after the final norm, and the state after these tokens, per layer. `attention_mask` covers
        the whole sequence seen (start + these tokens), 2-D; `states` is the state before them (None: the start)."""
        from transformers.masking_utils import create_causal_mask, create_recurrent_attention_mask
        text, B, S = self.text, input_ids.shape[0], input_ids.shape[1]
        emb = text.embed_tokens(input_ids)
        positions = (torch.arange(S, device=input_ids.device) + start).view(1, 1, -1).expand(4, B, -1)
        text_pos, rot_pos = positions[0], positions[1:]
        for_masks = self._cache(states, B)
        masks = {"full_attention": create_causal_mask(config=self.config, inputs_embeds=emb, attention_mask=attention_mask,
                                                      past_key_values=for_masks, position_ids=text_pos, allow_is_causal_skip=False),
                 "linear_attention": create_recurrent_attention_mask(config=self.config, inputs_embeds=emb,
                                                                     attention_mask=attention_mask, past_key_values=for_masks)}
        pos_emb = text.rotary_emb(emb, rot_pos)
        hidden, out_states = emb, []
        for i, layer in enumerate(text.layers):
            kind, st_in = self.kinds[i], (states[i] if states is not None else None)

            def one(h, *st, layer=layer, i=i, kind=kind):
                per_layer = [None] * len(self.kinds)
                if st:
                    per_layer[i] = st
                c = self._cache(per_layer, B)
                was = getattr(layer, "gradient_checkpointing", False)
                layer.gradient_checkpointing = False             # this loop checkpoints; the model's own would re-run the cache update
                try:
                    h = layer(h, position_embeddings=pos_emb, attention_mask=masks[kind], position_ids=text_pos,
                              past_key_values=c, use_cache=True)
                finally:
                    layer.gradient_checkpointing = was
                return (h, *self._state_of(c, i))
            args = (hidden, *st_in) if st_in is not None else (hidden,)
            if self.checkpointing and torch.is_grad_enabled():
                hidden, *st_out = checkpoint(one, *args, use_reentrant=False)
            else:
                hidden, *st_out = one(*args)
            out_states.append(tuple(st_out))
        return text.norm(hidden), out_states

    # ---- the loss of a batch sharing a prefix --------------------------------------------------------------------
    def loss(self, prefix_ids, suffix_ids, suffix_labels, suffix_mask, num_items_in_batch=None):
        """Cross-entropy on the labelled suffix tokens, the prefix (1, P) computed once. The first suffix token must
        not be a target: it would be predicted by the prefix's last position, which is not computed per row."""
        assert (suffix_labels[:, 0] == -100).all(), "the first suffix token is predicted by the prefix: it must not be a target"
        P = prefix_ids.shape[1]
        _, states = self.run(prefix_ids, torch.ones_like(prefix_ids), 0, None)
        full_mask = torch.cat([torch.ones(suffix_ids.shape[0], P, dtype=suffix_mask.dtype, device=suffix_mask.device), suffix_mask], dim=1)
        hidden, _ = self.run(suffix_ids, full_mask, P, states)
        predicts = suffix_labels[:, 1:] != -100
        logits = self.base.lm_head(hidden[:, :-1][predicts]).float()
        targets = suffix_labels[:, 1:][predicts]
        if num_items_in_batch is None:
            return torch.nn.functional.cross_entropy(logits, targets)
        total = torch.nn.functional.cross_entropy(logits, targets, reduction="sum")
        return total / (num_items_in_batch.to(total.device) if torch.is_tensor(num_items_in_batch) else num_items_in_batch)


def common_prefix(rows: list) -> int:
    """How many leading tokens every row shares."""
    n = min(len(r) for r in rows)
    first = rows[0]
    for i in range(n):
        if any(r[i] != first[i] for r in rows[1:]):
            return i
    return n


def split(features: list[dict], pad_id: int, prefix_len: int | None = None) -> dict:
    """A padded batch of rows as the prefix (1, P) and the suffixes (B, S) with their labels and mask. P is the
    tokens every row shares, or `prefix_len` when given (a batch of one row shares everything with itself)."""
    ids = [f["input_ids"] for f in features]
    P = common_prefix(ids) if prefix_len is None else prefix_len
    assert all(r[:P] == ids[0][:P] for r in ids), "the rows do not share the prefix"
    assert all(len(r) > P for r in ids), "a row ends inside the prefix"
    width = max(len(r) for r in ids) - P
    B = len(ids)
    suffix = torch.full((B, width), pad_id, dtype=torch.long)
    labels = torch.full((B, width), -100, dtype=torch.long)
    mask = torch.zeros((B, width), dtype=torch.long)
    for i, f in enumerate(features):
        n = len(f["input_ids"]) - P
        suffix[i, :n] = torch.tensor(f["input_ids"][P:])
        labels[i, :n] = torch.tensor(f["labels"][P:])
        mask[i, :n] = 1
    return {"prefix_ids": torch.tensor([ids[0][:P]]), "suffix_ids": suffix, "suffix_labels": labels, "suffix_mask": mask}


# ---- the check -------------------------------------------------------------------------------------------------------

def tiny_model(seed: int = 0, layers: str = "LLFL", device: str = "cpu", dtype=torch.float64):
    from transformers import Qwen3_5ForCausalLM, Qwen3_5TextConfig
    torch.manual_seed(seed)
    kinds = {"L": "linear_attention", "F": "full_attention"}
    config = Qwen3_5TextConfig(vocab_size=97, hidden_size=32, intermediate_size=64, num_hidden_layers=len(layers),
                               layer_types=[kinds[c] for c in layers],
                               num_attention_heads=2, num_key_value_heads=1, head_dim=16, linear_num_key_heads=2,
                               linear_num_value_heads=2, linear_key_head_dim=8, linear_value_head_dim=8,
                               linear_conv_kernel_dim=4, max_position_embeddings=512, tie_word_embeddings=False, pad_token_id=0)
    return Qwen3_5ForCausalLM(config).to(device=device, dtype=dtype)


def check(seed: int = 0, batch: int = 3, prefix: int = 20, verbose: bool = True, layers: str = "LLFL", exact64: bool = False,
          device: str = "cpu") -> dict:
    """The plain per-row loss and gradients against the shared-prefix ones, in double precision on the CPU. The
    model casts its norms and its decay gate to 32-bit on purpose, which puts a 32-bit floor under both paths (the
    plain path moves by 1e-2 in the decay gate's gradients when its own chunks change from 64 to 32 tokens);
    `exact64` keeps those casts in 64-bit, and both floors fall to 1e-10, so the comparison is of the schedule alone.
    Measured 2026-10-06: exact to 2e-10 over seeds, prefix lengths, batch sizes and layer layouts, checkpointing on
    or off."""
    saved = (torch.Tensor.to, torch.Tensor.float)
    if exact64:
        _to = torch.Tensor.to

        def to64(self, *args, **kwargs):                             # every cast to 32-bit (`.float()`, `.to(torch.float32)`) keeps 64-bit
            args = tuple(torch.float64 if a is torch.float32 else a for a in args)
            kwargs = {k: (torch.float64 if v is torch.float32 else v) for k, v in kwargs.items()}
            return _to(self, *args, **kwargs)
        torch.Tensor.to = to64
        torch.Tensor.float = lambda self: _to(self, torch.float64)   # noqa: E731
    try:
        return _check(seed, batch, prefix, verbose, layers, device, torch.float64 if exact64 or device == "cpu" else torch.float32)
    finally:
        torch.Tensor.to, torch.Tensor.float = saved


def _check(seed, batch, prefix, verbose, layers, device, dtype) -> dict:
    """On a card the model is 32-bit (the fast kernels take no 64-bit) and the bar follows the plain path's own floor."""
    sys.path.insert(0, __file__.rsplit("/", 1)[0])
    from student_sft import pad_batch, response_loss
    model = tiny_model(seed, layers, device, dtype)

    def on(d):
        return {k: (v.to(device) if torch.is_tensor(v) else v) for k, v in d.items()}
    pad_batch_cpu = pad_batch
    pad_batch = lambda f, pad: on(pad_batch_cpu(f, pad))               # noqa: E731
    g = torch.Generator().manual_seed(seed + 1)
    shared_ids = torch.randint(1, 97, (prefix,), generator=g).tolist()
    features = []
    for n in (7, 9, 5, 11, 6, 8)[:batch]:
        ids = shared_ids + torch.randint(1, 97, (n,), generator=g).tolist()
        labels = [-100] * (prefix + 2) + ids[prefix + 2:]
        features.append({"input_ids": ids, "labels": labels})
    names = [n for n, p in model.named_parameters() if p.requires_grad]

    def grads():
        return {n: p.grad.detach().clone() for n, p in model.named_parameters() if p.grad is not None}

    plain = response_loss(model, pad_batch(features, 0))
    plain.backward()
    plain_grads = grads()
    model.zero_grad(set_to_none=True)
    out = {"plain": plain.item()}
    # The same plain loss with the linear-attention chunks half as long: two exact formulations of one recurrence, whose
    # difference is the floor the model's 32-bit casts put under any comparison (the decay gate is computed in 32-bit)
    import transformers.models.qwen3_5.modeling_qwen3_5 as mod
    original = mod.torch_chunk_gated_delta_rule
    plain_torch = getattr(original, "__wrapped__", original)           # the reference implementation itself, past any kernel hub
    try:
        mod.torch_chunk_gated_delta_rule = lambda *a, **k: plain_torch(*a, **{**k, "chunk_size": 32})
        again = response_loss(model, pad_batch(features, 0))
        again.backward()
        again_grads = grads()
        model.zero_grad(set_to_none=True)
    finally:
        mod.torch_chunk_gated_delta_rule = original
    floor = {n: float((again_grads[n] - plain_grads[n]).abs().max() / (plain_grads[n].abs().max() + 1e-30)) for n in plain_grads}
    out["plain_chunk32"] = {"loss_diff": abs(again.item() - plain.item()), "worst_grad_rel": max(floor.values())}
    if verbose:
        print(f"plain with 32-token chunks against 64: loss differs by {out['plain_chunk32']['loss_diff']:.2e}, worst gradient relative "
              f"difference {out['plain_chunk32']['worst_grad_rel']:.2e}")
        for n, r in sorted(floor.items(), key=lambda kv: -kv[1])[:3]:
            print(f"    {r:.2e}  {n}")
    for ckpt in (False, True):
        parts = on(split(features, 0, prefix_len=prefix))
        shared = Shared(model, checkpointing=ckpt).loss(**parts)
        shared.backward()
        got = grads()
        model.zero_grad(set_to_none=True)
        rel = {n: float((got[n] - plain_grads[n]).abs().max() / (plain_grads[n].abs().max() + 1e-30)) for n in plain_grads if n in got}
        worst = max(rel.values(), default=0.0)
        missing = [n for n in plain_grads if n not in got]
        if verbose and worst > 1e-7:
            for n, r in sorted(rel.items(), key=lambda kv: -kv[1])[:6]:
                print(f"    {r:.2e}  {n}")
        out[f"shared{'_ckpt' if ckpt else ''}"] = {"loss": shared.item(), "loss_diff": abs(shared.item() - plain.item()),
                                                   "worst_grad_rel": worst, "missing": missing, "params": len(names)}
        if verbose:
            print(f"checkpointing={ckpt}: loss {shared.item():.12f} (plain {plain.item():.12f}), worst gradient relative difference "
                  f"{worst:.2e}, {len(got)} of {len(plain_grads)} gradients present" + (f", MISSING {missing}" if missing else ""))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--layers", default="LLFL", help="the tiny model's layer kinds: L linear attention, F full attention")
    ap.add_argument("--batch", type=int, default=5)
    ap.add_argument("--prefix", type=int, default=100, help="longer than one 64-token chunk, so the plain path's chunking floor is measured")
    ap.add_argument("--exact64", action="store_true", help="keep the model's 32-bit casts in 64-bit, to compare the schedule alone")
    ap.add_argument("--device", default="cpu", help="cuda: the fast kernels (fla) and their gradient of the initial state are what is checked")
    a = ap.parse_args(argv)
    if a.check:
        out = check(a.seed, batch=a.batch, prefix=a.prefix, layers=a.layers, exact64=a.exact64, device=a.device)
        # the bar: the loss to 1e-8, and the gradients within 1.5x of what the plain path itself moves by when its
        # linear-attention chunks are 32 tokens instead of 64 (two exact formulations of one recurrence), or 1e-6 in
        # 64-bit and 1e-4 otherwise, whichever is larger
        floor = out["plain_chunk32"]["worst_grad_rel"]
        bar = max(1.5 * floor, 1e-6 if a.exact64 else 1e-4)
        ok = all(v["loss_diff"] < 1e-8 and v["worst_grad_rel"] <= bar and not v["missing"] for k, v in out.items() if k not in ("plain", "plain_chunk32"))
        print(f"bar {bar:.2e} (the plain path's own chunking floor {floor:.2e})")
        print("EXACT" if ok else "NOT EXACT")
        return 0 if ok else 1
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
