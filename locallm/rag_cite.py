"""rag_cite.py: answers from documents that must quote their source, the quotes forced to be verbatim by the
decoder (2026-10-02).

    python3 locallm/rag_cite.py run --host H:P[,H:P ...] --data hotpot.jsonl --out answers.jsonl [--n 300]
    python3 locallm/rag_cite.py score --weights alignscore-large.safetensors --answers answers.jsonl --out scores.jsonl
    python3 locallm/rag_cite.py report --answers answers.jsonl --scores scores.jsonl [--json r.json]

GopherCite (Menick et al., arXiv:2203.11147, 2.1): an answer is written `%<Claim>%(Document title)%[Quote]%`, and
"constrained sampling ensures that the model quotes are verbatim from the claimed source". Here the constraint is a
grammar built for each question (llama.cpp's GBNF, sent in llama-server's `grammar` field): a claim citing Document
k can only quote one of Document k's own sentences, or the reply is RGB's refusal sentence (locallm/rag_rgb.py).
GopherCite judged support with raters and a reward model; here each claim must be supported by the one sentence it
quotes, by AlignScore (arXiv:2305.16739; locallm/rag_gate.py), at 0.5.

Questions: HotpotQA's distractor setting (Yang et al., arXiv:1809.09600; CC-BY-SA-4.0, used for evaluation only),
whose paragraphs come split into sentences. Each question is asked twice, with five documents: "present" holds its
two gold paragraphs and three of its distractors, "absent" five distractors on the same topics and no gold one.
Only bridge questions, with no yes/no answers: a comparison question names both candidates, so its gold answer
appears in a wrong reply's claims too. Greedy decoding.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import string
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from locallm import rag_rgb  # noqa: E402

REJECT = "I can not answer the question because of the insufficient information in documents."
SYSTEM = ("You answer questions using only the documents given. Write each answer as %<the answer>%(Document N)%[a "
          "sentence copied from Document N that states it]%. If the question needs two facts, write two such claims. "
          "If no document states the answer, write: " + REJECT)
TRIPLE = re.compile(r"%<(.*?)>%\(Document (\d+)\)%\[(.*?)\]%", re.S)
SEED = 2026


def norm(s: str) -> str:
    """HotpotQA's normalize_answer: lower case, no punctuation, no articles, single spaces."""
    s = s.lower()
    s = "".join(ch for ch in s if ch not in set(string.punctuation))
    s = re.sub(r"\b(a|an|the)\b", " ", s)
    return " ".join(s.split())


def documents(row: dict, condition: str, seed: int = SEED) -> list[dict]:
    """Five documents ({"title", "sentences"}): the two gold paragraphs and three distractors, or five distractors."""
    titles, sents = row["context"]["title"], row["context"]["sentences"]
    gold = set(row["supporting_facts"]["title"])
    paras = [{"title": t, "sentences": [x.strip() for x in s if x.strip()]} for t, s in zip(titles, sents)]
    golds = [p for p in paras if p["title"] in gold]
    others = [p for p in paras if p["title"] not in gold and p["sentences"]]
    rnd = random.Random(f"{seed}:{row['id']}:{condition}")
    picked = (golds + others[:3]) if condition == "present" else others[:5]
    rnd.shuffle(picked)
    return picked


def gbnf_string(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'


def grammar(docs: list[dict]) -> str:
    """root: the refusal, or one or two claims; a claim citing Document k quotes one of Document k's sentences."""
    lines = ['root ::= reject | claims', 'reject ::= ' + gbnf_string(REJECT), 'claims ::= claim (" " claim)?',
             'claim ::= "%<" text ">%" cite', 'text ::= [^<>%\\n]{1,160}',
             'cite ::= ' + " | ".join(f"c{k}" for k in range(1, len(docs) + 1))]
    for k, d in enumerate(docs, 1):
        alts = " | ".join(gbnf_string(s) for s in d["sentences"])
        lines.append(f'c{k} ::= "(Document {k})%[" ( {alts} ) "]%"')
    return "\n".join(lines) + "\n"


def messages(question: str, docs: list[dict]) -> list[dict]:
    body = "\n\n".join(f"Document {k} ({d['title']}):\n" + " ".join(d["sentences"]) for k, d in enumerate(docs, 1))
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"{body}\n\nQuestion:\n{question}"}]


def parse(reply: str) -> list[tuple[str, int, str]]:
    return [(c.strip(), int(k), q.strip()) for c, k, q in TRIPLE.findall(reply or "")]


def right(reply: str, answer: str) -> bool:
    """The gold answer, normalised, appears in one of the claims (or in the reply when it is not in the syntax)."""
    claims = [c for c, _k, _q in parse(reply)] or [reply]
    a = norm(answer)
    return bool(a) and any(a in norm(c) for c in claims)


def sample(rows: list[dict], n: int, seed: int = SEED) -> list[dict]:
    # bridge questions only: a comparison question names both candidates, so the gold answer appears in a wrong
    # reply's claims too and containment cannot score it (found on the first probe, 2026-10-02)
    pool = [r for r in rows if r["type"] == "bridge" and r["answer"].strip().lower() not in ("yes", "no")]
    return sorted(random.Random(seed).sample(pool, min(n, len(pool))), key=lambda r: r["id"])


def cmd_run(a) -> int:
    rows = sample([json.loads(l) for l in Path(a.data).read_text().splitlines() if l.strip()], a.n)
    done = set()
    if Path(a.out).exists():
        done = {(r["id"], r["condition"]) for r in map(json.loads, Path(a.out).read_text().splitlines()) if r and not r.get("error")}
    todo = [(r, c) for r in rows for c in ("present", "absent") if (r["id"], c) not in done]
    hosts = a.host.split(",")

    def worker(k):
        for r, c in todo[k::len(hosts)]:
            docs = documents(r, c)
            row = {"id": r["id"], "condition": c, "question": r["question"], "answer": r["answer"], "docs": docs}
            try:
                body = {"messages": messages(r["question"], docs), "temperature": 0, "max_tokens": 400, "grammar": grammar(docs)}
                row["reply"] = rag_rgb._post(f"http://{hosts[k]}/v1/chat/completions", body)["choices"][0]["message"]["content"] or ""
            except Exception as e:                                # noqa: BLE001
                row["reply"], row["error"] = "", f"{type(e).__name__}: {e}"[:300]
            with open(a.out, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    with ThreadPoolExecutor(len(hosts)) as ex:
        list(ex.map(worker, range(len(hosts))))
    return 0


def cmd_score(a) -> int:
    from locallm import rag_gate
    align = rag_gate.Aligner(Path(a.weights), base=a.base)
    done = set()
    if Path(a.out).exists():
        done = {(r["id"], r["condition"]) for r in map(json.loads, Path(a.out).read_text().splitlines()) if r}
    with open(a.out, "a", encoding="utf-8") as f:
        for r in map(json.loads, Path(a.answers).read_text().splitlines()):
            if not r or r.get("error") or (r["id"], r["condition"]) in done:
                continue
            claims = parse(r["reply"])
            scores = [align([q], [c])[0] for c, _k, q in claims]
            f.write(json.dumps({"id": r["id"], "condition": r["condition"], "claim_support": scores}) + "\n"); f.flush()
    return 0


def report(rows: list[dict], scores: dict, threshold: float = 0.5) -> dict:
    out = {}
    for cond in ("present", "absent"):
        rs = [r for r in rows if r["condition"] == cond and not r.get("error")]
        refused = [r for r in rs if REJECT in r["reply"]]
        answered = [r for r in rs if r not in refused]
        def shown(r, t):
            s = scores.get((r["id"], cond)) or []
            return bool(parse(r["reply"])) and len(s) == len(parse(r["reply"])) and all(x >= t for x in s)
        sec = {"replies": len(rs), "refused": len(refused), "answered": len(answered),
               "answered, right": sum(right(r["reply"], r["answer"]) for r in answered)}
        for t in (0.3, 0.5, 0.7, 0.9):
            sh = [r for r in answered if shown(r, t)]
            sec[f"shown at {t}"] = len(sh)
            sec[f"shown and right at {t}"] = sum(right(r["reply"], r["answer"]) for r in sh)
        out[cond] = sec
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("--host", required=True); r.add_argument("--data", required=True)
    r.add_argument("--out", required=True); r.add_argument("--n", type=int, default=300)
    s = sub.add_parser("score"); s.add_argument("--weights", required=True); s.add_argument("--answers", required=True)
    s.add_argument("--out", required=True); s.add_argument("--base", default="FacebookAI/roberta-large")
    p = sub.add_parser("report"); p.add_argument("--answers", required=True); p.add_argument("--scores", required=True)
    p.add_argument("--json")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        return cmd_run(a)
    if a.cmd == "score":
        return cmd_score(a)
    rows = [json.loads(l) for l in Path(a.answers).read_text().splitlines() if l.strip()]
    sc = {(x["id"], x["condition"]): x["claim_support"] for x in map(json.loads, Path(a.scores).read_text().splitlines()) if x}
    rep = report(rows, sc)
    print(json.dumps(rep, indent=1))
    if a.json:
        Path(a.json).write_text(json.dumps(rep, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
