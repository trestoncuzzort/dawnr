"""extract_docs.py: fields out of a person's own files, each value a run of words copied from one of their
sentences, or left empty (2026-10-05).

    python3 locallm/extract_docs.py --host 127.0.0.1:8712 --field "total(number): the amount due" \
        --field "due(date): when payment is due" FILE [FILE ...] [--json OUT.json]

`dawnr extract` is this.

Models that fill a JSON schema are held to the schema's shape by the decoder (llama.cpp turns a JSON Schema into a
grammar); the string inside a field can still be anything. LangExtract (github.com/google/langextract) maps each
extraction back to its place in the source after decoding and marks the ones it cannot place, for the caller to
drop. Here the value cannot be written unless it is in the source: the reply is held, by a grammar built for the
passages (llama-server's `grammar` field, as locallm/rag_cite.py holds a quote to a whole sentence after GopherCite,
arXiv:2203.11147), to `NONE` or `S<n>: <a contiguous run of sentence n's own words>`. So every value shown is a
span of one of the person's sentences, shown with that sentence and its file. A typed field (number, date) is
offered only the runs that read as one, so it is of its type and in the source by construction, where a schema
gives the type and nothing about the source. Research receipt f949bfc4e047.

What this does not check is that the span is the right one for the field: the sentence is printed beside the value
so that a glance settles it, and how often the span is right, and how often a field that is not in the document is
left empty, is measured on SQuAD 2.0 (arXiv:1806.03822; locallm/PREDICT-2026-10-05-extract.md).

Measured the day it was written, and changed by it twice (X1 to X9 of that file; two samples of 300 answerable
and 300 unanswerable questions). Held to a run of a sentence's words, the model quoted the whole sentence where two
words were the value: 165 and 154 of 300 answerable exact, against 227 and 235 when it wrote a short answer freely
under a JSON Schema. So a text field is read twice. Once freely, under a schema, for the value. Once under the
grammar above, for the sentence. The value is shown only when its words are in the document as words and inside
the sentence the second reading named (`held`). The first build of that rule also rearranged both prompts so that
the server would read the document once, and the rearranged free reading filled in 148 of 300 absent fields where
the measured one filled in 83; the prompts are therefore the measured ones again, word for word (`VALUE_SYSTEM` and
`value_messages` are the schema arm's, `SYSTEM` and `messages` the span arm's) and the document is read once for
each kind of reading. Measured so, on 600 questions it had not seen (X10 to X13): 340 values shown, 65.9% exactly
right, 230 of 300 absent fields left empty, nothing shown that is not in the document; the schema alone 378,
64.5%, 215, and 9 values not in the document as words. A number or a date keeps the grammar of typed runs, which
are short by construction, and is not measured.

A short document is read whole, so the model reads it once for all fields; a long one is cut to the passages BM25
ranks best for each field (locallm/dawnr_retrieval/bm25.py).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from locallm import cite_docs, doc_read, rag_cite, rag_rgb  # noqa: E402
from locallm.dawnr_retrieval.bm25 import UNSPACED, tokenize_any  # noqa: E402

NONE = "NONE"
SYSTEM = ("You fill in one field from the numbered sentences of a document. Reply with the number of the sentence that "
          "states the field's value, then the exact words of that sentence that are the value and nothing more, like "
          "`S3: 4417`. If no sentence states it, reply " + NONE + ".")
# the free reading's prompt and schema, word for word what was measured as the `schema` arm (locallm/extract_eval.py)
VALUE_SYSTEM = ("You answer a question from a passage. Reply with JSON: {\"answer\": the exact phrase from the passage "
                "that answers the question, or null if the passage does not state the answer}.")
VALUE_SCHEMA = {"type": "object", "properties": {"answer": {"type": ["string", "null"]}}, "required": ["answer"]}
WHOLE = 40                     # a document of at most this many sentences is read whole
# a piece: a character of a script written without spaces (Han, kana, Hangul, Thai: any run of characters can be a
# value there), else a word or number whole, else one other mark
_SPACED = f"[^\\W{UNSPACED}]"
PIECE = re.compile(f"[{UNSPACED}]|{_SPACED}+(?:[.,'’:/-]{_SPACED}+)*|[^\\w\\s]")
REPLY = re.compile(r"S(\d+): (.+)", re.S)
FIELD = re.compile(r"\s*([^\W\d][\w -]*?)\s*(?:\((number|date|text)\))?\s*(?:[:：]\s*(.*))?$", re.S)     # a name in any script
NUMBER = re.compile(r"-?\d[\d.,]*\d|-?\d")                  # a numeric piece: digits, with separators only inside
# The two ways a number is written. 1,250.00 is English and 1.250,00 continental; 1.250 and 1,250 can be either.
_ENGLISH = re.compile(r"-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?")
_CONTINENTAL = re.compile(r"-?(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?")
_SURELY_CONTINENTAL = re.compile(r"-?(?:\d{1,3}(?:\.\d{3})+,\d+|\d+,\d{2})")     # both separators, or a comma and two decimals
_SURELY_ENGLISH = re.compile(r"-?(?:\d{1,3}(?:,\d{3})+\.\d+|\d+\.\d{1,2})")
_DATES = ("%Y-%m-%d", "%d %B %Y", "%B %d, %Y", "%B %d %Y", "%d %b %Y", "%b %d, %Y", "%b %d %Y", "%B %Y")
_NUMERIC_DATE = re.compile(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})")


def read_field(text: str) -> dict:
    """`name: what it is`, `name(number): ...` or `name(date): ...` as {"name", "kind", "description"}."""
    m = FIELD.match(text)
    if not m:
        raise ValueError(f"a field is written `name: what it is` or `name(number): what it is`; got {text!r}")
    name = m.group(1).strip()
    return {"name": name, "kind": m.group(2) or "text", "description": (m.group(3) or name).strip()}


def pieces(sentence: str) -> list[tuple[str, bool]]:
    """The sentence as (piece, whether a space stands before it): words and numbers whole, other marks alone, so that
    any contiguous run of pieces, joined as the sentence spaces them, is a substring of the sentence."""
    out, end = [], 0
    for m in PIECE.finditer(sentence):
        out.append((m.group(0), m.start() > end))
        end = m.end()
    return out


def runs(sentence: str, longest: int = 7) -> list[str]:
    """Every contiguous run of at most `longest` pieces, as the sentence spaces it."""
    ps, out = pieces(sentence), []
    for i in range(len(ps)):
        text = ""
        for j in range(i, min(len(ps), i + longest)):
            text += (" " if ps[j][1] and j > i else "") + ps[j][0]
            out.append(text)
    return out


def read_number(text: str) -> tuple[Fraction | None, Fraction | None]:
    """(the English reading, the continental reading) of a numeric piece, None where it is not written that way:
    `1,250.00` is (1250, None), `1.250,00` is (None, 1250), `1.250` is (1.25, 1250), `1,2,3` is (None, None)."""
    english = Fraction(text.replace(",", "")) if _ENGLISH.fullmatch(text) else None
    continental = Fraction(text.replace(".", "").replace(",", ".")) if _CONTINENTAL.fullmatch(text) else None
    return english, continental


def convention(sentences: list[str]) -> str:
    """How the document writes numbers: `continental` when it has a number that can only be continental and of a
    sure kind (`1.250,00`, `12,50`) and none that is surely English (`1,250.00`, `12.5`); `mixed` when it has both;
    else `english`, which is also how a number is read when nothing in the document decides."""
    seen = {p for s in sentences for p, _ in pieces(s) if p[0].isdigit() or p[0] == "-"}
    continental = any(_SURELY_CONTINENTAL.fullmatch(p) for p in seen)
    english = any(_SURELY_ENGLISH.fullmatch(p) for p in seen)
    return "mixed" if continental and english else "continental" if continental else "english"


def typed_spans(kind: str, sentence: str) -> list[str]:
    """The runs of the sentence that read as the field's kind, the longest reading of each place only: for a number
    its own piece (`1,250.00`, not `$1,250.00, payable`), for a date the whole date (`March 3, 2026`, not `3, 2026`)."""
    if kind == "number":
        return list(dict.fromkeys(p for p, _ in pieces(sentence) if NUMBER.fullmatch(p) and read_number(p) != (None, None)))
    good = [r for r in runs(sentence) if r[0].isalnum() and r[-1].isalnum() and typed(kind, r)[1] is None]
    return [r for r in good if not any(r != other and r in other for other in good)]


def grammar(sentences: list[str], kind: str = "text") -> str:
    """root: NONE, or `S<n>: ` and a contiguous run of sentence n's pieces. For a number or a date the runs offered
    are only those that read as one (typed_spans), so a typed field is of its type and in the source by construction;
    a sentence with none is not offered."""
    lines, picks = [], []
    for n, sentence in enumerate(sentences, 1):
        if kind != "text":
            spans = typed_spans(kind, sentence)
            if spans:
                picks.append(f"s{n}")
                lines.append(f's{n} ::= "S{n}: " ( ' + " | ".join(rag_cite.gbnf_string(x) for x in spans) + " )")
            continue
        ps = pieces(sentence)
        if not ps:
            continue
        picks.append(f"s{n}")
        lines.append(f's{n} ::= "S{n}: " ( ' + " | ".join(f"s{n}p{i}" for i in range(len(ps))) + " )")
        for i, (text, _spaced) in enumerate(ps):
            rule = f"s{n}p{i} ::= {rag_cite.gbnf_string(text)}"
            if i + 1 < len(ps):
                rule += " ( " + ('" " ' if ps[i + 1][1] else "") + f"s{n}p{i + 1} )?"
            lines.append(rule)
    return "\n".join([f'root ::= "{NONE}"' + "".join(f" | {p}" for p in picks)] + lines) + "\n"


def messages(field: dict, sentences: list[str]) -> list[dict]:
    body = "\n".join(f"S{n}: {s}" for n, s in enumerate(sentences, 1))
    return [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"{body}\n\nField: {field['name']}: {field['description']}"}]


def value_messages(field: dict, sentences: list[str]) -> list[dict]:
    """The free reading's prompt: the sentences as one passage, and what the field is as the question."""
    return [{"role": "system", "content": VALUE_SYSTEM},
            {"role": "user", "content": f"Passage:\n{' '.join(sentences)}\n\nQuestion:\n{field['description']}"}]


def parse(reply: str, sentences: list[str]) -> tuple[int, str] | None:
    """(sentence number, the words) when the reply names a sentence and a run of words that is in it, else None.
    The grammar already holds the reply to that; a server that ignored the grammar is caught here."""
    m = REPLY.match((reply or "").strip())
    if not m:
        return None
    n, words = int(m.group(1)), m.group(2).strip()
    if not (1 <= n <= len(sentences)) or not words or words not in sentences[n - 1]:
        return None
    return n, words


def typed(kind: str, words: str, numbers: str = "english") -> tuple[object, str | None]:
    """(the value in the field's kind, None), or (None, why the words do not read as that kind). `numbers` is the
    document's `convention`: it decides a number that can be read two ways (`1.250`), and where the document
    writes numbers both ways such a number is not taken."""
    if kind == "number":
        m = NUMBER.search(words)
        if not m:
            return None, "the words picked hold no number"
        english, continental = read_number(m.group(0))
        if english is None and continental is None:
            return None, "the number is not written in a way that can be read"
        if english is not None and continental is not None and english != continental and numbers == "mixed":
            return None, f"the number can be read as {show(english)} or as {show(continental)}, and the document writes numbers both ways"
        if english is None or (numbers == "continental" and continental is not None):
            x, decimal = continental, "," in m.group(0)
        else:
            x, decimal = english, "." in m.group(0)
        return (float(x) if decimal else int(x)), None
    if kind == "date":
        text = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", words.strip().rstrip(".,"))
        for form in _DATES:
            try:
                return datetime.strptime(text, form).strftime("%Y-%m-%d" if "%d" in form else "%Y-%m"), None
            except ValueError:
                continue
        m = _NUMERIC_DATE.fullmatch(text)
        if m:
            a, b, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if a > 12 >= b:
                return f"{year:04d}-{b:02d}-{a:02d}", None
            if b > 12 >= a:
                return f"{year:04d}-{a:02d}-{b:02d}", None
            if a == b and a <= 12:
                return f"{year:04d}-{a:02d}-{b:02d}", None
            return None, "the date can be read day first or month first"
        return None, "the words picked do not read as a date"
    return words, None


def located(paths: list[Path]) -> list[dict]:
    """Every sentence of the files: {"file", "n" (its number in that file), "text", "page" where the file has pages}.
    A file is read by locallm/doc_read.py (text in its real encoding, Word, a saved web page, a PDF through
    pdftotext); doc_read.Unreadable says why one could not be."""
    out = []
    for p in paths:
        pages, _how = doc_read.read(p)
        n = 0
        for page, text in pages:
            for s in cite_docs.sentences(text):
                n += 1
                out.append({"file": Path(p).name, "n": n, "text": s, **({"page": page} if page is not None else {})})
    return out


def candidates(sentences: list[dict], field: dict, whole: int = WHOLE, k: int = 5, size: int = 6) -> list[dict]:
    """The sentences the model is shown for a field: all of a short document, else the windows BM25 ranks best."""
    if len(sentences) <= whole:
        return sentences
    from locallm.dawnr_retrieval.bm25 import BM25Index
    index, windows = BM25Index(tokenizer=tokenize_any), [sentences[i:i + size] for i in range(0, len(sentences), size)]
    for n, w in enumerate(windows):
        index.add(n, " ".join(s["text"] for s in w))
    picked = sorted(n for n, _score in index.search(f"{field['name']} {field['description']}", k))
    return [s for n in picked for s in windows[n]]


def ask(host: str, field: dict, texts: list[str], post=rag_rgb._post) -> str:
    g = grammar(texts, field["kind"])
    if g.startswith(f'root ::= "{NONE}"\n'):                    # nothing of the field's kind anywhere: no model is asked
        return NONE
    body = {"messages": messages(field, texts), "temperature": 0, "max_tokens": 120, "grammar": g}
    return post(f"http://{host}/v1/chat/completions", body)["choices"][0]["message"]["content"] or ""


def ask_value(host: str, field: dict, texts: list[str], post=rag_rgb._post) -> str | None:
    """The free reading: the value in as few words as state it, held only to a JSON Schema; None for null or a reply
    that is not that JSON."""
    body = {"messages": value_messages(field, texts), "temperature": 0, "max_tokens": 120,
            "response_format": {"type": "json_schema", "json_schema": {"schema": VALUE_SCHEMA}}}
    reply = post(f"http://{host}/v1/chat/completions", body)["choices"][0]["message"]["content"] or ""
    try:
        value = json.loads(reply).get("answer")
    except (ValueError, AttributeError):
        return None
    return " ".join(value.split()) if isinstance(value, str) and value.strip() else None


def show(x: Fraction) -> str:
    return str(x.numerator) if x.denominator == 1 else str(float(x))


def stated_in(value: str, sentence: str) -> bool:
    """Whether the words are in the sentence as words: `art` is not in `party`, `12` is not in `2012`. An edge of
    the value in a script written without spaces has no word boundary to respect, nor has an edge beside one."""
    if not value:
        return False
    before = f"(?<!{_SPACED})" if re.match(_SPACED, value[0]) else ""
    after = f"(?!{_SPACED})" if re.match(_SPACED, value[-1]) else ""
    return re.search(before + re.escape(value) + after, sentence) is not None


def held(value: str | None, named: tuple[int, str] | None, texts: list[str]) -> tuple[int, str] | str:
    """The rule for a text field, given its two readings: (sentence number, the value's words), or why the value is
    not taken. `value` is the free reading; `named` is the grammar-held reading, of which only the sentence is used."""
    if value is None:
        return "no sentence shown states it"
    holders = [n for n, s in enumerate(texts, 1) if stated_in(value, s)]
    if not holders:
        return "the words given for it are not in the document"
    if named is None:
        return "a second reading found no sentence that states it"
    if named[0] not in holders:
        return "two readings put it in different sentences"
    return named[0], value


def extract(host: str, fields: list[dict], sentences: list[dict], post=rag_rgb._post) -> list[dict]:
    """One row a field: {"name", "kind", "value", "words", "sentence", "file", "n"} or {"name", "kind", "value": None, "why"}.
    Every text field's free reading is asked first and the grammar-held readings after, so that the server, which
    keeps the prompt it last read, reads the document once for each kind of reading and not once a field."""
    shown = [candidates(sentences, field) for field in fields]
    texts = [[s["text"] for s in ss] for ss in shown]
    numbers = convention([s["text"] for s in sentences])
    free = {i: ask_value(host, field, texts[i], post) for i, field in enumerate(fields) if field["kind"] == "text" and shown[i]}
    rows = []
    for i, field in enumerate(fields):
        row = {"name": field["name"], "kind": field["kind"], "value": None}
        if not shown[i]:
            rows.append(dict(row, why="no passage shares a word with the field"))
            continue
        if field["kind"] == "text":
            asked = free[i] is not None and any(stated_in(free[i], s) for s in texts[i])   # else `held` needs no second reading
            found = held(free[i], parse(ask(host, field, texts[i], post), texts[i]) if asked else None, texts[i])
        else:
            found = parse(ask(host, field, texts[i], post), texts[i]) or "no sentence shown states it"
        if isinstance(found, str):
            rows.append(dict(row, why=found))
            continue
        n, words = found
        value, why = typed(field["kind"], words, numbers)
        source = shown[i][n - 1]
        row.update(words=words, sentence=source["text"], file=source["file"], n=source["n"], **({"page": source["page"]} if "page" in source else {}))
        rows.append(dict(row, value=value) if why is None else dict(row, why=why))
    return rows


def render(rows: list[dict]) -> str:
    width = max((len(r["name"]) for r in rows), default=0)
    lines = []
    for r in rows:
        if r["value"] is None and "sentence" not in r:
            lines.append(f"{r['name']:<{width}}  NOT STATED: {r['why']}.")
            continue
        head = r["value"] if r["value"] is not None else f"NOT TAKEN: {r['why']} (\"{r['words']}\")"
        where = f"{r['file']}, " + (f"page {r['page']}, " if "page" in r else "") + f"sentence {r['n']}"
        lines += [f"{r['name']:<{width}}  {head}", f"{'':<{width}}      \"{r['sentence']}\" ({where})"]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--host", required=True, help="host:port of a llama-server holding the base model")
    ap.add_argument("--field", action="append", default=[], required=True,
                    help="`name: what it is`, `name(number): ...` or `name(date): ...`; repeat")
    ap.add_argument("--json", type=Path, help="write the rows here as JSON")
    ap.add_argument("files", nargs="+", type=Path)
    a = ap.parse_intermixed_args(argv)                          # files and --field in any order
    missing = [str(f) for f in a.files if not f.is_file()]
    if missing:
        print(f"extract: not a file: {', '.join(missing)}", file=sys.stderr)
        return 2
    try:
        fields = [read_field(f) for f in a.field]
    except ValueError as error:
        print(f"extract: {error}", file=sys.stderr)
        return 2
    try:
        sentences = located(a.files)
    except doc_read.Unreadable as unreadable:
        print(f"extract: {unreadable}.", file=sys.stderr)
        return 2
    try:
        rows = extract(a.host, fields, sentences)
    except OSError as error:
        print(f"extract: the model server at {a.host} did not answer ({error}).", file=sys.stderr)
        return 2
    print(render(rows))
    if a.json:
        a.json.write_text(json.dumps({"fields": rows}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
