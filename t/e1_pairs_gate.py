#!/usr/bin/env python3
"""E1 — the twin-refutation seven-kernel gate over the 426 ARCHIVED real/twin pairs in t/twins/pairs,
run through the AUTHENTIC paired grounded-witness gate, NOT the direct-body audit path.

For each archived pair we take the stored real program, the stored twin, and the stored grounded witness,
lower them per kernel exactly as run_par/conformance do -- the real verified plainly, the twin with its
witness appended as the kernel's `t_refutation_certificate` (a goal the kernel must PROVE, so a genuine
REFUTED, never a body-only UNPROVED) -- and grade both through verifiers.cell_pair at flake n=3. The
per-kernel outcome is three-state: verified / refuted / unproved (and every other Outcome, e.g. timeout,
tool-error, carried verbatim as its own reason). Every lowered source is kept as the replayable certificate.

ASCERTAINMENT (report honestly): the 426 pairs were SELECTED for all-seven real-verification AND all-seven
twin-refutation (twins_artifact.py). This is therefore a CURATED reproducibility/adequacy population, not a
random sample. The measurement here is whether the recorded all-seven verdicts REPRODUCE under an independent
re-run, and where (if anywhere) a kernel now disagrees -- not a discovery of the gate's base rate on
unseen specs (that is the corpora-matrix milestone, a separate, direct-body measurement).

    python3 -I e1_pairs_gate.py run     <out-dir> [--jobs N] [--flake 3] [--limit N] [--only ID[,ID..]]
    python3 -I e1_pairs_gate.py replay  <out-dir> [--sample N]     # re-run kernels on stored sources, NO model
"""
import argparse
import hashlib
import json
import os
import pathlib
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
HOME = os.path.expanduser("~")
KDIRS = [f"{HOME}/.cargo/bin", f"{HOME}/.opam/default/bin", f"{HOME}/.elan/bin",
         f"{HOME}/.local/lean/bin", f"{HOME}/.local/fstar/fstar/bin",
         f"{HOME}/.local/gnatprove/gnatprove-x86_64-linux-16.1.0-1/bin",
         f"{HOME}/.local/verus/verus-x86-linux", f"{HOME}/.local/dafny"]
os.environ["PATH"] = ":".join(KDIRS) + ":" + os.environ.get("PATH", "")
os.environ.setdefault("T_LEAN_BIN", f"{HOME}/.local/lean/bin/lean")
sys.path.insert(0, HERE)

import surface          # noqa: E402
import run_par          # noqa: E402
import conformance      # noqa: E402  (reuse its pool-safe, module-level _cell)
import verifiers        # noqa: E402
from concurrent.futures import ProcessPoolExecutor, as_completed  # noqa: E402

PAIRS = pathlib.Path("twins/pairs")


def unfence(s: str) -> str:
    s = (s or "").strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else ""
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3]
    return s.strip()


def load_pairs(limit=0, only=None):
    out = []
    for p in sorted(PAIRS.glob("*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        if only and r.get("id") not in only:
            continue
        out.append(r)
    if limit:
        out = out[:limit]
    return out


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pair_cell(bname: str, pid: str, suffix: str, src_dir: str, flake_n: int):
    """Module-level (pool-safe) paired cell that RETAINS the full backend Result for real and twin -- unlike
    conformance._cell, which keeps only the outcome string. We need Result.error/budget/wall_ms/source_sha256
    for unverifiable-with-reason and for portable replay. cell_pair runs flake_check on both halves (2*n
    kernel calls per cell)."""
    import importlib
    backend = importlib.import_module(f"verifiers.{bname}")
    real = pathlib.Path(src_dir) / f"{pid}.{suffix}"
    twin = pathlib.Path(src_dir) / f"{pid}_twin.{suffix}"
    (r_real, a1), (r_twin, a2) = verifiers.cell_pair(backend.verify, real, twin, flake_n)
    return {"id": pid, "kernel": bname, "real": r_real.to_json(), "twin": r_twin.to_json(),
            "real_agreed": bool(a1), "twin_agreed": bool(a2)}


def lower_sources(pairs, present, src: pathlib.Path):
    """Lower real + twin per kernel into src/, sequential (as run_par.lower_and_dispatch). Returns
    (pending, meta): pending = [(bname, pairid, suffix)] cells to grade; meta = per-pair parse/lower record.
    A pair/kernel that fails to parse or lower is recorded with its reason, never silently dropped."""
    src.mkdir(parents=True, exist_ok=True)
    pending, meta = [], {}
    for r in pairs:
        pid = r["id"]
        w = r.get("witness") or {}
        m = {"id": pid, "task": r.get("task"), "problem": r.get("problem"), "operator": r.get("operator"),
             "written_by": r.get("written_by"), "witness_kind": w.get("_kind"),
             # archived labels kept ONLY for the reproducibility comparison; never used as a verdict here
             "archived_verified_by": r.get("verified_by"), "archived_twin_refuted_by": r.get("twin_refuted_by"),
             "lowered": {}, "lower_errors": {}}
        try:
            real_task = surface.parse(unfence(r["program"]))
            twin_task = surface.parse(unfence(r["twin"]))
        except Exception as e:  # noqa: BLE001
            m["parse_error"] = f"{type(e).__name__}: {e}"[:160]
            meta[pid] = m
            continue
        clean = {k: v for k, v in real_task.items() if not k.startswith("_")}
        twin_body = twin_task.get("body")
        m["witness_present"] = bool(w)
        for bname, lower, suffix in present:
            try:
                real_src = lower(clean, clean["body"])
            except Exception as e:  # noqa: BLE001
                m["lower_errors"][bname] = f"real:{type(e).__name__}:{e}"[:120]
                continue
            try:
                twin_src = lower(clean, twin_body, witness=w)
            except Exception as e:  # noqa: BLE001
                m["lower_errors"][bname] = f"twin:{type(e).__name__}:{e}"[:120]
                continue
            rp = src / f"{pid}.{suffix}"
            tp = src / f"{pid}_twin.{suffix}"
            rp.write_text(real_src, encoding="utf-8", newline="\n")
            tp.write_text(twin_src, encoding="utf-8", newline="\n")
            m["lowered"][bname] = {"suffix": suffix, "real_sha256": sha(rp), "twin_sha256": sha(tp)}
            pending.append((bname, pid, suffix))
        meta[pid] = m
    return pending, meta


def cmd_run(a):
    out = pathlib.Path(a.out_dir)
    src = out / "src"
    out.mkdir(parents=True, exist_ok=True)
    cols, present = run_par.probe_backends()
    pairs = load_pairs(a.limit, set(a.only.split(",")) if a.only else None)
    # shared-lab budget: cell_pair fires 2*flake kernel calls per cell, so true kernel-call concurrency is
    # 2*flake*jobs (before each backend's own subjobs). Keep it modest and keep T_SPARK_JOBS=1.
    jobs = a.jobs
    spark_env = run_par.spark_jobs_env(jobs)
    conc = {"cells_in_flight": jobs, "flake_n": a.flake, "kernel_calls_in_flight": 2 * a.flake * jobs,
            "spark_jobs_env": spark_env, "kernels": [b for b, _, _ in present]}
    print(f"E1-PAIRS: {len(pairs)} archived pairs x {len(present)} kernels "
          f"({[b for b,_,_ in present]}); flake={a.flake} cells_in_flight={jobs} "
          f"kernel_calls_in_flight={2*a.flake*jobs} T_SPARK_JOBS={spark_env.get('T_SPARK_JOBS')}", flush=True)

    ckpt = out / "E1PAIRS.jsonl"
    done = set()
    if ckpt.exists():
        for ln in ckpt.read_text().splitlines():
            try:
                done.add((json.loads(ln)["id"], json.loads(ln)["kernel"]))
            except Exception:  # noqa: BLE001
                pass
    pending, meta = lower_sources(pairs, present, src)
    (out / "E1PAIRS-meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    pending = [(b, pid, s) for (b, pid, s) in pending if (pid, b) not in done]
    print(f"  {len(pending)} (pair,kernel) cells to grade ({len(done)} already in checkpoint)", flush=True)

    ctx = verifiers.mp_context()
    versions = {}
    fh = ckpt.open("a", encoding="utf-8")
    n = 0
    if pending:
        with ProcessPoolExecutor(max_workers=jobs, mp_context=ctx, initializer=run_par._worker_env,
                                 initargs=(spark_env,)) as ex:
            futs = {ex.submit(_pair_cell, b, pid, s, str(src), a.flake): (b, pid, s)
                    for (b, pid, s) in pending}
            for fut in as_completed(futs):
                d = fut.result()
                pid, bname = d["id"], d["kernel"]
                m = meta.get(pid, {})
                versions.setdefault(bname, d["real"].get("backend_version"))
                rec = {"id": pid, "kernel": bname, "witness_kind": m.get("witness_kind"),
                       "suffix": m.get("lowered", {}).get(bname, {}).get("suffix"),
                       "real_outcome": d["real"]["outcome"], "twin_outcome": d["twin"]["outcome"],
                       "real_agreed": d["real_agreed"], "twin_agreed": d["twin_agreed"],
                       "real_sha256": d["real"].get("source_sha256"), "twin_sha256": d["twin"].get("source_sha256"),
                       "real_result": d["real"], "twin_result": d["twin"]}
                fh.write(json.dumps(rec) + "\n"); fh.flush(); n += 1
                if n % 50 == 0:
                    print(f"  .. graded {n}/{len(pending)}", flush=True)
    fh.close()
    (out / "E1PAIRS-versions.json").write_text(json.dumps(
        {"concurrency": conc, "versions": versions}, indent=2), encoding="utf-8")
    print(f"E1-PAIRS done: wrote {n} cells this run -> {ckpt}", flush=True)
    print("E1-PAIRS-RUN-COMPLETE", flush=True)
    return 0


def cmd_replay(a):
    """Replay certificates with NO model: re-run each kernel on the STORED lowered source and confirm the
    outcome (and that the bytes still hash to the recorded sha256). This is `dawnr check` in spirit --
    deterministic kernel replay, no LLM anywhere."""
    import importlib
    import random
    out = pathlib.Path(a.out_dir)
    src = out / "src"
    recs = [json.loads(l) for l in (out / "E1PAIRS.jsonl").read_text().splitlines() if l.strip()]
    run_par.probe_backends()
    # one replay unit per side (real, twin) that carried a decided outcome
    units = []
    for d in recs:
        for side in ("real", "twin"):
            outcome = d[f"{side}_outcome"]
            if outcome not in (verifiers.Outcome.VERIFIED, verifiers.Outcome.REFUTED):
                continue
            fn = f"{d['id']}{'_twin' if side == 'twin' else ''}.{d['suffix']}"
            units.append({"id": d["id"], "kernel": d["kernel"], "side": side,
                          "file": fn, "recorded_outcome": outcome,
                          "recorded_sha256": d.get(f"{side}_sha256")})
    if a.sample:
        random.Random(0).shuffle(units)
        units = units[:a.sample]
    ok = sha_ok = 0
    fails = []
    for u in units:
        p = src / u["file"]
        if not p.exists():
            fails.append({**u, "why": "source-missing"}); continue
        if u["recorded_sha256"] and sha(p) != u["recorded_sha256"]:
            fails.append({**u, "why": "sha-mismatch"}); continue
        sha_ok += 1
        backend = importlib.import_module(f"verifiers.{u['kernel']}")
        r, agreed = verifiers.flake_check(backend.verify, p, 3)
        if r.outcome == u["recorded_outcome"] and agreed:
            ok += 1
        else:
            fails.append({**u, "why": f"replayed {r.outcome} agreed={agreed}"})
    res = {"replayed": len(units), "sha_ok": sha_ok, "reproduced": ok,
           "reproduced_pct": round(100 * ok / max(1, len(units)), 2), "failures": fails[:50]}
    (out / "E1PAIRS-replay.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"replay: {ok}/{len(units)} reproduced ({res['reproduced_pct']}%); sha_ok={sha_ok}; "
          f"{len(fails)} failures -> {out / 'E1PAIRS-replay.json'}", flush=True)
    return 0 if not fails else 1


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("out_dir"); r.add_argument("--jobs", type=int, default=8)
    r.add_argument("--flake", type=int, default=3); r.add_argument("--limit", type=int, default=0)
    r.add_argument("--only", default=None); r.set_defaults(fn=cmd_run)
    rp = sub.add_parser("replay"); rp.add_argument("out_dir"); rp.add_argument("--sample", type=int, default=0)
    rp.set_defaults(fn=cmd_replay)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
