"""extract_eval.py: how often a field `dawnr extract` fills is right, and how often one that is not in the document
is left empty, beside the schema-only way (2026-10-05).

    python3 locallm/extract_eval.py prep --parquet validation.parquet --out squad2-val.jsonl
    python3 locallm/extract_eval.py run --host H:P[,H:P ...] --data squad2-val.jsonl --out answers.jsonl [--n 300]
    python3 locallm/extract_eval.py report --answers answers.jsonl [--json r.json]

SQuAD 2.0 (Rajpurkar, Jia, Liang, arXiv:1806.03822; CC BY-SA 4.0, kept out of this repository): a paragraph and a
question whose answer is a span of the paragraph, or a question written to look answerable that the paragraph does
not answer. Here the paragraph is the document and the question is a field's description. `--n` answerable and
`--n` unanswerable questions are drawn with a fixed seed. Registered in locallm/PREDICT-2026-10-05-extract.md.

The arms, one model and one temperature (0) for all:

  schema    what a schema-holding deployment does: the reply is held to {"answer": string or null} (llama-server's
            `response_format`, a JSON Schema turned into a grammar), the string free
  located   the schema arm's answers, dropped when they are not in the paragraph word for word (LangExtract's rule,
            github.com/google/langextract: an extraction that cannot be placed in the source is filtered out)
  span      locallm/extract_docs.py: the reply held to NONE or a sentence's number and a run of its own words
  twice     span asked a second time with the sentences listed in reverse; a value is kept only when both replies
            name the same sentence and one run of words contains the other (the shorter is kept)

Scoring is SQuAD's own: exact match and token F1 after its normalisation (lower case, punctuation and articles
removed), against any of the question's gold answers. A value shown for an unanswerable question is wrong.
"""
from __future__ import annotations

import argparse
import collections
import json
import random
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from locallm import cite_docs, extract_docs as ex, rag_cite, rag_rgb  # noqa: E402

SEED = 2026
ARMS = ("schema", "located", "span", "twice")
SCHEMA_SYSTEM = ("You answer a question from a passage. Reply with JSON: {\"answer\": the exact phrase from the passage "
                 "that answers the question, or null if the passage does not state the answer}.")
SCHEMA = {"type": "object", "properties": {"answer": {"type": ["string", "null"]}}, "required": ["answer"]}


def f1(prediction: str, gold: str) -> float:
    """SQuAD's token F1 after its normalisation."""
    p, g = rag_cite.norm(prediction).split(), rag_cite.norm(gold).split()
    common = sum((collections.Counter(p) & collections.Counter(g)).values())
    if not p or not g or not common:
        return float(p == g)
    precision, recall = common / len(p), common / len(g)
    return 2 * precision * recall / (precision + recall)


def score(value: str | None, golds: list[str]) -> dict:
    """{"shown", "em", "f1"} for one question; with no gold answer a shown value scores 0."""
    if value is None:
        return {"shown": False, "em": False, "f1": 0.0}
    return {"shown": True, "em": any(rag_cite.norm(value) == rag_cite.norm(g) for g in golds),
            "f1": max((f1(value, g) for g in golds), default=0.0)}


def sample(rows: list[dict], n: int, seed: int = SEED) -> list[dict]:
    rnd = random.Random(seed)
    yes = sorted((r for r in rows if r["answers"]), key=lambda r: r["id"])
    no = sorted((r for r in rows if not r["answers"]), key=lambda r: r["id"])
    return rnd.sample(yes, min(n, len(yes))) + rnd.sample(no, min(n, len(no)))


def ask_schema(host: str, row: dict, post=rag_rgb._post) -> str | None:
    body = {"messages": [{"role": "system", "content": SCHEMA_SYSTEM},
                         {"role": "user", "content": f"Passage:\n{row['context']}\n\nQuestion:\n{row['question']}"}],
            "temperature": 0, "max_tokens": 120, "response_format": {"type": "json_schema", "json_schema": {"schema": SCHEMA}}}
    reply = post(f"http://{host}/v1/chat/completions", body)["choices"][0]["message"]["content"] or ""
    try:
        answer = json.loads(reply).get("answer")
    except (ValueError, AttributeError):
        return None
    return answer.strip() if isinstance(answer, str) and answer.strip() else None


def ask_span(host: str, row: dict, reverse: bool = False, post=rag_rgb._post) -> tuple[int, str] | None:
    """(sentence number, words) by extract_docs' grammar; `reverse` lists the sentences last first, numbers kept."""
    sentences = cite_docs.sentences(row["context"])
    field = {"name": "answer", "kind": "text", "description": row["question"]}
    listed = list(enumerate(sentences, 1))
    if reverse:
        listed.reverse()
    body = {"messages": [{"role": "system", "content": ex.SYSTEM},
                         {"role": "user", "content": "\n".join(f"S{n}: {s}" for n, s in listed)
                          + f"\n\nField: {field['name']}: {field['description']}"}],
            "temperature": 0, "max_tokens": 120, "grammar": ex.grammar(sentences)}
    return ex.parse(post(f"http://{host}/v1/chat/completions", body)["choices"][0]["message"]["content"] or "", sentences)


def agree(a: tuple[int, str] | None, b: tuple[int, str] | None) -> str | None:
    """The value both replies stand behind: the same sentence, one run of words inside the other; the shorter."""
    if a is None or b is None or a[0] != b[0]:
        return None
    short, long = sorted((a[1], b[1]), key=len)
    return short if short in long else None


def answers(host: str, row: dict, post=rag_rgb._post) -> dict:
    schema = ask_schema(host, row, post)
    span = ask_span(host, row, False, post)
    again = ask_span(host, row, True, post)
    return {"schema": schema, "located": schema if schema is not None and schema in row["context"] else None,
            "span": span[1] if span else None, "twice": agree(span, again)}


def report(rows: list[dict]) -> dict:
    out = {}
    for arm in ARMS:
        yes = [score(r["values"][arm], r["answers"]) for r in rows if r["answers"]]
        no = [score(r["values"][arm], []) for r in rows if not r["answers"]]
        shown = [s for s in yes + no if s["shown"]]
        out[arm] = {
            "answerable": len(yes), "unanswerable": len(no),
            "shown on answerable": sum(s["shown"] for s in yes),
            "exact on answerable": sum(s["em"] for s in yes),
            "f1 on answerable shown": round(sum(s["f1"] for s in yes if s["shown"]) / max(1, sum(s["shown"] for s in yes)), 4),
            "left empty on unanswerable": sum(not s["shown"] for s in no),
            "shown": len(shown), "exact of shown": round(sum(s["em"] for s in shown) / max(1, len(shown)), 4),
            "not in the passage word for word": sum(1 for r in rows if r["values"][arm] is not None and r["values"][arm] not in r["context"]),
        }
    return out


def cmd_prep(a) -> int:
    import pyarrow.parquet as pq                                # the only use of a dependency, and only here
    table = pq.read_table(a.parquet).to_pylist()
    with open(a.out, "w", encoding="utf-8") as f:
        for r in table:
            f.write(json.dumps({"id": r["id"], "context": r["context"], "question": r["question"],
                                "answers": sorted(set(r["answers"]["text"]))}, ensure_ascii=False) + "\n")
    print(f"{len(table)} rows -> {a.out}")
    return 0


def cmd_run(a) -> int:
    rows = sample([json.loads(l) for l in Path(a.data).read_text(encoding="utf-8").splitlines() if l.strip()], a.n)
    done = set()
    if Path(a.out).exists():
        done = {json.loads(l)["id"] for l in Path(a.out).read_text(encoding="utf-8").splitlines() if l.strip()}
    todo = [r for r in rows if r["id"] not in done]
    hosts, lock = a.host.split(","), threading.Lock()

    def worker(k: int) -> None:
        for r in todo[k::len(hosts)]:
            try:
                values = answers(hosts[k], r)
            except Exception as error:                          # noqa: BLE001 -- a failed request is rerun, not scored
                print(f"{r['id']}: {type(error).__name__}: {error}", file=sys.stderr)
                continue
            with lock, open(a.out, "a", encoding="utf-8") as f:
                f.write(json.dumps(dict(r, values=values), ensure_ascii=False) + "\n")
    threads = [threading.Thread(target=worker, args=(k,)) for k in range(len(hosts))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    print(f"{len(rows)} questions, {len(todo)} asked now -> {a.out}")
    return 0


def cmd_report(a) -> int:
    rows = [json.loads(l) for l in Path(a.answers).read_text(encoding="utf-8").splitlines() if l.strip()]
    r = report(rows)
    for arm, v in r.items():
        print(f"{arm:8} answerable: shown {v['shown on answerable']}/{v['answerable']}, exact {v['exact on answerable']}; "
              f"unanswerable left empty {v['left empty on unanswerable']}/{v['unanswerable']}; "
              f"of {v['shown']} shown {100 * v['exact of shown']:.1f}% exact; not word for word {v['not in the passage word for word']}")
    if a.json:
        Path(a.json).write_text(json.dumps(r, indent=1) + "\n", encoding="utf-8")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prep")
    p.add_argument("--parquet", required=True)
    p.add_argument("--out", required=True)
    r = sub.add_parser("run")
    r.add_argument("--host", required=True)
    r.add_argument("--data", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--n", type=int, default=300)
    s = sub.add_parser("report")
    s.add_argument("--answers", required=True)
    s.add_argument("--json")
    a = ap.parse_args(argv)
    return {"prep": cmd_prep, "run": cmd_run, "report": cmd_report}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
