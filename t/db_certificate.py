#!/usr/bin/env python3
"""DIRECT-BODY observation certificate for the 11,088-cell matrix (e1_full_adjudicate), distinct from the
paired grounded-witness certificate (obs_certificate.py).

The historical direct-body record is STATE-ONLY: `{path, which, kernel, config_id, config, src_hash (task-AST
hash), state, raw}`. It did NOT retain a full Result, a lowered-source digest, or flake-agreement flags, and it
is a BODY-ONLY adjudication (the wrong body is read as UNPROVED, never a grounded-witness REFUTED) whose
survivor-verification carries UNKNOWN intended-correctness (a survivor-VERIFICATION rate, not an accuracy).

A certificate therefore binds what was actually retained and replays only what is reconstructable:
  * it embeds the state-only record + the input identity (task-AST hash `src_hash`, and for a survivor the
    frozen body + bodyhash). It invents NO historical Result / lowered digest / stable flag.
  * `check` reloads the task from its corpus path, confirms canon(task) == src_hash (and, for a survivor,
    canon(body) == bodyhash), re-lowers the BODY ONLY (no witness substitution) and re-adjudicates the kernel,
    then compares the FRESH normalized state to the recorded one.
  * the fresh Result metadata (state + current engine/solver config + a freshly computed lowered-source digest)
    is a NEW observation under the CURRENT engine, reported as such and linked to the preserved original by
    (path, which, src_hash, bodyhash, config_id) -- never presented as the historical record.
  * an engine different from the recorded `engine_pin` is reported explicitly; a state match under a DIFFERENT
    engine is UNDECIDED (not a same-engine reproduction), never silently "reproduced".

    python3 -I db_certificate.py check <cert.json>
    python3 -I db_certificate.py --self-test
"""
import hashlib
import json
import os
import pathlib
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
_HOME = os.path.expanduser("~")
for _d in [f"{_HOME}/.cargo/bin", f"{_HOME}/.opam/default/bin", f"{_HOME}/.elan/bin", f"{_HOME}/.local/lean/bin",
           f"{_HOME}/.local/fstar/fstar/bin", f"{_HOME}/.local/gnatprove/gnatprove-x86_64-linux-16.1.0-1/bin",
           f"{_HOME}/.local/verus/verus-x86-linux", f"{_HOME}/.local/dafny"]:
    if _d not in os.environ.get("PATH", ""):
        os.environ["PATH"] = _d + ":" + os.environ.get("PATH", "")
os.environ.setdefault("T_LEAN_BIN", f"{_HOME}/.local/lean/bin/lean")
os.environ.setdefault("T_SPARK_JOBS", "1")
os.environ.setdefault("T_SPARK_PROVER", "z3")

STATEMENT = "https://in-toto.io/Statement/v1"
PREDICATE = "urn:dawnr:direct-body-observation:v1"
VERSION = 1
KIND = "direct-body-observation"
REPRODUCED, FAILED, UNDECIDED = "reproduced", "failed", "undecided here"


def canon(x):                                   # exactly e1_full_adjudicate.canon (sha1 over sort_keys json)
    return hashlib.sha1(json.dumps(x, sort_keys=True, default=str).encode()).hexdigest()


def norm(v):                                    # exactly e1_full_adjudicate.norm
    s = "verified" if v == "verified" else "refuted" if v == "refuted" else \
        "unverifiable:" + (v.split(":", 1)[0] if ":" in v else v)
    return s, v


def current_engine_pin():
    try:
        m = re.search(r"Pinned commit:\s*`?([0-9a-f]{40})`?", pathlib.Path(os.path.join(HERE, "ENGINE.md")).read_text())
        return (m.group(1)[:12] if m else "nopin")
    except Exception:  # noqa: BLE001
        return "?"


def _default_load(path):
    import tasks_io
    return tasks_io.load_task(path)


def _default_adjudicate(task, body, kernel):
    """Body-only adjudication through the real engine, exactly as e1_full_adjudicate._cell does: lower the body
    (NO witness) and read the kernel verdict. Returns (normalized_state, raw)."""
    import audit
    _lmod, suffix = audit.tlib._LOWER_MOD[kernel]
    work = pathlib.Path(tempfile.mkdtemp(prefix="t-db-"))
    v = audit._kernel_verdict(task, body, kernel, work / f"c.{suffix}")
    return norm(v)


def mint(row, task_entry, config, out_path=None):
    """Build a direct-body certificate from a retained adjudication ROW + its manifest TASK entry + the run
    config. `which` == 'REAL' embeds no body (reconstructed from the task at check); a survivor embeds its
    frozen body + bodyhash + op."""
    which = row["which"]
    survivor = None
    body = None
    if which != "REAL":
        s = next((s for s in (task_entry.get("survivors") or []) if s["id"] == which), None)
        if s is None:
            raise ValueError(f"survivor id {which} not found in manifest task entry")
        survivor = {"id": s["id"], "op": s.get("op"), "bodyhash": s["bodyhash"]}
        body = s["body"]
    pred = {"version": VERSION, "kind": KIND, "task_path": row["path"], "which": which, "kernel": row["kernel"],
            "config_id": row["config_id"], "config": config, "src_hash": row["src_hash"],
            "survivor": survivor, "body": body,
            "recorded": {"state": row["state"], "raw": row.get("raw")},
            "semantics": "direct-body adjudication (body-only lowering, NO grounded-witness substitution); "
                         "survivor verification carries UNKNOWN intended-correctness (survivor-verification rate, "
                         "not accuracy); the historical record is STATE-ONLY (no full Result / lowered digest / "
                         "flake retained); the replay's Result metadata is a NEW observation under the current "
                         "engine, linked by (path,which,src_hash,bodyhash,config_id)"}
    subj = [{"name": "task", "digest": {"sha1": row["src_hash"]}}]
    if survivor:
        subj.append({"name": "body", "digest": {"sha1": survivor["bodyhash"]}})
    cert = {"_type": STATEMENT, "predicateType": PREDICATE, "predicate": pred, "subject": subj}
    if out_path:
        pathlib.Path(out_path).write_text(json.dumps(cert, indent=1), encoding="utf-8")
    return cert


def check(cert, load_override=None, adjudicate_override=None):
    steps = []

    def step(w, r, d=""):
        steps.append({"what": w, "result": r, "detail": d}); return r != "FAILED"
    out = {"verdict": FAILED, "steps": steps, "kind": KIND,
           "semantics": "direct-body state reproduction (body-only, no witness); survivor-verification rate, not "
                        "accuracy; historical record is state-only, fresh Result is a new observation"}
    pred = cert.get("predicate") if isinstance(cert, dict) else None
    if (not isinstance(pred, dict) or cert.get("_type") != STATEMENT or cert.get("predicateType") != PREDICATE
            or pred.get("version") != VERSION or pred.get("kind") != KIND):
        step("certificate", "FAILED", f"not a dawnr direct-body-observation certificate v{VERSION}"); return out
    which, kernel = pred.get("which"), pred.get("kernel")
    rec_state = (pred.get("recorded") or {}).get("state")
    # subjects must echo the embedded identity
    subj = {s.get("name"): (s.get("digest") or {}).get("sha1") for s in cert.get("subject") or []}
    if subj.get("task") != pred.get("src_hash"):
        step("subject-identity", "FAILED", "task subject digest != embedded src_hash"); return out
    load = load_override or _default_load
    try:
        task = load(pred["task_path"])
    except Exception as e:  # noqa: BLE001
        step("corpus", "not checked here", f"cannot load task source ({type(e).__name__}); corpus not available here")
        out["verdict"] = UNDECIDED; return out
    got = canon(task)
    if got != pred.get("src_hash"):
        step("task-identity", "FAILED", f"canon(task) {got[:8]} != recorded src_hash {str(pred.get('src_hash'))[:8]} "
             f"(spec changed or wrong task)"); return out
    step("task-identity", "ok", "task re-hashes to the recorded task-AST hash (reconstructed from retained input)")
    if which == "REAL":
        body = task.get("body")
    else:
        sv = pred.get("survivor") or {}
        body = pred.get("body")
        if subj.get("body") != sv.get("bodyhash") or canon(body) != sv.get("bodyhash"):
            step("body-identity", "FAILED", "embedded survivor body != recorded bodyhash"); return out
        step("body-identity", "ok", "survivor body re-hashes to the recorded bodyhash")
    # engine context (reported explicitly; a different engine is NOT a silent reproduction)
    rec_pin = (pred.get("config") or {}).get("engine_pin")
    cur_pin = current_engine_pin()
    engine_match = (rec_pin == cur_pin)
    step("engine", "ok" if engine_match else "not checked here",
         f"recorded engine_pin {rec_pin}, current {cur_pin}" + ("" if engine_match else " (DIFFERENT engine)"))
    # re-adjudicate BODY-ONLY (no witness substitution)
    adj = adjudicate_override or _default_adjudicate
    try:
        fresh_state, fresh_raw = adj(task, body, kernel)
    except Exception as e:  # noqa: BLE001
        step("replay", "not checked here", f"{type(e).__name__}: {e}"[:160]); out["verdict"] = UNDECIDED; return out
    out["fresh_observation"] = {"state": fresh_state, "raw": fresh_raw, "engine_pin": cur_pin,
                                "note": "NEW observation under the current engine; the historical record was state-only"}
    same = (fresh_state == rec_state)
    if not engine_match:
        step("replay", "not checked here",
             f"fresh state {fresh_state} vs recorded {rec_state} under a DIFFERENT engine; not a same-engine "
             f"reproduction of the recorded observation")
        out["verdict"] = UNDECIDED; return out
    step("replay", "ok" if same else "FAILED", f"fresh body-only state {fresh_state} (recorded {rec_state})")
    out["verdict"] = REPRODUCED if same else FAILED
    return out


def render(rep):
    lines = [f"direct-body-observation certificate: {rep['verdict']}"]
    for s in rep["steps"]:
        lines.append(f"  - {s['what']}: {s['result']}" + (f" ({s['detail']})" if s.get("detail") else ""))
    if "fresh_observation" in rep:
        f = rep["fresh_observation"]
        lines.append(f"  fresh observation (no model, current engine {f['engine_pin']}): state {f['state']} "
                     f"-- a NEW observation; the historical record was state-only (survivor-verification, not accuracy)")
    return "\n".join(lines)


def self_test():
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond))); print(f"  {name}: [{'ok' if cond else 'FAIL'}]")
    # a fake task (dict, as tasks_io.load_task returns) + a stub adjudicator keyed on body content
    task = {"name": "q", "requires": ["n >= 0"], "ensures": ["r == (n >= 0)"], "body": "r := true;"}
    src = canon(task)
    surv_body = "r := false;"
    task_entry = {"survivors": [{"id": "sv1", "op": "neg", "witness": {}, "body": surv_body, "bodyhash": canon(surv_body)}]}
    config = {"engine_pin": current_engine_pin(), "spark_prover": "z3", "spark_jobs": "1", "dafny": "d", "z3": "z"}
    load = lambda p: task

    def adj_stub(tk, body, kernel):
        return ("verified" if "true" in body else "refuted"), body
    # REAL cell: stub says verified -> record verified
    row_real = {"path": "corpus/q.json", "which": "REAL", "kernel": "dafny", "config_id": "cfg1",
                "src_hash": src, "state": "verified", "raw": "verified"}
    cert_real = mint(row_real, task_entry, config)
    ok("REAL positive reproduces", check(cert_real, load, adj_stub)["verdict"] == REPRODUCED)
    # survivor cell: stub says refuted (body has 'false') -> record refuted
    row_sv = {"path": "corpus/q.json", "which": "sv1", "kernel": "dafny", "config_id": "cfg1",
              "src_hash": src, "state": "refuted", "raw": "refuted"}
    cert_sv = mint(row_sv, task_entry, config)
    ok("survivor positive reproduces (body-only)", check(cert_sv, load, adj_stub)["verdict"] == REPRODUCED)
    ok("survivor cert is state-only (no invented full Result / lowered digest / flake)",
       cert_sv["predicate"]["body"] == surv_body
       and all(k not in cert_sv["predicate"] for k in ("result_meta", "run_backed", "real_result", "twin_result")))
    # recorded-state tamper (engine matches) -> FAILED
    import copy
    t1 = copy.deepcopy(cert_real); t1["predicate"]["recorded"]["state"] = "refuted"
    ok("recorded-state tamper (same engine) -> FAILED", check(t1, load, adj_stub)["verdict"] == FAILED)
    # src_hash tamper -> identity FAILED
    t2 = copy.deepcopy(cert_real); t2["predicate"]["src_hash"] = "0" * 40
    ok("src_hash tamper -> FAILED", check(t2, load, adj_stub)["verdict"] == FAILED)
    # subject digest not matching embedded src_hash -> FAILED
    t2b = copy.deepcopy(cert_real); t2b["subject"][0]["digest"]["sha1"] = "1" * 40
    ok("subject!=src_hash -> FAILED", check(t2b, load, adj_stub)["verdict"] == FAILED)
    # survivor body tamper (bodyhash mismatch) -> FAILED
    t3 = copy.deepcopy(cert_sv); t3["predicate"]["body"] = "r := true;"
    ok("survivor body tamper -> FAILED", check(t3, load, adj_stub)["verdict"] == FAILED)
    # task source changed since freeze -> identity FAILED
    ok("task source changed -> FAILED",
       check(cert_real, lambda p: {**task, "ensures": ["r == true"]}, adj_stub)["verdict"] == FAILED)
    # engine differs -> UNDECIDED (state match is NOT a same-engine reproduction), fresh observation attached
    t4 = copy.deepcopy(cert_real); t4["predicate"]["config"] = {**config, "engine_pin": "deadbeefdead"}
    r4 = check(t4, load, adj_stub)
    ok("engine mismatch -> UNDECIDED + fresh observation attached",
       r4["verdict"] == UNDECIDED and r4.get("fresh_observation", {}).get("state") == "verified")
    # corpus unavailable -> UNDECIDED (not a false reproduce)
    def _noload(p):
        raise FileNotFoundError(p)
    ok("corpus unavailable -> UNDECIDED", check(cert_real, _noload, adj_stub)["verdict"] == UNDECIDED)
    # render never claims a proof / never says accuracy
    txt = render(check(cert_real, load, adj_stub))
    ok("render says survivor-verification not accuracy, no 'proof'", "not accuracy" in txt and "proof" not in txt.lower())
    allok = all(c for _, c in checks); print("DB-CERT-SELF-TEST " + ("PASS" if allok else "FAIL"))
    return 0 if allok else 1


def main():
    if "--self-test" in sys.argv:
        return self_test()
    if len(sys.argv) >= 3 and sys.argv[1] == "check":
        cert = json.loads(pathlib.Path(sys.argv[2]).read_text())
        rep = check(cert)
        print(render(rep))
        return 0 if rep["verdict"] == REPRODUCED else (2 if rep["verdict"] == UNDECIDED else 1)
    print("usage: db_certificate.py check <cert.json> | --self-test"); return 2


if __name__ == "__main__":
    sys.exit(main())
