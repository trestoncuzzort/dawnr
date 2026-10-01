"""vision_pope.py: object hallucination of a vision-language model, POPE's way (2026-10-01).

    python3 locallm/vision_pope.py --host H:P[,H:P ...] --questions coco_pope_adversarial.json \\
        --images DIR --out answers.jsonl [--report report.json]

POPE (Li et al., arXiv:2305.10355; github.com/RUCAIBox/POPE, MIT): balanced yes/no questions "Is there a
<object> in the image?" over 500 COCO images; an answer is "no" when its first sentence contains "No",
"not" or "no", otherwise "yes" (evaluate.py, copied below as `parse`); accuracy, precision, recall, F1 and
the share answered yes. Each question goes to a llama.cpp server holding the model and its vision projector
(OpenAI-style image_url content, the image inlined as base64), greedy, 16 new tokens: the first sentence is
all POPE reads. A run resumes from --out.
"""
from __future__ import annotations

import argparse
import base64
import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def parse(text: str) -> str:
    """POPE's evaluate.py: keep the first sentence, drop commas, 'no' if No/not/no is a word of it."""
    if text.find(".") != -1:
        text = text.split(".")[0]
    words = text.replace(",", "").split(" ")
    return "no" if ("No" in words or "not" in words or "no" in words) else "yes"


def metrics(labels: list[str], preds: list[str]) -> dict:
    tp = sum(1 for l, p in zip(labels, preds) if l == "yes" and p == "yes")
    fp = sum(1 for l, p in zip(labels, preds) if l == "no" and p == "yes")
    tn = sum(1 for l, p in zip(labels, preds) if l == "no" and p == "no")
    fn = sum(1 for l, p in zip(labels, preds) if l == "yes" and p == "no")
    n = len(labels)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"questions": n, "TP": tp, "FP": fp, "TN": tn, "FN": fn, "accuracy": round((tp + tn) / n, 4) if n else None,
            "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4),
            "yes ratio": round((tp + fp) / n, 4) if n else None}


def _post(url: str, body: dict, timeout: float = 900.0) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def ask(host: str, image: bytes, question: str, post=_post) -> str:
    body = {"messages": [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(image).decode()}},
        {"type": "text", "text": question}]}], "temperature": 0, "max_tokens": 16}
    return post(f"http://{host}/v1/chat/completions", body)["choices"][0]["message"]["content"] or ""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--host", required=True)
    ap.add_argument("--questions", type=Path, required=True)
    ap.add_argument("--images", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--report", type=Path)
    a = ap.parse_args(argv)
    qs = [json.loads(l) for l in a.questions.read_text(encoding="utf-8").splitlines() if l.strip()]
    done = {}
    if a.out.exists():
        for l in a.out.read_text(encoding="utf-8").splitlines():
            if l.strip():
                r = json.loads(l)
                done[r["question_id"]] = r
    todo = [q for q in qs if q["question_id"] not in done]
    hosts = a.host.split(",")
    started = time.monotonic()

    def worker(k: int):
        rows = []
        for q in todo[k::len(hosts)]:
            try:
                text = ask(hosts[k], (a.images / q["image"]).read_bytes(), q["text"])
            except Exception as e:                              # noqa: BLE001  (recorded, then parsed as POPE parses)
                text = f"<error {type(e).__name__}>"
            r = {"question_id": q["question_id"], "image": q["image"], "question": q["text"], "label": q["label"],
                 "answer": text, "parsed": parse(text)}
            with a.out.open("a", encoding="utf-8") as f:
                f.write(json.dumps(r) + "\n")
            rows.append(r)
        return rows
    with ThreadPoolExecutor(max_workers=len(hosts)) as pool:
        for rows in pool.map(worker, range(len(hosts))):
            for r in rows:
                done[r["question_id"]] = r
    rows = [done[q["question_id"]] for q in qs if q["question_id"] in done]
    report = {"questions file": str(a.questions), **metrics([r["label"] for r in rows], [r["parsed"] for r in rows]),
              "errors": sum(1 for r in rows if r["answer"].startswith("<error")), "seconds": round(time.monotonic() - started)}
    print(json.dumps(report))
    if a.report:
        a.report.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
