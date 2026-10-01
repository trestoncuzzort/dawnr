"""rag_rgb.py: answering from retrieved documents, RGB's way (2026-10-01).

    python3 locallm/rag_rgb.py --host H:P[,H:P ...] --data en.json --noise-rate 0.4 --out answers.jsonl \\
        [--passage-num 5] [--report report.json]

RGB, the Retrieval-Augmented Generation Benchmark (Chen et al., AAAI 2024, arXiv:2309.01431;
github.com/chen700564/RGB, data CC BY-NC-SA 4.0, kept out of this repository): 300 English questions about
news, each with documents that hold the answer ("positive") and documents that do not ("negative").
A question gets `passage_num` documents, a `noise_rate` share of them negative; at noise rate 1 every
document is negative and the right answer is to say the information is insufficient. Ported from its
evalue.py: the document choice (`processdata`'s plain-dataset branch, the generator reseeded with 2333 for
every question), `checkanswer`, the rejection rule (the answer contains "insufficient information") and
the score (`all_rate`: at noise rate 1 the share rejected, otherwise the share whose every answer part is
in the reply). The prompt is config/instruction.yaml's English system and instruction, the system as a
system turn as its Qwen2 wrapper sends it, at most 512 new tokens; with no documents (`--passage-num 0`,
the closed-book row) there is no system turn, as in evalue.py. Greedy, where RGB samples at 0.7: one
reproducible answer a question, as every other measurement here. A run resumes from --out.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SYSTEM = ("You are an accurate and reliable AI assistant that can answer questions with the help of external documents. "
          "Please note that external documents may contain noisy or factually incorrect information. If the information in "
          "the document contains the correct answer, you will give an accurate answer. If the information in the document "
          "does not contain the answer, you will generate ’I can not answer the question because of the insufficient "
          "information in documents.‘. If there are inconsistencies with the facts in some of the documents, please "
          "generate the response 'There are factual errors in the provided documents.' and provide the correct answer.")
INSTRUCTION = "Document:\n{DOCS} \n\nQuestion:\n{QUERY}"
SEED = 2333


def select(instance: dict, noise_rate: float, passage_num: int) -> list[str]:
    """evalue.py processdata, plain dataset: the first positives and first negatives, shuffled under seed 2333."""
    rnd = random.Random(SEED)                          # evalue.py: random.seed(2333) before each question
    neg_num = math.ceil(passage_num * noise_rate)
    pos_num = passage_num - neg_num
    if noise_rate == 1:
        neg_num, pos_num = passage_num, 0
    elif neg_num > len(instance["negative"]):
        neg_num = len(instance["negative"]); pos_num = passage_num - neg_num
    elif pos_num > len(instance["positive"]):
        pos_num = len(instance["positive"]); neg_num = passage_num - pos_num
    docs = instance["positive"][:pos_num] + instance["negative"][:neg_num]
    rnd.shuffle(docs)
    return docs


def checkanswer(prediction: str, ground_truth) -> list[int]:
    """evalue.py checkanswer: one label a part of the answer; a part that is a list is right if any alternative appears."""
    prediction = prediction.lower()
    if not isinstance(ground_truth, list):
        ground_truth = [ground_truth]
    labels = []
    for part in ground_truth:
        if isinstance(part, list):
            flag = any(alt.lower() in prediction for alt in part)
        else:
            flag = part.lower() in prediction
        labels.append(int(flag))
    return labels


def label(prediction: str, ground_truth) -> list[int]:
    """evalue.py predict: [-1] when the reply says the information is insufficient, else checkanswer."""
    if "insufficient information" in prediction:
        return [-1]
    return checkanswer(prediction, ground_truth)


def right(labels: list[int], noise_rate: float) -> bool:
    """evalue.py's count: at noise rate 1 a rejection; otherwise no part missed and some part found."""
    if noise_rate == 1:
        return labels[0] == -1
    return 0 not in labels and 1 in labels


def messages(query: str, docs: list[str]) -> list[dict]:
    if not docs:
        return [{"role": "user", "content": INSTRUCTION.format(QUERY=query, DOCS="")}]
    return [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": INSTRUCTION.format(QUERY=query, DOCS="\n".join(docs))}]


def _post(url: str, body: dict, timeout: float = 900) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def ask(host: str, msgs: list[dict], max_tokens: int = 512, post=_post) -> str:
    body = {"messages": msgs, "temperature": 0, "max_tokens": max_tokens}
    return post(f"http://{host}/v1/chat/completions", body)["choices"][0]["message"]["content"] or ""


def report(rows: list[dict], noise_rate: float) -> dict:
    n = len(rows)
    ok = sum(1 for r in rows if right(r["label"], noise_rate))
    rejected = sum(1 for r in rows if r["label"] and r["label"][0] == -1)
    errors = sum(1 for r in rows if r.get("error"))
    return {"noise_rate": noise_rate, "nums": n, "tt": ok, "all_rate": ok / n if n else 0.0,
            "rejected": rejected, "errors": errors}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--host", required=True)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--noise-rate", type=float, default=0.0)
    ap.add_argument("--passage-num", type=int, default=5)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--report", type=Path)
    ap.add_argument("--max-tokens", type=int, default=512)
    a = ap.parse_args(argv)
    data = [json.loads(l) for l in a.data.read_text(encoding="utf-8").splitlines() if l.strip()]
    done = {}
    if a.out.exists():
        for l in a.out.read_text(encoding="utf-8").splitlines():
            if l.strip():
                r = json.loads(l)
                if not r.get("error"):
                    done[r["id"]] = r
    todo = [d for d in data if d["id"] not in done]
    hosts = a.host.split(",")
    started = time.monotonic()

    def worker(k: int) -> list[dict]:
        rows = []
        for d in todo[k::len(hosts)]:
            docs = select(d, a.noise_rate, a.passage_num) if a.passage_num else []
            row = {"id": d["id"], "query": d["query"], "ans": d["answer"], "noise_rate": a.noise_rate,
                   "passage_num": a.passage_num}
            try:
                row["prediction"] = ask(hosts[k], messages(d["query"], docs), a.max_tokens)
                row["label"] = label(row["prediction"], d["answer"])
            except Exception as e:                       # recorded and counted as not right; a rerun retries it
                row["prediction"], row["label"], row["error"] = "", [0], f"{type(e).__name__}: {e}"[:300]
            with a.out.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            rows.append(row)
            print(f"{len(rows)} on {hosts[k]}, {time.monotonic() - started:.0f} s", flush=True)
        return rows

    with ThreadPoolExecutor(len(hosts)) as ex:
        new = [r for rs in ex.map(worker, range(len(hosts))) for r in rs]
    rows = {r["id"]: r for r in list(done.values()) + new}
    rows = [rows[d["id"]] for d in data if d["id"] in rows]
    rep = report(rows, a.noise_rate)
    rep["passage_num"] = a.passage_num
    print(json.dumps(rep), flush=True)
    if a.report:
        a.report.write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
