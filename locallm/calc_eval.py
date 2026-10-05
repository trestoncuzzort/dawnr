"""calc_eval.py: how often an answer `dawnr calc` shows is right, and how many questions get one, beside the same
model answering step by step in prose (2026-10-05).

    python3 locallm/calc_eval.py prep --parquet test.parquet --out gsm8k-test.jsonl
    python3 locallm/calc_eval.py run --host H:P[,H:P ...] --data gsm8k-test.jsonl --out answers.jsonl [--n 300]
    python3 locallm/calc_eval.py report --answers answers.jsonl [--json r.json]

GSM8K's test split (Cobbe et al., arXiv:2110.14168; MIT): grade-school word problems, each with one final number.
`--n` are drawn with a fixed seed. Registered in locallm/PREDICT-2026-10-05-calc.md.

What is asked of the model for a question, all by one model:

  prose      a step-by-step answer in words ending `#### <number>`, temperature 0: the model answering as it does
  workings   three workings under locallm/calc.py's grammar, the first at temperature 0 and two sampled

What is scored, from those replies alone:

  prose      the number after ####
  one        the first working, computed (PAL, arXiv:2211.10435), shown whenever it computes
  agree      the three workings, shown when at least two compute and all that compute give one number
  calc       `dawnr calc`: as agree, and a working that uses a number the question does not state is not used

An answer is right when it equals the problem's final number exactly.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
import threading
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from locallm import calc, rag_rgb  # noqa: E402

SEED = 2026
ARMS = ("prose", "one", "agree", "calc")
PROSE_SYSTEM = ("Work the problem out step by step. Then give the final number on a line of its own, after ####, "
                "with no units.")
_NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def gold(answer: str) -> Fraction:
    """GSM8K's final number: what follows ####."""
    return Fraction(answer.rsplit("####", 1)[1].strip().replace(",", "").replace("$", ""))


def prose_number(reply: str) -> Fraction | None:
    """The number after the last ####, or the last number of a reply that has none."""
    tail = reply.rsplit("####", 1)[1] if "####" in reply else reply
    found = _NUMBER.findall(tail)
    if not found:
        return None
    text = (found[0] if "####" in reply else found[-1]).replace(",", "")
    try:
        return Fraction(text)
    except (ValueError, ZeroDivisionError):
        return None


def shown(arm: str, row: dict) -> Fraction | None:
    """What the arm shows for a question, from the replies kept for it."""
    if arm == "prose":
        return prose_number(row["prose"])
    if arm == "one":
        try:
            return calc.evaluate(row["workings"][0])[0]
        except calc.Unusable:
            return None
    return calc.judge(row["question"], row["workings"], grounded=arm == "calc")["answer"]


def report(rows: list[dict]) -> dict:
    out = {}
    for arm in ARMS:
        values = [(shown(arm, r), gold(r["answer"])) for r in rows]
        n_shown = sum(v is not None for v, _g in values)
        right = sum(v is not None and v == g for v, g in values)
        out[arm] = {"questions": len(rows), "shown": n_shown, "right": right,
                    "right of shown": round(right / max(1, n_shown), 4), "wrong shown": n_shown - right}
    missed = [r for r in rows if shown("prose", r) != gold(r["answer"])]
    out["where prose is wrong"] = {
        "questions": len(missed),
        "calc shows a wrong answer": sum(1 for r in missed if shown("calc", r) is not None and shown("calc", r) != gold(r["answer"])),
        "calc shows the right answer": sum(1 for r in missed if shown("calc", r) == gold(r["answer"])),
        "calc refuses": sum(1 for r in missed if shown("calc", r) is None)}
    return out


def ask_prose(host: str, question: str, post=rag_rgb._post) -> str:
    body = {"messages": [{"role": "system", "content": PROSE_SYSTEM}, {"role": "user", "content": question}],
            "temperature": 0, "max_tokens": 600}
    return post(f"http://{host}/v1/chat/completions", body)["choices"][0]["message"]["content"] or ""


def cmd_prep(a) -> int:
    import pyarrow.parquet as pq                                # the only use of a dependency, and only here
    table = pq.read_table(a.parquet).to_pylist()
    with open(a.out, "w", encoding="utf-8") as f:
        for n, r in enumerate(table):
            f.write(json.dumps({"id": n, "question": r["question"], "answer": r["answer"]}, ensure_ascii=False) + "\n")
    print(f"{len(table)} rows -> {a.out}")
    return 0


def cmd_run(a) -> int:
    rows = [json.loads(l) for l in Path(a.data).read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = sorted(random.Random(SEED).sample(rows, min(a.n, len(rows))), key=lambda r: r["id"])
    done = set()
    if Path(a.out).exists():
        done = {json.loads(l)["id"] for l in Path(a.out).read_text(encoding="utf-8").splitlines() if l.strip()}
    todo = [r for r in rows if r["id"] not in done]
    hosts, lock = a.host.split(","), threading.Lock()

    def worker(k: int) -> None:
        for r in todo[k::len(hosts)]:
            try:
                row = dict(r, prose=ask_prose(hosts[k], r["question"]),
                           workings=[calc.ask(hosts[k], r["question"], 0.0 if w == 0 else calc.TEMPERATURE, w) for w in range(3)])
            except Exception as error:                          # noqa: BLE001 -- a failed request is rerun, not scored
                print(f"{r['id']}: {type(error).__name__}: {error}", file=sys.stderr)
                continue
            with lock, open(a.out, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
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
    for arm in ARMS:
        v = r[arm]
        print(f"{arm:6} shown {v['shown']}/{v['questions']}, right {v['right']} ({100 * v['right of shown']:.1f}% of shown), wrong shown {v['wrong shown']}")
    w = r["where prose is wrong"]
    print(f"where prose is wrong ({w['questions']}): calc right {w['calc shows the right answer']}, refuses {w['calc refuses']}, "
          f"wrong {w['calc shows a wrong answer']}")
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
