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
import os
from dataclasses import dataclass
from pathlib import Path

from .sources import Passage, _chunks


@dataclass
class FetchedPage:
    url: str
    text: str
    fetched_at: str = ""


def _page(row) -> FetchedPage:
    """Validate a whole snapshot before it can replace the previous page."""
    if not isinstance(row, dict):
        raise ValueError("a fetched page must be a JSON object")
    url, text, fetched_at = row.get("url"), row.get("text"), row.get("fetched_at", "")
    if not isinstance(url, str) or not url.strip():
        raise ValueError("url must be a nonempty string")
    if not isinstance(text, str) or not isinstance(fetched_at, str):
        raise ValueError("text and fetched_at must be strings")
    # Escaped lone surrogates are accepted by json.loads but cannot be emitted
    # as valid UTF-8 when the passage is later displayed or written.
    for value in (url, text, fetched_at):
        value.encode("utf-8")
    return FetchedPage(url, text, fetched_at)


def append_fetched_page(path, url: str, text: str, fetched_at: str = "") -> None:
    """Append one fetched page to the cache at `path`, creating it if needed."""
    row = {"url": url, "text": text, "fetched_at": fetched_at}
    _page(row)
    record = json.dumps(row, ensure_ascii=True).encode("utf-8") + b"\n"
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a+b", buffering=0) as f:
        end = f.seek(0, os.SEEK_END)
        if end:
            f.seek(-1, os.SEEK_END)
            if f.read(1) != b"\n":
                # Keep a torn last record isolated, so it cannot swallow the
                # next complete page. The loader reports the damaged line.
                record = b"\n" + record
        if f.write(record) != len(record):
            raise OSError("incomplete fetched-page cache write")


def load_fetched_cache(path) -> tuple[list["Passage"], list[str]]:
    """(passages, problems) from a JSONL fetched-page cache at `path`. A missing file is not an
    error: it returns ([], [])."""
    p = Path(path)
    passages: list[Passage] = []
    problems: list[str] = []
    try:
        stream = p.open("rb")
    except FileNotFoundError:
        return passages, problems
    latest: dict[str, FetchedPage] = {}
    with stream:
        # Binary iteration recognizes only LF records. str.splitlines also
        # splits U+0085/U+2028/U+2029 inside otherwise valid page text.
        for n, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                page = _page(json.loads(line.decode("utf-8")))
            except (ValueError, TypeError) as e:
                problems.append(f"fetched cache {p}:{n}: {e}")
                continue
            latest[page.url] = page
    # Re-chunk only the newest complete snapshot, so a shorter update cannot
    # inherit obsolete trailing chunks from a longer previous version.
    for page in latest.values():
        for i, chunk in enumerate(_chunks(page.text)):
            passages.append(Passage(id=f"fetched:{page.url}#chunk{i}", kind="fetched", source=page.url,
                                    locator=f"chunk{i}", text=chunk, title=page.url, trust="untrusted",
                                    fetched_at=page.fetched_at))
    return passages, problems
