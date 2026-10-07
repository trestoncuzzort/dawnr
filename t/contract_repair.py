#!/usr/bin/env python3
"""t/contract_repair.py: proved specification repair (programme R1, internal/RESEARCH-2026-10-07-zoom-out.md section 8).

`t/audit.py` finds survivors: one-edit mutants that compute something different from the real program while meeting
its `ensures` everywhere on the bounded domain. This module proposes the missing clauses, picks a set that kills every
survivor, and hands the repaired contract back to the audit and to a kernel.

1. **Candidates** come from a typed grammar over the task's own vocabulary. For each result term (the result, or a
   pair result's two components), by its type:
   - **int:** equality with each int parameter, and the disjunction of those equalities. Membership in, and the two
     extremal bounds over, each sequence parameter. Equality with its length. Equality with every int spec function
     the task defines, applied to its parameters. Equality with E wherever an `ensures` only bounds the term by E.
   - **seq:** equal length to each sequence parameter, and equality with every seq spec function. For each
     `forall k in [0, len(r)) . B(r[k])` in the contract, its converse over each sequence parameter s:
     `forall j in [0, len(s)) . B(s[j]) ==> (exists m in [0, len(r)) . r[m] == s[j])`, the missing half of a
     subset-only postcondition.
   - **bool:** equality with every bool spec function.
2. **The filter:** a candidate is kept only if it holds for the real program at every domain point (the interpreter's
   `ev`, at the real result), and it kills at least one survivor (false at that survivor's result somewhere).
3. **The cover:** greedily, the candidate that kills the most survivors not yet killed, ties to the smaller clause,
   until every survivor is killed or no candidate kills another.
4. **The check:** the repaired task is audited again from scratch, and with `--kernel` it is verified there: the real
   body proved against the stronger contract, its twin refuted. A repair whose real body the kernel cannot prove is
   reported as such, never dropped. Its loop invariants may be too weak for the stronger contract (R1b).

Prior art (receipt dc2c168fbaca): SpecFuzzer (arXiv 2201.10874) fuzzes assertions from a grammar, filters them by a
test suite with Daikon and ranks them by mutation analysis; nothing is proved. Here the filter is the whole bounded
domain, the target is the measured survivors, and soundness for every input is the kernel's proof.

  python3 t/contract_repair.py t/dafnybench --jobs 4 --kernel dafny --table REPAIR.md --write repaired/
"""
from __future__ import annotations

import argparse
import copy
import json
import signal
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import audit  # noqa: E402
import harness  # noqa: E402
import interp  # noqa: E402
import surface  # noqa: E402
import tasks_io  # noqa: E402
import tlib  # noqa: E402

TASK_SECONDS = 120
SPEC_FUN_ARGS = 40      # argument assignments tried per spec function


def V(n):
    return {"var": n}


def I(n):
    return {"int": n}


def op(o, *a):
    return {"op": o, "args": list(a)}


def call(f, *a):
    return {"call": {"fun": f, "args": list(a)}}


def quant(kind, v, lo, hi, body):
    return {kind: {"var": v, "lo": lo, "hi": hi, "body": body}}


def _size(e) -> int:
    return len(json.dumps(e, sort_keys=True))


def _mentions(e, name: str) -> bool:
    if isinstance(e, dict):
        if e.get("var") == name:
            return True
        return any(_mentions(v, name) for v in e.values())
    if isinstance(e, list):
        return any(_mentions(v, name) for v in e)
    return False


def _mentions_any(e, names: set) -> bool:
    if isinstance(e, dict):
        v = e.get("var")
        if isinstance(v, str) and v in names:
            return True
        return any(_mentions_any(x, names) for x in e.values())
    if isinstance(e, list):
        return any(_mentions_any(x, names) for x in e)
    return False


def _replace(e, old, new):
    if e == old:
        return copy.deepcopy(new)
    if isinstance(e, dict):
        return {k: _replace(v, old, new) for k, v in e.items()}
    if isinstance(e, list):
        return [_replace(v, old, new) for v in e]
    return e


def _result_terms(task: dict) -> list:
    r = task["returns"][0]
    t = r["type"]
    if t in ("int", "bool", "seq"):
        return [(V(r["name"]), t)]
    if isinstance(t, dict) and "pair" in t:
        a, b = t["pair"]
        return [(op(k, V(r["name"])), c) for k, c in (("fst", a), ("snd", b)) if c in ("int", "bool", "seq")]
    return []


def _arg_choices(task: dict, ptypes: list) -> list:
    """Assignments of the task's parameters to a spec function's parameter types, in order, at most SPEC_FUN_ARGS."""
    pool = {"int": [V(p["name"]) for p in task["params"] if p["type"] == "int"],
            "bool": [V(p["name"]) for p in task["params"] if p["type"] == "bool"],
            "seq": [V(p["name"]) for p in task["params"] if p["type"] == "seq"]}
    pool["int"] += [op("len", s) for s in pool["seq"]]
    out = [[]]
    for t in ptypes:
        if t not in pool or not pool[t]:
            return []
        out = [a + [x] for a in out for x in pool[t]][:SPEC_FUN_ARGS]
    return out


def _comparisons(e, term) -> list:
    """Every E that an `ensures` compares the term against with an order (term >= E, E <= term, term < E, ...)."""
    out = []
    if isinstance(e, dict):
        if e.get("op") in ("<", "<=", ">", ">=") and len(e.get("args", ())) == 2:
            a, b = e["args"]
            if a == term and not _mentions(b, _root(term)):
                out.append(b)
            if b == term and not _mentions(a, _root(term)):
                out.append(a)
        for v in e.values():
            out += _comparisons(v, term)
    elif isinstance(e, list):
        for v in e:
            out += _comparisons(v, term)
    return out


def _root(term) -> str:
    return term["var"] if "var" in term else term["args"][0]["var"]


def _attained(c, term):
    """`forall x in R . ... E <= term` (or `term >= E`, or the mirror) as `exists x in R . ... E == term`, else None."""
    if isinstance(c, dict) and "forall" in c:
        q = c["forall"]
        inner = _attained(q["body"], term)
        return None if inner is None else quant("exists", q["var"], q["lo"], q["hi"], inner)
    if isinstance(c, dict) and c.get("op") in ("<", "<=", ">", ">=") and len(c.get("args", ())) == 2:
        a, b = c["args"]
        if term in (a, b):
            other = b if a == term else a
            if not _mentions(other, _root(term)):
                return op("==", other, term)
    return None


def _term_value(term, val):
    """The value of a result term (the result, or `fst`/`snd` of it) given the result's value."""
    if "var" in term:
        return val
    if isinstance(val, interp.Pair):
        return val.a if term["op"] == "fst" else val.b
    return None


def _atom_values(atom, env0):
    if "var" in atom:
        return env0.get(atom["var"])
    return len(env0.get(atom["args"][0]["var"], ()))      # len(s)


def _fitted(task: dict, ref) -> list:
    """Daikon-style clauses read off the real program's values on the whole domain, numerically, before any is built:
    an int term equal to an affine combination of at most two int atoms (parameters, sequence lengths) with
    coefficients in [-2, 2] and a constant in [-3, 3], or to `(p op q) % r` or `/ r`; any term equal to one of the
    at most three values it ever takes. The interpreter checks every built clause again, so a fit only proposes."""
    if ref is None or not ref.points:
        return []
    seqs = [V(p["name"]) for p in task["params"] if p["type"] == "seq"]
    atoms = [V(p["name"]) for p in task["params"] if p["type"] == "int"] + [op("len", s) for s in seqs]
    atoms = atoms[:5]
    cols = [[_atom_values(a, env0) for env0, _r in ref.points] for a in atoms]
    out = []
    for term, t in _result_terms(task):
        vals = [_term_value(term, real) for _e, real in ref.points]
        if any(v is None for v in vals):
            continue
        distinct = []
        for v in vals:
            if v not in distinct:
                distinct.append(v)
        if 1 <= len(distinct) <= 3 and t in ("int", "bool", "seq"):
            lits = [I(v) if t == "int" and not isinstance(v, bool) else
                    ({"bool": bool(v)} if t == "bool" else op("seq", *[I(x) for x in v])) for v in distinct]
            d = op("==", term, lits[0])
            for lit in lits[1:]:
                d = op("or", d, op("==", term, lit))
            out.append(d)
        if t != "int" or any(isinstance(v, bool) or not isinstance(v, int) for v in vals):
            continue
        n = len(atoms)
        for c0 in range(-3, 4):
            if all(v == c0 for v in vals):
                out.append(op("==", term, I(c0)))
        for i in range(n):
            for ci in (-2, -1, 1, 2):
                for c0 in range(-3, 4):
                    if all(v == ci * a + c0 for v, a in zip(vals, cols[i])):
                        out.append(op("==", term, _affine([(ci, atoms[i])], c0)))
            for j in range(i + 1, n):
                for ci in (-2, -1, 1, 2):
                    for cj in (-2, -1, 1, 2):
                        for c0 in range(-3, 4):
                            if all(v == ci * a + cj * b + c0 for v, a, b in zip(vals, cols[i], cols[j])):
                                out.append(op("==", term, _affine([(ci, atoms[i]), (cj, atoms[j])], c0)))
        for i in range(n):
            for j in range(n):
                for k in range(n):
                    for o, f in (("+", lambda a, b: a + b), ("-", lambda a, b: a - b), ("*", lambda a, b: a * b)):
                        for m, g in (("mod", lambda x, y: x % y), ("div", lambda x, y: x // y)):
                            try:
                                ok = all(r != 0 and v == g(f(a, b), abs(r)) and r > 0
                                         for v, a, b, r in zip(vals, cols[i], cols[j], cols[k]))
                            except Exception:                   # noqa: BLE001
                                ok = False
                            if ok:
                                out.append(op("==", term, op(m, op(o, atoms[i], atoms[j]), atoms[k])))
    return out


def _affine(terms, c0):
    e = None
    for c, a in terms:
        t = a if c == 1 else (op("neg", a) if c == -1 else op("*", I(c), a))
        e = t if e is None else op("+", e, t)
    if c0:
        e = op("+", e, I(c0)) if e is not None else I(c0)
    return e if e is not None else I(0)


def candidates(task: dict, ref=None) -> list:
    """The grammar's clauses for this task, deduplicated, each one an `ensures` expression."""
    out = _fitted(task, ref)
    seqs = [V(p["name"]) for p in task["params"] if p["type"] == "seq"]
    ints = [V(p["name"]) for p in task["params"] if p["type"] == "int"]
    funs = task.get("spec_funs", [])
    for term, t in _result_terms(task):
        for f in funs:
            if f.get("result") == t:
                for args in _arg_choices(task, [p["type"] for p in f["params"]]):
                    out.append(op("==", term, call(f["name"], *args)))
        if t == "int":
            out += [op("==", term, p) for p in ints]
            if len(ints) >= 2:
                d = op("==", term, ints[0])
                for p in ints[1:]:
                    d = op("or", d, op("==", term, p))
                out.append(d)
            for s in seqs:
                k = "t_rk"
                out.append(quant("exists", k, I(0), op("len", s), op("==", op("at", s, V(k)), term)))
                out.append(quant("forall", k, I(0), op("len", s), op("<=", op("at", s, V(k)), term)))
                out.append(quant("forall", k, I(0), op("len", s), op(">=", op("at", s, V(k)), term)))
                out.append(op("==", term, op("len", s)))
            for c in task.get("ensures", []):
                for e in _comparisons(c, term):
                    out.append(op("==", term, e))
            # bounds against zero, the int parameters and the sequences' lengths (a remainder below its divisor)
            for b in [I(-1), I(0), I(1)] + ints + [op("len", s) for s in seqs]:
                out += [op("<=", b, term), op("<", term, b), op("<=", term, b)]
            out.append(op("and", op("<=", I(0), term), op("<", term, ints[-1])) if ints else op("<=", I(0), term))
        if t == "bool":
            # a boolean result equal to a comparison of two int parameters (a precedence slip's intended `z <==> x == y`)
            for i, a in enumerate(ints):
                for b in ints[i + 1:]:
                    out += [op("==", term, op(o, a, b)) for o in ("==", "!=", "<", "<=")]
        if t == "seq":
            for s in seqs:
                out.append(op("==", op("len", term), op("len", s)))
            # every element predicate the contract states over the result, conjoined: the converse of the whole filter
            preds = []
            for c in task.get("ensures", []):
                q = c.get("forall") if isinstance(c, dict) else None
                if q and q.get("lo") == I(0) and q.get("hi") == op("len", term):
                    body = _replace(q["body"], op("at", term, V(q["var"])), V("t_rx"))
                    if not _mentions(body, q["var"]) and not _mentions(body, _root(term)):
                        preds.append(body)
            if len(preds) >= 2:
                both = preds[0]
                for b in preds[1:]:
                    both = op("and", both, b)
                for s in seqs:
                    if s == term:
                        continue
                    body = _replace(both, V("t_rx"), op("at", s, V("t_rj")))
                    member = quant("exists", "t_rm", I(0), op("len", term),
                                   op("==", op("at", term, V("t_rm")), op("at", s, V("t_rj"))))
                    out.append(quant("forall", "t_rj", I(0), op("len", s), op("implies", body, member)))
            for c in task.get("ensures", []):
                q = c.get("forall") if isinstance(c, dict) else None
                if not q or q.get("lo") != I(0) or q.get("hi") != op("len", term):
                    continue
                k = q["var"]
                for s in seqs:
                    if s == term:
                        continue
                    body = _replace(q["body"], op("at", term, V(k)), op("at", s, V("t_rj")))
                    if _mentions(body, k) or _mentions(body, _root(term)):
                        continue     # the clause reads its index or other elements: no converse of this shape
                    member = quant("exists", "t_rm", I(0), op("len", term),
                                   op("==", op("at", term, V("t_rm")), op("at", s, V("t_rj"))))
                    out.append(quant("forall", "t_rj", I(0), op("len", s), op("implies", body, member)))
    # attainment: an `ensures` bounding a term by every E over quantified indices, `forall i . forall j . E <= T`, is
    # answered by the bound being reached, `exists i . exists j . E == T` (maxDifference's missing half)
    for term, t in _result_terms(task):
        if t != "int":
            continue
        for c in task.get("ensures", []):
            att = _attained(c, term)
            if att is not None:
                out.append(att)
                out.append(op("or", op("==", term, I(0)), att))      # attained, or the empty case's zero
    seen, uniq = set(), []
    for c in out:
        key = json.dumps(c, sort_keys=True)
        if key not in seen and c not in task.get("ensures", []):
            seen.add(key)
            uniq.append(c)
    return uniq


def _holds(ref, clause, env0, val) -> bool:
    env = dict(env0)
    env[ref.ret] = val
    try:
        return bool(interp.ev(clause, env, ref.funs, interp.St()))
    except Exception:                           # noqa: BLE001 (an ill-typed candidate is no candidate)
        return False


def _values(ref, task: dict, body: list) -> list | None:
    """The body's result at every domain point, or None if it has no value somewhere."""
    funs = interp.funs_of(task, body)
    vals = []
    for env0, _real in ref.points:
        env = ref._start(env0)
        try:
            interp.exec_body(body, env, funs, interp.St())
        except (interp.Undef, interp.Budget, RecursionError):
            return None
        vals.append(env.get(ref.ret))
    return vals


def repair_task(task: dict) -> dict:
    """The repair, without a kernel: status, survivors before, the chosen clauses, the repaired task, survivors after."""
    res = {"name": task.get("name", "?")}
    before = audit.classify(task)
    res["status"] = before["status"]
    res["before"] = len(before.get("survivors", []))
    if before["status"] != "ok" or not before["survivors"]:
        res["clauses"], res["after"] = [], res["before"]
        return res
    names = {p["name"] for p in task["params"]}
    if names and not _mentions_any(task["body"], names):
        # the real program never reads its inputs (a constant answer to a task with parameters, measured in
        # vericoding's APPS solutions): its behaviour is no evidence of the intended one, so nothing is fitted to it
        res["status"] = "refused: the real body never reads its parameters"
        res["clauses"], res["after"] = [], res["before"]
        return res
    harness._set_ctx(task)
    ref = interp.Reference(task)
    if ref.mods:
        res["status"] = "refused: a heap task (repair v1 reads results, not arrays)"
        res["clauses"], res["after"] = [], res["before"]
        return res
    surv_vals = [v for v in (_values(ref, task, s["body"]) for s in before["survivors"]) if v is not None]
    kills = []
    for c in candidates(task, ref):
        if not all(_holds(ref, c, env0, real) for env0, real in ref.points):
            continue
        killed = {i for i, vals in enumerate(surv_vals)
                  if any(not _holds(ref, c, env0, v) for (env0, _r), v in zip(ref.points, vals))}
        if killed:
            kills.append((c, killed))
    chosen, left = [], set(range(len(surv_vals)))
    while left:
        best = max(kills, key=lambda ck: (len(ck[1] & left), -_size(ck[0])), default=None)
        if best is None or not best[1] & left:
            break
        chosen.append(best[0])
        left -= best[1]
    res["clauses"] = chosen
    repaired = dict(task, ensures=list(task["ensures"]) + chosen)
    res["task"] = repaired
    after = audit.classify(repaired) if chosen else before
    res["after"] = len(after.get("survivors", [])) if after["status"] == "ok" else res["before"]
    return res


def _loop_states(task: dict, ref) -> dict:
    """R1b: the states at every head of every top-level `while`, over the whole domain: {statement index: [states]}."""
    body = task["body"]
    out: dict = {}

    def tr(ev):
        p = ev.get("path") or []
        if ev["kind"] == "guard" and len(p) == 1 and isinstance(p[0], int) and "while" in body[p[0]]:
            out.setdefault(p[0], []).append(ev["state"])

    for env0, _real in ref.points:
        env = ref._start(env0)
        try:
            interp.exec_body(body, env, ref.funs, interp.St(), trace=tr)
        except (interp.Undef, interp.Budget, RecursionError):
            continue
    return out


def _kind(v):
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, tuple) and all(isinstance(x, int) and not isinstance(x, bool) for x in v):
        return "seq"
    return None


def _swap_hi(c, new_hi):
    """The clause with its outermost quantifier's upper bound replaced: the postcondition over a prefix."""
    for kind in ("forall", "exists"):
        if isinstance(c, dict) and kind in c:
            return {kind: dict(c[kind], hi=new_hi)}
    return None


def invariant_candidates(task: dict, clauses: list, states: list, moved: set | None = None) -> list:
    """Candidate invariants for one loop: each repair clause moved onto the loop's accumulators and prefix index, and
    every int accumulator attained in, and bounding, the scanned prefix of each sequence parameter."""
    if not states:
        return []
    scope = set(states[0])
    for st in states[1:]:
        scope &= set(st)
    kinds = {}
    for n in sorted(scope):
        ks = {_kind(st[n]) for st in states}
        if len(ks) == 1 and None not in ks:
            kinds[n] = ks.pop()
    if moved is not None:       # accumulators and prefix indices are what the loop changes
        kinds_all = dict(kinds)
        kinds = {n: k for n, k in kinds.items() if n in moved}
    ints = [n for n, k in kinds.items() if k == "int"]
    seqs_state = [n for n, k in kinds.items() if k == "seq"]
    seq_params = [p["name"] for p in task["params"] if p["type"] == "seq"]
    ret = task["returns"][0]["name"]
    out = []
    for c in clauses:
        for acc in [n for n in seqs_state + ints if n != ret] + [ret]:
            moved = _replace(c, V(ret), V(acc))
            for idx in ints:
                if idx == acc:
                    continue
                pre = _swap_hi(moved, V(idx))
                if pre is not None:
                    out.append(pre)
            out.append(moved)
    for x in ints:
        for s in seq_params:
            for idx in ints:
                if idx == x:
                    continue
                k = "t_ik"
                out.append(quant("exists", k, I(0), V(idx), op("==", op("at", V(s), V(k)), V(x))))
    seen, uniq = set(), []
    for c in out:
        key = json.dumps(c, sort_keys=True)
        if key not in seen:
            seen.add(key)
            uniq.append(c)
    return uniq


def _assigned(stmts) -> set:
    """The variables a statement list assigns (or declares), at any depth."""
    out = set()
    for st in stmts if isinstance(stmts, list) else []:
        if not isinstance(st, dict):
            continue
        if "assign" in st:
            tgt = st["assign"][0]
            out.add(tgt if isinstance(tgt, str) else json.dumps(tgt))
        if "var" in st and isinstance(st["var"], dict):
            out.add(st["var"].get("name"))
        for v in st.values():
            if isinstance(v, dict):
                for k in ("body", "then", "else"):
                    if isinstance(v.get(k), list):
                        out |= _assigned(v[k])
            elif isinstance(v, list):
                out |= _assigned(v)
    return out


def strengthen_loops(task: dict, clauses: list) -> tuple[dict, list]:
    """R1b: the task with every top-level loop's invariants extended by the candidates that hold at every observed
    loop-head state; and the invariants added, as (statement index, clause)."""
    harness._set_ctx(task)
    ref = interp.Reference(task)
    states = _loop_states(task, ref)
    body = copy.deepcopy(task["body"])
    added = []
    for k, sts in sorted(states.items()):
        w = body[k]["while"]
        have = w.get("invariants", [])
        moved = _assigned(w["body"])
        for c in invariant_candidates(task, clauses, sts, moved):
            if c in have or not any(_mentions(c, v) for v in moved):
                continue      # already there, or it reads nothing the loop changes (true before it, then forever)
            ok = True
            for st in sts:
                try:
                    if not interp.ev(c, dict(st), ref.funs, interp.St()):
                        ok = False
                        break
                except Exception:                           # noqa: BLE001 (an ill-typed candidate is no candidate)
                    ok = False
                    break
            if ok:
                have = have + [c]
                added.append((k, c))
        w["invariants"] = have
    return dict(task, body=body), added


class _Out(Exception):
    pass


def _alarm(_s, _f):
    raise _Out()


def repair_file(path: str, kernel: str | None = None, seconds: int = TASK_SECONDS) -> dict:
    try:
        task = tasks_io.load_task(path)
    except Exception as e:                              # noqa: BLE001
        return {"file": path, "name": Path(path).stem, "status": f"load-error: {type(e).__name__}"}
    old = signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(seconds)
    try:
        res = repair_task(task)
    except _Out:
        res = {"name": task.get("name", "?"), "status": "timeout"}
    except Exception as e:                              # noqa: BLE001 (one task's failure is reported, never fatal)
        res = {"name": task.get("name", "?"), "status": f"error: {type(e).__name__}: {e}"[:200]}
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)
    res["file"] = path
    if kernel and res.get("clauses"):
        entry = tlib.verify(res["task"], kernels=[kernel], flake=1)[kernel]
        res["kernel"], res["real"], res["twin"] = kernel, entry.get("real"), entry.get("twin")
        if res["real"] != "verified" and any("while" in st for st in res["task"]["body"] if isinstance(st, dict)):
            # R1b: the old invariants may not carry the stronger contract; strengthen them from the observed states
            try:
                stronger, added = strengthen_loops(res["task"], res["clauses"])
            except Exception as e:                      # noqa: BLE001
                stronger, added = res["task"], []
                res["r1b_error"] = f"{type(e).__name__}: {e}"[:200]
            if added:
                entry = tlib.verify(stronger, kernels=[kernel], flake=1)[kernel]
                res["invariants"] = [_show(c) for _k, c in added]
                res["real_r1b"], res["twin_r1b"] = entry.get("real"), entry.get("twin")
                if res["real_r1b"] == "verified":
                    res["task"], res["real"], res["twin"] = stronger, res["real_r1b"], res["twin_r1b"]
                    res["inv_ast"] = [[k, c] for k, c in added]
    res["clause_text"] = [_show(c) for c in res.get("clauses", [])]
    return res


def _show(c) -> str:
    try:
        return surface.pexpr(c)
    except Exception:                                   # noqa: BLE001
        return json.dumps(c)


def patches(results: list[dict], kernel: str) -> str:
    """R2: for every task whose repaired contract the kernel proved, the lines to add, in that kernel's own language
    (its lowering's expression printer): the `ensures`, and each loop's `invariant`s, named by the loop's guard."""
    import importlib
    lmod = importlib.import_module(tlib._LOWER_MOD[kernel][0])
    head = "ensures" if kernel != "verus" else "ensures (add to the list)"
    out = [f"# Specification repairs, as {kernel} source", "",
           "Each block names a source file and the lines to add to its method's contract and loops. Every repaired "
           f"contract was proved by {kernel} for the program as written, its twin refuted, and the repaired task's "
           "audit reads zero survivors. `t_r*` and `t_i*` are fresh bound variables. A pair result's `.0` and `.1` are "
           "the method's first and second return values. Names are the lifted task's (the file under `t/`), which the "
           "lifter may have renamed from the source (a loop index `i` can read `i_v2`).", ""]
    for r in sorted(results, key=lambda r: r["name"]):
        if not (r.get("after") == 0 and r.get("clauses") and r.get("real") == "verified"
                and r.get("twin") == "refuted"):
            continue
        out.append(f"## {Path(r['file']).name}")
        out.append("")
        out.append("```")
        for c in r["clauses"]:
            out.append(f"  {head} {lmod.expr(c)}")
        body = r["task"]["body"]
        for k, c in r.get("inv_ast", []):
            guard = lmod.expr(body[k]["while"]["cond"])
            out.append(f"  invariant {lmod.expr(c)}    // the loop `while {guard}`")
        out.append("```")
        out.append("")
    return "\n".join(out) + "\n"


def table(results: list[dict], kernel: str | None) -> str:
    tried = [r for r in results if r.get("before") and (r.get("status") == "ok" or "never reads" in r.get("status", ""))]
    blind = [r for r in tried if "never reads" in r.get("status", "")]
    full = [r for r in tried if r.get("clauses") and r.get("after") == 0]
    lines = ["# Specification repair", "",
             "For each task whose spec admits a survivor (`t/audit.py`), the clauses `t/contract_repair.py` adds: each holds for "
             "the real program at every domain point, and together they kill every survivor they can. **after** is "
             "the repaired task's own audit, from scratch.", "",
             f"- tasks with survivors: {len(tried)}; repaired to zero survivors: {len(full)}",
             f"- refused because the real body never reads its parameters: {len(blind)}"]
    if kernel:
        proved = [r for r in full if r.get("real") == "verified" and r.get("twin") == "refuted"]
        lines.append(f"- {kernel}: repaired contract proved for the real body, twin refuted: {len(proved)} of {len(full)}")
    lines += ["", "| task | survivors before | after | " + (f"{kernel} real / twin | " if kernel else "")
              + "clauses added |", "|---|---|---|" + ("---|" if kernel else "") + "---|"]
    for r in sorted(tried, key=lambda r: r["name"]):
        kv = f" {r.get('real', '')} / {r.get('twin', '')} |" if kernel else ""
        cl = "; ".join(f"`{c}`" for c in r.get("clause_text", [])) or "(none found)"
        lines.append(f"| {r['name']} | {r['before']} | {r['after']} |{kv} {cl.replace('|', chr(92) + '|')} |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="contract_repair.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("target", metavar="FILE|DIR")
    ap.add_argument("--kernel", help="verify each repaired task in this kernel")
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--table", metavar="PATH")
    ap.add_argument("--write", metavar="DIR", help="write each repaired task here as JSON")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--patches", metavar="PATH", help="with --kernel: the proved repairs as source lines (R2)")
    args = ap.parse_args(argv)
    target = Path(args.target)
    files = ([str(p) for p in sorted(target.iterdir()) if p.suffix in (".t", ".json")] if target.is_dir()
             else [str(target)])
    if args.jobs > 1:
        with ProcessPoolExecutor(max_workers=args.jobs) as ex:
            results = list(ex.map(repair_file, files, [args.kernel] * len(files)))
    else:
        results = [repair_file(f, args.kernel) for f in files]
    for r in results:
        if args.write and r.get("task") and r.get("clauses"):
            out = Path(args.write)
            out.mkdir(parents=True, exist_ok=True)
            (out / (Path(r["file"]).stem + ".json")).write_text(json.dumps(r["task"], indent=1, sort_keys=True))
        line = dict(r)
        line.pop("task", None)
        line.pop("clauses", None)
        if args.json:
            print(json.dumps(line, sort_keys=True))
        elif r.get("before"):
            print(f"{r['name']}: {r['before']} -> {r.get('after')} survivors"
                  + (f"; {r.get('kernel')}: {r.get('real')} / {r.get('twin')}" if r.get("kernel") else "")
                  + "".join(f"\n  + ensures {c}" for c in r.get("clause_text", []))
                  + "".join(f"\n  + invariant {c}" for c in r.get("invariants", []))
                  + (f"\n  (with the invariants: {r.get('real_r1b')} / {r.get('twin_r1b')})" if "real_r1b" in r else ""))
    if args.table:
        Path(args.table).write_text(table(results, args.kernel), encoding="utf-8", newline="\n")
    if args.patches and args.kernel:
        Path(args.patches).write_text(patches(results, args.kernel), encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
