#!/usr/bin/env python3
"""ruler_noise.py — measure the new ruler's run-to-run noise floor, and decompose it.

WHY THIS EXISTS. Section 70 confirmed a 31-task band and published an MDE table
(k=5 -> 6.7pp ... k=25 -> 3.0pp) derived from ONE assumption it labelled
UNMEASURED: that per-task outcomes are independent within a run, so the run-level
sd is per_task_sd/sqrt(T) = 0.0376. Section 62 A1b measured that assumption
FAILING on the old held-in bank - observed sd came in 2.9x BELOW the independence
prediction because per-task deviations partly cancelled. Section 70's own words:
"Measuring it costs 10 runs of the null arm and should happen before any k is
chosen." Every generation budget downstream rests on this number, so it is
measured here before a k is picked.

WHAT MAKES THIS MORE THAN A REPEAT OF SECTION 61. That measurement (null sd
0.0129, 4.3x under a binomial prediction of 0.0557) was taken on a bank where
7 of 10 tasks sat at ceiling and 1 at floor. A saturated task contributes zero
variance, so "observed << predicted" there had a boring explanation available and
no way to rule it out. This ruler admits only [0.2, 0.8], so NO task is
saturated. If the shortfall survives here, saturation cannot be the cause.

THE DECOMPOSITION, which is the actual product. A shortfall against the binomial
prediction has three candidate causes, and they have different consequences:

  (1) The greedy anchor. eval.py takes sample 0 at temp 0.0, so it is ~constant
      across runs of one model and contributes ~no variance. With N_SAMPLES=5
      that alone predicts sd*sqrt(4/5) = 0.894x - a real effect, and far too
      small to explain 2.9x. Measured here by checking whether `greedy` actually
      is constant per task across runs, rather than assumed.
  (2) Marginal rates below the band-centre assumption. Handled by predicting from
      each task's OWN rate rather than from a pooled mean.
  (3) Negative covariance between tasks within a run - genuine cancellation, the
      section 62 A1b effect.

These separate cleanly, because
      Var(run mean) = (1/T^2) * [ sum_i Var_i + sum_{i!=j} Cov_ij ]
so comparing the OBSERVED run-level variance against the sum of the OBSERVED
per-task variances isolates the covariance term from the marginals. (1) and (2)
live in the marginals; (3) is whatever is left. Predicting and observing the same
quantity two ways is the only way to say which cause fired.

WHY IT REUSES eval.evaluate RATHER THAN SAMPLING ITSELF. The number has to be the
noise floor OF THE INSTRUMENT, not of a lookalike. eval_heldin_direct.py already
cost this project a result that had to be labelled "not comparable across stacks"
(section 61 non-claims) because it ran its own generation path. One
implementation, imported.

Run:
    python ruler_noise.py measure --runs 10      # GPU/Ollama; resumable
    python ruler_noise.py analyze                # CPU only; re-runnable
    python ruler_noise.py selftest               # CPU only; validates the stats
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from pathlib import Path

import dataset_gate
import eval as ev
import forge
import screen_tasks
# verifier_key lived here until analyze_run1.py needed the same pooling key.
# Importing this module to get it is not available to a CPU-only re-scoring
# script (dataset_gate SystemExits at import without a pinned verifier), and a
# second copy of a pooling rule is the failure that rule exists to prevent, so
# it moved to provenance.py -- stdlib only -- and is re-exported here.
from provenance import verifier_key  # noqa: F401

HERE = Path(__file__).resolve().parent
RULER = HERE / "data" / "ruler_confirmed.json"
SCREEN = HERE / "data" / "screen_results.jsonl"
OUT = HERE / "data" / "ruler_noise.jsonl"
STOP = HERE / "council" / "STOP"

TASK_SET = "ruler_v2_null"      # labels these rows so they can never be pooled
                                # with held_out or held_in series


# ---------------------------------------------------------------------------
# Incomplete gamma -> chi-square quantiles, so the variance CI is computed
# rather than typed. A hand-entered pair of critical values is exactly the
# "superseded figure retyped" class section 65/67 closed in screen_tasks.py;
# `selftest` checks these against published values instead.
# ---------------------------------------------------------------------------
def _gammap(a: float, x: float) -> float:
    """Regularized lower incomplete gamma P(a, x). Series below a+1, continued
    fraction above (Numerical Recipes 6.2)."""
    if x < 0 or a <= 0:
        raise ValueError("domain")
    if x == 0:
        return 0.0
    if x < a + 1.0:
        term = 1.0 / a
        total = term
        n = 0
        while abs(term) > abs(total) * 1e-15 and n < 10_000:
            n += 1
            term *= x / (a + n)
            total += term
        return total * math.exp(-x + a * math.log(x) - math.lgamma(a))
    # continued fraction for Q(a,x), then P = 1 - Q
    tiny = 1e-300
    b = x + 1.0 - a
    c = 1.0 / tiny
    d = 1.0 / b
    h = d
    for i in range(1, 10_000):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    q = math.exp(-x + a * math.log(x) - math.lgamma(a)) * h
    return 1.0 - q


def chi2_ppf(p: float, df: int) -> float:
    """Inverse chi-square CDF by bisection on _gammap. Plenty fast at this size."""
    lo, hi = 1e-9, 1e4
    for _ in range(300):
        mid = (lo + hi) / 2
        if _gammap(df / 2.0, mid / 2.0) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def sd_ci(s: float, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Chi-square CI for a normal sd. Reported because an sd from 10 runs is
    itself an estimate - section 70's own method note: n=1 is a rumour, and n=10
    is a number with a visible interval around it."""
    df = n - 1
    return (s * math.sqrt(df / chi2_ppf(1 - alpha / 2, df)),
            s * math.sqrt(df / chi2_ppf(alpha / 2, df)))


# ---------------------------------------------------------------------------
# The ruler tasks
# ---------------------------------------------------------------------------
def ruler_tasks() -> tuple[list[forge.Task], dict[str, float], str]:
    """Rebuild the 31 confirmed tasks and their confirmed rates.

    Tasks come from the payload screen_tasks.py stored on each admitted row
    (`rec["task"]`), NOT from a fresh parquet draw. build_ruler.confirm re-derived
    them by re-running candidates(--draw 500 --seed 1337) and matching tids, which
    silently depends on those two flags still matching the screen. The stored
    payload has no such coupling: the bytes that were screened are the bytes
    re-used here.
    """
    # THROUGH THE FREEZE GATE, not around it. Council activation #17 finding F2:
    # freeze wrote ruler_set_sha256 and nothing read it, so the freeze was a
    # comment. verify_frozen() re-hashes every task from its stored payload and
    # raises if the ruler on disk is not the ruler that was frozen; obtaining the
    # tasks through it is what makes the check unskippable.
    import build_ruler
    frozen = build_ruler.verify_frozen()
    kept = {t: rec["confirmed_rate"] for t, rec in frozen["ruler"].items()}
    print(f"[noise] frozen ruler verified: {len(kept)} tasks, "
          f"set sha256 {frozen['ruler_set_sha256'][:12]}...")

    payloads: dict[str, dict] = {}
    for line in SCREEN.open(encoding="utf-8"):
        r = json.loads(line)
        if r.get("admitted") and r.get("task") and r["tid"] in kept:
            payloads[r["tid"]] = r["task"]

    missing = sorted(set(kept) - set(payloads))
    if missing:
        raise SystemExit(
            f"{len(missing)} confirmed tids have no stored task payload in "
            f"{SCREEN.name}: {missing[:5]}. Refusing to measure a partial ruler.")

    tasks = [screen_tasks.as_task(payloads[t]) for t in sorted(kept)]
    return tasks, kept, frozen["model"]


# ---------------------------------------------------------------------------
def verifier_drift(baseline: dict, current: dict | None = None) -> dict:
    """Entries where the verifier on disk no longer matches `baseline`.

    Returns {name: (snapshot_value, disk_value)} for every entry that differs in
    either direction, including one that only one side has -- a fingerprint that
    GAINS or LOSES a file has changed what "verified" covers just as much as one
    whose hash moved. Empty means nothing moved.
    """
    cur = dataset_gate.verifier_fingerprint() if current is None else current
    return {k: (baseline.get(k), cur.get(k))
            for k in sorted(set(baseline) | set(cur))
            if baseline.get(k) != cur.get(k)}


def replicate_row(res: dict, replicate: int, verifier: dict) -> dict:
    """The banked row: one evaluate() result, numbered, carrying the WHOLE
    verifier it was scored by.

    THE INTERPRETER IS ONLY HALF OF "WHAT DECIDED CORRECT". Section 71 pinned the
    Python and taught eval.evaluate to record it, and the resume/pool rules above
    refuse to mix replicates whose `verifier["version"]` differs. That closes one
    way ground truth can move under a 40-replicate series. The other stayed open:
    forge.verify() is also its own source and its task source, so loosening
    BANNED, shortening CAND_TIMEOUT, dropping the return-type guard or
    re-screening a task changes what "correct" means while every row still
    records the same interpreter -- and the rows scored before and after are then
    indistinguishable in the file, silently pooled into one sd.

    dataset_gate already owns that scope decision for the dataset receipt
    (VERIFIER_FILES + TASK_SOURCE_FILES + SPLIT_FILES, whole files on purpose)
    and already computes it. It is IMPORTED here rather than re-derived, for the reason
    venv_guard.py exists: a second definition of "what the verifier is" would be
    free to drift from the first, which is the failure this row is meant to make
    visible.

    ADDITIVE, and deliberately so. The section 71 keys (`version`, `executable`,
    `pinned_away_from_launcher`, `launcher_version`) are what `measure` and
    `analyze` partition on, so they are merged LAST and cannot be displaced; the
    fingerprint's keys are filenames plus `interpreter`, which cannot collide
    with them. Rows already in the bank keep whatever they had -- they are
    evidence of the state they were written in, and nothing here rewrites them.
    Both readers reach the verifier dict through `.get`, so a row without these
    fields still parses exactly as before.

    THE SNAPSHOT IS PASSED IN, NOT RE-READ HERE, and the difference is the whole
    point. This function runs AFTER evaluate() has scored the replicate, so
    hashing the files at this moment records the state of the DISK at banking
    time -- while the code that actually reached the verdict is the state LOADED
    at import: forge and screen_tasks stay imported for the entire run, and
    `tasks` are built once before the loop. Edit forge.py while a 40-replicate
    run is in flight and a self-hashing builder writes rows claiming the NEW hash
    for verdicts produced by the OLD bytes. That is worse than the missing
    fingerprint this replaced, because it is a confident label that is false.
    Codex review, P1, on the first version of this fix. `measure` therefore takes
    the fingerprint ONCE before the loop, when it still describes the loaded
    modules, and hands it down; `verifier_drift` re-reads the disk before each
    row is banked so a mid-run edit ABORTS instead of mislabelling.

    HONEST RESIDUAL: the modules are imported before cmd_measure runs, so the
    snapshot is taken microseconds after the bytes that were loaded, not at the
    instant of loading. An edit landing inside that window is recorded as though
    it were the loaded state. Closing it would mean hashing at import time in
    every module; the drift check bounds everything after it.
    """
    return dict(res, replicate=replicate,
                verifier={**verifier, **(res.get("verifier") or {})})


# ---------------------------------------------------------------------------
def cmd_measure(args: argparse.Namespace) -> None:
    # THE SNAPSHOT OF WHAT WILL SCORE THESE REPLICATES, taken FIRST -- before the
    # tasks are built and before anything is generated. forge and screen_tasks
    # were imported at process start and stay loaded for the whole run, so this
    # is the fingerprint of the code that will actually reach every verdict
    # below. Every row is stamped with it, and it is re-checked against disk
    # before each row is banked (see replicate_row / verifier_drift).
    baseline = dataset_gate.verifier_fingerprint()
    tasks, rates, model = ruler_tasks()
    model = args.model or model

    # REPLICATES ARE ONLY INTERCHANGEABLE IF THE SAME PYTHON DECIDED "correct".
    # Section 71 found forge.verify inheriting its interpreter from the caller, so
    # rows banked before the pin were scored by a more permissive verifier (3.14
    # accepts unimported typing annotations, 3.11 does not) and 5 ruler tasks were
    # dead channels under it. Counting those toward `--runs` would silently pool
    # two instruments, which is the exact failure the fingerprint exists to stop.
    fp = forge.verifier_interpreter()
    done, foreign = 0, 0
    if OUT.exists():
        for line in OUT.open(encoding="utf-8"):
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("model") != model or r.get("task_set") != TASK_SET:
                continue
            if verifier_key(r) == verifier_key({"verifier": fp}):
                done += 1
            else:
                foreign += 1
    print(f"[noise] verifier {fp['version']} @ {fp['executable']}")
    if foreign:
        print(f"[noise] ignoring {foreign} replicate(s) banked under a different "
              f"verifier - they are kept in the file as evidence, not pooled")
    todo = max(0, args.runs - done)
    print(f"[noise] ruler {len(tasks)} tasks | model {model}")
    print(f"[noise] {done} replicate(s) already banked, {todo} to go "
          f"({len(tasks) * ev.N_SAMPLES} generations each)")
    if not todo:
        print("[noise] nothing to do; run `analyze`")
        return

    t0 = time.time()
    for i in range(done + 1, done + todo + 1):
        if STOP.exists():
            print("[noise] STOP file present - halting cleanly.")
            break
        print(f"\n=== replicate {i}/{args.runs} ===", flush=True)
        res = ev.evaluate(model, tasks=tasks, task_set=TASK_SET)
        if res is None:
            print("[noise] evaluate() returned None - aborting rather than "
                  "banking a partial replicate.")
            return
        # THE STRADDLE, CAUGHT INSTEAD OF LABELLED. `tasks` and the imported
        # forge/screen_tasks are the snapshot's bytes for the whole run, so a
        # file edited now cannot have scored this replicate. Banking it under
        # either fingerprint would be a lie in one direction or the other.
        moved = verifier_drift(baseline)
        if moved:
            for name, (was, now) in moved.items():
                print(f"[noise]   {name}: snapshot {str(was)[:16]}... "
                      f"on-disk {str(now)[:16]}...")
            print("[noise] the VERIFIER changed mid-run.")
            print("[noise] aborting rather than banking a row whose label would "
                  "not name the code that scored it. Re-run `measure`; the "
                  "replicates already in the file were scored by the snapshot "
                  "above and are unaffected.")
            return
        res = replicate_row(res, i, baseline)
        with OUT.open("a", encoding="utf-8") as f:
            f.write(json.dumps(res, ensure_ascii=False) + "\n")
        mins = (time.time() - t0) / 60
        print(f"[noise] replicate {i}: pass@1={res['aggregate']['pass@1']} "
              f"({mins:.1f}m elapsed)", flush=True)

    print(f"\n[noise] appended to {OUT}. Run `analyze`.")


def decompose(runs: list[dict], conf: dict[str, float]) -> dict:
    """All the arithmetic, separated from the printing so it can be tested.

    tests/test_ruler_noise.py drives this with SYNTHETIC runs whose dependence
    structure is known by construction: independent draws must come back at
    ratio ~1.0, a frozen greedy draw must come back at ~sqrt((N-1)/N) against the
    naive prediction and ~1.0 against the greedy-corrected one, and imposed
    cancellation must come back below 1. An analyzer that cannot recover an
    answer it was handed cannot be trusted to report a surprising one.
    """
    R = len(runs)
    tids = [p["tid"] for p in runs[0]["per_task"]]
    T = len(tids)
    N = runs[0]["n_samples"]

    obs: dict[str, list[float]] = {t: [] for t in tids}
    run_means: list[float] = []
    for r in runs:
        by = {p["tid"]: p for p in r["per_task"]}
        vals = []
        for t in tids:
            p = by[t]
            vals.append(p["correct"] / p["n"] if p["n"] else float("nan"))
            obs[t].append(vals[-1])
        run_means.append(sum(vals) / len(vals))

    s_obs = statistics.stdev(run_means)

    def indep_sd(p_of: dict[str, float], eff_n: float) -> float:
        v = sum(p_of[t] * (1 - p_of[t]) / eff_n for t in tids) / (T * T)
        return math.sqrt(v)

    obs_mean = {t: sum(obs[t]) / R for t in tids}
    per_task_var = {t: statistics.variance(obs[t]) for t in tids}
    sum_var = sum(per_task_var.values())
    var_run = s_obs * s_obs
    cov_total = var_run * T * T - sum_var          # sum_{i!=j} Cov_ij

    g_rate, s_rate = {}, {}
    for t in tids:
        gs = [p["greedy"] for r in runs for p in r["per_task"]
              if p["tid"] == t and p["greedy"] is not None]
        ss = [x for r in runs for p in r["per_task"]
              if p["tid"] == t for x in (p["sampled"] or [])]
        g_rate[t] = sum(gs) / len(gs) if gs else float("nan")
        s_rate[t] = sum(ss) / len(ss) if ss else float("nan")
    flip = [t for t in tids
            if len({p["greedy"] for r in runs for p in r["per_task"]
                    if p["tid"] == t}) > 1]

    return {
        "R": R, "T": T, "N": N, "tids": tids,
        "run_means": run_means, "sd_obs": s_obs, "sd_ci": sd_ci(s_obs, R),
        "obs": obs, "obs_mean": obs_mean,
        "pred_conf": indep_sd(conf, N),
        "pred_obsm": indep_sd(obs_mean, N),
        # Greedy-corrected: if sample 0 is constant across runs it contributes no
        # variance, leaving N-1 varying draws out of N -> Var = (N-1)p(1-p)/N^2.
        "pred_greedy": indep_sd(obs_mean, N * N / (N - 1)),
        "per_task_var": per_task_var, "sum_var": sum_var,
        "var_run": var_run, "cov_total": cov_total,
        "binom_var": sum(obs_mean[t] * (1 - obs_mean[t]) / N for t in tids),
        "g_rate": g_rate, "s_rate": s_rate, "greedy_flipped": flip,
    }


def cmd_analyze(args: argparse.Namespace) -> None:
    if not OUT.exists():
        raise SystemExit(f"no replicates at {OUT}; run `measure` first")
    runs = [json.loads(l) for l in OUT.open(encoding="utf-8")]
    runs = [r for r in runs if r.get("task_set") == TASK_SET]
    if args.model:
        runs = [r for r in runs if r["model"] == args.model]
    models = sorted({r["model"] for r in runs})
    if len(models) > 1:
        raise SystemExit(f"replicates span {models}; pass --model to pick one")

    # Same rule as `measure`: never pool across verifiers (section 71).
    vers = {verifier_key(r) for r in runs}
    if len(vers) > 1:
        want = ((args.verifier, None) if args.verifier
                else verifier_key({"verifier": forge.verifier_interpreter()}))
        kept = [r for r in runs
                if verifier_key(r) == want
                or (want[1] is None and verifier_key(r)[0] == want[0])]
        print(f"[!] replicates span {len(vers)} verifiers {sorted(vers)}.")
        print(f"[!] analyzing only the {len(kept)} row(s) scored by {want!r}. "
              f"Pass --verifier to choose another; they are NOT poolable "
              f"(section 71: the permissive reading made 5 tasks dead channels).")
        runs = kept
    R = len(runs)
    if R < 3:
        raise SystemExit(f"{R} replicate(s) is not a variance estimate")

    # ---- integrity: the added fields must reconcile with the score ---------
    bad = [(r["replicate"], p["tid"]) for r in runs for p in r["per_task"]
           if p["correct"] != (p.get("greedy") or 0) + sum(p.get("sampled") or [])]
    gen_err = sum(r["gen_errors_total"] for r in runs)
    print(f"REPLICATES {R} | model {models[0]} | tasks {runs[0]['n_tasks']} "
          f"| N_SAMPLES {runs[0]['n_samples']}")
    print(f"integrity: correct == greedy+sum(sampled) on all rows? "
          f"{'YES' if not bad else f'NO -> {bad[:5]}'}")
    print(f"generation errors across all replicates: {gen_err}")
    if bad:
        raise SystemExit("refusing to analyze rows whose own fields disagree")

    spec = json.loads(RULER.read_text(encoding="utf-8"))
    conf = {k["tid"]: k["confirmed_rate"] for k in spec["kept"]}
    d = decompose(runs, conf)
    tids, T, N = d["tids"], d["T"], d["N"]
    obs, obs_mean, run_means = d["obs"], d["obs_mean"], d["run_means"]
    s_obs = d["sd_obs"]
    lo, hi = d["sd_ci"]
    pred_conf, pred_obsm, pred_greedy = d["pred_conf"], d["pred_obsm"], d["pred_greedy"]
    per_task_var, sum_var = d["per_task_var"], d["sum_var"]
    var_run, cov_total = d["var_run"], d["cov_total"]
    g_rate, s_rate, flip = d["g_rate"], d["s_rate"], d["greedy_flipped"]

    print(f"\nOBSERVED run-level pass@1")
    print(f"  mean {statistics.fmean(run_means):.4f}   "
          f"per-run: {', '.join(f'{m:.4f}' for m in run_means)}")
    print(f"  sd   {s_obs:.4f}   95% CI [{lo:.4f}, {hi:.4f}]  (chi-square, df={R-1})")
    print(f"\nPREDICTED run-level sd, independence assumed")
    print(f"  from confirmed rates (section 70's own input)  {pred_conf:.4f}"
          f"   ratio obs/pred {s_obs / pred_conf:.2f}x")
    print(f"  from these runs' own mean rates               {pred_obsm:.4f}"
          f"   ratio obs/pred {s_obs / pred_obsm:.2f}x")
    print(f"  same, minus the constant greedy draw          {pred_greedy:.4f}"
          f"   ratio obs/pred {s_obs / pred_greedy:.2f}x")

    # ---- cause 1: is the greedy draw actually constant? -------------------
    print(f"\nCAUSE 1 - greedy anchor determinism")
    print(f"  tasks whose temp-0 draw was NOT constant across {R} runs: "
          f"{len(flip)}/{T}")
    if flip:
        print(f"  e.g. {flip[:6]}")
    print(f"  -> the greedy draw is {'NOT ' if flip else ''}a constant; "
          f"treating it as one explains a {pred_obsm / pred_greedy:.3f}x "
          f"reduction at most")

    # ---- cause 2/3: marginals vs covariance ------------------------------
    sd_from_obs_marginals = math.sqrt(sum_var / (T * T))
    denom = T * (T - 1)
    binom_var = d["binom_var"]
    print(f"\nCAUSE 2 - marginal (per-task) variance, observed vs binomial")
    print(f"  sum of OBSERVED per-task variances  {sum_var:.4f}")
    print(f"  sum of binomial predictions p(1-p)/N {binom_var:.4f}"
          f"   ratio {sum_var / binom_var:.2f}x")
    print(f"  run-level sd implied by observed marginals alone, if independent: "
          f"{sd_from_obs_marginals:.4f}")
    print(f"\nCAUSE 3 - covariance between tasks within a run (the residual)")
    print(f"  observed Var(run mean) {var_run:.6f} vs "
          f"sum_i Var_i / T^2 {sum_var / (T * T):.6f}")
    print(f"  implied sum of off-diagonal covariances {cov_total:+.4f}"
          f"  -> mean pairwise cov {cov_total / denom:+.5f}")
    mean_v = sum_var / T
    print(f"  mean pairwise correlation {cov_total / denom / mean_v:+.4f}"
          f"   ({'cancellation' if cov_total < 0 else 'reinforcement'})")

    # ---- the instrument seam ---------------------------------------------
    # build_ruler.confirm measured every task at PURE temp 0.8 (screen_tasks.rate).
    # eval.py scores 1 greedy draw + 4 at temp 0.8. Those are different
    # instruments, so "in band" under one does not imply "in band" under the
    # other -- if greedy reliably passes a task, the eval rate is pulled up by
    # 1/5 regardless of its temp-0.8 rate. The band exists to guarantee every
    # task can move in both directions AT EVAL TIME, so it is the eval
    # instrument's rate that has to satisfy it. Nothing has checked that.
    print(f"\nTHE INSTRUMENT SEAM - confirm measured pure temp 0.8; eval scores "
          f"1 greedy + {N-1} at 0.8")
    print(f"  mean greedy pass rate over tasks        "
          f"{statistics.fmean(g_rate.values()):.4f}")
    print(f"  mean temp-0.8 pass rate over tasks      "
          f"{statistics.fmean(s_rate.values()):.4f}")
    print(f"  mean confirmed rate (n=60, temp 0.8)    "
          f"{statistics.fmean(conf[t] for t in tids):.4f}")
    dev = [obs_mean[t] - conf[t] for t in tids]
    print(f"  eval-instrument rate minus confirmed:   mean {statistics.fmean(dev):+.4f}"
          f"   max |dev| {max(abs(d) for d in dev):.4f}")
    # The temp-0.8 half replicates what confirm measured, so it is a real
    # cross-check on the screen rather than a new quantity.
    dev8 = [s_rate[t] - conf[t] for t in tids]
    print(f"  temp-0.8 half minus confirmed (same     mean {statistics.fmean(dev8):+.4f}"
          f"   max |dev| {max(abs(d) for d in dev8):.4f}")
    print(f"    quantity, independent draw)")
    out_band = [(t, conf[t], obs_mean[t]) for t in tids
                if not (0.2 <= obs_mean[t] <= 0.8)]
    print(f"  tasks OUTSIDE [0.2,0.8] under the EVAL instrument: "
          f"{len(out_band)}/{T}")
    for t, c, o in sorted(out_band, key=lambda x: -abs(x[2] - 0.5)):
        print(f"    {t:<18} confirmed {c:.3f} -> eval-instrument {o:.3f} "
              f"(greedy {g_rate[t]:.2f}, temp0.8 {s_rate[t]:.2f})")
    pinned = [t for t in tids if obs_mean[t] in (0.0, 1.0)]
    print(f"  tasks pinned at 0.000 or 1.000 across all {R} runs "
          f"(zero variance, dead channel): {len(pinned)}"
          + (f" -> {pinned}" if pinned else ""))

    # ---- what it means for k ---------------------------------------------
    print(f"\nWHAT THIS DOES TO THE SECTION 70 TABLE")
    print(f"  {'k':>4} {'se_diff':>9} {'MDE@80%':>9} {'gens/arm':>10}   "
          f"(sd={s_obs:.4f} measured, vs {pred_conf:.4f} assumed)")
    for k in (5, 10, 20, 25):
        se = s_obs * math.sqrt(2.0 / k)
        print(f"  {k:>4} {se:>9.4f} {2.802 * se * 100:>8.1f}pp "
              f"{T * k * N:>10,}")
    print(f"  for reference, the same table at the CI's pessimistic end "
          f"(sd={hi:.4f}):")
    for k in (5, 10, 20, 25):
        se = hi * math.sqrt(2.0 / k)
        print(f"  {k:>4} {se:>9.4f} {2.802 * se * 100:>8.1f}pp "
              f"{T * k * N:>10,}")


def cmd_selftest(args: argparse.Namespace) -> None:
    """Validate the stats helpers against values that can be checked
    independently, so the CI in `analyze` is not resting on my arithmetic."""
    fails = 0

    # chi-square quantiles against published tables (Abramowitz & Stegun /
    # any standard table). Tolerance 1e-3 relative.
    known = {(0.025, 9): 2.7004, (0.975, 9): 19.0228,
             (0.025, 4): 0.4844, (0.975, 4): 11.1433,
             (0.05, 1): 0.003932, (0.95, 1): 3.8415,
             (0.5, 10): 9.3418}
    for (p, df), want in sorted(known.items()):
        got = chi2_ppf(p, df)
        ok = abs(got - want) / want < 1e-3
        fails += not ok
        print(f"  chi2_ppf({p}, df={df}) = {got:.5f}  want {want:.5f}  "
              f"{'ok' if ok else 'FAIL'}")

    # _gammap against the closed form for a=1: P(1,x) = 1 - exp(-x).
    for x in (0.1, 0.5, 1.0, 2.5, 12.0):
        got, want = _gammap(1.0, x), 1 - math.exp(-x)
        ok = abs(got - want) < 1e-12
        fails += not ok
        print(f"  P(1,{x}) = {got:.12f}  want {want:.12f}  "
              f"{'ok' if ok else 'FAIL'}")

    # sd_ci must bracket the point estimate and widen as n falls.
    a = sd_ci(1.0, 10)
    b = sd_ci(1.0, 5)
    ok = a[0] < 1.0 < a[1] and (b[1] - b[0]) > (a[1] - a[0])
    fails += not ok
    print(f"  sd_ci(1.0, 10)={a[0]:.3f}-{a[1]:.3f}  sd_ci(1.0, 5)="
          f"{b[0]:.3f}-{b[1]:.3f}  brackets & widens: {'ok' if ok else 'FAIL'}")

    # The independence formula must reproduce section 70's published table from
    # the confirmed artifact. If it cannot, one of the two is wrong.
    spec = json.loads(RULER.read_text(encoding="utf-8"))
    ps = [k["confirmed_rate"] for k in spec["kept"]]
    T, N = len(ps), ev.N_SAMPLES
    mpq = sum(p * (1 - p) for p in ps) / T
    per_task_sd = math.sqrt(mpq / N)
    run_sd = per_task_sd / math.sqrt(T)
    for got, want, label in ((T, 31, "T"), (round(mpq, 4), 0.2190, "mean p(1-p)"),
                             (round(per_task_sd, 4), 0.2093, "per-task sd"),
                             (round(run_sd, 4), 0.0376, "run-level sd")):
        ok = got == want
        fails += not ok
        print(f"  section 70 {label}: {got} want {want}  "
              f"{'ok' if ok else 'FAIL'}")

    print(f"\n{'ALL PASS' if not fails else f'{fails} FAILURE(S)'}")
    sys.exit(1 if fails else 0)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("measure")
    m.add_argument("--runs", type=int, default=10,
                   help="total replicates wanted; already-banked ones count")
    m.add_argument("--model", default=None,
                   help="default: the model recorded in ruler_confirmed.json")
    a = sub.add_parser("analyze")
    a.add_argument("--model", default=None)
    a.add_argument("--verifier", default=None,
                   help="verifier version to analyze when the file spans several; "
                        "default is the currently pinned one")
    sub.add_parser("selftest")
    args = ap.parse_args()
    {"measure": cmd_measure, "analyze": cmd_analyze,
     "selftest": cmd_selftest}[args.cmd](args)


if __name__ == "__main__":
    main()
