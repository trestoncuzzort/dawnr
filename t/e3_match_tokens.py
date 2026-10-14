#!/usr/bin/env python3
"""E3 token-budget matching, measured through the ACTUAL training preprocessing (train_lora_cpu.encode_row),
so the audit counts the effective input and supervised tokens the trainer consumes AFTER compact-prompt and
left-truncation — not raw pre-truncation prompts. Matches the SUPERVISED-label budget to all7 (the smallest)
with a declared two-sided tolerance, fills without stopping early (scans all candidates until none fits),
holds the task set equal, and emits task-set / per-task frequency / solution-diversity / cross-arm overlap /
truncation audits. Never trades away task context silently: truncation is reported, and the arms share tasks.

    ~/e3-venv/bin/python e3_match_tokens.py <arms-in-dir> <out-dir> [tolerance=0.03]
"""
import json, os, sys, random, collections
from pathlib import Path
os.environ.setdefault("HF_HOME", os.path.expanduser("~/hf-cache"))
sys.path.insert(0, ".")
from transformers import AutoTokenizer
from train_lora_cpu import encode_row

A = Path(sys.argv[1]); OUT = Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
TOL = float(sys.argv[3]) if len(sys.argv) > 3 else 0.03
tok = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-Coder-0.5B-Instruct"); tok.pad_token = tok.eos_token
load = lambda n: [json.loads(l) for l in (A / f"arm-{n}.jsonl").read_text().splitlines()]
raw, graded, all7 = load("raw"), load("graded-k4"), load("all7")
tasks7 = sorted({r["task"] for r in all7}); tset = set(tasks7)


def enrich(rows):
    out = []
    for r in rows:
        if r["task"] not in tset:
            continue
        e = encode_row(r, tok)
        if e["n_supervised"] < 1:
            continue
        out.append({**r, "_inp": e["n_input"], "_lab": e["n_supervised"],
                    "_trunc": e["truncated"], "_dropped": e["prompt_dropped"],
                    "_overflow": e["n_input"] > 768})
    return out


r_raw, r_grd, r_all = enrich(raw), enrich(graded), enrich(all7)
budget = sum(x["_lab"] for x in r_all)
lo, hi = budget * (1 - TOL), budget * (1 + TOL)
rng = random.Random(0)


def fill(rows):
    """Balanced per-task round-robin, then keep scanning ALL remaining candidates (shortest first) adding any
    that still fit under the upper bound — never stops early while a shorter candidate would still fit."""
    by = collections.defaultdict(list)
    for r in rows:
        by[r["task"]].append(r)
    for t in by:
        rng.shuffle(by[t])
    picked, used, ptr = [], 0, {t: 0 for t in by}
    tasks = sorted(by)
    # pass 1: round-robin for task balance
    progressed = True
    while used < hi and progressed:
        progressed = False
        for t in tasks:
            i = ptr[t]
            if i < len(by[t]) and used + by[t][i]["_lab"] <= hi:
                picked.append(by[t][i]); used += by[t][i]["_lab"]; ptr[t] += 1; progressed = True
    # pass 2: fill remaining headroom with the shortest still-fitting candidates (no early stop)
    rest = sorted((by[t][i] for t in tasks for i in range(ptr[t], len(by[t]))), key=lambda r: r["_lab"])
    for r in rest:
        if used + r["_lab"] <= hi:
            picked.append(r); used += r["_lab"]
    return picked


def audit(nm, rows):
    freq = collections.Counter(r["task"] for r in rows)
    out = {"rows": len(rows), "input_tokens": sum(r["_inp"] for r in rows),
           "supervised_tokens": sum(r["_lab"] for r in rows), "tasks": len(freq),
           "task_set": sorted(freq), "task_freq": dict(freq),
           "distinct_solutions": len({r["chosen"] for r in rows}),
           "rows_truncated": sum(1 for r in rows if r["_trunc"]),
           "prompt_tokens_dropped": sum(r["_dropped"] for r in rows),
           "rows_over_maxlen": sum(1 for r in rows if r["_overflow"])}
    return out


res = {"tolerance": TOL, "budget_supervised_tokens": budget, "bounds": [round(lo), round(hi)], "arms": {}}
for nm, rows in (("raw", r_raw), ("graded", r_grd), ("all7", r_all)):
    m = rows if nm == "all7" else fill(rows)
    clean = [{k: v for k, v in r.items() if not k.startswith("_")} for r in m]
    (OUT / f"{nm}.jsonl").write_text("".join(json.dumps(x) + "\n" for x in clean), encoding="utf-8")
    res["arms"][nm] = audit(nm, m)

# two-sided budget assertion + cross-arm overlap
sets = {nm: set(a["task_set"]) for nm, a in res["arms"].items()}
inter = set.intersection(*sets.values()); union = set.union(*sets.values())
res["task_overlap"] = {"intersection": len(inter), "union": len(union),
                       "identical_task_set": all(s == sets["all7"] for s in sets.values())}
res["budget_ok"] = {}
for nm, a in res["arms"].items():
    ok = lo <= a["supervised_tokens"] <= hi
    res["budget_ok"][nm] = ok
(OUT / "match-audit.json").write_text(json.dumps(res, indent=2), encoding="utf-8")

for nm, a in res["arms"].items():
    flag = "OK" if res["budget_ok"][nm] else "OUT-OF-TOLERANCE"
    print(f"{nm}: rows={a['rows']} sup_toks={a['supervised_tokens']} inp_toks={a['input_tokens']} "
          f"tasks={a['tasks']} distinct_sol={a['distinct_solutions']} truncated={a['rows_truncated']} "
          f"dropped_prompt_toks={a['prompt_tokens_dropped']} over_maxlen={a['rows_over_maxlen']} [{flag}]")
print(f"budget={budget} tol=±{TOL} bounds=[{round(lo)},{round(hi)}] identical_task_set="
      f"{res['task_overlap']['identical_task_set']}")
if not all(res["budget_ok"].values()):
    print("WARN: an arm is out of the declared supervised-token tolerance; do NOT use for final runs as-is.")
    sys.exit(3)
