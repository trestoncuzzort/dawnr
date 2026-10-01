#!/usr/bin/env python3
"""t/self_eval.py -- does the student know when its own answer is right? (2026-10-01)

    python3 t/self_eval.py --host H:P[,H:P ...] --ids-file IDS --verdicts V.json [--gate G.json] \\
        [--shots EXAMPLES.jsonl] --out OUT.json TAG [TAG ...]

Kadavath et al., "Language Models (Mostly) Know What They Know" (arXiv:2207.05221): a model is
shown a question and a proposed answer and asked

    Is the proposed answer:
     (A) True
     (B) False
    The proposed answer is:

and P(True) is the probability it puts on (A). They report it with AUROC (chance 0.5), the
expected calibration error over 10 equal-count bins, the Brier score, and the accuracy of the
answers it calls true against the accuracy of all of them; it is poorly calibrated zero-shot and
better few-shot, and judging long-form answers (code) is harder than short ones.

Here the model judges answers to the dev problems in its own chat template, the assistant turn
prefilled to "The proposed answer is: (", and P(True) = p(A) / (p(A) + p(B)) from the server's
next-token probabilities (llama.cpp's /completion with n_probs, github.com/ggml-org/llama.cpp
tools/server). The ground truth is not the model's word but the instruments': an answer is RIGHT
when it passes its problem's tests, at least one kernel proves it and none refutes it, and its
specification agrees with the problem's reference and rejects at least 60% of mutated outputs
(t/score_levels.py's complete count). The gate's own verdict (t/spec_gate.py) can be scored the
same way, as the instrument P(True) would have to beat.

--shots gives few-shot examples: rows {"question", "answer", "right"} from TRAINING problems only;
the build refuses an example whose problem is among the judged ids.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import graded_pool                                              # noqa: E402
import loop_dataset                                             # noqa: E402
import score_heldout                                            # noqa: E402
import score_levels                                             # noqa: E402
import spec_check                                               # noqa: E402
import spec_experiment as se                                    # noqa: E402

PREFILL = "The proposed answer is: ("
OPTIONS = "Is the proposed answer:\n (A) True\n (B) False"


def question_text(entry: dict) -> str:
    tests = "\n".join(entry["rec"]["test_list"])
    return f"Question: {entry['rec']['text'].strip()}\nTests:\n{tests}"


def judge_turn(question: str, answer: str) -> str:
    return f"{question}\nProposed Answer:\n{answer.strip()}\n{OPTIONS}"


def conversation(question: str, answer: str, shots: list[dict] = ()) -> list[dict]:
    msgs = []
    for s in shots:
        msgs += [{"role": "user", "content": judge_turn(s["question"], s["answer"])},
                 {"role": "assistant", "content": PREFILL + ("A) True" if s["right"] else "B) False")}]
    return msgs + [{"role": "user", "content": judge_turn(question, answer)}]


def p_true(top: list[dict]) -> float | None:
    """P(True) from the next token's top candidates ({"token", "logprob"} or {"token", "prob"})."""
    pa = pb = 0.0
    for t in top:
        p = t["prob"] if "prob" in t else math.exp(t["logprob"])
        piece = str(t.get("token", "")).strip()
        if piece.startswith("A"):
            pa += p
        elif piece.startswith("B"):
            pb += p
    return pa / (pa + pb) if pa + pb > 0 else None


def _post(url: str, body: dict, timeout: float = 900.0) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def ask(host: str, messages: list[dict], post=_post) -> float | None:
    """One P(True) from a llama.cpp server: its own template, the assistant turn prefilled."""
    prompt = post(f"http://{host}/apply-template", {"messages": messages})["prompt"] + PREFILL
    r = post(f"http://{host}/completion", {"prompt": prompt, "n_predict": 1, "n_probs": 20, "temperature": 0,
                                           "cache_prompt": True})
    probs = r.get("completion_probabilities") or []
    if not probs:
        return None
    first = probs[0]
    return p_true(first.get("top_logprobs") or first.get("top_probs") or [])


# ---------------------------------------------------------------------------------- metrics --

def auroc(scores: list[float], labels: list[bool]) -> float | None:
    """The probability that a random right answer scores above a random wrong one (ties half)."""
    pos = [s for s, y in zip(scores, labels) if y]
    neg = [s for s, y in zip(scores, labels) if not y]
    if not pos or not neg:
        return None
    wins = sum(1.0 if p > n else 0.5 if p == n else 0.0 for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def ece(scores: list[float], labels: list[bool], bins: int = 10) -> float | None:
    """Kadavath et al.'s ECE: equal-count bins, the mean |mean prediction - frequency| weighted by size."""
    pairs = sorted(zip(scores, labels), key=lambda p: p[0])     # by score only: a label never orders a tie
    n = len(pairs)
    if n == 0:
        return None
    total = 0.0
    for b in range(bins):
        chunk = pairs[b * n // bins:(b + 1) * n // bins]
        if chunk:
            total += len(chunk) * abs(sum(s for s, _ in chunk) / len(chunk) - sum(1 for _, y in chunk if y) / len(chunk))
    return total / n


def brier(scores: list[float], labels: list[bool]) -> float | None:
    return sum((s - (1.0 if y else 0.0)) ** 2 for s, y in zip(scores, labels)) / len(scores) if scores else None


def summary(scores: list[float], labels: list[bool]) -> dict:
    n, k = len(scores), sum(labels)
    called = [y for s, y in zip(scores, labels) if s > 0.5]
    return {"answers": n, "right": k, "base rate": round(k / n, 4) if n else None,
            "auroc": _r(auroc(scores, labels)), "ece": _r(ece(scores, labels)), "brier": _r(brier(scores, labels)),
            "called true (P > 0.5)": len(called), "right among those": sum(called),
            "accuracy among those": _r(sum(called) / len(called)) if called else None,
            "mean P(True)": _r(sum(scores) / n) if n else None}


def _r(x):
    return None if x is None else round(x, 4)


# ---------------------------------------------------------------------------------- labels --

def answers(tags: list[str], ids: set[int], verdicts: dict, gate: dict | None = None) -> list[dict]:
    """Every valid task (stage == task) of the sets on the ids, with its labels."""
    out = []
    for tag in tags:
        d = se.OUT_ROOT / se.model_tag(tag)
        ext = json.loads((d / "extract.json").read_text(encoding="utf-8"))
        tests = json.loads((d / "tests.json").read_text(encoding="utf-8")) if (d / "tests.json").exists() else {}
        _c, cells = se.parse_kernel_table(d / "kernels.md") if (d / "kernels.md").exists() else ([], {})
        for tid, e in ext.items():
            if not str(tid).isdigit() or int(tid) not in ids or e.get("stage") != "task":
                continue
            name = e["name"]
            path = d / "tasks" / f"{name}.json"
            t = tests.get(str(tid), {})
            _lvl, proved = score_levels.answer_level(t.get("overall"), cells.get(name), None)
            raw = verdicts.get(f"{tag}/{name}") or {}
            status = score_heldout.checked_spec(raw, path)
            complete = not isinstance(raw.get("completeness"), (int, float)) or raw["completeness"] >= score_levels.MIN_COMPLETENESS
            row = {"tag": tag, "tid": int(tid), "name": name, "path": str(path),
                   "tests pass": t.get("overall") == "pass", "proved": proved,
                   "right": bool(proved) and status == "agrees" and complete}
            if gate is not None:
                g = gate.get(f"{tag}/{name}") or {}
                try:
                    bound = g.get("task_sha256") == spec_check.task_sha256(json.loads(path.read_text(encoding="utf-8")))
                except (OSError, ValueError, KeyError, TypeError):
                    bound = False
                row["shown by the gate"] = bool(proved) and bool(g.get("passes")) and bound
            out.append(row)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tags", nargs="+")
    ap.add_argument("--host", required=True, help="host:port[,host:port] of llama.cpp servers holding the student")
    ap.add_argument("--ids-file", type=Path, required=True)
    ap.add_argument("--verdicts", type=Path, required=True)
    ap.add_argument("--gate", type=Path)
    ap.add_argument("--shots", type=Path, help="JSONL of {task_id, question, answer, right} from training problems")
    ap.add_argument("--pool", choices=se.POOL_VERSIONS, default="v5")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    ids = {int(x) for x in a.ids_file.read_text(encoding="utf-8").split()}
    P = se.pool(a.pool)
    verdicts = json.loads(a.verdicts.read_text(encoding="utf-8")).get("results", {})
    gate = json.loads(a.gate.read_text(encoding="utf-8")).get("results", {}) if a.gate else None
    shots = []
    if a.shots:
        shots = [json.loads(l) for l in a.shots.read_text(encoding="utf-8").splitlines() if l.strip()]
        leak = sorted({s["task_id"] for s in shots} & ids)
        if leak:
            raise SystemExit(f"self_eval: few-shot examples from judged problems: {leak}")
    rows = answers(a.tags, ids, verdicts, gate)
    hosts = a.host.split(",")

    def one(i_row):
        i, row = i_row
        task = json.loads(Path(row["path"]).read_text(encoding="utf-8"))
        answer = loop_dataset.fence(graded_pool.answer_text(task, P[row["tid"]]["fn"]))   # the name it was asked for
        try:
            return ask(hosts[i % len(hosts)], conversation(question_text(P[row["tid"]]), answer, shots))
        except Exception:                                       # noqa: BLE001
            return None
    with ThreadPoolExecutor(max_workers=len(hosts)) as pool:
        for row, p in zip(rows, pool.map(one, enumerate(rows))):
            row["p_true"] = p
    scored = [r for r in rows if r["p_true"] is not None]
    report = {"shots": len(shots), "answers": len(rows), "scored": len(scored),
              "right (all valid answers)": summary([r["p_true"] for r in scored], [r["right"] for r in scored])}
    passing = [r for r in scored if r["tests pass"]]
    report["right (answers that pass their tests)"] = summary([r["p_true"] for r in passing], [r["right"] for r in passing])
    report["tests pass (all valid answers)"] = summary([r["p_true"] for r in scored], [r["tests pass"] for r in scored])
    if gate is not None:
        shown = [r for r in scored if r["shown by the gate"]]
        report["the gate, for comparison"] = {"shown": len(shown), "right among those": sum(r["right"] for r in shown)}
    a.out.write_text(json.dumps({"report": report, "rows": rows}, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":                                      # pragma: no cover
    raise SystemExit(main())
