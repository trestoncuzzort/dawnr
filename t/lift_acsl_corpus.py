#!/usr/bin/env python3
"""t/lift_acsl_corpus.py -- lift ACSL by Example into t, check each lift against its C source,
gate it like every training document (2026-09-26).

    python3 t/lift_acsl_corpus.py --corpus DIR/acsl-by-example --out t/out/lifted-tasks-acsl-by-example \\
        --split t/out/loop/split-v5.json [--pool v5] [--wp-par 2] [--no-wp] [--no-gates]

Source: ACSL by Example, github.com/fraunhoferfokus/acsl-by-example (MIT, Fraunhofer FOKUS),
StandardAlgorithms/*/*.c: one C function per file, its contract in the .h beside it, named
logic definitions in Logic/*.acsl, every example proved by the corpus with Frama-C/WP
(-wp-rte, unsigned overflow checked; Results/*.json).

Stages, each a refusal by name, and everything written under <out>.meta/:
  1. front end   t/lift_acsl.py: C/ACSL -> the lifter's Dafny input (staged/*.dfy, staged/*.acsl.json),
                 or a refusal (front-refusals.jsonl)
  2. lifter      t/lifter.py --skip-check over staged/: Dafny -> t (lift/)
  3. check       t/lift_acsl_check.py: Frama-C/WP specification equivalence and a differential
                 run of the C function against the lifted task (check/<task>/), a trust level
                 per task (trust.jsonl)
  4. gates       the held-out ids under every alias and the dev split (loop_filter.TrainingDataGate),
                 and the behavioural twin rule over drawn inputs (lift_corpora.twin_of), exactly as
                 t/lift_corpora.py gates the Dafny lifts; the pool must be all here
  5. out         one task JSON per accepted task in --out, sidecars/, census (lift-census.json)

There is no English head: the corpus's prose lives in its PDF (ACSL-by-Example.pdf), not
beside each program, and nothing here writes one. Kernel grading is the next step:
t/run_par.py over --out (see t/LIFT-ACSL-BY-EXAMPLE.md).
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lift_acsl                                                  # noqa: E402
import lift_acsl_check                                            # noqa: E402

LICENSE = "MIT (Fraunhofer FOKUS, ACSL by Example)"
PREFIX = "acsl_"


def stage(root: Path, staged: Path) -> tuple[list[dict], dict]:
    """Every .c under root/*/ through the front end: (refusal rows, stem -> sidecar)."""
    if staged.exists():
        shutil.rmtree(staged)
    staged.mkdir(parents=True)
    refused, sides = [], {}
    for f in sorted(root.glob("*/*.c")):
        stem = PREFIX + f.stem
        try:
            lifted = lift_acsl.translate(f, root)
        except lift_acsl.AcslRefusal as r:
            refused.append({"file": f"{f.parent.name}/{f.name}", "reason": r.reason, "detail": r.detail,
                            "where": r.where})
            continue
        (staged / f"{stem}.dfy").write_text(lifted.dafny, encoding="utf-8", newline="\n")
        side = lifted.sidecar()
        side["c_file"] = str(f)
        side["source"] = f"{f.parent.name}/{f.name}"
        (staged / f"{stem}.acsl.json").write_text(json.dumps(side, indent=2, default=str) + "\n", encoding="utf-8")
        sides[stem] = side
    return refused, sides


def run_lifter(staged: Path, out: Path, jobs: int) -> dict:
    cmd = [sys.executable, str(HERE / "lifter.py"), "--dir", str(staged), "--out", str(out), "--jobs", str(jobs),
           "--skip-check", "--force"]
    subprocess.run(cmd, check=False)
    s = out / "run_summary.json"
    return json.loads(s.read_text()) if s.exists() else {}


def lifted_tasks(out: Path) -> list[tuple[str, Path, dict, dict]]:
    res = []
    for side in sorted(out.glob("*.lift.json")):
        tf = side.with_name(side.name[:-len(".lift.json")] + ".json")
        if tf.exists():
            res.append((tf.name.split(".", 1)[0], tf, json.loads(tf.read_text()), json.loads(side.read_text())))
    return res


def lifter_refusals(out: Path) -> list[dict]:
    rows = []
    for o in sorted(out.glob("*.outcome.json")):
        rec = json.loads(o.read_text())
        for key in ("resolve_refusal", "parse_refusal"):
            if rec.get(key):
                rows.append({"stem": o.name.split(".")[0], "reason": f"lifter:{rec[key]['reason']}",
                             "detail": rec[key].get("token")})
        for m in rec.get("methods", []):
            if m.get("refusal"):
                rows.append({"stem": o.name.split(".")[0], "reason": f"lifter:{m['refusal']['reason']}",
                             "detail": m["refusal"].get("token")})
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--corpus", required=True, help="a checkout of acsl-by-example")
    ap.add_argument("--out", required=True)
    ap.add_argument("--split", default=None, help="the split whose eval ids are held out (gates)")
    ap.add_argument("--pool", default="v5")
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--wp-par", type=int, default=2, help="prover processes (desktop: at most 2)")
    ap.add_argument("--wp-timeout", type=int, default=20)
    ap.add_argument("--no-wp", action="store_true")
    ap.add_argument("--no-gates", action="store_true", help="skip the pool gates (not for a corpus)")
    a = ap.parse_args(argv)
    corpus = Path(a.corpus)
    root = corpus / "StandardAlgorithms" if (corpus / "StandardAlgorithms").is_dir() else corpus
    out = Path(a.out)
    meta = out.with_name(out.name + ".meta")
    meta.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()

    gating = None
    if not a.no_gates:
        if not a.split:
            raise SystemExit("--split is required unless --no-gates")
        import lift_corpora
        import loop_filter
        import twin_draws
        gates, pool, index = lift_corpora.load_gating(a.split, a.pool)
        gate = loop_filter.TrainingDataGate(frozenset(gates.held_out | gates.dev))
        runner = twin_draws.runner(pool, lift_corpora.hung_path_for(out))
        gating = (gates, pool, index, gate, runner, lift_corpora)

    front_refused, sides = stage(root, meta / "staged")
    summary = run_lifter(meta / "staged", meta / "lift", a.jobs)
    lift_refused = lifter_refusals(meta / "lift")

    accepted, refused, trust_rows = [], [], []
    tally: Counter = Counter()
    for stem, tf, task, record in lifted_tasks(meta / "lift"):
        side = sides[stem]
        res = lift_acsl_check.check(task, record, side, root, meta / "check" / stem, par=a.wp_par,
                                    timeout=a.wp_timeout, wp=not a.no_wp)
        row = {"name": task["name"], "source": side["source"], "trust": res["trust"], "refusal": res["refusal"],
               "wp": {k: v for k, v in (res["wp"] or {}).items() if k != "log"}, "diff": res["diff"]}
        trust_rows.append(row)
        if res["refusal"]:
            tally["refused: " + res["refusal"]] += 1
            refused.append({"name": task["name"], "source": side["source"], "reason": res["refusal"]})
            continue
        if gating is not None:
            gates, pool, index, gate, runner, lc = gating
            import surface
            try:
                document = surface.print_task(task).strip() + "\n"
            except surface.SurfaceError as e:
                tally["refused: no t notation"] += 1
                refused.append({"name": task["name"], "source": side["source"], "reason": f"no t notation: {e}"})
                continue
            if not gate.admit(document, [task["name"]], []):
                tally["refused: gates"] += 1
                refused.append({"name": task["name"], "source": side["source"],
                                "reason": "held-out, listed or dev id under an alias"})
                continue
            evidence: list = []
            twin = lc.twin_of(task, index, pool, gates, runner, evidence)
            row["twin_check"] = evidence
            if twin is not None:
                tally["refused: twin"] += 1
                refused.append({"name": task["name"], "source": side["source"],
                                "reason": f"passes every test point of gated problem {twin[0]} ({twin[1]})"})
                continue
        tally["accepted"] += 1
        tally["trust: " + res["trust"]] += 1
        accepted.append((tf, task, stem))

    out.mkdir(parents=True, exist_ok=True)
    (meta / "sidecars").mkdir(exist_ok=True)
    for stale in out.glob("*.json"):
        stale.unlink()
    for tf, task, stem in accepted:
        shutil.copyfile(tf, out / tf.name)
        shutil.copyfile(tf.with_name(tf.name[:-5] + ".lift.json"), meta / "sidecars" / (tf.name[:-5] + ".lift.json"))
        shutil.copyfile(meta / "staged" / f"{stem}.acsl.json", meta / "sidecars" / f"{stem}.acsl.json")
    w = lambda name, rows: (meta / name).write_text("".join(json.dumps(r, sort_keys=True, default=str) + "\n"  # noqa: E731
                                                            for r in rows), encoding="utf-8")
    w("front-refusals.jsonl", front_refused)
    w("lifter-refusals.jsonl", lift_refused)
    w("refused.jsonl", refused)
    w("trust.jsonl", trust_rows)
    census = {
        "schema": 1, "when": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "github.com/fraunhoferfokus/acsl-by-example", "license": LICENSE,
        "c_files": len(list(root.glob("*/*.c"))), "front_end_lifted": len(sides),
        "front_end_refusals": dict(Counter(r["reason"] for r in front_refused).most_common()),
        "lifter_verdicts": summary.get("verdict_counts") or summary.get("verdicts"),
        "lifter_refusals": dict(Counter(r["reason"] for r in lift_refused).most_common()),
        "checked": len(trust_rows), "outcomes": dict(tally), "accepted": len(accepted),
        "wp": {"par": a.wp_par, "timeout": a.wp_timeout, "run": not a.no_wp},
        "gates": None if gating is None else {"split": a.split, "pool": a.pool, "pool_size": len(gating[1])},
        "wall_seconds": round(time.monotonic() - started, 1),
    }
    (meta / "lift-census.json").write_text(json.dumps(census, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(census, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
