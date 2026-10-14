#!/usr/bin/env python3
"""Exact-pair OBSERVATION certificate for the twin gate, replayed through the real `dawnr check` path.

Distinct from certificate.py's prove/ask/verify certificates (which bind only the real program and regenerate
their OWN sabotaged twin): a `paired-observation` certificate EMBEDS the exact archived real program, the exact
archived twin, and the grounded witness as source text (each a Statement subject, matched purely by sha256 per
in-toto Statement v1), plus the per-kernel OUTCOME and flake-agreement flags that were measured. `check`
replays with NO model: it recomputes the pair identity from the embedded sources, re-lowers the archived real
and the archived twin (twin WITH the witness -- the paired grounded-witness path), re-runs the kernel under the
RECORDED flake policy, and confirms the SAME outcomes AND stable agreement. This REPRODUCES THE OBSERVATION --
explicitly NOT a whole-program correctness proof (in-toto: the Statement binds; trust comes from the replay) --
and covers undecided (unproved/timeout) and refused (vacuous) observations. Any edit to the archived
real/twin/witness text, the pair id, the recorded outcome, or loss of stable agreement FAILS or is UNDECIDED.

dawnr-owned (bin/dawnr + t/certificate.py are tracked by dawnr, not the upstream engine), so this needs no
engine change; certificate.check() dispatches `kind == "paired-observation"` here.

    python3 -I obs_certificate.py mint  <pair.json> <kernel> <out.cert.json> [--flake N]
    python3 -I obs_certificate.py check <cert.json>                             # replay (no model)
    python3 -I obs_certificate.py --self-test
"""
import hashlib
import json
import os
import pathlib
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
# the seven-kernel PATH, so kernels resolve whether run directly or via certificate.check()'s dispatch
_HOME = os.path.expanduser("~")
for _d in [f"{_HOME}/.cargo/bin", f"{_HOME}/.opam/default/bin", f"{_HOME}/.elan/bin", f"{_HOME}/.local/lean/bin",
           f"{_HOME}/.local/fstar/fstar/bin", f"{_HOME}/.local/gnatprove/gnatprove-x86_64-linux-16.1.0-1/bin",
           f"{_HOME}/.local/verus/verus-x86-linux", f"{_HOME}/.local/dafny"]:
    if _d not in os.environ.get("PATH", ""):
        os.environ["PATH"] = _d + ":" + os.environ.get("PATH", "")
os.environ.setdefault("T_LEAN_BIN", f"{_HOME}/.local/lean/bin/lean")
# shared-lab politeness + match the study's recorded policy: one SPARK prover per call, never the adapter's
# 8-job fallback (the paired cell already fires 2*flake kernel calls). Replay re-applies the recorded policy.
os.environ.setdefault("T_SPARK_JOBS", "1")
DEFAULT_SPARK_JOBS = 1

STATEMENT = "https://in-toto.io/Statement/v1"
PREDICATE = "urn:dawnr:observation:v1"
RECORD_PREDICATE = "urn:dawnr:observation-record:v1"
VERSION = 1
KIND = "paired-observation"
RECORD_KIND = "observation-record-only"
REPRODUCED, FAILED, UNDECIDED = "reproduced", "failed", "undecided here"


def _sha(text):
    # same canonicalisation as the gate manifest's canon() (sort_keys + default=str), so a witness/contract
    # hash computed here matches the frozen manifest's.
    s = text if isinstance(text, str) else json.dumps(text, sort_keys=True, default=str)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _pair_id(real_t, twin_t):
    return hashlib.sha256((real_t + "\0" + twin_t).encode("utf-8")).hexdigest()[:16]


def _sha12(obj):
    return hashlib.sha1(json.dumps(obj, sort_keys=True).encode()).hexdigest()[:12]


def unfence(s):
    s = (s or "").strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else ""
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3]
    return s.strip()


def _contract_sha(real_t):
    """sha256 of the body-stripped (non-body) contract, so a body-only edit is distinguishable from a spec edit."""
    import surface
    t = surface.parse(real_t)
    contract = {k: v for k, v in t.items() if k != "body" and not k.startswith("_")}
    return hashlib.sha256(json.dumps(contract, sort_keys=True, default=str).encode()).hexdigest()


_RESULT_KEYS = ("backend", "backend_version", "source_sha256", "outcome", "ok", "exit_code", "wall_ms", "budget", "error", "extras")


def _result_fields(r):
    """Normalise a Result (object or dict) to the recorded-field dict, so the replay's freshly observed Result
    can be compared field-by-field against the certificate's recorded result_meta."""
    if r is None:
        return None
    if isinstance(r, dict):
        return r
    return {k: getattr(r, k, None) for k in _RESULT_KEYS}


def _lower_and_run(real_t, twin_t, witness, kernel, flake, spark_jobs=DEFAULT_SPARK_JOBS, spark_prover=None, verify_override=None):
    """Lower the archived real + twin (twin WITH witness) for one kernel and grade via the paired cell under the
    RECORDED resource policy (flake + T_SPARK_JOBS + SPARK prover). Returns (real_outcome, twin_outcome,
    real_agreed, twin_agreed, real_src_sha, twin_src_sha, real_result, twin_result) or raises; the two Result
    dicts are None on the verify_override path. The twin is grafted onto the real's contract -- sound only
    because check() enforces real/twin non-body contract EQUALITY first."""
    import surface
    import run_par
    import verifiers
    os.environ["T_SPARK_JOBS"] = str(spark_jobs or DEFAULT_SPARK_JOBS)   # recorded policy; never the 8-job fallback
    if spark_prover:                                                    # recorded SPARK prover policy, when pinned
        os.environ["T_SPARK_PROVER"] = str(spark_prover)
    real_task = surface.parse(real_t)
    twin_task = surface.parse(twin_t)
    clean = {k: v for k, v in real_task.items() if not k.startswith("_")}
    _cols, present = run_par.probe_backends()
    pm = {b: (low, suf) for b, low, suf in present}
    if kernel not in pm:
        raise RuntimeError(f"kernel {kernel} not available on this machine")
    lower, suffix = pm[kernel]
    import tempfile
    work = pathlib.Path(tempfile.mkdtemp(prefix="obs-"))
    rp = work / f"real.{suffix}"; tp = work / f"twin.{suffix}"
    real_src = lower(clean, clean["body"]); twin_src = lower(clean, twin_task.get("body"), witness=witness)
    rp.write_bytes(real_src.encode("utf-8")); tp.write_bytes(twin_src.encode("utf-8"))
    rh = hashlib.sha256(real_src.encode("utf-8")).hexdigest(); th = hashlib.sha256(twin_src.encode("utf-8")).hexdigest()
    if verify_override is not None:
        ro, ra = verify_override(str(rp)); to, ta = verify_override(str(tp))
        return ro, to, ra, ta, rh, th, None, None               # stub replay: no full Result to bind
    import importlib
    backend = importlib.import_module(f"verifiers.{kernel}")
    (r_real, a1), (r_twin, a2) = verifiers.cell_pair(backend.verify, rp, tp, flake)
    return r_real.outcome, r_twin.outcome, bool(a1), bool(a2), rh, th, _result_fields(r_real), _result_fields(r_twin)


def mint(pair_path, kernel, out_path, flake=3, spark_jobs=DEFAULT_SPARK_JOBS, verify_override=None):
    r = json.loads(pathlib.Path(pair_path).read_text())
    real_t, twin_t = unfence(r["program"]), unfence(r["twin"])
    w = r.get("witness")
    if _contract_sha(real_t) != _contract_sha(twin_t):          # refuse to attest a twin that is not a twin
        print("REFUSED mint: real/twin non-body contracts differ; not a valid twin of the real."); return 5
    ro, to, ra, ta, _rh, _th, _rr, _tr = _lower_and_run(real_t, twin_t, w, kernel, flake, spark_jobs=spark_jobs, verify_override=verify_override)
    if not (ra and ta):
        print(f"REFUSED mint: the measured observation is not flake-stable (real_agreed={ra} twin_agreed={ta}); "
              f"a certificate must record a stable observation."); return 4
    pid = _pair_id(real_t, twin_t)
    predicate = {"version": VERSION, "kind": KIND, "pair": pid, "task": r.get("task"),
                 "kernel": kernel, "flake": flake, "spark_jobs": spark_jobs, "witness": w, "witness_kind": (w or {}).get("_kind"),
                 "real_program": real_t, "twin_program": twin_t, "contract_sha256": _contract_sha(real_t),
                 "observed": {"real_outcome": ro, "twin_outcome": to, "real_agreed": ra, "twin_agreed": ta},
                 "semantics": "reproduces the measured OBSERVATION under re-run; NOT whole-program correctness"}
    cert = {"_type": STATEMENT, "predicateType": PREDICATE, "predicate": predicate,
            "subject": [{"name": "real.t", "digest": {"sha256": _sha(real_t)}},
                        {"name": "twin.t", "digest": {"sha256": _sha(twin_t)}},
                        {"name": "witness", "digest": {"sha256": _sha(w)}}]}
    pathlib.Path(out_path).write_text(json.dumps(cert, indent=1), encoding="utf-8")
    print(f"minted paired-observation cert ({kernel}: real={ro} twin={to}, stable) -> {out_path}")
    return 0


def make_record(pair, kernel, state, reason, identity, eff_config_id, manifest_config_id, witness_kind=None, partial_result=None):
    """A native-checkable observation-record-only certificate for a cell where NO kernel observation exists
    (parse/lower error, backend unavailable, input drift, worker failure, conflict). It embeds the pair's
    identity hashes as subjects and carries the typed state + reason + config, so `dawnr check` can verify its
    identity and report it explicitly (UNDECIDED), never an empty-denominator success."""
    pred = {"version": VERSION, "kind": RECORD_KIND, "pair": pair, "kernel": kernel, "state": state,
            "reason": reason, "witness_kind": witness_kind, "identity": identity, "partial_result": partial_result,
            "eff_config_id": eff_config_id, "manifest_config_id": manifest_config_id,
            "semantics": "no admissible stable/replayable observation established for this cell (a kernel may or "
                         "may not have run -- e.g. unstable/conflict/worker/source-corruption); carries its "
                         "reason + any partial result; never a reproduction and never a proof"}
    return {"_type": STATEMENT, "predicateType": RECORD_PREDICATE, "predicate": pred,
            "subject": [{"name": "program_sha256", "digest": {"sha256": identity.get("program_sha256")}},
                        {"name": "twin_sha256", "digest": {"sha256": identity.get("twin_sha256")}},
                        {"name": "witness_sha256", "digest": {"sha256": identity.get("witness_sha256")}}]}


def check_record(cert):
    """Replay a record-only certificate: verify its identity subjects are present and self-consistent, then
    report its recorded reason. Verdict is UNDECIDED (there is no kernel observation to reproduce) -- NEVER
    REPRODUCED. This keeps typed/absent cells explicit instead of a vacuous success."""
    steps = []

    def step(w, r, d=""):
        steps.append({"what": w, "result": r, "detail": d}); return r != "FAILED"
    pred = cert.get("predicate") if isinstance(cert, dict) else None
    out = {"verdict": FAILED, "steps": steps, "kind": RECORD_KIND,
           "semantics": "no admissible stable/replayable observation established for this cell (a kernel may or "
                        "may not have run); carries its reason; never a reproduction and never a proof"}
    if (not isinstance(pred, dict) or cert.get("_type") != STATEMENT or cert.get("predicateType") != RECORD_PREDICATE
            or pred.get("kind") != RECORD_KIND):
        step("certificate", "FAILED", f"not a dawnr observation-record certificate v{VERSION}"); return out
    ident = pred.get("identity") or {}
    subj = {s.get("name"): (s.get("digest") or {}).get("sha256") for s in cert.get("subject") or []}
    if not ident or not subj:
        step("identity", "FAILED", "record carries no identity/subjects to verify"); return out
    for k in ("program_sha256", "twin_sha256", "witness_sha256"):
        if not ident.get(k) or ident.get(k) != subj.get(k):
            step("identity", "FAILED", f"subject {k} absent or != embedded identity"); return out
    step("identity", "ok", "pair identity hashes present and self-consistent")
    step("record", "not checked here", f"{pred.get('state')}: {pred.get('reason')}")
    out.update(verdict=UNDECIDED, record_state=pred.get("state"), reason=pred.get("reason"),
               eff_config_id=pred.get("eff_config_id"))
    return out


def render(rep):
    if rep.get("kind") == RECORD_KIND:
        lines = [f"OBSERVATION-RECORD ({rep['verdict']}): {rep.get('record_state')}"
                 + (f" -- {rep.get('reason')}" if rep.get("reason") else "")]
        for s in rep["steps"]:
            lines.append(f"  - {s['what']}: {s['result']}" + (f" ({s['detail']})" if s.get("detail") else ""))
        lines.append("  no admissible stable/replayable observation established for this cell -- NOT a proof, "
                     "NOT a reproduction (a kernel may or may not have run; see the reason)")
        return "\n".join(lines)
    """Observation-only rendering -- NEVER 'proved here' (that is certificate.py's prove-cert language). An
    unproved/timeout twin reads as an unverifiable observation, not a proof."""
    lines = [f"paired-observation certificate: {rep['verdict']}"]
    for s in rep["steps"]:
        lines.append(f"  - {s['what']}: {s['result']}" + (f" ({s['detail']})" if s.get("detail") else ""))
    if "replayed" in rep:
        rp = rep["replayed"]
        lines.append(f"  observed-again (no model): real {rp['real_outcome']}, twin {rp['twin_outcome']} "
                     f"[stable real={rp['real_agreed']} twin={rp['twin_agreed']}] -- an OBSERVATION, not a correctness proof")
    return "\n".join(lines)


def check(cert, spec=None, kernels=None, jobs=2, verify_override=None):
    """Replay a paired-observation certificate with NO model, honouring the `dawnr check` CLI contract: a
    supplied `spec` (the real program must keep it), a `kernels` filter (an excluded recorded kernel is NOT run
    -> UNDECIDED), and `jobs`. kernels is a set/list of selected kernel names, or None/empty for all."""
    steps = []
    kernels = set(kernels) if kernels else None

    def step(what, result, detail=""):
        steps.append({"what": what, "result": result, "detail": detail}); return result != "FAILED"
    pred = cert.get("predicate") if isinstance(cert, dict) else None
    out = {"verdict": FAILED, "steps": steps, "kind": KIND,
           "semantics": "observation replay (no model); not a whole-program correctness proof"}
    if (not isinstance(pred, dict) or cert.get("_type") != STATEMENT or cert.get("predicateType") != PREDICATE
            or pred.get("version") != VERSION or pred.get("kind") != KIND):
        step("certificate", "FAILED", f"not a dawnr paired-observation certificate v{VERSION}"); return out
    real_t, twin_t, w = pred.get("real_program"), pred.get("twin_program"), pred.get("witness")
    if not isinstance(real_t, str) or not isinstance(twin_t, str):
        step("payload", "FAILED", "certificate does not embed the archived real/twin program text"); return out
    # subject digests must match the embedded text (in-toto: subjects matched by digest)
    subj = {s.get("name"): (s.get("digest") or {}).get("sha256") for s in cert.get("subject") or []}
    if subj.get("real.t") != _sha(real_t) or subj.get("twin.t") != _sha(twin_t) or subj.get("witness") != _sha(w):
        step("subject-digests", "FAILED", "embedded real/twin/witness text does not match its subject digest"); return out
    step("subject-digests", "ok", "real/twin/witness text match their digests")
    # INPUT-TO-SOURCE binding: recompute the pair id from the embedded sources (a self-digest is not enough).
    if pred.get("pair") != _pair_id(real_t, twin_t):
        step("pair-identity", "FAILED",
             f"pair id {pred.get('pair')} != sha256(real\\0twin)[:16] {_pair_id(real_t, twin_t)}"); return out
    try:
        c_real, c_twin = _contract_sha(real_t), _contract_sha(twin_t)
    except Exception as e:  # noqa: BLE001
        step("contract-identity", "FAILED", f"cannot parse embedded real/twin program: {e}"[:120]); return out
    if c_real != pred.get("contract_sha256"):
        step("contract-identity", "FAILED", "non-body contract hash does not match the embedded real program"); return out
    # the twin MUST share the real's non-body contract (that is what makes it a twin). Without this, a payload
    # could embed a twin with a weakened spec while the replay silently graded the body under the real's spec.
    if c_real != c_twin:
        step("contract-equality", "FAILED",
             "the embedded twin's non-body contract differs from the real's; it is not a valid twin of it"); return out
    step("identity", "ok", "pair id + real/twin non-body contract equality recomputed from the embedded sources")
    # honour an explicit --kernels filter: an excluded recorded kernel is NOT silently run.
    if kernels is not None and pred.get("kernel") not in kernels:
        step("kernel-filter", "not checked here",
             f"the certificate's kernel {pred.get('kernel')} is excluded by --kernels {sorted(kernels)}")
        out["verdict"] = UNDECIDED; return out
    # honour a supplied --spec: the real program must keep it (same contract as certificate.check's generic path).
    if spec is not None:
        import surface
        import spec_given
        try:
            changed = spec_given.kept(spec, surface.parse(real_t))
        except Exception as e:  # noqa: BLE001
            step("specification", "FAILED", f"cannot check the given specification: {e}"[:120]); return out
        if changed is not None:
            step("specification kept", "FAILED", f"the real program does not keep the given specification: {changed}"); return out
        step("specification kept", "ok", "the real program keeps the given specification")
    obs = pred.get("observed") or {}
    if not (obs.get("real_agreed") is True and obs.get("twin_agreed") is True):
        step("recorded-stability", "FAILED", "certificate records an unstable observation (agreed flags not both True)"); return out
    # ---- RUN-BACKED PROVENANCE: ONE consistency chain, validated FAIL-CLOSED before any prover runs ----
    # Structural mode first. The key ABSENT => an ad-hoc certificate (narrower scope, reported plainly). The key
    # PRESENT but malformed (null / list / scalar / missing fields) => a STRUCTURAL failure, never a silent
    # downgrade to ad-hoc, never an AttributeError. When present and well-formed, the replay DERIVES its flake +
    # SPARK policy FROM the hash-bound config (not from a top-level field an edit could lower), binds the full
    # recorded Result to the freshly observed one, and binds the recorded lowered-source digests.
    rb_present = "run_backed" in pred
    rb = pred.get("run_backed")
    use_flake = pred.get("flake", 3)
    use_spark_jobs = pred.get("spark_jobs", DEFAULT_SPARK_JOBS)
    use_spark_prover = None
    if rb_present and not isinstance(rb, dict):
        step("run-backed-structure", "FAILED",
             f"run_backed present but not an object (type {type(rb).__name__}); a present provenance block must "
             f"be well-formed -- it is never downgraded to ad-hoc"); return out
    if not rb_present:
        step("run-backed", "not checked here",
             "ad-hoc certificate: no run-backed provenance block, so no run's recorded Result/config/policy is "
             "bound; the replay reproduces the embedded observation only (narrower scope)")
    else:
        req = ("eff_config_id", "manifest_config_id", "eff_config", "base_config",
               "run_real_src_sha256", "run_twin_src_sha256")
        missing = [k for k in req if not rb.get(k)]
        if missing:
            step("run-backed-fields", "FAILED", f"missing/empty required run-backed binding fields: {missing}"); return out
        ec, bc = rb["eff_config"], rb["base_config"]
        # (1) eff_config AND base_config each recompute to their ids. base_config is the FULL manifest config
        #     (flake_n / spark_prover / kernel versions / engine+harness source hashes), not an opaque base id,
        #     so the policy fields read below are hash-bound and cannot be edited without breaking this.
        if not isinstance(ec, dict) or _sha12(ec) != rb["eff_config_id"]:
            step("run-backed-config", "FAILED", f"eff_config_id {rb['eff_config_id']} != recompute(eff_config)"); return out
        if not isinstance(bc, dict) or _sha12(bc) != rb["manifest_config_id"]:
            step("run-backed-config", "FAILED",
                 f"manifest_config_id {rb['manifest_config_id']} != recompute(base_config) "
                 f"{_sha12(bc) if isinstance(bc, dict) else 'n/a'}"); return out
        if ec.get("base") != rb["manifest_config_id"]:
            step("run-backed-config", "FAILED", f"eff_config.base {ec.get('base')} != manifest_config_id {rb['manifest_config_id']}"); return out
        # (2) result_meta present, well-formed, backend == this kernel.
        rm = pred.get("result_meta") or {}
        rmr, rmt = rm.get("real"), rm.get("twin")
        if not isinstance(rmr, dict) or not isinstance(rmt, dict):
            step("run-backed-result", "FAILED", "result_meta.real/twin missing or not objects"); return out
        if rmr.get("backend") != pred.get("kernel") or rmt.get("backend") != pred.get("kernel"):
            step("run-backed-result", "FAILED",
                 f"result_meta backend != certificate kernel {pred.get('kernel')} "
                 f"(real {rmr.get('backend')}, twin {rmt.get('backend')})"); return out
        # (3) internal consistency (cheap): the cert's two records of the SAME measurement must agree, and the
        #     recorded Result source hashes must equal the recorded run source hashes -- so a lone result_meta
        #     outcome or source edit is caught here, before the prover, even if the replay would re-observe it.
        if rmr.get("outcome") != obs.get("real_outcome") or rmt.get("outcome") != obs.get("twin_outcome"):
            step("run-backed-consistency", "FAILED",
                 f"result_meta outcome != recorded observation (real {rmr.get('outcome')} vs {obs.get('real_outcome')}, "
                 f"twin {rmt.get('outcome')} vs {obs.get('twin_outcome')})"); return out
        if rmr.get("source_sha256") != rb["run_real_src_sha256"] or rmt.get("source_sha256") != rb["run_twin_src_sha256"]:
            step("run-backed-consistency", "FAILED", "result_meta.source_sha256 != recorded run source hash"); return out
        # (4) RECIPE POLICY binding: the certificate's flake + spark_jobs must EQUAL the hash-bound config, and
        #     the replay APPLIES that config's policy -- a top-level flake 3->1 or spark_jobs 1->99 edit (which an
        #     opaque base id could not constrain) now fails, and the measured flake/SPARK is what actually runs.
        rec_flake = bc.get("flake_n")
        if not isinstance(rec_flake, int):
            step("run-backed-policy", "FAILED", f"recorded base_config has no integer flake_n ({rec_flake!r})"); return out
        if pred.get("flake") != rec_flake:
            step("run-backed-policy", "FAILED",
                 f"certificate flake {pred.get('flake')} != recorded hash-bound flake_n {rec_flake} "
                 f"(the replay must use the measured flake policy)"); return out
        # SPARK per-cell effective policy = the gnatprove jobs the ADAPTER actually used, recorded in BOTH
        # Results' extras. eff_config.spark_env is only a worker-env UPDATE: an EMPTY dict is UNKNOWN about the
        # inherited policy (do not bind, never read as jobs=1), but an EXPLICIT value IS a real override and must
        # agree with the Results; a present top-level spark_jobs must agree too. A missing extras policy stays
        # UNBOUND -- the replay may still RUN at the politeness default, but that fallback is never presented as
        # the recorded policy. (Do not derive from one Result and ignore contradictory recorded fields.)
        rec_spark_jobs = None
        if pred.get("kernel") == "spark":
            gjr = (rmr.get("extras") or {}).get("gnatprove_jobs")
            gjt = (rmt.get("extras") or {}).get("gnatprove_jobs")
            if gjr is not None and gjt is not None and gjr != gjt:
                step("run-backed-spark-policy", "FAILED",
                     f"recorded gnatprove_jobs differ across Results (real {gjr!r} vs twin {gjt!r})"); return out
            rec = gjr if gjr is not None else gjt
            if rec is not None:
                try:
                    rec_spark_jobs = int(rec)
                except (TypeError, ValueError):
                    step("run-backed-spark-policy", "FAILED", f"recorded gnatprove_jobs is not an integer ({rec!r})"); return out
                eff_sj = (ec.get("spark_env") or {}).get("T_SPARK_JOBS")   # worker-env UPDATE: explicit override if non-blank
                if eff_sj is not None and str(eff_sj).strip():
                    try:
                        eff_sj_i = int(str(eff_sj).strip())
                    except ValueError:
                        step("run-backed-spark-policy", "FAILED", f"explicit eff_config.spark_env T_SPARK_JOBS not an integer ({eff_sj!r})"); return out
                    if eff_sj_i != rec_spark_jobs:
                        step("run-backed-spark-policy", "FAILED",
                             f"explicit eff_config.spark_env T_SPARK_JOBS {eff_sj_i} contradicts recorded gnatprove_jobs {rec_spark_jobs}"); return out
                if pred.get("spark_jobs") is not None and pred.get("spark_jobs") != rec_spark_jobs:
                    step("run-backed-spark-policy", "FAILED",
                         f"top-level spark_jobs {pred.get('spark_jobs')} contradicts recorded gnatprove_jobs {rec_spark_jobs}"); return out
        use_flake = rec_flake
        use_spark_jobs = rec_spark_jobs if rec_spark_jobs is not None else DEFAULT_SPARK_JOBS
        use_spark_prover = bc.get("spark_prover")
        step("run-backed-fields", "ok",
             "eff_config+base_config recompute to their ids, backends+outcomes+sources consistent, flake bound to "
             "the hash-bound config; SPARK per-cell jobs taken from Result.extras, not the worker-env-update dict")
        rr_ref = rb.get("run_ref") or {}
        if rr_ref:                                                  # concrete source-run provenance (retained, not re-verified here): names WHICH run + the exact record, so identical-config runs are distinguishable
            step("run-provenance", "not checked here",
                 f"source run manifest {str(rr_ref.get('manifest_sha256'))[:12]} / checkpoint "
                 f"{str(rr_ref.get('checkpoint_sha256'))[:12]} / record {str(rr_ref.get('record_sha256'))[:12]}")
    try:
        ro, to, ra, ta, rh, th, rr_obs, tr_obs = _lower_and_run(
            real_t, twin_t, w, pred["kernel"], use_flake, spark_jobs=use_spark_jobs,
            spark_prover=use_spark_prover, verify_override=verify_override)
    except Exception as e:  # noqa: BLE001
        step("replay", "not checked here", f"{type(e).__name__}: {e}"[:160]); out["verdict"] = UNDECIDED; return out
    out["replayed"] = {"real_outcome": ro, "twin_outcome": to, "real_agreed": ra, "twin_agreed": ta,
                       "real_src_sha256": rh, "twin_src_sha256": th}
    if rb_present:                                              # fields already validated present + consistent above
        # (5) the run-backed cert claims a specific run's lowered sources; the replay must re-lower to the SAME
        #     digests, else the lowering recipe changed (or run_backed was tampered).
        if rh != rb["run_real_src_sha256"] or th != rb["run_twin_src_sha256"]:
            step("run-backed-binding", "FAILED",
                 f"re-lowered source sha != recorded run source (recipe changed or tampered): "
                 f"real {rh[:8]} vs {rb['run_real_src_sha256'][:8]}, twin {th[:8]} vs {rb['run_twin_src_sha256'][:8]}")
            return out
        step("run-backed-binding", "ok", "re-lowered sources match the recorded run digests")
        # (6) full-Result FIDELITY: when the replay produced real Results (not the override stub), every
        #     consistency-relevant recorded field must match what was FRESHLY observed -- outcome / ok /
        #     source_sha256 / backend / backend_version / budget. wall_ms is provenance, NOT an equality target,
        #     and is excluded; a version or budget edit now fails here instead of silently reproducing.
        rm = pred.get("result_meta") or {}
        fidelity = ("backend", "backend_version", "source_sha256", "outcome", "ok", "budget")
        for side, recorded, observed in (("real", rm.get("real") or {}, rr_obs), ("twin", rm.get("twin") or {}, tr_obs)):
            if observed is None:
                continue                                        # override/stub replay: no observed Result to bind
            for f in fidelity:
                if recorded.get(f) != observed.get(f):
                    step("run-backed-result-fidelity", "FAILED",
                         f"{side}.{f}: recorded {recorded.get(f)!r} != freshly observed {observed.get(f)!r} "
                         f"(wall_ms excluded as provenance)"); return out
        if rr_obs is not None and tr_obs is not None:
            step("run-backed-result-fidelity", "ok",
                 "recorded full Result matches the freshly observed Result on outcome/ok/source/version/budget (wall_ms excluded)")
            # SPARK per-cell policy fidelity: the gnatprove jobs actually used must match what was recorded in
            # extras. This is per-cell policy (global sweep jobs/memory/walltime stay provenance). When the
            # archived Result carries no gnatprove_jobs, the cert REPORTS it is unbound -- never assumes jobs=1.
            if pred.get("kernel") == "spark":
                bound = True
                for side, recorded, observed in (("real", rm.get("real") or {}, rr_obs), ("twin", rm.get("twin") or {}, tr_obs)):
                    rgj = (recorded.get("extras") or {}).get("gnatprove_jobs")
                    ogj = (observed.get("extras") or {}).get("gnatprove_jobs")
                    if rgj is None:
                        bound = False; continue
                    if rgj != ogj:
                        step("run-backed-spark-policy", "FAILED",
                             f"{side}: recorded gnatprove_jobs {rgj!r} != freshly observed {ogj!r}"); return out
                if bound:
                    step("run-backed-spark-policy", "ok", "per-cell SPARK gnatprove_jobs recorded == freshly observed")
                else:
                    step("run-backed-spark-policy", "not checked here",
                         "archived SPARK Result lacks extras.gnatprove_jobs; this certificate does not bind SPARK "
                         "per-cell policy (an empty worker-env-update dict is NOT read as jobs=1)")
    if not (ra and ta):                                          # replay was not flake-stable -> cannot reproduce
        step("replay-stability", "FAILED", f"replay not stable (real_agreed={ra} twin_agreed={ta})"); return out
    same = (ro == obs.get("real_outcome") and to == obs.get("twin_outcome"))
    step("replay", "ok" if same else "FAILED",
         f"real {ro} (recorded {obs.get('real_outcome')}), twin {to} (recorded {obs.get('twin_outcome')})")
    out["verdict"] = REPRODUCED if same else FAILED
    return out


def self_test():
    import tempfile
    import verifiers
    d = pathlib.Path(tempfile.mkdtemp())
    real_t = "t 1\ntask q(n: int) returns (r: bool)\n  requires n >= 0\n  ensures r == (n >= 0)\n{ r := true; }"
    twin_t = "t 1\ntask q(n: int) returns (r: bool)\n  requires n >= 0\n  ensures r == (n >= 0)\n{ r := false; }"
    w = {"_kind": "value", "_ens": True, "n": 0}
    pair = d / "p.json"
    pair.write_text(json.dumps({"id": _pair_id(real_t, twin_t), "task": "q", "program": real_t, "twin": twin_t, "witness": w}))

    def vstub(path):                                            # outcome by lowered body content; stable
        txt = pathlib.Path(path).read_text()
        return (verifiers.Outcome.REFUTED if "false" in txt else verifiers.Outcome.VERIFIED), True

    def vstub_unstable(path):
        o, _ = vstub(path); return o, False
    cert_path = d / "c.cert.json"; mint(str(pair), "dafny", str(cert_path), verify_override=vstub)
    cert = json.loads(cert_path.read_text())
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond))); print(f"  {name}: [{'ok' if cond else 'FAIL'}]")
    ok("positive replay reproduces", check(cert, verify_override=vstub)["verdict"] == REPRODUCED)
    for field in ("real_program", "twin_program"):
        t = json.loads(cert_path.read_text()); t["predicate"][field] = t["predicate"][field].replace("r :=", "r  :=")
        ok(f"{field} text tamper -> FAIL", check(t, verify_override=vstub)["verdict"] == FAILED)
    # keep the embedded text but LIE about the pair id -> recompute catches it
    pt = json.loads(cert_path.read_text()); pt["predicate"]["pair"] = "0" * 16
    ok("pair-id tamper -> FAIL", check(pt, verify_override=vstub)["verdict"] == FAILED)
    # substitute an UNRELATED real/twin that still yields the same outcomes, re-digest + recompute pair id:
    # it is a DIFFERENT pair, so it is a valid cert FOR THAT PAIR, but it no longer claims the original id.
    sub = json.loads(cert_path.read_text())
    r2 = real_t.replace("task q", "task z"); t2 = twin_t.replace("task q", "task z")
    sub["predicate"]["real_program"] = r2; sub["predicate"]["twin_program"] = t2
    sub["predicate"]["contract_sha256"] = _contract_sha(r2)
    sub["subject"] = [{"name": "real.t", "digest": {"sha256": _sha(r2)}}, {"name": "twin.t", "digest": {"sha256": _sha(t2)}},
                      {"name": "witness", "digest": {"sha256": _sha(w)}}]
    ok("substituted source WITHOUT recomputing pair id -> FAIL", check(sub, verify_override=vstub)["verdict"] == FAILED)
    sub["predicate"]["pair"] = _pair_id(r2, t2)
    ok("substituted source with recomputed id is a DIFFERENT pair (reproduces, not the original)",
       check(sub, verify_override=vstub)["verdict"] == REPRODUCED and sub["predicate"]["pair"] != cert["predicate"]["pair"])
    # recorded-outcome tamper
    to = json.loads(cert_path.read_text()); to["predicate"]["observed"]["twin_outcome"] = verifiers.Outcome.VERIFIED
    ok("recorded-outcome tamper -> FAIL", check(to, verify_override=vstub)["verdict"] == FAILED)
    # unstable replay -> FAIL (not reproduced)
    ok("unstable replay -> FAIL", check(cert, verify_override=vstub_unstable)["verdict"] == FAILED)
    # replay disagreement -> FAIL
    ok("replay disagreement -> FAIL",
       check(cert, verify_override=lambda p: (verifiers.Outcome.VERIFIED, True))["verdict"] == FAILED)
    # twin-contract SUBSTITUTION: weaken only the twin's ensures, re-digest + recompute pair id -> the embedded
    # twin is no longer a valid twin of the real (different non-body contract) -> contract-equality FAIL
    tw2 = twin_t.replace("ensures r == (n >= 0)", "ensures true")
    sb2 = json.loads(cert_path.read_text()); sb2["predicate"]["twin_program"] = tw2
    sb2["predicate"]["pair"] = _pair_id(real_t, tw2)
    sb2["subject"] = [{"name": "real.t", "digest": {"sha256": _sha(real_t)}},
                      {"name": "twin.t", "digest": {"sha256": _sha(tw2)}}, {"name": "witness", "digest": {"sha256": _sha(w)}}]
    ok("twin-contract substitution -> contract-equality FAIL", check(sb2, verify_override=vstub)["verdict"] == FAILED)
    # --kernels filter: excluding the recorded kernel -> UNDECIDED (not silently run); including it -> reproduced
    ok("--kernels excludes recorded kernel -> UNDECIDED", check(cert, kernels=["lean"], verify_override=vstub)["verdict"] == UNDECIDED)
    ok("--kernels includes recorded kernel -> reproduced", check(cert, kernels=["dafny"], verify_override=vstub)["verdict"] == REPRODUCED)
    # unavailable kernel -> UNDECIDED (not a false reproduce)
    nk = json.loads(cert_path.read_text()); nk["predicate"]["kernel"] = "no-such-kernel"
    ok("unavailable kernel -> UNDECIDED", check(nk)["verdict"] == UNDECIDED)
    # observation rendering never says 'proved here'
    ok("render is observation-only (no 'proved here')", "proved here" not in render(check(cert, verify_override=vstub)))
    # the SHARED renderer (certificate.render) must dispatch obs reports -- no KeyError('proved here'), no proof claim
    import certificate
    shared = certificate.render(check(cert, verify_override=vstub))
    ok("shared certificate.render dispatches obs (no KeyError, no 'proved here')",
       "proved here" not in shared and "reproduced" in shared.lower())
    # ---- SPARK per-cell policy chain (deterministic; executor returns full Results under the requested jobs) ----
    import copy as _copy
    base_cfg = {"flake_n": 3, "spark_prover": None}; mcid = _sha12(base_cfg)
    eff_cfg = {"base": mcid, "jobs": 2, "spark_env": {"T_SPARK_JOBS": "1"}, "available": ["spark"]}; ecid = _sha12(eff_cfg)
    RH, TH = "a" * 64, "b" * 64

    def _R(sha, out_, gj):
        return {"backend": "spark", "backend_version": "sv1", "source_sha256": sha, "outcome": out_,
                "ok": out_ == "verified", "budget": "bud", "wall_ms": 1, "extras": {"gnatprove_jobs": gj}}
    spark_cert = {"_type": STATEMENT, "predicateType": PREDICATE, "predicate": {
        "version": VERSION, "kind": KIND, "pair": _pair_id(real_t, twin_t), "kernel": "spark", "flake": 3,
        "spark_jobs": 1, "witness": w, "real_program": real_t, "twin_program": twin_t,
        "contract_sha256": _contract_sha(real_t),
        "observed": {"real_outcome": "verified", "twin_outcome": "refuted", "real_agreed": True, "twin_agreed": True},
        "result_meta": {"real": _R(RH, "verified", 1), "twin": _R(TH, "refuted", 1)},
        "run_backed": {"eff_config_id": ecid, "manifest_config_id": mcid, "eff_config": eff_cfg, "base_config": base_cfg,
                       "run_real_src_sha256": RH, "run_twin_src_sha256": TH,
                       "run_ref": {"manifest_sha256": "m", "checkpoint_sha256": "c", "record_sha256": "r"}}},
        "subject": [{"name": "real.t", "digest": {"sha256": _sha(real_t)}},
                    {"name": "twin.t", "digest": {"sha256": _sha(twin_t)}}, {"name": "witness", "digest": {"sha256": _sha(w)}}]}

    def _exec_jobs(gj_real, gj_twin):
        def _f(rt, tt, ww, kernel, flake, spark_jobs=1, spark_prover=None, verify_override=None):
            return ("verified", "refuted", True, True, RH, TH, _R(RH, "verified", gj_real), _R(TH, "refuted", gj_twin))
        return _f
    _saved_lr = globals()["_lower_and_run"]
    try:
        globals()["_lower_and_run"] = _exec_jobs(1, 1)
        ok("SPARK positive (recorded==explicit==top==observed==1) reproduces", check(spark_cert)["verdict"] == REPRODUCED)
        ca = _copy.deepcopy(spark_cert); ca["predicate"]["result_meta"]["real"]["extras"]["gnatprove_jobs"] = 4
        ok("SPARK Results disagree (real4/twin1) -> FAIL", check(ca)["verdict"] == FAILED)
        cc = _copy.deepcopy(spark_cert); cc["predicate"]["spark_jobs"] = 99
        ok("SPARK top-level spark_jobs=99 vs recorded/explicit 1 -> FAIL", check(cc)["verdict"] == FAILED)
        cb = _copy.deepcopy(spark_cert)
        cb["predicate"]["result_meta"]["real"]["extras"]["gnatprove_jobs"] = 4
        cb["predicate"]["result_meta"]["twin"]["extras"]["gnatprove_jobs"] = 4
        cb["predicate"]["spark_jobs"] = 4                           # both Results + top-level = 4, explicit update stays 1
        ok("SPARK both Results+top=4 vs explicit worker-update=1 -> FAIL", check(cb)["verdict"] == FAILED)
        globals()["_lower_and_run"] = _exec_jobs(4, 4)             # observed 4 vs recorded 1 -> post-replay fidelity
        ok("SPARK observed gnatprove_jobs(4)!=recorded(1) -> FAIL", check(spark_cert)["verdict"] == FAILED)
    finally:
        globals()["_lower_and_run"] = _saved_lr
    allok = all(c for _, c in checks); print("OBS-CERT-SELF-TEST " + ("PASS" if allok else "FAIL"))
    return 0 if allok else 1


def main():
    if "--self-test" in sys.argv:
        return self_test()
    cmd = sys.argv[1]
    if cmd == "mint":
        flake = int(sys.argv[sys.argv.index("--flake") + 1]) if "--flake" in sys.argv else 3
        return mint(sys.argv[2], sys.argv[3], sys.argv[4], flake=flake)
    if cmd == "check":
        cert = json.loads(pathlib.Path(sys.argv[2]).read_text())
        rep = check_record(cert) if cert.get("predicateType") == RECORD_PREDICATE else check(cert)
        print(render(rep))
        return 0 if rep["verdict"] == REPRODUCED else (2 if rep["verdict"] == UNDECIDED else 1)
    print("usage: obs_certificate.py mint|check|--self-test ..."); return 2


if __name__ == "__main__":
    sys.exit(main())
