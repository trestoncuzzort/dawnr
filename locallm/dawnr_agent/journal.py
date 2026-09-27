"""journal.py: every change the agent makes to a file, and the bytes it replaced, so each change can be undone.

Before a file is overwritten or edited, its old bytes are kept in the agent's
state directory under their SHA-256 (content-addressed, so an unchanged file
kept twice costs nothing), and one line is appended to journal.jsonl: the
change's id, the root and path, what was done, the hash before and after.
Undo restores the bytes a change replaced, or removes a file the change
created, and only when the file is still exactly what that change left
(its hash after): an undo never clobbers a later change, the agent's or the
person's. The undo itself is journaled, so it can be undone too.

The journal is the person's record, not the model's: it lives in the state
directory, which the agent protects from its own writes, and each line is one
JSON object with every non-ASCII character escaped (the harness audit log's
rule: a raw U+2028 must not split a record for a line-based reader).
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from pathlib import Path


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class JournalError(ValueError):
    pass


class Journal:
    def __init__(self, state_dir: str | Path):
        self.dir = Path(state_dir)
        self.backups = self.dir / "backups"
        self.path = self.dir / "journal.jsonl"

    def ensure(self) -> None:
        self.backups.mkdir(parents=True, exist_ok=True, mode=0o700)

    def keep(self, data: bytes) -> str:
        """Store bytes under their hash (once); return the hash."""
        self.ensure()
        digest = sha256(data)
        final = self.backups / digest
        if final.exists():
            return digest
        tmp = self.backups / f".{digest}.{uuid.uuid4().hex[:8]}.tmp"
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, final)
        return digest

    def backup(self, digest: str) -> bytes:
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise JournalError(f"not a backup id: {digest!r}")
        try:
            data = (self.backups / digest).read_bytes()
        except OSError as e:
            raise JournalError(f"backup {digest[:12]} is missing: {e.strerror}") from None
        if sha256(data) != digest:
            raise JournalError(f"backup {digest[:12]} does not match its hash; not restored")
        return data

    def record(self, **entry) -> str:
        self.ensure()
        change = "c-" + uuid.uuid4().hex[:10]
        row = {"id": change, "time": round(time.time(), 3), **entry}
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")
        return change

    def entries(self) -> list[dict]:
        try:
            text = self.path.read_text(encoding="utf-8")
        except OSError:
            return []
        out = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict) and isinstance(row.get("id"), str):
                out.append(row)
        return out

    def find(self, change: str) -> dict | None:
        for row in self.entries():
            if row["id"] == change:
                return row
        return None
