#!/usr/bin/env python3
"""t/lift_check_lean.py -- prove, in Lean itself, that a task lifted from a Lean file states
the same contract as the file: the native equivalence check of the Lean track (the Lean
half of what `t/lift_check_verus.py` does for Verus; read that docstring first).

The harness holds the source's own definitions, verbatim (without `import Mathlib`: the
kernels here run core Lean 4.33.1, so a source that needs Mathlib to elaborate gets no
harness, by name), the lifted contract lowered by `t/lower_lean.py`'s own `Lower` printer,
and two theorems over the SOURCE's parameter types:

    theorem t_eq_requires (xs) : <source requires> ↔ t_lift_pre <views>
    theorem t_eq_ensures (xs) (result) (h : <source requires>) :
        <source ensures> ↔ t_lift_post <views> <view of result>

For the pre/post shape the source requires and ensures ARE the source's `f_precond` and
`f_postcond` definitions, applied; for the specification-theorem shape they are the
theorem's hypotheses and its conclusion with the program's application `f xs` replaced by
`result`, a token-level substitution on the statement as written (any other mention of `f`
gets no harness). Views: `Nat` as `(x : Int)`, `Array Int` as `x.toList`, a `Nat`
collection mapped to `Int` elementwise.

The proof is a fixed tactic cascade, the same one for every task (unfold every definition
both sides reach, then `omega`, `simp`, or `grind`, Lean 4 reference "The grind tactic");
nothing is written per task. `#print axioms` on both theorems must show no `sorryAx`
(t/verifiers/lean.py's audit rule).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

import lift_lean
import lower_lean

LEAN_BIN = Path(os.environ.get("T_LEAN_BIN", Path.home() / ".elan/bin/lean"))


def memory_capped(cmd: list) -> list:
    """`cmd` under a per-prover memory cap when T_PROVER_MEMORY_MAX is set (e.g. 3G):
    a transient systemd scope, whose MemoryMax the kernel enforces on the whole process
    tree (systemd.resource-control(5), freedesktop.org/software/systemd/man/latest/
    systemd.resource-control.html). A 14.6 GB desktop lost a run to one z3 at 8.5 GB."""
    cap = os.environ.get("T_PROVER_MEMORY_MAX")
    if cap and shutil.which("systemd-run"):
        return ["systemd-run", "--user", "--scope", "--quiet", "-p", f"MemoryMax={cap}", "--"] + cmd
    return cmd


class NoHarness(Exception):
    pass


def _view(name: str, t: lift_lean.LType) -> str:
    k = t.kind
    if k == "int" or k == "bool":
        return name
    if k == "nat":
        return f"(({name} : Nat) : Int)"
    if k == "prop":
        raise NoHarness("a Prop value")
    if k == "seq":
        base = f"{name}.toList" if t.text.strip().startswith("Array") else name
        if t.elem.kind == "nat":
            return f"({base}.map (fun (v : Nat) => (v : Int)))"
        if t.elem.kind == "char":
            return f"({base}.map (fun (c : Char) => (c.toNat : Int)))"
        return base
    if k == "string":
        # feature 6 (2026-09-27): a String is its list of chars, each its
        # code point (Lean core: `String.toList s = s.data`; `Char.toNat`)
        return f"({name}.toList.map (fun (c : Char) => (c.toNat : Int)))"
    if k == "char":
        return f"(({name}.toNat : Nat) : Int)"
    raise NoHarness(f"type {t.text}")


def _reach_defs(lf: lift_lean.LeanFile, roots: set[str]) -> list[str]:
    """Source definitions reachable from `roots` by name mention, in file order."""
    names = list(lf.defs)
    seen, stack = set(), list(roots)
    while stack:
        n = stack.pop()
        if n in seen or n not in lf.defs:
            continue
        seen.add(n)
        for m in names:
            if m not in seen and re.search(r"(?<![\w.])" + re.escape(m) + r"(?![\w'])", lf.defs[n].text):
                stack.append(m)
    return [n for n in names if n in seen]


def _substitute_program(stmt_text: str, fname: str, params: list[str], result: str) -> str:
    """`fname p1 .. pn` -> `result` in token text; any other mention of fname refuses."""
    pat = re.compile(r"\(\s*" + re.escape(fname) + r"\s+" + r"\s+".join(map(re.escape, params)) + r"\s*\)"
                     if params else r"(?<![\w.])" + re.escape(fname) + r"(?![\w'])")
    out = pat.sub(result, stmt_text)
    if params:
        out = re.sub(r"(?<![\w.])" + re.escape(fname) + r"\s+" + r"\s+".join(map(re.escape, params))
                     + r"(?![\w'])", result, out)
    if re.search(r"(?<![\w.])" + re.escape(fname) + r"(?![\w'_])", out):
        raise NoHarness(f"{fname} mentioned other than applied to its own parameters")
    return out


def build(source_text: str, task: dict) -> tuple[str, list[str]]:
    r = lift_lean.render(source_text)
    if r.refusal is not None or r.file is None:
        raise NoHarness("the source does not render")
    lf = r.file
    fn = lf.defs[r.target]
    params = [b for b in fn.binders if b.type.kind != "proof"]
    if len(params) != len(task["params"]):
        raise NoHarness(f"{len(params)} source parameters, {len(task['params'])} lifted")
    pnames = [b.name for b in params]
    decl = " ".join(f"({b.name} : {b.src})" for b in params)
    views = " ".join(_view(b.name, b.type) for b in params)
    result = r.result_name if r.result_name != fn.name else "result"
    rview = _view(result, fn.ret)
    roots: set[str] = set()
    if r.shape == "pre-post":
        post = lf.defs[f"{fn.name}_postcond"]
        pre = lf.defs.get(f"{fn.name}_precond")
        hyp_binder = next((b for b in post.binders if b.type.kind == "proof"), None)
        pre_text = f"{pre.name} {' '.join(pnames)}" if pre is not None else "True"
        if pre is not None:
            roots.add(pre.name)
        roots.add(post.name)
        args = " ".join(pnames + [result] + (["h"] if hyp_binder is not None else []))
        post_text = f"{post.name} {args}"
    else:
        thm = next(t for n, t in lf.theorems.items() if n.startswith(f"{fn.name}_spec"))
        stmt = thm.stmt_text
        if not stmt:
            raise NoHarness("theorem statement")
        hyps, conc = _split_hyps(stmt, fn.name)
        pre_text = " ∧ ".join(f"({h})" for h in hyps) or "True"
        post_text = _substitute_program(conc, fn.name, pnames, result)
        roots |= set(re.findall(r"[A-Za-z_][\w.']*", stmt))
    roots |= set(re.findall(r"[A-Za-z_][\w.']*", fn.text))
    roots.discard(fn.name)
    src_defs = [lf.defs[n].text for n in _reach_defs(lf, roots) if n != fn.name]

    # the lifted contract, printed by lower_lean's own Lower
    lo = lower_lean.Lower(task, task["body"])
    sfuns = []
    for f in task.get("spec_funs", []):
        ptypes = {p["name"]: p["type"] for p in f["params"]}
        pb = lo.binders([(p["name"], p["type"]) for p in f["params"]])
        body_t = lo.term(f["body"], {}, dict(ptypes), dep=True)
        text = f"def {f['name']}_s {pb} : {lo.lean_type(f['result'])} :=\n  {body_t}"
        if lo._self_calls_named(f["body"], f["name"]):
            text += f"\ntermination_by ({lo.term(f['decreases'], {}, dict(ptypes))}).toNat"
            text += "\n" + lo._dec().rstrip("\n")
        sfuns.append(text)
    tparams = [(p["name"], p["type"]) for p in task["params"]]
    tb = lo.binders(tparams)
    pre_l = " ∧ ".join(f"({x})" for x in lo.pre_props()) or "True"
    ret = task["returns"][0]
    post_l = " ∧ ".join(f"({lo.prop(e, {}, lo.types)})" for e in task["ensures"])
    lifted = "\n\n".join(sfuns) + "\n\n" if sfuns else ""
    lifted += (f"def t_lift_pre {tb} : Prop :=\n  {pre_l}\n\n"
               f"def t_lift_post {lo.binders(tparams + [(ret['name'], ret['type'])])} : Prop :=\n  {post_l}\n")
    unfold = sorted(set(re.findall(r"^(?:@\[[^\]]*\]\s*)?(?:noncomputable\s+)?def\s+([^\s(:{]+)",
                                   "\n".join(src_defs), re.M))
                    | {f"{f['name']}_s" for f in task.get("spec_funs", [])} | {"t_lift_pre", "t_lift_post"})
    simp_set = ", ".join(unfold)
    reducible = {n for n in unfold if n in lf.defs and "reducible" in lf.defs[n].text.split(":=")[0]}
    grind_set = ", ".join(n for n in unfold if n not in reducible)
    tac = ("by\n  first\n"
           f"  | (simp only [{simp_set}]; done)\n"
           f"  | (simp only [{simp_set}] <;> omega)\n"
           f"  | (simp [{simp_set}]; done)\n"
           f"  | (simp [{simp_set}] <;> omega)\n"
           f"  | (unfold {' '.join(unfold)}; constructor <;> intro h <;> omega)\n"
           f"  | (grind [{grind_set}])\n")
    hyp = f" (h : {pre_text})"
    text = ("-- equivalence harness, t/lift_check_lean.py\n\n"
            "-- ---- the source's own definitions, as written\n" + "\n\n".join(src_defs) + "\n\n"
            "-- ---- the lifted contract, lowered by t/lower_lean.py\n" + lifted + "\n"
            f"theorem t_eq_requires {decl} :\n    ({pre_text}) ↔ t_lift_pre {views} := {tac}\n"
            f"theorem t_eq_ensures {decl} ({result} : {fn.ret_src}){hyp} :\n"
            f"    ({post_text}) ↔ t_lift_post {views} {rview} := {tac}\n"
            "#print axioms t_eq_requires\n#print axioms t_eq_ensures\n")
    return text, ["t_eq_requires", "t_eq_ensures"]


def _top_level_colon(text: str) -> Optional[int]:
    depth = 0
    start = text.find("theorem")
    for k in range(start, len(text)):
        c = text[k]
        if c in "([{⟨":
            depth += 1
        elif c in ")]}⟩":
            depth -= 1
        elif c == ":" and depth == 0 and text[k:k + 2] != ":=":
            return k
    return None


def _split_hyps(stmt: str, fname: str) -> tuple[list[str], str]:
    """Top-level `H →` premises not mentioning fname, and the conclusion."""
    hyps = []
    rest = stmt.strip()
    while True:
        depth, cut = 0, None
        for k, c in enumerate(rest):
            if c in "([{⟨":
                depth += 1
            elif c in ")]}⟩":
                depth -= 1
            elif depth == 0 and rest.startswith("→", k):
                cut = k
                break
            elif depth == 0 and (rest.startswith("∀", k) or rest.startswith("∃", k) or rest.startswith("let ", k)):
                break
        if cut is None:
            return hyps, rest
        head = rest[:cut].strip()
        if re.search(r"(?<![\w.])" + re.escape(fname) + r"(?![\w'])", head):
            return hyps, rest
        hyps.append(head)
        rest = rest[cut + 1:].strip()


def run(text: str, workdir: Path, stem: str, timeout_s: float = 180.0) -> dict:
    workdir.mkdir(parents=True, exist_ok=True)
    path = workdir / (re.sub(r"[^A-Za-z0-9_]", "_", stem) + "_eq.lean")
    path.write_text(text, encoding="utf-8")
    started = time.monotonic()
    try:
        p = subprocess.run(memory_capped([str(LEAN_BIN), str(path)]), capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return {"verdict": "error", "seconds": round(time.monotonic() - started, 1), "message": "timeout"}
    except OSError as e:
        return {"verdict": "error", "seconds": 0.0, "message": f"lean did not start: {e}"}
    secs = round(time.monotonic() - started, 1)
    out = p.stdout + p.stderr
    errors = [ln for ln in out.splitlines() if ": error" in ln]
    audit = re.findall(r"'(t_eq_requires|t_eq_ensures)' (?:depends on axioms: \[([^\]]*)\]|does not depend on any axioms)",
                       out)
    clean = len(audit) == 2 and all("sorryAx" not in (ax or "") for _n, ax in audit)
    if p.returncode == 0 and not errors and clean:
        return {"verdict": "proved", "seconds": secs, "message": ""}
    first = errors[0] if errors else (out.strip().splitlines() or [""])[0]
    at = None
    m = re.search(r":(\d+):\d+: error", first)
    if m:
        lines = text.splitlines()
        for k in range(min(int(m.group(1)), len(lines)) - 1, -1, -1):
            mm = re.match(r"\s*(?:theorem|def)\s+(\S+)", lines[k])
            if mm:
                at = mm.group(1)
                break
    return {"verdict": "not-proved" if (errors and at in ("t_eq_requires", "t_eq_ensures")) else
            ("no-harness" if errors else "not-proved"),
            "seconds": secs, "message": re.sub(r"^\S+:\d+:\d+: ", "", first)[:300], "at": at}


def check(source_path: Path, task: dict, workdir: Path, stem: str, timeout_s: float = 180.0) -> dict:
    try:
        text, lemmas = build(source_path.read_text(encoding="utf-8"), task)
    except NoHarness as e:
        return {"verdict": "no-harness", "message": str(e)}
    except (lift_lean.LeanRefusal, KeyError, ValueError, AssertionError, NotImplementedError, StopIteration) as e:
        return {"verdict": "no-harness", "message": f"{type(e).__name__}: {e}"}
    res = run(text, workdir, stem, timeout_s)
    res["lemmas"] = lemmas
    return res


if __name__ == "__main__":
    import argparse
    import tempfile
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("source")
    ap.add_argument("task")
    ap.add_argument("--work", default=tempfile.gettempdir())
    ap.add_argument("--print", action="store_true")
    a = ap.parse_args()
    task = json.loads(Path(a.task).read_text())
    if a.print:
        print(build(Path(a.source).read_text(), task)[0])
    else:
        print(json.dumps(check(Path(a.source), task, Path(a.work), Path(a.task).stem), indent=2))
