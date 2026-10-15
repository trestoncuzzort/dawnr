#!/usr/bin/env python3
"""Aggregate the fully-adjudicated matrix honestly. Expected cells come from the FROZEN MANIFEST, so a
survivor with zero observed cells still appears (as not-run x7) and completeness cannot read 100% by
omission. Unknown keys and conflicting duplicates are flagged. Survivor taxonomy over fully-decided cells
distinguishes unanimous-verified (spec-gap acceptance) from unanimous-refuted (agreement it is wrong) from
mixed (genuine cross-kernel disagreement); unverifiable/not-run are never counted as rejections.

Backends (corrected): Z3 = dafny, verus, fstar, spark; Alt-Ergo = framac; no SMT = lean, rocq.

    python3 -I e1_full_aggregate.py <tag> [<tag> ...]
"""
import json, sys, collections, pathlib

KERNELS = ["dafny", "verus", "spark", "framac", "lean", "rocq", "fstar"]
BACKEND = {"dafny": "Z3", "verus": "Z3", "fstar": "Z3", "spark": "Z3", "framac": "AltErgo",
           "lean": "none", "rocq": "none"}
OUT = pathlib.Path("out")


def load(tags):
    expected = {}                      # (path,which,kernel) -> survivor-id or "REAL"
    meta = {}                          # id -> {task, op, witness}
    totals = collections.Counter()
    for tag in tags:
        man = json.loads((OUT / f"E1MAN-{tag}.json").read_text())
        for path, t in man["tasks"].items():
            if t.get("status") != "ok":
                continue
            totals["tasks_ok"] += 1
            totals["survivors_total"] += t["n_survivors_total"]
            totals["survivors_selected"] += t["n_selected"]
            totals["classify_capped"] += 1 if t.get("classify_capped") else 0
            totals["selection_capped"] += 1 if t.get("capped_selection") else 0
            for k in KERNELS:
                expected[(path, "REAL", k)] = "REAL"
            for s in t["survivors"]:
                meta[s["id"]] = {"task": t["name"], "op": s["op"], "witness": s["witness"]}
                for k in KERNELS:
                    expected[(path, s["id"], k)] = s["id"]
    # per-tag run config_id (from meta) and per-task frozen src_hash, to reject stale/cross-config/wrong-src rows
    run_cfg, src_by = {}, {}
    for tag in tags:
        mp = OUT / f"E1FULL-{tag}.meta.json"
        run_cfg[tag] = json.loads(mp.read_text()).get("config_id") if mp.exists() else None
        man = json.loads((OUT / f"E1MAN-{tag}.json").read_text())
        for path, t in man["tasks"].items():
            if t.get("status") == "ok":
                src_by[path] = t["task_src_hash"]
    observed, dup, unknown, excl_cfg, excl_src, excl_nometa, conflicts = {}, 0, 0, 0, 0, 0, set()
    for tag in tags:
        fp = OUT / f"E1FULL-{tag}.jsonl"
        if not fp.exists():
            continue
        cfg = run_cfg.get(tag)
        for ln in fp.read_text().splitlines():
            try:
                r = json.loads(ln)
            except Exception:
                continue
            key = (r.get("path"), r.get("which"), r.get("kernel"))
            if key not in expected:
                unknown += 1; continue
            if not cfg:                                          # FAIL CLOSED: no valid run metadata/config id
                excl_nometa += 1; continue
            if r.get("config_id") != cfg:                        # stale / cross-config row
                excl_cfg += 1; continue
            if r.get("src_hash") != src_by.get(r.get("path")):   # evaluated against a different spec
                excl_src += 1; continue
            if key in observed:
                dup += 1
                if observed[key].get("state") != r.get("state"):  # conflicting duplicate: do NOT last-wins
                    conflicts.add(key)
            observed[key] = r
    for key in conflicts:                                 # a conflicted cell is not a trusted verdict
        observed[key] = {**observed.get(key, {}), "state": "conflict", "raw": "conflicting-duplicate"}
    return (expected, observed, meta, totals, dup, unknown,
            {"excluded_stale_config": excl_cfg, "excluded_wrong_src": excl_src,
             "excluded_no_metadata": excl_nometa, "conflicts": len(conflicts)})


def main():
    tags = sys.argv[1:]
    expected, observed, meta, totals, dup, unknown, excl = load(tags)
    # per survivor id (and REAL per task): verdict vector across kernels, not-run where unobserved
    surv = collections.defaultdict(dict)
    real = collections.defaultdict(dict)
    for (path, which, k), sid in expected.items():
        r = observed.get((path, which, k))
        state = (r or {}).get("state", "not-run")
        if which == "REAL":
            real[path][k] = state
        else:
            surv[which][k] = state
    n = len(surv)

    dec = lambda st: st in ("verified", "refuted")
    vec = lambda d: [d.get(k, "not-run") for k in KERNELS]
    fully = [sid for sid in surv if all(dec(surv[sid].get(k, "not-run")) for k in KERNELS)]
    unan_v = [sid for sid in fully if all(surv[sid][k] == "verified" for k in KERNELS)]
    unan_r = [sid for sid in fully if all(surv[sid][k] == "refuted" for k in KERNELS)]
    mixed = [sid for sid in fully if sid not in unan_v and sid not in unan_r]
    not_fully = n - len(fully)

    print("## E1 (fixed) — fully-adjudicated mutant matrix\n")
    print(f"Tags: {', '.join(tags)}. Tasks ok: {totals['tasks_ok']}. Survivors found: {totals['survivors_total']}; "
          f"frozen/selected: {totals['survivors_selected']} (selection cap hit on {totals['selection_capped']} tasks; "
          f"classify cap on {totals['classify_capped']}).\n")
    exp_n = len(expected); obs_n = len(observed)
    print(f"**Cell completeness (manifest-based):** {obs_n}/{exp_n} expected cells observed "
          f"({100*obs_n/max(exp_n,1):.1f}%); {exp_n-obs_n} not-run. A missing cell is `not-run`, never a "
          f"rejection.\n")
    print(f"Row hygiene: unknown records rejected: {unknown}; identical duplicates: {dup}; "
          f"**excluded stale-config rows: {excl['excluded_stale_config']}; excluded wrong-src rows: "
          f"{excl['excluded_wrong_src']}; excluded no-metadata rows (fail-closed): {excl['excluded_no_metadata']}; "
          f"conflicting duplicates flagged (not last-wins): {excl['conflicts']}**.\n")

    print("### Survivor taxonomy over the COMMON DENOMINATOR of fully-decided survivors\n")
    print(f"- Fully decided (all 7 kernels returned verified or refuted): **{len(fully)} / {n}** "
          f"({100*len(fully)/max(n,1):.0f}%). Not fully decided (>=1 unverifiable or not-run): {not_fully}.")
    if fully:
        print(f"- **Unanimous-verified** (all 7 accept): **{len(unan_v)}** "
              f"({100*len(unan_v)/len(fully):.0f}% of fully-decided) — spec-gap acceptances; a program differing from "
              f"the real one at its witness that every kernel proves. May include spec-permitted alternatives.")
        print(f"- **Unanimous-refuted** (all 7 reject): **{len(unan_r)}** ({100*len(unan_r)/len(fully):.0f}%) — the "
              f"kernels AGREE the mutant is wrong (not disagreement).")
        print(f"- **Mixed / cross-kernel disagreement** (some verify, some refute): **{len(mixed)}** "
              f"({100*len(mixed)/len(fully):.0f}%).\n")

    print("### Per-kernel adjudication (over all frozen survivors) + real-body verified\n")
    print("| kernel | backend | surv verified | surv refuted | surv unverifiable | surv not-run | real verified |")
    print("|---|---|--:|--:|--:|--:|--:|")
    for k in KERNELS:
        col = [surv[sid].get(k, "not-run") for sid in surv]
        sv = col.count("verified"); sr = col.count("refuted")
        su = sum(1 for x in col if x.startswith("unverifiable")); nr = col.count("not-run")
        rv = sum(1 for d in real.values() if d.get(k) == "verified")
        print(f"| {k} | {BACKEND[k]} | {sv} | {sr} | {su} | {nr} | {rv} |")

    reasons = collections.Counter()
    for sid in surv:
        for k in KERNELS:
            st = surv[sid].get(k, "not-run")
            if st.startswith("unverifiable") or st.startswith("refused"):
                reasons[st] += 1
    print("\n### Unverifiable / refused reasons (kept as their own states)\n")
    for r, c in reasons.most_common(12):
        print(f"- {r}: {c}")

    print("\n### Mixed-disagreement survivors (a real cross-kernel contradiction) — sample\n")
    for sid in mixed[:10]:
        m = meta.get(sid, {})
        v = {k: surv[sid][k] for k in KERNELS}
        print(f"- `{m.get('task')}` {m.get('op')} — {v}")
    print("\n### Unanimous-verified survivors (spec-gap acceptances) — sample for intended-incorrectness triage\n")
    for sid in unan_v[:10]:
        m = meta.get(sid, {})
        print(f"- `{m.get('task')}` {m.get('op')} — {m.get('witness')}")


if __name__ == "__main__":
    main()
