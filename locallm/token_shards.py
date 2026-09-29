"""A pretraining corpus read from uint16 token shards through memmap: research-side data input.

Lives beside data.py, not in it (2026-09-29): this reader needs numpy, which locallm's shipped
app never installs, and release.py's closure walks every import in a shipped module, deferred
ones included, so a numpy import inside data.py (an entry point of the zip) stopped the build on
every standard-library CI cell. nanoGPT keeps the same memmap get_batch inside its training
script (github.com/karpathy/nanoGPT train.py), on the research side; so does this. Only
train_distributed.py and its test import it, and release.py names it RESEARCH so that if the app
ever reaches it the build stops and says so instead of shipping numpy by accident.

Nothing is copied into memory (2026-09-29, second version): the first version concatenated the
used shards into one RAM array, which the pilot's 0.6 GB slice tolerated and the 16.4B-token
English set (33 GB, once per data-parallel rank) cannot. Every shard stays a memmap, as
nanoGPT's get_batch keeps its train.bin, and a batch draws each window from one shard chosen in
proportion to the shards' used lengths, then an offset inside it, so no window straddles two
shards and the operating system's page cache is all the ranks share.
"""
from __future__ import annotations

from pathlib import Path

import torch


class _Concat:
    """The used shards read as one sequence: length, integer and slice access, no copy."""

    def __init__(self, parts, offset: int = 0, length: int | None = None):
        self.parts = list(parts)
        self.starts, total = [], 0
        for p in self.parts:
            self.starts.append(total)
            total += len(p)
        self.offset = offset
        self.length = total - offset if length is None else length

    def __len__(self) -> int:
        return self.length

    def _locate(self, i: int):
        if i < 0:
            i += self.length
        if not 0 <= i < self.length:
            raise IndexError(i)
        i += self.offset
        for start, part in zip(reversed(self.starts), reversed(self.parts)):
            if i >= start:
                return part, i - start
        raise IndexError(i)

    def __getitem__(self, key):
        import numpy as np
        if isinstance(key, slice):
            start, stop, step = key.indices(self.length)
            return np.array([self[i] for i in range(start, stop, step)], dtype=np.uint16)
        part, j = self._locate(int(key))
        return part[j]


class TokenShards:
    """A pretraining corpus already tokenized into uint16 shard files, read without holding it.

    The contract is Corpus's: `.train` and `.val` with a length, `.train_text` and `.val_text`
    (here the manifest lines the identity digests), and get_batch(split, batch_size, block_size,
    generator) drawing from the trainer's own generator. The used range is the first
    `limit_tokens` of the shards in file order (all when 0); its last `val_tokens` are the
    validation split, which must fit inside the last used shard; the rest is training.
    """

    def __init__(self, paths, val_tokens: int = 1_000_000, limit_tokens: int = 0, device: str = "cpu"):
        import numpy as np
        self.paths = [Path(p) for p in paths]
        if not self.paths:
            raise ValueError("no token shard files")
        if val_tokens < 1:
            raise ValueError("val_tokens must be positive")
        self.shards, total = [], 0
        for path in self.paths:
            arr = np.memmap(path, dtype=np.uint16, mode="r")
            if limit_tokens and total + len(arr) > limit_tokens:
                arr = arr[:limit_tokens - total]
            if len(arr):
                self.shards.append(arr)
                total += len(arr)
            if limit_tokens and total >= limit_tokens:
                break
        if total <= val_tokens:
            raise ValueError(f"{total} tokens in the used range, not enough for {val_tokens} validation tokens")
        if len(self.shards[-1]) <= val_tokens:
            raise ValueError(f"the validation tail ({val_tokens} tokens) must fit inside the last used shard "
                             f"({len(self.shards[-1])} tokens, {self.paths[len(self.shards) - 1].name})")
        self.total = total
        # the training part of each shard: all of it, except the last shard's validation tail
        self.train_lengths = [len(s) for s in self.shards]
        self.train_lengths[-1] -= val_tokens
        self.data = _Concat(self.shards)
        self.train = _Concat(self.shards, 0, total - val_tokens)
        self.val = _Concat(self.shards, total - val_tokens, val_tokens)
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
        """Windows of block_size + 1 tokens: each from one shard, never across two, never across the split."""
        import numpy as np
        if split == "train":
            avail = [n - block_size for n in self.train_lengths]         # windows that fit in each shard's training part
            bases = [0] * len(self.shards)
        else:
            avail = [self.val_tokens - block_size]
            bases = [len(self.shards[-1]) - self.val_tokens]
        if max(avail) < 1:
            raise ValueError(f"{split} split holds too few tokens for block_size {block_size}")
        weights = torch.tensor([max(a, 0) for a in avail], dtype=torch.float64)
        which = torch.multinomial(weights, batch_size, replacement=True, generator=generator)
        offsets = torch.rand(batch_size, generator=generator, dtype=torch.float64)
        rows = []
        for k in range(batch_size):
            i = int(which[k]) if split == "train" else len(self.shards) - 1
            hi = avail[int(which[k])]
            off = bases[int(which[k])] + int(offsets[k] * hi)
            rows.append(np.asarray(self.shards[i][off:off + block_size + 1]).astype(np.int64))
        chunk = torch.from_numpy(np.stack(rows))
        x, y = chunk[:, :-1].contiguous(), chunk[:, 1:].contiguous()
        if self.device != "cpu":
            x, y = x.to(self.device), y.to(self.device)
        return x, y
