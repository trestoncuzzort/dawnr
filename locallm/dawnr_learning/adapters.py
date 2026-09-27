"""adapters.py: one small LoRA adapter per person on a frozen base, saved with what it was trained on.

OPPU (Tan et al., "Democratizing Large Language Models via Personalized
Parameter-Efficient Fine-tuning", arXiv:2402.04401): each user owns a small
LoRA module plugged into a shared, frozen, already task-adapted base, and the
base itself never sees any one user's data. dawnr keeps that shape: the base is
the chat-trained checkpoint (dawnr_pipeline.py), the adapter is model.py's
LoRA over attention and MLP, and everything learned about a person lives in
<person>/adapters/<base>/ and nowhere else.

What an adapter carries beside its tensors (adapter.json), so that every claim
about it can be checked:

* the base it belongs to: the sha256 of the checkpoint file and the tokenizer
  fingerprint. An adapter is a set of deltas to one exact set of weights; on
  any other base it is noise, so a mismatch is refused, not tried;
* the examples it was trained on, by record id and content hash. If the person
  erases or corrects one of them, the adapter is stale: it is not attached again
  until a sleep rebuilds it from what remains (exact unlearning by retraining,
  the baseline that SISA, arXiv:1912.03817, makes cheaper; at a few thousand
  small examples the baseline is cheap enough on its own);
* its size, and the cap it was checked against (small, as the track asks: a
  rank-8 adapter on the 92.9M core is 1.2M parameters, 4.7 MB).
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

ADAPTER_FILE = "adapter.pt"
MANIFEST_FILE = "adapter.json"
MAX_ADAPTER_BYTES = 16 * 2 ** 20


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(8 * 2 ** 20), b""):
            h.update(block)
    return h.hexdigest()


_IDENTITY_CACHE: dict = {}


def base_identity(checkpoint_dir: Path | str) -> dict:
    """What identifies a base: its weights file's sha256 and its tokenizer's fingerprint (cached per file state)."""
    from data import load_tokenizer, tokenizer_fingerprint
    out = Path(checkpoint_dir)
    ckpt, tokf = (out, out.parent / "tokenizer.json") if out.is_file() else (out / "ckpt.pt", out / "tokenizer.json")
    stat = ckpt.stat()
    key = (str(ckpt.resolve()), stat.st_size, stat.st_mtime_ns, tokf.stat().st_mtime_ns)
    if key not in _IDENTITY_CACHE:
        tok = load_tokenizer(tokf)
        _IDENTITY_CACHE[key] = {"ckpt_sha256": file_sha256(ckpt), "tokenizer_fingerprint": tokenizer_fingerprint(tok),
                                "vocab_size": tok.vocab_size}
    return dict(_IDENTITY_CACHE[key])


def adapter_dir(store, identity: dict) -> Path:
    """<person>/adapters/<first 16 hex digits of the base's sha256>/"""
    return store.dir / "adapters" / identity["ckpt_sha256"][:16]


def adapter_bytes(state: dict) -> int:
    return sum(t.numel() * t.element_size() for t in state["tensors"].values())


def save_adapter(state: dict, directory: Path, manifest: dict, max_bytes: int = MAX_ADAPTER_BYTES,
                 fisher: dict | None = None) -> dict:
    """Write adapter.pt (the LoRA tensors, optionally their diagonal Fisher) and adapter.json, atomically.

    Refuses an adapter over max_bytes: the per-person module stays small by rule, not by habit."""
    import torch
    size = adapter_bytes(state)
    if size > max_bytes:
        raise ValueError(f"the adapter is {size} bytes, over the cap of {max_bytes}; lower its rank")
    directory.mkdir(parents=True, exist_ok=True)
    tmp = directory / (ADAPTER_FILE + ".tmp")
    torch.save({"config": state["config"], "tensors": state["tensors"],
                **({"fisher": fisher} if fisher is not None else {})}, tmp)
    manifest = dict(manifest, bytes=size, cap_bytes=max_bytes, adapter_sha256=file_sha256(tmp),
                    saved=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), config=state["config"])
    mtmp = directory / (MANIFEST_FILE + ".tmp")
    mtmp.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, directory / ADAPTER_FILE)
    os.replace(mtmp, directory / MANIFEST_FILE)
    return manifest


def load_manifest(directory: Path) -> dict | None:
    path = Path(directory) / MANIFEST_FILE
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def load_adapter_file(directory: Path) -> dict:
    import torch
    return torch.load(Path(directory) / ADAPTER_FILE, map_location="cpu", weights_only=True)


def status(store, identity: dict) -> dict:
    """Whether this person has an adapter for this base, and whether it may be used.

    {"exists", "fresh", "why", "trained_on", "untrained"}: fresh means every
    example it was trained on is still in the store with the same content, and
    it was made for exactly this base."""
    directory = adapter_dir(store, identity)
    manifest = load_manifest(directory)
    current = store.current_hashes()
    if manifest is None:
        return {"exists": False, "fresh": False, "why": "no adapter yet", "trained_on": 0,
                "untrained": len(current), "dir": str(directory)}
    base = manifest.get("base", {})
    if base.get("ckpt_sha256") != identity["ckpt_sha256"] or \
            base.get("tokenizer_fingerprint") != identity["tokenizer_fingerprint"]:
        return {"exists": True, "fresh": False, "why": "made for another base", "trained_on": 0,
                "untrained": len(current), "dir": str(directory)}
    trained = {e["id"]: e["hash"] for e in manifest.get("examples", [])}
    gone = [i for i, h in trained.items() if current.get(i) != h]
    untrained = sum(1 for i in current if i not in trained)
    if gone:
        return {"exists": True, "fresh": False, "trained_on": len(trained), "untrained": untrained,
                "why": f"{len(gone)} example(s) it learned from were erased or corrected since; the next "
                       f"sleep rebuilds it without them", "dir": str(directory)}
    return {"exists": True, "fresh": True, "why": "", "trained_on": len(trained), "untrained": untrained,
            "dir": str(directory)}


def attach(model, store, identity: dict) -> dict:
    """Put the person's adapter on the model when there is a fresh one for this base; else leave the base.

    Returns status() plus "attached". The base is never modified: the adapter
    sits beside it (model.add_lora) and model.remove_lora takes it off."""
    from model import has_lora, load_lora_state, remove_lora
    st = status(store, identity)
    if has_lora(model):
        remove_lora(model)
    if not st["fresh"]:
        return dict(st, attached=False)
    saved = load_adapter_file(Path(st["dir"]))
    load_lora_state(model, {"config": saved["config"], "tensors": saved["tensors"]})
    device = next(model.parameters()).device
    model.to(device)
    model.eval()
    return dict(st, attached=True)


SLEEP_HINT = "python3 locallm/dawnr_learning sleep <your name> --model <this checkpoint>"


def describe(st: dict) -> str:
    """One sentence for the window about what was attached, and how the next sleep is started."""
    if st.get("attached"):
        more = (f"; {st['untrained']} newer example(s) wait for the next sleep ({SLEEP_HINT})"
                if st.get("untrained") else "")
        return f"Using what it learned from {st['trained_on']} of your examples{more}."
    if st.get("exists"):
        return f"Your adapter is not in use: {st['why']}."
    return f"No adapter yet: it learns from your feedback at the next sleep ({SLEEP_HINT})."
