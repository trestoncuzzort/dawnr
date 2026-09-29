"""A pretraining corpus read from uint16 token shards through memmap: research-side data input.

Lives beside data.py, not in it (2026-09-29): this reader needs numpy, which locallm's shipped
app never installs, and release.py's closure walks every import in a shipped module, deferred
ones included, so a numpy import inside data.py (an entry point of the zip) stopped the build on
every standard-library CI cell. nanoGPT keeps the same memmap get_batch inside its training
script (github.com/karpathy/nanoGPT train.py), on the research side; so does this. Only
train_distributed.py and its test import it, and release.py names it RESEARCH so that if the app
ever reaches it the build stops and says so instead of shipping numpy by accident.
"""
from __future__ import annotations

from pathlib import Path

import torch


class TokenShards:
    """A pretraining corpus already tokenized into uint16 shard files, read without holding it.

    nanoGPT's design (github.com/karpathy/nanoGPT: data/openwebtext/prepare.py writes uint16
    .bin shards once; train.py's get_batch memmaps them and gathers random windows per batch), so
    a corpus larger than RAM costs no RAM beyond one batch. Why it exists here (2026-09-29):
    `Corpus` tokenizes its text into a Python list of ints before the first step, which for the
    3.4 GB English pilot corpus is 1.17B ints, tens of gigabytes, on a 14 GB desktop; the pilot's
    calibration died in that loading phase. t/dawnr_english_corpus.py had already written the
    corpus as these shards (internal/PRETRAIN-DAWNR-GENERAL.md 7.3); this reads them.

    The contract is Corpus's: `.train` and `.val` with a length, `.train_text` and `.val_text`
    (here the manifest lines the identity digests), and get_batch(split, batch_size, block_size,
    generator) drawing offsets from the trainer's own generator. The used range is the first
    `limit_tokens` of the shards in file order (all when 0); its last `val_tokens` are the
    validation split, the rest training. The concatenated used range is held as one uint16
    array (2 bytes a token: 0.6 GB for the pilot's 300M), not as Python ints.
    """

    def __init__(self, paths, val_tokens: int = 1_000_000, limit_tokens: int = 0, device: str = "cpu"):
        import numpy as np
        self.paths = [Path(p) for p in paths]
        if not self.paths:
            raise ValueError("no token shard files")
        if val_tokens < 1:
            raise ValueError("val_tokens must be positive")
        parts, total = [], 0
        for path in self.paths:
            arr = np.memmap(path, dtype=np.uint16, mode="r")
            if limit_tokens and total + len(arr) > limit_tokens:
                arr = arr[:limit_tokens - total]
            parts.append(np.asarray(arr))
            total += len(arr)
            if limit_tokens and total >= limit_tokens:
                break
        data = np.concatenate(parts) if len(parts) > 1 else np.array(parts[0])
        if len(data) <= val_tokens:
            raise ValueError(f"{len(data)} tokens in the used range, not enough for {val_tokens} validation tokens")
        self.data = data
        self.train = data[:-val_tokens]
        self.val = data[-val_tokens:]
        self.device = device
        self.limit_tokens, self.val_tokens = limit_tokens, val_tokens
        self.train_text = f"token shards, train: {len(self.train)} tokens of {self.manifest(self.paths)}"
        self.val_text = f"token shards, val: the last {len(self.val)} tokens of the used range of {self.manifest(self.paths)}"

    @staticmethod
    def manifest(paths) -> str:
        """The shard files by name, size and sha256, one line each: what the run's identity digests."""
        import hashlib
        lines = []
        for path in paths:
            h = hashlib.sha256()
            with open(path, "rb") as f:
                for block in iter(lambda: f.read(1 << 24), b""):
                    h.update(block)
            lines.append(f"{Path(path).name} {Path(path).stat().st_size} {h.hexdigest()}")
        return "\n".join(lines)

    def get_batch(self, split: str, batch_size: int, block_size: int, generator=None):
        import numpy as np
        d = self.train if split == "train" else self.val
        hi = len(d) - block_size
        if hi < 1:
            raise ValueError(f"{split} split holds {len(d)} tokens but block_size is {block_size}")
        ix = torch.randint(hi, (batch_size,), generator=generator).numpy()
        idx = ix[:, None] + np.arange(block_size + 1)
        chunk = torch.from_numpy(d[idx].astype(np.int64))
        x, y = chunk[:, :-1].contiguous(), chunk[:, 1:].contiguous()
        if self.device != "cpu":
            x, y = x.to(self.device), y.to(self.device)
        return x, y
