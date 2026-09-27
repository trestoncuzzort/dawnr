"""cache.py: passages from pages dawnr has already fetched, read back offline. AMBITION.md asks
retrieval to cover "cached fetched pages" alongside the proved corpus and the knowledge folder;
DAWNR-HARNESS.md section 6 (web.py) fetches and returns a page but does not yet persist it anywhere,
so this module defines the on-disk shape and reads it -- dawnr_harness/web.py is a shared file this
track does not edit, so recording a fetch into this cache is the operator's or a future hook's job
(a PostToolUse command hook on web_fetch, or a small script, can call append_fetched_page below);
what matters for this track is that once a page IS recorded, search_knowledge can find it.

Format: a JSON Lines file, one fetched page per line, each object holding at least "url" and
"text"; "fetched_at" is an ISO-8601 timestamp when present. This is exactly the shape
dawnr_harness/web.py's own fetch() dict already has (url, text, ...), so recording one is one
json.dumps call, no translation. A malformed line is skipped and named in `problems` rather than
raising: a person's cache growing over time will eventually hold a partial write from an
interrupted process, and that must not take the rest of the cache down with it.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .sources import Passage, _chunks


@dataclass
class FetchedPage:
    url: str
    text: str
    fetched_at: str = ""


def append_fetched_page(path, url: str, text: str, fetched_at: str = "") -> None:
    """Append one fetched page to the cache at `path`, creating it if needed."""
    row = {"url": url, "text": text, "fetched_at": fetched_at}
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_fetched_cache(path) -> tuple[list["Passage"], list[str]]:
    """(passages, problems) from a JSONL fetched-page cache at `path`. A missing file is not an
    error: it returns ([], [])."""
    p = Path(path)
    passages: list[Passage] = []
    problems: list[str] = []
    if not p.exists():
        return passages, problems
    for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            url, text = row["url"], row["text"]
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            problems.append(f"fetched cache {p}:{n}: {e}")
            continue
        fetched_at = str(row.get("fetched_at", ""))
        for i, chunk in enumerate(_chunks(text)):
            passages.append(Passage(id=f"fetched:{url}#chunk{i}", kind="fetched", source=url, locator=f"chunk{i}",
                                    text=chunk, title=url, trust="untrusted", fetched_at=fetched_at))
    return passages, problems
