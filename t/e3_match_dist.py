#!/usr/bin/env python3
"""Build the final E3 training arms as an HONEST, proof-FAIR ablation.

The three requested arms share the SAME tasks and the SAME per-task solution count (q = the number of
all-seven-verified solutions for that task). They differ ONLY in how each task's q solutions are chosen:

  all7   - the q all-seven-verified solutions (k==7).                      [the strict proof gate]
  graded - q solutions drawn WITHOUT bias from the stated k-of-7 pool      [the graded proof gate]
           (kacc >= GRADED_K); NOT preferring 4..6 over 7 to invent a contrast.
  raw    - q solutions drawn PROOF-BLIND from ALL candidates for the task  [no proof gating]
           (kacc is never read); a fixed per-task seed makes it reproducible.

A fourth arm is written and labelled as a DIAGNOSTIC ONLY, never the requested raw baseline:
  raw_unverified_diag - prefers unverified (k<4) then 4..6 then verified; the maximally-adversarial
                        contrast. Reported, but excluded from the training index / headline comparison.

Matching: equal per-task counts are ENFORCED (hard fail on violation) -> matched diversity. The arms are
matched on the EFFECTIVE TRAINING BUDGET (train_budget.json = min supervised tokens across the three real
arms); proof-blind raw is NOT cherry-picked to a token target, so the raw selection's natural token total
may exceed the declared 3% bound. We report input / supervised / optimizer-step exposure SEPARATELY and
state honestly whether the *selection* is within 3% (diagnostic) vs. matched by *training budget*
(authoritative). All tokenisation uses the SAME pinned base+revision and the SAME encode_row the trainer uses.

    ~/e3-venv/bin/python e3_match_dist.py <cand-raw.jsonl with kacc> <out-dir> [graded_k=4] [tol=0.03]
"""
import json, os, sys, random, collections, hashlib
from pathlib import Path
os.environ.setdefault("HF_HOME", os.path.expanduser("~/hf-cache"))
sys.path.insert(0, ".")
import e3_base
from train_lora_cpu import encode_row

CAND = Path(sys.argv[1]); OUT = Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
GRADED_K = int(sys.argv[3]) if len(sys.argv) > 3 else 4
TOL = float(sys.argv[4]) if len(sys.argv) > 4 else 0.03                 # DECLARED selection bound (not relaxed)
tok = e3_base.load_tokenizer()
rows = [json.loads(l) for l in CAND.read_text().splitlines() if l.strip()]


def kacc(s):
    try:
        return int(s.get("kacc", 0) or 0)
    except (TypeError, ValueError):
        return 0


def tseed(task):
    return int(hashlib.sha1(task.encode()).hexdigest()[:8], 16)        # stable per-task seed (no salted hash())


bytask = collections.defaultdict(list)
for r in rows:
    bytask[r["task"]].append(r)

arms = {"raw": [], "graded": [], "all7": [], "raw_unverified_diag": []}
per_task, pool_sizes = {}, {}
for task, sols in sorted(bytask.items()):
    v7 = [s for s in sols if kacc(s) >= 7]
    q = len(v7)
    if q == 0:
        continue                                                      # all7 defines the task set
    gpool = [s for s in sols if kacc(s) >= GRADED_K]                  # graded = stated k-of-7 pool
    if len(gpool) < q or len(sols) < q:
        print(f"FAIL: per-task quota q={q} not satisfiable for {task} "
              f"(cands={len(sols)} graded_pool={len(gpool)})"); sys.exit(3)
    rng = random.Random(tseed(task))
    key = lambda s: s.get("chosen", "")

    all7_sel = sorted(v7, key=key)[:q]                               # deterministic; q == len(v7)
    gshuf = sorted(gpool, key=key); rng.shuffle(gshuf)               # proof-grade pool, UNBIASED sample
    graded_sel = gshuf[:q]
    rshuf = sorted(sols, key=key); rng.shuffle(rshuf)                # ALL candidates, PROOF-BLIND sample
    raw_sel = rshuf[:q]
    low = sorted([s for s in sols if kacc(s) < 4], key=key)          # DIAGNOSTIC: worst-first contrast
    mid = sorted([s for s in sols if 4 <= kacc(s) < 7], key=key)
    rng.shuffle(low); rng.shuffle(mid)
    diag_sel = (low + mid + sorted(v7, key=key))[:q]

    assert len(all7_sel) == len(graded_sel) == len(raw_sel) == len(diag_sel) == q
    for nm, sel in (("raw", raw_sel), ("graded", graded_sel), ("all7", all7_sel), ("raw_unverified_diag", diag_sel)):
        for s in sel:
            arms[nm].append({**{k: v for k, v in s.items()}, "arm": nm, "src_kacc": kacc(s)})
    per_task[task] = q
    pool_sizes[task] = {"candidates": len(sols), "graded_pool": len(gpool), "verified": q}


def exposure(sel):
    inp = sup = 0
    trunc = over = 0
    for r in sel:
        e = encode_row(r, tok, maxlen=e3_base.MAXLEN)
        inp += e["n_input"]; sup += e["n_supervised"]
        trunc += 1 if e["truncated"] else 0
        over += 1 if e["n_input"] > e3_base.MAXLEN else 0
    import math
    return {"rows": len(sel), "input_tokens": inp, "supervised_tokens": sup,
            "optimizer_steps_per_epoch": math.ceil(len(sel) / e3_base.ACCUM) if sel else 0,
            "distinct_solutions": len({r["chosen"] for r in sel}),
            "rows_truncated": trunc, "rows_over_maxlen": over}


tgt = collections.Counter(per_task)                                   # the common per-task quota
audit = {"base": e3_base.BASE, "revision": e3_base.REV, "maxlen": e3_base.MAXLEN, "accum": e3_base.ACCUM,
         "graded_k": GRADED_K, "declared_selection_tol": TOL, "tasks": len(per_task),
         "per_task_quota": dict(per_task), "pool_sizes": pool_sizes, "arms": {}}
for nm, sel in arms.items():
    freq = collections.Counter(r["task"] for r in sel)
    ex = exposure(sel)
    ex["per_task_equal_to_quota"] = (freq == tgt)
    audit["arms"][nm] = ex

sols_by = {nm: {r["chosen"] for r in arms[nm]} for nm in arms}
audit["overlap_vs_all7"] = {                                          # recorded even when the contrast is small
    nm: {"shared_with_all7": len(sols_by[nm] & sols_by["all7"]),
         "unique_vs_all7": len(sols_by[nm] - sols_by["all7"]),
         "pct_unique": round(100 * len(sols_by[nm] - sols_by["all7"]) / max(1, len(sols_by[nm])), 1)}
    for nm in ("raw", "graded", "raw_unverified_diag")}

real = ("raw", "graded", "all7")                                      # the diagnostic is NOT part of the match
sup = {nm: audit["arms"][nm]["supervised_tokens"] for nm in real}
spread = max(sup.values()) - min(sup.values())
within = spread <= TOL * max(sup.values())
counts_ok = all(audit["arms"][nm]["per_task_equal_to_quota"] for nm in real)
train_budget = min(sup.values())                                      # authoritative matched quantity
audit["token_match"] = {
    "real_arms_supervised_tokens": sup, "selection_spread": spread,
    "selection_spread_pct_of_max": round(100 * spread / max(sup.values()), 2),
    "selection_within_declared_tol": within,                          # reported honestly, NOT relaxed to pass
    "matched_by": "effective_training_budget",
    "effective_train_budget_supervised": train_budget,
    "note": ("raw is proof-blind, so its selection is NOT cherry-picked to the token target; the arms are "
             "matched by training each to the common effective_train_budget_supervised, not by selection.")}
audit["gates"] = {"equal_per_task_counts": counts_ok}

for nm, sel in arms.items():
    clean = [{k: v for k, v in r.items() if not k.startswith("_")} for r in sel]
    (OUT / f"{nm}.jsonl").write_text("".join(json.dumps(x) + "\n" for x in clean), encoding="utf-8")
(OUT / "dist-match-audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
(OUT / "train_budget.json").write_text(json.dumps(
    {"base": e3_base.BASE, "revision": e3_base.REV, "maxlen": e3_base.MAXLEN, "accum": e3_base.ACCUM,
     "max_supervised_tokens": train_budget, "applies_to_arms": list(real),
     "diagnostic_arms": ["raw_unverified_diag"],
     "rationale": "common effective training budget = min supervised tokens over the 3 real arms; the trainer "
                  "consumes rows in a fixed per-task round-robin until this budget is reached (identical for "
                  "every arm and seed), giving matched optimizer exposure without biasing selection."},
    indent=2), encoding="utf-8")

for nm in ("raw", "graded", "all7", "raw_unverified_diag"):
    a = audit["arms"][nm]
    tag = " [DIAGNOSTIC]" if nm == "raw_unverified_diag" else ""
    print(f"{nm}{tag}: rows={a['rows']} inp_tok={a['input_tokens']} sup_tok={a['supervised_tokens']} "
          f"opt_steps/epoch={a['optimizer_steps_per_epoch']} distinct={a['distinct_solutions']} "
          f"trunc={a['rows_truncated']} over_maxlen={a['rows_over_maxlen']} per_task_equal={a['per_task_equal_to_quota']}")
print(f"overlap_vs_all7: {audit['overlap_vs_all7']}")
print(f"token_match: spread={spread} ({audit['token_match']['selection_spread_pct_of_max']}% of max) "
      f"selection_within_{TOL:.0%}={within} | matched_by=effective_training_budget="
      f"{train_budget} sup-tok (train_budget.json)")
print(f"gates: equal_per_task_counts={counts_ok}")
if not counts_ok:
    print("FATAL: per-task counts not equal across real arms; selection is NOT a valid matched set."); sys.exit(4)
print("OK: arms frozen (proof-blind raw, stated-rule graded, all7) + labelled diagnostic; "
      "matched by effective training budget. Rebuild the eligibility/contamination manifest next.")
