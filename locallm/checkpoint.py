"""checkpoint.py — load a model YOU trained back off disk. One implementation.

WHY THIS EXISTS. studio.py could only ever sample a model it had just trained in
the same session: `self.model` was assigned in exactly one place, the "done"
message at the end of a training run, and the Sample button was created
`state="disabled"` and only re-enabled from that same handler. Nothing anywhere
loaded `<out>/ckpt.pt`. So closing the GUI and reopening it left the trained model
on disk unreachable — the button sat greyed out, clicking it did nothing, and
`_generate` began with `if self.model is None: return`, which is silent. From the
outside that is "I trained it and now it won't talk back."

generate.py already knew how to do this, in four lines inside `main()` where no
other caller could reach them. Rather than copy those lines into the GUI — the
mistake `venv_guard.py` exists in the parent repo to end, where a helper copied
into a second file was correct in the first and wrong in the second — the load
lives here once and both callers import it.

    from checkpoint import load_checkpoint
    model, tok, cfg = load_checkpoint("out_gui")
"""
from __future__ import annotations

from pathlib import Path

import torch

from data import load_tokenizer, tokenizer_fingerprint
from model import GPT, GPTConfig
from train import pick_device


def checkpoint_exists(out_dir: str | Path) -> bool:
    """Both files, not just one. A ckpt.pt with no tokenizer.json cannot decode
    what it generates, so half a checkpoint is not a checkpoint."""
    out = Path(out_dir)
    return (out / "ckpt.pt").exists() and (out / "tokenizer.json").exists()


def load_checkpoint(out_dir: str | Path, device: str | None = None):
    """Return (model, tokenizer, config) ready to generate from.

    Raises FileNotFoundError with the path when the checkpoint is absent, so a
    caller can report WHICH directory it looked in rather than failing silently.
    """
    out = Path(out_dir)
    if out.is_file():
        # a kept weights-only checkpoint (ckpt-step-N.pt, written by
        # continue_from_checkpoint --keep-every) decodes with the tokenizer
        # beside it, so a dev-split stopping step can be chosen by decoding
        ckpt, tokf = out, out.parent / "tokenizer.json"
    else:
        ckpt, tokf = out / "ckpt.pt", out / "tokenizer.json"
    missing = [str(p) for p in (ckpt, tokf) if not p.exists()]
    if missing:
        raise FileNotFoundError(
            f"no trained model in {out}/ — missing {', '.join(missing)}. "
            f"Train one first, or point at the directory a previous run wrote.")

    if device is None:
        device = pick_device()
    # weights_only=True: forward-compatible with torch>=2.6 where it becomes the
    # default. The checkpoint is a plain dict of tensors + config primitives.
    # Distributed training checkpoints also contain optimizer and rank RNG state.
    # Inference needs only model weights on the GPU; loading the entire training
    # state there can exhaust memory before the model is even constructed.
    ck = torch.load(ckpt, map_location="cpu", weights_only=True)
    ck.pop("optimizer", None)
    cfg = GPTConfig(**ck["config"])
    tok = load_tokenizer(tokf)

    # A checkpoint whose tokenizer disagrees with its embedding table will
    # generate index errors or silent garbage. Cheap to check, miserable to
    # debug: caught here, at load, naming both numbers.
    if tok.vocab_size != cfg.vocab_size:
        raise ValueError(
            f"{out}/ is inconsistent: tokenizer has {tok.vocab_size} tokens "
            f"but the model's vocab_size is {cfg.vocab_size}. The tokenizer and "
            f"the weights came from different training runs.")
    if "tokenizer_fingerprint" in ck and ck["tokenizer_fingerprint"] != tokenizer_fingerprint(tok):
        raise ValueError(
            f"{out}/ is inconsistent: tokenizer fingerprint does not match the weights. "
            "Token IDs or encoding rules changed; restore this checkpoint's tokenizer.json.")
    model = GPT(cfg).to(device)
    model.load_state_dict(ck["model"])
    model.eval()
    return model, tok, cfg


def _token_stop(tok, prompt_ids: list, stop):
    """A text-level stop as model.generate's token-level one.

    ``stop(text) -> int | None`` looks at the text sample() would return if
    generation ended now (prompt included) and answers with the character index
    where the reply ends, or None to keep going. The whole text is decoded after
    every token rather than a window, because the boundary this project stops
    at is a regex whose match can begin long before the token that completes
    it (a whitespace run before "Problem: "); vLLM's window trick assumes
    fixed-length stop strings (vllm/v1/engine/detokenizer.py check_stop_strings).
    """
    def token_stop(_row, new_tokens):
        return stop(tok.decode(prompt_ids + new_tokens)) is not None
    return token_stop


def sample(model, tok, prompt: str, tokens: int = 400,
           temperature: float = 0.8, top_k: int = 40, device: str | None = None,
           use_cache: bool = False, *, stop=None, generator=None) -> str:
    """Prompt in, text out. Shared so the GUI and the CLI cannot drift apart.

    An empty prompt, or one made entirely of characters absent from this model's
    vocabulary, encodes to nothing — and generating from an empty tensor is an
    error rather than an empty answer. Falling back to token 0 keeps that case
    producing text, which is what both callers already did separately.

    ``stop(text) -> int | None`` ends generation once the text so far contains
    the reply's end (see _token_stop). The returned text is exact: its tokens
    are a prefix of the unstopped run's tokens, so a caller that cuts the text
    at the same boundary gets the same reply either way. One limit, documented
    and tested rather than hidden: under byte-level BPE the last kept token can
    split a multi-byte character, and the text then ends in U+FFFD where the
    unstopped text has the character; the extracted reply never includes it.
    """
    if device is None:
        device = next(model.parameters()).device
    ids = tok.encode(prompt) or [0]
    idx = torch.tensor([ids], dtype=torch.long, device=device)
    model.eval()
    out = model.generate(idx, tokens, temperature=temperature, top_k=top_k, use_cache=use_cache,
                         stop=_token_stop(tok, ids, stop) if stop is not None else None,
                         generator=generator)
    return tok.decode(out[0].tolist())


def reply_token_count(tok, prompt_ids: list, new_tokens: list, cut: int) -> int:
    """How many of ``new_tokens`` lie inside the first ``cut`` characters of the
    decoded text: the largest n with len(decode(prompt + new[:n])) <= cut.

    Decoded length grows with n except for one byte-level BPE corner (two
    replacement characters collapsing into the one character they complete), so
    a binary search is followed by a linear fix-up in both directions. This is a
    ranking statistic, not a verdict: it decides which tokens the mean
    log-probability averages over.
    """
    def length(n):
        return len(tok.decode(prompt_ids + new_tokens[:n]))
    lo, hi = 0, len(new_tokens)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if length(mid) <= cut:
            lo = mid
        else:
            hi = mid - 1
    n = lo
    while n < len(new_tokens) and length(n + 1) <= cut:
        n += 1
    while n > 0 and length(n) > cut:
        n -= 1
    return n


def sample_batch(model, tok, prompt: str, num_samples: int, *, tokens: int,
                 temperature: float, top_k: int | None, stop=None, generator=None,
                 device: str | None = None) -> list[dict]:
    """k sampled continuations of one prompt in one batch, with per-row stop and
    the log-probability statistics a selector ranks by.

    Temperature and top_k have no defaults on purpose: the headline arm of round 7
    was sampled at 0.5 because a default filled in silently
    (t/RUN-NEXT-locallm-r12.md, A6). Each row is a dict with ``text`` (prompt
    included, like sample()), ``new_tokens``, ``stopped``, ``reply_tokens`` (the
    tokens before the reply's end when ``stop`` found one, else all of them),
    ``logprob_sum`` and ``mean_logprob`` over those reply tokens, and
    ``mean_logprob_all`` over every new token. The mean over reply tokens is the
    one to rank by: a stopped row otherwise carries the boundary tokens the
    extraction discards, which a budget-exhausted row never has (review of
    2026-09-21). Codex ranks by the mean, not the sum, arXiv:2107.03374.
    """
    if device is None:
        device = next(model.parameters()).device
    ids = tok.encode(prompt) or [0]
    prompt_ids = torch.tensor(ids, dtype=torch.long, device=device)
    model.eval()
    rows = model.sample_many(prompt_ids, num_samples, tokens, temperature=temperature, top_k=top_k,
                             stop=_token_stop(tok, ids, stop) if stop is not None else None,
                             generator=generator)
    out = []
    for row in rows:
        text = tok.decode(ids + row.tokens)
        cut = stop(text) if stop is not None else None
        reply_tokens = reply_token_count(tok, ids, row.tokens, cut) if cut is not None else len(row.tokens)
        kept = row.logprobs[:reply_tokens]
        out.append({"text": text, "new_tokens": len(row.tokens), "stopped": row.stopped,
                    "reply_tokens": reply_tokens, "logprob_sum": float(sum(kept)),
                    "mean_logprob": float(sum(kept)) / reply_tokens if reply_tokens else None,
                    "mean_logprob_all": row.mean_logprob})
    return out
