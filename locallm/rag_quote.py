"""rag_quote.py: answers from retrieved documents with verified quotes, GopherCite's way (2026-10-01).

    python3 locallm/rag_quote.py run --host H:P[,H:P ...] --data en_int_fresh.json --noise-rate 1.0 --out a.jsonl
    python3 locallm/rag_quote.py report --data en_int_fresh.json --answers a-1.0.jsonl a-0.4.jsonl [--json r.json]

GopherCite (Menick et al., arXiv:2203.11147, 2.1) writes an answer as `%<Claim>%(Document title)%[Quote from
document]%` and holds the quote to be verbatim from the document. Here the base is prompted for that form
(RGB's system prompt, locallm/rag_rgb.py, plus the syntax and one example), the documents are numbered so a
claim can name one, and the check is post hoc. A reply is shown when it parses, every quote is found word for
word in a given document (whitespace folded), and every content word of every claim is in its own quote
(diacritics, case and ordinal suffixes folded; this last rule is ours: GopherCite judges support with
raters and a reward model). Registered in locallm/PREDICT-2026-10-01-retrieval-on-the-base.md (18:10Z).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from locallm import rag_rgb  # noqa: E402

SYNTAX = ("\n\nWrite every answer in this form, and nothing else: %<the answer>%(Document N)%[a sentence copied exactly, "
          "word for word, from Document N that states the answer]%. If the question asks two things, write two of these, "
          "one after the other. For example: %<Frank Marshall>%(Document 2)%[The documentary is directed by Frank "
          "Marshall.]%")
TRIPLE = re.compile(r"%<(.*?)>%\s*\((.*?)\)%\s*\[(.*?)\]%", re.S)
STOP = set("a an the of in on at to for by with and or is was were be been are as from that this it its his her their "
           "he she they we you i which who whom what when where how did does do has have had on about into than then".split())


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"(\d+)(st|nd|rd|th)\b", r"\1", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def words(s: str) -> list[str]:
    return re.findall(r"\w+", fold(s))


def messages(query: str, docs: list[str]) -> list[dict]:
    numbered = "\n\n".join(f"Document {i + 1}:\n{d}" for i, d in enumerate(docs))
    return [{"role": "system", "content": rag_rgb.SYSTEM + SYNTAX},
            {"role": "user", "content": rag_rgb.INSTRUCTION.format(QUERY=query, DOCS=numbered)}]


def parse(reply: str) -> list[tuple[str, str, str]]:
    return [(c.strip(), t.strip(), q.strip()) for c, t, q in TRIPLE.findall(reply or "")]


def verbatim(quote: str, docs: list[str]) -> bool:
    q = re.sub(r"\s+", " ", quote).strip()
    return bool(q) and any(q in re.sub(r"\s+", " ", d) for d in docs)


def supported(claim: str, quote: str) -> bool:
    content = [w for w in words(claim) if w not in STOP]
    have = set(words(quote))
    return bool(content) and all(w in have for w in content)


def verdict(reply: str, docs: list[str]) -> dict:
    """{"parsed", "verbatim", "supported", "shown"} for one reply."""
    if "insufficient information" in (reply or ""):
        return {"parsed": 0, "verbatim": False, "supported": False, "shown": False, "rejected": True}
    t = parse(reply)
    vb = bool(t) and all(verbatim(q, docs) for _c, _n, q in t)
    sp = bool(t) and all(supported(c, q) for c, _n, q in t)
    return {"parsed": len(t), "verbatim": vb, "supported": sp, "shown": bool(t) and vb and sp, "rejected": False}


def cmd_run(a) -> int:
    data = [json.loads(l) for l in Path(a.data).read_text(encoding="utf-8").splitlines() if l.strip()]
    done = set()
    if Path(a.out).exists():
        done = {json.loads(l)["id"] for l in Path(a.out).read_text().splitlines() if l.strip() and not json.loads(l).get("error")}
    todo = [d for d in data if d["id"] not in done]
    hosts = a.host.split(",")

    def worker(k):
        for d in todo[k::len(hosts)]:
            docs = rag_rgb.select(d, a.noise_rate, 5)
            row = {"id": d["id"], "noise_rate": a.noise_rate}
            try:
                row["prediction"] = rag_rgb.ask(hosts[k], messages(d["query"], docs), 512)
            except Exception as e:                                # noqa: BLE001
                row["prediction"], row["error"] = "", f"{type(e).__name__}: {e}"[:300]
            with open(a.out, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    with ThreadPoolExecutor(len(hosts)) as ex:
        list(ex.map(worker, range(len(hosts))))
    return 0


def report(data: dict, rows: list[dict]) -> dict:
    out = {}
    for rate in sorted({r["noise_rate"] for r in rows}):
        rs = [r for r in rows if r["noise_rate"] == rate and not r.get("error")]
        sec = {"replies": len(rs)}
        vs = []
        for r in rs:
            docs = rag_rgb.select(data[r["id"]], rate, 5)
            v = verdict(r["prediction"], docs)
            v["right"] = rag_rgb.right(rag_rgb.label(r["prediction"], data[r["id"]]["answer"]), rate)
            vs.append(v)
        answered = [v for v in vs if not v["rejected"]]
        sec.update({"rejected": len(vs) - len(answered), "in the syntax": sum(1 for v in answered if v["parsed"]),
                    "quotes verbatim": sum(1 for v in answered if v["verbatim"]),
                    "shown": sum(1 for v in answered if v["shown"]), "right": sum(1 for v in vs if v["right"]),
                    "shown and right": sum(1 for v in answered if v["shown"] and v["right"])})
        out[str(rate)] = sec
    return out


def cmd_report(a) -> int:
    data = {json.loads(l)["id"]: json.loads(l) for l in Path(a.data).read_text(encoding="utf-8").splitlines() if l.strip()}
    rows = [json.loads(l) for f in a.answers for l in Path(f).read_text(encoding="utf-8").splitlines() if l.strip()]
    rep = report(data, rows)
    print(json.dumps(rep, indent=1))
    if a.json:
        Path(a.json).write_text(json.dumps(rep, indent=1) + "\n")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--host", required=True); r.add_argument("--data", required=True)
    r.add_argument("--noise-rate", type=float, required=True); r.add_argument("--out", required=True)
    p = sub.add_parser("report")
    p.add_argument("--data", required=True); p.add_argument("--answers", nargs="+", required=True); p.add_argument("--json")
    a = ap.parse_args(argv)
    return {"run": cmd_run, "report": cmd_report}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
