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
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from locallm import doc_read, rag_cite, rag_rgb  # noqa: E402
from locallm.dawnr_retrieval.bm25 import BM25Index, tokenize_any  # noqa: E402

# Where a sentence ends: a profile of Unicode's default rules (UAX #29, section 5.1; research receipt 6d3963f1027c).
#  - After . ! ? and following whitespace, when the next character can open a sentence: for ASCII a capital, a digit
#    or an opening mark, which is the whole rule every measurement of cite and extract ran with ("Harbor Supply Co.
#    until paid" is one sentence); beyond ASCII, read by Unicode category, any uppercase letter, any letter of a
#    script without case (Arabic, Hebrew, Devanagari, Han, kana, Thai), a digit, an opening mark.
#  - Right after a sentence terminal of another script (the ideographic full stop, the danda, the Arabic question
#    mark and the rest of Sentence_Break=STerm, and the fullwidth full stop), whitespace or not.
#  - At an empty line, and before a list item.
#  - Not between the day and the month of a date written `3. März 2026` (a day's number, a full stop, a capitalised
#    word, a year), the one case of a full stop inside a sentence that needs no word list.
# Not in the profile: per-language abbreviation lists (PySBD, arXiv:2010.09657), so German `Nr. 2291` still breaks
# after the full stop.
TERMINALS = ("\u0589\u061d\u061e\u061f\u06d4\u0700\u0701\u0702\u07f9\u0964\u0965\u104a\u104b\u1362\u1367\u1368\u166e\u17d4\u17d5"
             "\u1803\u1809\u203c\u203d\u2047\u2048\u2049\u3002\ua4ff\ua60e\ua60f\ufe52\ufe56\ufe57\uff01\uff0e\uff1f\uff61")
CLOSERS = "\"'”’)\\]」』）】》〉"
_AFTER = re.compile(r"(?:(?<=[.!?])|(?<=[.!?][\"'”’)\]»›」』）】》〉]))\s+")
_HARD = re.compile(f"(?<=[{TERMINALS}])(?![{TERMINALS}{CLOSERS}])\\s*|(?<=[{TERMINALS}][{CLOSERS}])(?![{TERMINALS}{CLOSERS}])\\s*"
                   r"|\n\s*\n|\n(?=\s*[-*•]\s)")
_ASCII_OPENS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789\"'([")
_DAY = re.compile(r"(?<![\w.])\d{1,2}\.$")                    # what a block ends on before the break
_MONTH_YEAR = re.compile(r"[^\W\d_]+\.? \d{4}(?!\d)")         # what follows it
LONGEST = 400                  # characters; a longer sentence is cut, at a clause mark or a space where there is one
_CLAUSE = ";:,،、，；："


def _opens(ch: str) -> bool:
    """Whether a sentence can start with this character (see the profile above)."""
    if ch.isascii():
        return ch in _ASCII_OPENS
    return unicodedata.category(ch) in ("Lu", "Lt", "Lo", "Nd", "Ps", "Pi") or ch in "¿¡"


def _fit(s: str) -> list[str]:
    """A sentence in pieces of at most LONGEST characters, cut after the last clause mark in the second half of
    what fits, else at the last space there, else at the limit. Nothing is dropped."""
    out = []
    while len(s) > LONGEST:
        window = s[:LONGEST]
        at = max(window.rfind(c) for c in _CLAUSE)
        if at < LONGEST // 2:
            at = window.rfind(" ")
        cut = at + 1 if at >= LONGEST // 2 else LONGEST
        out.append(s[:cut].strip())
        s = s[cut:].strip()
    return out + [s]


def sentences(text: str) -> list[str]:
    """A file's sentences, whitespace collapsed (the grammar and the shown text must hold the same string). All of
    the text is in them: a sentence longer than LONGEST characters comes back as several."""
    parts = []
    for block in _HARD.split(text):
        start = 0
        for m in _AFTER.finditer(block):
            if m.end() < len(block) and _opens(block[m.end()]):
                if _DAY.search(block[start:m.start()]) and _MONTH_YEAR.match(block, m.end()):
                    continue
                parts.append(block[start:m.start()])
                start = m.end()
        parts.append(block[start:])
    out = []
    for part in parts:
        s = " ".join(part.split())
        out += [piece for piece in _fit(s) if len(piece) >= 3] if len(s) >= 3 else []
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
    index = BM25Index(tokenizer=tokenize_any)
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
    try:
        reply = ask(a.host, a.question, docs)
    except OSError as error:
        print(f"cite: the model server at {a.host} did not answer ({error}).", file=sys.stderr)
        return 2
    print(render(reply, docs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
