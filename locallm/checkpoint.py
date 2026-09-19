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


def sample(model, tok, prompt: str, tokens: int = 400,
           temperature: float = 0.8, top_k: int = 40, device: str | None = None,
           use_cache: bool = False) -> str:
    """Prompt in, text out. Shared so the GUI and the CLI cannot drift apart.

    An empty prompt, or one made entirely of characters absent from this model's
    vocabulary, encodes to nothing — and generating from an empty tensor is an
    error rather than an empty answer. Falling back to token 0 keeps that case
    producing text, which is what both callers already did separately.
    """
    if device is None:
        device = next(model.parameters()).device
    ids = tok.encode(prompt) or [0]
    idx = torch.tensor([ids], dtype=torch.long, device=device)
    model.eval()
    out = model.generate(idx, tokens, temperature=temperature, top_k=top_k, use_cache=use_cache)
    return tok.decode(out[0].tolist())
