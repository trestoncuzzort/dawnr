"""search.py: the fixture web's search engine, run by the harness's `command` search backend.

    python search.py search-index.json "<query>"

dawnr_harness/web.py's CommandBackend runs an operator program with the query
as its last argument and reads a JSON list of {"title", "url", "snippet"}. This
is that program over a committed index of the fixture pages (tool_fixtures.py
writes it): a result's score is three times the query words in its title plus
the query words in its snippet, ties broken by URL, results with no shared word
dropped. Deterministic and offline, so a conversation that searches is
reproducible byte for byte.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

WORD = re.compile(r"[a-z0-9]+")
MAX_RESULTS = 10


def words(text: str) -> set[str]:
    return set(WORD.findall(text.lower()))


def search(index: list[dict], query: str, n: int = MAX_RESULTS) -> list[dict]:
    q = words(query)
    scored = []
    for entry in index:
        score = 3 * len(q & words(entry["title"])) + len(q & words(entry["snippet"]))
        if score:
            scored.append((-score, entry["url"], entry))
    scored.sort(key=lambda s: (s[0], s[1]))
    return [{"title": e["title"], "url": e["url"], "snippet": e["snippet"]} for _, _, e in scored[:n]]


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("usage: search.py search-index.json QUERY", file=sys.stderr)
        return 2
    index = json.loads(Path(argv[0]).read_text(encoding="utf-8"))["results"]
    print(json.dumps(search(index, argv[1]), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
