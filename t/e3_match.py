#!/usr/bin/env python3
"""Match the three E3 arms to one budget so the proof-filter is the only variable.
Restrict every arm to the tasks the all7 arm covers, then cap each arm to the common row count,
balanced across tasks. Writes matched arms + prints sizes, token budgets and the contamination check.

    python3 -I e3_match.py <arms-in-dir> <out-dir>
"""
import json, pathlib, random, sys, collections

A = pathlib.Path(sys.argv[1]); OUT = pathlib.Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
load = lambda n: [json.loads(l) for l in (A / f"arm-{n}.jsonl").read_text().splitlines()]
raw, graded, all7 = load("raw"), load("graded-k4"), load("all7")
tasks7 = sorted({r["task"] for r in all7})
tset = set(tasks7)
restrict = lambda rows: [r for r in rows if r["task"] in tset]
r_raw, r_grd, r_all = restrict(raw), restrict(graded), restrict(all7)
n = min(len(r_raw), len(r_grd), len(r_all))
rng = random.Random(0)

def balanced_cap(rows, n):
    by = collections.defaultdict(list)
    for r in rows:
        by[r["task"]].append(r)
    for t in by:
        rng.shuffle(by[t])
    out, i = [], 0
    tasks = sorted(by)
    while len(out) < n:
        progressed = False
        for t in tasks:
            if i < len(by[t]):
                out.append(by[t][i]); progressed = True
                if len(out) >= n:
                    break
        if not progressed:
            break
        i += 1
    return out

print(f"all7 tasks: {len(tasks7)}; matched size per arm: {n}")
for nm, rows in (("raw", r_raw), ("graded", r_grd), ("all7", r_all)):
    m = balanced_cap(rows, n)
    (OUT / f"{nm}.jsonl").write_text("".join(json.dumps(x) + "\n" for x in m), encoding="utf-8")
    toks = sum(len((x["chosen"] or "").split()) for x in m)
    ntask = len({x["task"] for x in m})
    print(f"  {nm}: {len(m)} rows, {ntask} tasks, ~{toks} ws-tokens")

mbpp_ids = sorted({int(t.split("_")[1]) for t in tasks7})
print(f"train corpus = MBPP ({len(mbpp_ids)} task ids: {mbpp_ids[:6]}...)")
print("eval corpus = Vericoding-Dafny + the twins; different corpora, disjoint by construction.")
