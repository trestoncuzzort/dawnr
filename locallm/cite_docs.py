"""cite_docs.py: answer a question from a person's own files, every claim quoting one of their sentences word for
word, or say the files do not hold the answer (2026-10-02).

    python3 locallm/cite_docs.py --host 127.0.0.1:8712 "QUESTION" FILE [FILE ...]

The files are split into passages of a few sentences, the five that best match the question are picked with BM25
(locallm/dawnr_retrieval/bm25.py), and the base model answers under a grammar built for them
(locallm/rag_cite.py, GopherCite's constrained quoting, arXiv:2203.11147): each claim names one passage and quotes
one of that passage's sentences exactly, or the reply is the refusal sentence. Measured on HotpotQA with the base
at 4 bits on a CPU (locallm/PREDICT-2026-10-01-retrieval-on-the-base.md, outcome 2026-10-02): it refused 286 of 300
questions whose answer was not in its documents and answered 78% of those where it was, at least 79% right. The
quotes are what the person checks; nothing here judges them further (a model judge of support added nothing).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from locallm import doc_read, rag_cite, rag_rgb  # noqa: E402
from locallm.dawnr_retrieval.bm25 import BM25Index  # noqa: E402

# a sentence ends at . ! ? before a capital, a digit or an opening mark; "Harbor Supply Co. until paid" is one sentence
SENTENCE = re.compile(r"(?:(?<=[.!?])|(?<=[.!?][\"'”’)\]]))\s+(?=[A-Z0-9\"'“‘(\[])|\n\s*\n|\n(?=\s*[-*•]\s)")


def sentences(text: str) -> list[str]:
    """A file's sentences, whitespace collapsed (the grammar and the shown text must hold the same string)."""
    out = []
    for part in SENTENCE.split(text):
        s = " ".join(part.split())
        if len(s) >= 3:
            out.append(s[:400])
    return out


def passages(paths: list[Path], size: int = 6) -> list[dict]:
    """[{"title", "sentences"}]: each file in windows of `size` sentences, titled by file name, page (where the
    file has pages) and position. A file is read by locallm/doc_read.py: text in its real encoding, a Word
    document, a saved web page, a PDF through pdftotext; doc_read.Unreadable says why one could not be."""
    out = []
    for p in paths:
        pages, _how = doc_read.read(p)
        for page, text in pages:
            ss = sentences(text)
            where = f"{Path(p).name}, page {page}" if page is not None else Path(p).name
            for i in range(0, len(ss), size):
                out.append({"title": f"{where}, part {i // size + 1}", "sentences": ss[i:i + size]})
    return out


def pick(ps: list[dict], question: str, k: int = 5) -> list[dict]:
    """The k passages BM25 ranks best for the question; none when no passage shares a word with it."""
    index = BM25Index()
    for n, p in enumerate(ps):
        index.add(n, " ".join(p["sentences"]))
    return [ps[n] for n, _score in index.search(question, k)]


def ask(host: str, question: str, docs: list[dict], post=rag_rgb._post) -> str:
    body = {"messages": rag_cite.messages(question, docs), "temperature": 0, "max_tokens": 400,
            "grammar": rag_cite.grammar(docs)}
    return post(f"http://{host}/v1/chat/completions", body)["choices"][0]["message"]["content"] or ""


def render(reply: str, docs: list[dict]) -> str:
    claims = rag_cite.parse(reply)
    if rag_cite.REJECT in reply or not claims:
        return "NOT IN YOUR FILES: none of the passages that best match the question states its answer."
    lines = []
    for claim, k, quote in claims:
        title = docs[k - 1]["title"] if 1 <= k <= len(docs) else f"Document {k}"
        lines += [claim, f'    "{quote}"', f"    ({title})"]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--host", required=True, help="host:port of a llama-server holding the base model")
    ap.add_argument("question")
    ap.add_argument("files", nargs="+", type=Path)
    a = ap.parse_args(argv)
    missing = [str(f) for f in a.files if not f.is_file()]
    if missing:
        print(f"cite: not a file: {', '.join(missing)}", file=sys.stderr)
        return 2
    try:
        docs = pick(passages(a.files), a.question)
    except doc_read.Unreadable as unreadable:
        print(f"cite: {unreadable}.", file=sys.stderr)
        return 2
    if not docs:
        print("NOT IN YOUR FILES: no passage shares a word with the question.")
        return 0
    print(render(ask(a.host, a.question, docs), docs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
