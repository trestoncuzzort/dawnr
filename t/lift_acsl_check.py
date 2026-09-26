#!/usr/bin/env python3
r"""t/lift_acsl_check.py -- is a lifted task the C/ACSL function it came from? (2026-09-26)

Two instruments, strongest first, and a trust level per task that says which
of them agreed.

1. Frama-C/WP, specification equivalence. One C file per task: the source's
   own headers (its typedefs and every logic definition, verbatim through
   Frama-C's preprocessor), then ACSL lemmas, and WP proves them
   (`-wp-prop` restricted to these; the corpus's own lemmas stay available as
   hypotheses, which is how the corpus itself proves things). Every lemma
   quantifies the source's variables at their C types, so it speaks about
   exactly the source's domain (ACSL manual, "Quantification on C integral
   types"). The lifted clauses are printed back into ACSL from the t task,
   with each lifted spec function written as the source logic function it
   came from; that identification is itself proved, below.

     tlift_pre        SRC_PRE <==> LIFT_PRE
     tlift_post       SRC_PRE ==> (SRC_POST <==> LIFT_POST)            (\result as `result`)
     tlift_inv_k      SRC_PRE ==> (SRC_INV_k <==> LIFT_INV_k)          (per loop, locals quantified)
     tlift_var_k      SRC_PRE && SRC_INV_k ==> src_variant == lift_decreases
     tlift_eqn_F      D_F(x) ==> G(x) == body_F(x)[F := G]
     tlift_close_F_j  D_F(x) && path_j ==> D_F(args_j)                 (per self-call j of F)
     tlift_site_F_j   context_j ==> D_F(args_j)                        (per call of F in a clause)

   F is a lifted spec function (its array reads guarded, see lift_acsl.py),
   G the source's recursive logic function, D_F the domain the front end
   wrote for it (bounds of its index parameters). eqn says G satisfies F's
   defining equation on D_F; close says D_F is closed under F's recursion;
   F's measure is well-founded (every kernel proves the lifted `decreases`).
   So by induction on the measure F(x) = G(x) for every x in D_F, and
   `site` puts every call the lifted clauses make inside D_F. Hence printing F
   as G is exact at every place the task uses it, and the three equivalence
   lemmas compare the source's clauses with the lifted ones as the same
   formulas over the same functions. No lemma needs induction, which WP's
   automatic provers do not do. t's Euclidean `div`/`mod` is printed with
   lower_framac's own definitions (t_div, t_mod), so a truncating ACSL `/`
   is compared against the Euclidean one it was lifted to, not assumed equal.

2. The differential run. The source C function, compiled as it is
   (`gcc -fsanitize=undefined`, the corpus's own .c), and the lifted task in
   t's interpreter, on inputs drawn at random and kept when the LIFTED
   requires holds; a disagreement refuses the task (`lift-diff-failed`), and
   a C run that trips the sanitizer on an input the lifted requires admits
   refuses it too (`lift-diff-ub`): the lifted domain would then be wider
   than the source's. This is the body check; WP above checks the
   specification.

Trust levels (the `trust` field, also in the coverage table):
    wp-equivalent+differential   every lemma proved, differential agreed on >= 1 input
    wp-equivalent                every lemma proved, no drawn input satisfied requires
    differential                 some lemma unproved within budget, differential agreed
    (refused)                    differential disagreed, sanitizer fired, or no evidence;
                                 a task whose specification divides by something the
                                 front end could not show non-negative (`spec_division`)
                                 is refused unless every lemma is proved
                                 (`spec-division-unproved`)

At most two prover processes on the desktop (`--wp-par 2`); the lab runs it
with more. Research receipt 4ba9253bafdb (the ACSL manual sections this relies
on); INVENTED: the lemma scheme above.
"""
from __future__ import annotations

import json
import os
import random
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import interp

T_DIVMOD_ACSL = (
    "/*@\n"
    "  logic integer t_mod(integer x, integer y) =\n"
    "    (x % y < 0) ? x % y + \\abs(y) : x % y;\n"
    "  logic integer t_div(integer x, integer y) =\n"
    "    (x % y < 0) ? (x / y) - (y > 0 ? 1 : -1) : x / y;\n"
    "*/\n"
)   # lower_framac.T_DIVMOD_ACSL, copied so this module does not import the 9,600-line lowering

FRAMAC = shutil.which("frama-c") or os.path.expanduser("~/.opam/default/bin/frama-c")
PROVERS = ("alt-ergo,z3", "alt-ergo")     # the second only when why3 does not know the z3 on PATH
# One z3 reached 8.5 GB on the 14.6 GB desktop (2026-09-26): every prover this module
# starts runs in a memory-capped scope where systemd-run exists. T_PROVER_MEMCAP=0
# turns it off (the lab), any other value replaces the 3G cap.
MEMCAP = os.environ.get("T_PROVER_MEMCAP", "3G")


def capped(cmd: list) -> list:
    """cmd under `systemd-run --user --scope -p MemoryMax=...` when available (the
    memory limit applies to the whole process tree, provers included:
    https://www.freedesktop.org/software/systemd/man/latest/systemd.resource-control.html)."""
    if MEMCAP in ("", "0") or not shutil.which("systemd-run"):
        return cmd
    return ["systemd-run", "--user", "--scope", "-q", "-p", f"MemoryMax={MEMCAP}", "--"] + cmd


# ------------------------------------------------------------ t -> ACSL --

class Printer:
    """t expressions back into ACSL, over the source's names.

    `names`: lifted variable name -> source name. `seq_len`: lifted seq name ->
    the ACSL term for its length. `funs`: lifted spec-fun name -> (ACSL name,
    result kind). `types`: lifted variable name -> "int" | "bool" | "seq"."""

    def __init__(self, names: dict, seq_len: dict, funs: dict, types: dict):
        self.names = dict(names)
        self.seq_len = dict(seq_len)
        self.funs = funs
        self.types = dict(types)
        self.divmod = False
        self.fresh = 0

    def is_bool(self, e: dict) -> bool:
        if "bool" in e:
            return True
        if "var" in e:
            return self.types.get(e["var"]) == "bool"
        if "forall" in e or "exists" in e:
            return True
        if "ite" in e:
            return self.is_bool(e["ite"]["then"])
        if "call" in e:
            return self.funs.get(e["call"]["fun"], ("", "int"))[1] == "bool"
        op = e.get("op")
        return op in ("==", "!=", "<", "<=", ">", ">=", "and", "or", "not", "implies")

    def term(self, e: dict) -> str:
        if "int" in e:
            v = e["int"]
            return str(v) if v >= 0 else f"({v})"
        if "bool" in e:
            return "1" if e["bool"] else "0"
        if "var" in e:
            nm = self.names.get(e["var"], e["var"])
            if self.types.get(e["var"]) == "bool":
                return f"({nm} != 0 ? 1 : 0)"
            return nm
        if "ite" in e:
            it = e["ite"]
            return f"({self.pred(it['cond'])} ? {self.term(it['then'])} : {self.term(it['else'])})"
        if "call" in e:
            c = e["call"]
            name, kind = self.funs[c["fun"]]
            s = f"{name}({', '.join(self.arg(a) for a in c['args'])})"
            return f"({s} ? 1 : 0)" if kind == "bool" else s
        if self.is_bool(e):
            return f"({self.pred(e)} ? 1 : 0)"
        op, args = e["op"], e["args"]
        if op == "neg":
            return f"(-{self.term(args[0])})"
        if op in ("+", "-", "*"):
            return "(" + f" {op} ".join(self.term(a) for a in args) + ")"
        if op in ("div", "mod"):
            self.divmod = True
            return f"t_{op}({self.term(args[0])}, {self.term(args[1])})"
        if op == "len":
            s = args[0].get("var")
            if s not in self.seq_len:
                raise ValueError(f"len of {args[0]}")
            return self.seq_len[s]
        if op == "at":
            return f"{self.arg(args[0])}[{self.term(args[1])}]"
        raise ValueError(f"no ACSL for op {op}")

    def arg(self, e: dict) -> str:
        if "var" in e and self.types.get(e["var"]) == "seq":
            return self.names.get(e["var"], e["var"])
        return self.term(e)

    def pred(self, e: dict) -> str:
        if "bool" in e:
            return "\\true" if e["bool"] else "\\false"
        if "var" in e:
            if self.types.get(e["var"]) == "bool":
                return f"({self.names.get(e['var'], e['var'])} != 0)"
            raise ValueError(f"non-bool var {e['var']} as predicate")
        if "ite" in e:
            it = e["ite"]
            return f"({self.pred(it['cond'])} ? {self.pred(it['then'])} : {self.pred(it['else'])})"
        if "call" in e:
            c = e["call"]
            name, kind = self.funs[c["fun"]]
            s = f"{name}({', '.join(self.arg(a) for a in c['args'])})"
            return s if kind == "bool" else f"({s} != 0)"
        for q in ("forall", "exists"):
            if q in e:
                b = e[q]
                v = b["var"]
                self.fresh += 1
                nv = f"tq{self.fresh}_{v}"
                saved = (self.names.get(v), self.types.get(v))
                lo, hi = self.term(b["lo"]), self.term(b["hi"])
                self.names[v] = nv
                self.types[v] = "int"
                body = self.pred(b["body"])
                if saved[0] is None:
                    self.names.pop(v, None)
                else:
                    self.names[v] = saved[0]
                if saved[1] is None:
                    self.types.pop(v, None)
                else:
                    self.types[v] = saved[1]
                if q == "forall":
                    return f"(\\forall integer {nv}; {lo} <= {nv} < {hi} ==> {body})"
                return f"(\\exists integer {nv}; {lo} <= {nv} < {hi} && {body})"
        op, args = e["op"], e["args"]
        if op == "and":
            return "(" + " && ".join(self.pred(a) for a in args) + ")"
        if op == "or":
            return "(" + " || ".join(self.pred(a) for a in args) + ")"
        if op == "not":
            return f"(!{self.pred(args[0])})"
        if op == "implies":
            return f"({self.pred(args[0])} ==> {self.pred(args[1])})"
        if op in ("==", "!="):
            if self.is_bool(args[0]) or self.is_bool(args[1]):
                s = f"({self.pred(args[0])} <==> {self.pred(args[1])})"
                return s if op == "==" else f"(!{s})"
            return f"({self.term(args[0])} {op} {self.term(args[1])})"
        if op in ("<", "<=", ">", ">="):
            return f"({self.term(args[0])} {op} {self.term(args[1])})"
        return f"({self.term(e)} != 0)"


def conj(parts: list[str]) -> str:
    return "(" + " && ".join(f"({p})" for p in parts) + ")" if parts else "\\true"


# ----------------------------------------------------- call-site contexts --

def calls_with_context(e: dict, pc: list, out: list, funs: set) -> None:
    """Every call to one of `funs` in e, with the path condition (t expressions)
    under which t evaluates it: short-circuit `and`/`implies`/`or`, `ite`
    branches, quantifier ranges (SPEC.md: and/or short-circuit)."""
    if not isinstance(e, dict):
        return
    if "call" in e:
        c = e["call"]
        for a in c["args"]:
            calls_with_context(a, pc, out, funs)
        if c["fun"] in funs:
            out.append((c, list(pc)))
        return
    if "ite" in e:
        it = e["ite"]
        calls_with_context(it["cond"], pc, out, funs)
        calls_with_context(it["then"], pc + [it["cond"]], out, funs)
        calls_with_context(it["else"], pc + [{"op": "not", "args": [it["cond"]]}], out, funs)
        return
    for q in ("forall", "exists"):
        if q in e:
            b = e[q]
            calls_with_context(b["lo"], pc, out, funs)
            calls_with_context(b["hi"], pc, out, funs)
            rng = {"op": "and", "args": [{"op": "<=", "args": [b["lo"], {"var": b["var"]}]},
                                         {"op": "<", "args": [{"var": b["var"]}, b["hi"]]}]}
            calls_with_context(b["body"], pc + [("bind", b["var"]), rng], out, funs)
            return
    if "op" in e:
        op, args = e["op"], e["args"]
        if op in ("and", "implies"):
            acc = list(pc)
            for a in args:
                calls_with_context(a, acc, out, funs)
                acc = acc + [a]
            return
        if op == "or":
            acc = list(pc)
            for a in args:
                calls_with_context(a, acc, out, funs)
                acc = acc + [{"op": "not", "args": [a]}]
            return
        for a in args:
            calls_with_context(a, pc, out, funs)


def pc_formula(pr: Printer, ctx: list[str], pc: list, goal) -> str:
    """ctx && pc ==> goal, with quantifier-bound names of pc universally closed."""
    binders = []
    hyps = list(ctx)
    for p in pc:
        if isinstance(p, tuple) and p[0] == "bind":
            v = p[1]
            pr.fresh += 1
            nv = f"tb{pr.fresh}_{v}"
            pr.names[v] = nv
            pr.types[v] = "int"
            binders.append(nv)
        else:
            hyps.append(pr.pred(p))
    goal = goal() if callable(goal) else goal       # printed after the binders are named
    body = f"{conj(hyps)} ==> {goal}"
    for nv in reversed(binders):
        body = f"\\forall integer {nv}; {body}"
    return body


# ------------------------------------------------------------ the lemmas --

def body_loops(body: list) -> list:
    out = []
    for s in body:
        if "while" in s:
            out.append(s["while"])
            out += body_loops(s["while"]["body"])
        elif "if" in s:
            out += body_loops(s["if"]["then"]) + body_loops(s["if"]["else"])
    return out


def body_vars(body: list) -> list:
    out = []
    for s in body:
        if "var" in s:
            out.append(s["var"])
        elif "while" in s:
            out += body_vars(s["while"]["body"])
        elif "if" in s:
            out += body_vars(s["if"]["then"]) + body_vars(s["if"]["else"])
    return out


def build(task: dict, record: dict, side: dict) -> dict:
    """The check file's ACSL (lemmas) and the names of the lemmas, or raises ValueError."""
    params = [p for p in side["params"]]
    tparams = task["params"]
    kept = [p for p in params if p["role"] != "len"]
    if len(kept) != len(tparams):
        raise ValueError("parameter lists do not align")
    names, types, seq_len = {}, {}, {}
    cdecl = {}          # source name -> C type text for quantification
    for p, tp in zip(kept, tparams):
        names[tp["name"]] = p["dafny_name"]
        types[tp["name"]] = tp["type"] if isinstance(tp["type"], str) else "other"
        if p["role"] == "seq":
            seq_len[tp["name"]] = p["of"]
    for p in params:
        ct = p["c_type"].replace("const ", "")
        cdecl[p["dafny_name"]] = ct
    # locals: lifted `var` statements in order <-> the front end's locals in order
    lvars = body_vars(task["body"])
    if len(lvars) != len(side["locals"]):
        raise ValueError(f"locals do not align ({len(lvars)} lifted, {len(side['locals'])} source)")
    for v, l in zip(lvars, side["locals"]):
        names[v["name"]] = l["dafny_name"]
        types[v["name"]] = v["type"] if isinstance(v["type"], str) else "other"
        cdecl[l["dafny_name"]] = l["c_type"].replace("const ", "")
    ret = task["returns"][0]
    names[ret["name"]] = "result"
    types[ret["name"]] = ret["type"] if isinstance(ret["type"], str) else "other"
    # spec functions: t name -> the source logic function
    rename = {k: v["t_name"] for k, v in (record.get("rename_map") or {}).items()}
    by_dafny = {r["dafny_name"]: r for r in side["rec_funs"]}
    funs, recs = {}, {}
    for f in task.get("spec_funs", []):
        src = None
        for dn, r in by_dafny.items():
            if rename.get(dn, dn) == f["name"]:
                src = r
        if src is None:
            raise ValueError(f"spec fun {f['name']} has no source logic function")
        funs[f["name"]] = (src["acsl_name"], src["result"])
        recs[f["name"]] = (f, src)
    pr = Printer(names, {k: v for k, v in seq_len.items()}, funs, types)

    lemmas: list[tuple[str, str]] = []
    src_pre = side["src_pre"]
    lift_pre = [pr.pred(r) for r in task.get("requires", [])]
    lift_post = [pr.pred(e) for e in task["ensures"]]
    # quantified variables
    param_decl = [f"{cdecl[p['dafny_name']]} {p['dafny_name']}" for p in params if p["role"] != "seq"]
    ptr_decl = [f"{cdecl[p['dafny_name']]} {p['dafny_name']}".replace("* ", " *") for p in params
                if p["role"] == "seq"]
    ret_c = side["ret"]["c_type"]

    def forall(decls: list[str], body: str) -> str:
        out = body
        for d in reversed(decls):
            ty, nm = d.rsplit(" ", 1)
            if nm.startswith("*"):
                ty, nm = ty + " *", nm[1:]
            out = f"\\forall {ty} {nm}; {out}"
        return out

    base = ptr_decl + param_decl
    lemmas.append(("tlift_pre", forall(base, f"{conj(src_pre)} <==> {conj(lift_pre)}")))
    lemmas.append(("tlift_post", forall(base + [f"{ret_c} result"],
                                        f"{conj(src_pre)} ==> ({conj(side['src_post'])} <==> {conj(lift_post)})")))
    loops = body_loops(task["body"])
    if len(loops) != len(side["src_loops"]):
        raise ValueError("loops do not align")
    local_decl = [f"{l['c_type'].replace('const ', '')} {l['dafny_name']}" for l in side["locals"]]
    for k, (lp, sl) in enumerate(zip(loops, side["src_loops"])):
        linv = [pr.pred(i) for i in lp["invariants"]]
        lemmas.append((f"tlift_inv_{k}", forall(base + local_decl,
                                                f"{conj(src_pre)} ==> ({conj(sl['inv'])} <==> {conj(linv)})")))
        if sl.get("variant"):
            lemmas.append((f"tlift_var_{k}", forall(base + local_decl,
                                                    f"({conj(src_pre)} && {conj(sl['inv'])}) ==> "
                                                    f"({sl['variant']}) == ({pr.term(lp['decreases'])})")))
    # spec functions: equation, closure, call sites
    defs = []
    for fname, (f, src) in recs.items():
        fparams = [p["name"] for p in f["params"]]
        sparams = [pn for pn, _ in src["params"]]
        kinds = {pn: k for pn, k in src["params"]}
        dname = f"tlift_D_{src['dafny_name']}"
        dparams = []
        for pn in sparams:
            if kinds[pn] == "seq":
                dparams += [f"value_type* {pn}", f"integer {pn}_n"]
            else:
                dparams.append(f"integer {pn}")
        dom = " && ".join(src["domain"]) or "\\true"
        nonneg = " && ".join(f"{pn}_n >= 0" for pn in sparams if kinds[pn] == "seq") or "\\true"
        defs.append(f"predicate {dname}{{L}}({', '.join(dparams)}) = {nonneg} && {dom};")
        fpr = Printer({fp: sp for fp, sp in zip(fparams, sparams)},
                      {fp: f"{sp}_n" for fp, sp in zip(fparams, sparams) if kinds[sp] == "seq"},
                      funs, {fp: ("seq" if kinds[sp] == "seq" else "int") for fp, sp in zip(fparams, sparams)})
        qdecl = []
        declared = dict((pn, ty) for pn, ty in src.get("acsl_params") or [])
        for pn in sparams:
            if kinds[pn] == "seq":
                qdecl += [f"value_type *{pn}", f"integer {pn}_n"]
            else:
                # the source's declared type: ACSL has no implicit cast from integer to a C type
                qdecl.append(f"{declared.get(pn, 'integer')} {pn}")
        dargs = ", ".join((f"{pn}, {pn}_n" if kinds[pn] == "seq" else pn) for pn in sparams)
        head = f"{src['acsl_name']}({', '.join(sparams)})"
        if src["result"] == "bool":
            eq = f"({head} <==> {fpr.pred(f['body'])})"
        else:
            eq = f"({head} == {fpr.term(f['body'])})"
        lemmas.append((f"tlift_eqn_{src['dafny_name']}", forall(qdecl, f"{dname}({dargs}) ==> {eq}")))
        sites: list = []
        calls_with_context(f["body"], [], sites, {fname})
        for j, (c, pc) in enumerate(sites):
            goal = (lambda c=c: call_domain(fpr, dname, c, recs))
            lemmas.append((f"tlift_close_{src['dafny_name']}_{j}",
                           forall(qdecl, pc_formula(fpr, [f"{dname}({dargs})"], pc, goal))))
    if recs:
        # every call in the task's clauses, under its context
        clause_sets = [("pre", task.get("requires", []), [], base, lambda i: lift_pre[:i]),
                       ("post", task["ensures"], lift_pre, base + [f"{ret_c} result"], lambda i: lift_post[:i])]
        for k, lp in enumerate(loops):
            invs = [pr.pred(i) for i in lp["invariants"]]
            clause_sets.append((f"inv{k}", lp["invariants"], lift_pre, base + local_decl,
                                (lambda invs: (lambda i: invs[:i]))(invs)))
            clause_sets.append((f"dec{k}", [lp["decreases"]], lift_pre + invs, base + local_decl, lambda i: []))
        n = 0
        for tag, clauses, ctx0, decls, earlier in clause_sets:
            for i, cl in enumerate(clauses):
                sites = []
                calls_with_context(cl, [], sites, set(recs))
                for c, pc in sites:
                    goal = (lambda c=c: call_domain(pr, f"tlift_D_{recs[c['fun']][1]['dafny_name']}", c, recs))
                    lemmas.append((f"tlift_site_{tag}_{n}",
                                   forall(decls, pc_formula(pr, ctx0 + earlier(i), pc, goal))))
                    n += 1
    return {"defs": defs, "lemmas": lemmas, "divmod": pr.divmod}


def call_domain(pr: Printer, dname: str, c: dict, recs: dict) -> str:
    f, src = recs[c["fun"]]
    out = []
    for (pn, kind), a in zip(src["params"], c["args"]):
        if kind == "seq":
            nm = a.get("var")
            if nm is None or nm not in pr.seq_len:
                raise ValueError(f"spec fun called on a seq expression {a}")
            out += [pr.names.get(nm, nm), pr.seq_len[nm]]
        else:
            out.append(pr.term(a))
    return f"{dname}({', '.join(out)})"


def check_file(side: dict, built: dict) -> str:
    """The C file WP reads: the source header (typedefs, logic definitions), then the lemmas."""
    header = Path(side["c_file"]).with_suffix(".h")
    lines = ['#include "typedefs.h"']
    if header.is_file():
        lines.append(f'#include "{header.name}"')
    else:
        lines.append(f'#include "{Path(side["c_file"]).name}"')
    if built["divmod"]:
        lines.append(T_DIVMOD_ACSL)
    lines.append("/*@")
    for d in built["defs"]:
        lines.append("  " + d)
    for name, body in built["lemmas"]:
        lines.append(f"  lemma {name}{{L}}:\n    {body};")
    lines.append("*/")
    return "\n".join(lines) + "\n"


def run_wp(side: dict, built: dict, root: Path, work: Path, par: int = 2, timeout: int = 20) -> dict:
    """WP on the check file: {"lemmas": {name: status}, "proved": k, "total": n, "log": tail}."""
    work.mkdir(parents=True, exist_ok=True)
    src = check_file(side, built)
    cf = work / "check.c"
    cf.write_text(src, encoding="utf-8")
    incs = [str(root), str(root / "Logic"), str(Path(side["c_file"]).parent)]
    rj = work / "wp.json"
    if rj.exists():
        rj.unlink()
    names = [n for n, _ in built["lemmas"]]
    log = ""
    for provers in PROVERS:
        cmd = [FRAMAC, "-pp-annot", "-cpp-extra-args=" + " ".join(f"-I{i}" for i in incs), str(cf),
               "-wp", "-wp-prop", ",".join(names), "-wp-prover", provers, "-wp-timeout", str(timeout),
               "-wp-par", str(par), "-wp-cache", "none", "-wp-report-json", str(rj)]
        try:
            p = subprocess.run(capped(cmd), capture_output=True, text=True, timeout=60 + timeout * len(names) * 3)
            log = p.stdout + p.stderr
        except subprocess.TimeoutExpired as e:
            log = f"TIMEOUT {e}"
        # a z3 why3 does not know (another z3 first on PATH) is a missing tool, not a verdict
        if "Unknown prover" not in log:
            break
    log = f"[provers] {provers}\n" + log
    (work / "wp.log").write_text(log, encoding="utf-8")
    status = {n: "unknown" for n in names}
    for line in log.splitlines():
        m = re.search(r"\[wp\] \[(\w[\w ]*)\] Goal (?:\w+_)?lemma_(tlift_\w+)", line)
        if m:
            status[m.group(2)] = m.group(1)
    if rj.exists():
        try:
            rep = json.loads(rj.read_text())
            for entry in rep if isinstance(rep, list) else rep.get("goals", []):
                goal = entry.get("goal") or entry.get("property") or ""
                m = re.search(r"(tlift_\w+)", str(goal))
                if m and m.group(1) in status:
                    verdict = entry.get("verdict") or entry.get("status") or entry.get("result")
                    if verdict:
                        status[m.group(1)] = verdict
        except (json.JSONDecodeError, AttributeError):
            pass
    if "User Error" in log or "Frama-C aborted" in log:
        for n in status:
            if status[n] == "unknown":
                status[n] = "frama-c-error"
    proved = sum(1 for v in status.values() if v.lower() in ("valid", "proved", "qed") or v.lower().startswith("valid"))
    return {"lemmas": status, "proved": proved, "total": len(status), "provers": provers,
            "log": "\n".join(log.splitlines()[-25:])}


# -------------------------------------------------------- differential --

def draw_inputs(task: dict, rng: random.Random, n: int, side: dict) -> list[dict]:
    """Random inputs of the task's parameter types, kept when the lifted requires holds."""
    funs = interp.funs_of(task, task["body"])
    unsigned = {p["dafny_name"] for p in side["params"] if "unsigned" in p["c_type"] or "size_type" in p["c_type"]}
    out, tries = [], 0
    while len(out) < n and tries < n * 40:
        tries += 1
        env = {}
        L = rng.choice([0, 1, 2, 3, 4, 5, 6, 8])
        mode = rng.random()
        for p in task["params"]:
            t = p["type"]
            if t == "seq":
                xs = [rng.randint(-4, 4) for _ in range(L)]
                if mode < 0.35:
                    xs.sort()
                elif mode < 0.45:
                    xs = [xs[0]] * L if xs else xs
                env[p["name"]] = tuple(xs)
            elif t == "bool":
                env[p["name"]] = rng.random() < 0.5
            else:
                env[p["name"]] = rng.randint(0, 9) if p["name"] in unsigned else rng.randint(-6, 9)
        st = interp.St()
        try:
            if all(interp.ev(c, env, funs, st) for c in task.get("requires", [])):
                out.append(env)
        except (interp.Undef, interp.Budget, RecursionError):
            continue
    return out


def run_lifted(task: dict, env0: dict):
    funs = interp.funs_of(task, task["body"])
    env = dict(env0)
    ret = task["returns"][0]["name"]
    env[ret] = None
    interp.exec_body(task["body"], env, funs, interp.St())
    return env[ret]


def c_harness(side: dict, task: dict, inputs: list[dict]) -> str:
    """A main() calling the source function on every input, one result per line."""
    kept = [p for p in side["params"] if p["role"] != "len"]
    tmap = {tp["name"]: p for p, tp in zip(kept, task["params"])}
    lines = [f'#include "{Path(side["c_file"]).name}"', "#include <stdio.h>", "int main(void) {"]
    for k, env in enumerate(inputs):
        args = []
        arrays = {}
        for tname, v in env.items():
            p = tmap[tname]
            if p["role"] == "seq":
                arr = f"a{k}_{p['c_name']}"
                vals = ", ".join(str(x) for x in v) or "0"
                lines.append(f"  static const value_type {arr}[] = {{{vals}}};")
                arrays[p["c_name"]] = (arr, len(v))
        for p in side["params"]:
            if p["role"] == "seq":
                args.append(arrays[p["c_name"]][0])
            elif p["role"] == "len":
                args.append(f"{arrays[p['of']][1]}u")
            else:
                tname = [t for t, q in tmap.items() if q is p][0]
                v = env[tname]
                args.append(str(int(v)) + ("u" if "unsigned" in p["c_type"] or "size_type" in p["c_type"] else ""))
        ret_c = side["ret"]["c_type"]
        fmt = "%u" if ("size_type" in ret_c or "unsigned" in ret_c) else "%d"
        lines.append(f'  printf("{fmt}\\n", {side["function"]}({", ".join(args)}));')
    lines.append("  return 0;\n}")
    return "\n".join(lines) + "\n"


def run_differential(task: dict, side: dict, root: Path, work: Path, n: int = 120, seed: int = 20260926) -> dict:
    work.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    inputs = draw_inputs(task, rng, n, side)
    if not inputs:
        return {"inputs": 0, "agree": 0, "verdict": "no-input"}
    expected = []
    for env in inputs:
        try:
            expected.append(run_lifted(task, env))
        except (interp.Undef, interp.Budget, RecursionError) as e:
            return {"inputs": len(inputs), "agree": 0, "verdict": "lifted-undefined", "input": _show(env),
                    "detail": str(e)}
    src = c_harness(side, task, inputs)
    cf = work / "diff.c"
    cf.write_text(src, encoding="utf-8")
    exe = work / "diff.bin"
    incs = [root, root / "Logic", Path(side["c_file"]).parent]
    cc = ["gcc", "-std=c99", "-O0", "-fsanitize=undefined", "-fno-sanitize-recover=all", "-w",
          *[f"-I{i}" for i in incs], str(cf), "-o", str(exe)]
    p = subprocess.run(cc, capture_output=True, text=True)
    if p.returncode != 0:
        return {"inputs": len(inputs), "agree": 0, "verdict": "compile-error", "detail": p.stderr[-800:]}
    p = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
    got = p.stdout.split()
    if p.returncode != 0 or len(got) != len(inputs):
        k = len(got)
        return {"inputs": len(inputs), "agree": k, "verdict": "c-runtime-error",
                "input": _show(inputs[min(k, len(inputs) - 1)]), "detail": p.stderr[-800:]}
    ret_t = task["returns"][0]["type"]
    for env, e, g in zip(inputs, expected, got):
        gv = int(g)
        ev = (1 if e else 0) if ret_t == "bool" else e
        if gv != ev:
            return {"inputs": len(inputs), "agree": 0, "verdict": "disagree", "input": _show(env),
                    "lifted": _show(e), "c": gv}
    return {"inputs": len(inputs), "agree": len(inputs), "verdict": "agree"}


def _show(v):
    if isinstance(v, dict):
        return {k: _show(x) for k, x in v.items()}
    if isinstance(v, tuple):
        return list(v)
    return v


# --------------------------------------------------------------- verdict --

def check(task: dict, record: dict, side: dict, root: Path, work: Path, par: int = 2,
          timeout: int = 20, wp: bool = True) -> dict:
    """Both instruments and the trust level: {"trust", "refusal", "wp", "diff"}."""
    diff = run_differential(task, side, root, work)
    res: dict = {"diff": diff, "wp": None, "trust": None, "refusal": None}
    if diff["verdict"] in ("disagree",):
        res["refusal"] = "lift-diff-failed"
        return res
    if diff["verdict"] in ("c-runtime-error",):
        res["refusal"] = "lift-diff-ub"
        return res
    if diff["verdict"] in ("compile-error", "lifted-undefined"):
        res["refusal"] = f"lift-diff-{diff['verdict']}"
        return res
    all_proved = False
    if wp:
        try:
            built = build(task, record, side)
            res["wp"] = run_wp(side, built, root, work, par, timeout)
            res["wp"]["file"] = str(work / "check.c")
            all_proved = res["wp"]["total"] > 0 and res["wp"]["proved"] == res["wp"]["total"]
        except ValueError as e:
            res["wp"] = {"error": str(e), "proved": 0, "total": 0, "lemmas": {}}
    agreed = diff["verdict"] == "agree"
    if all_proved:
        res["trust"] = "wp-equivalent+differential" if agreed else "wp-equivalent"
    elif side.get("spec_division"):
        res["refusal"] = "spec-division-unproved"
    elif agreed:
        res["trust"] = "differential"
    else:
        res["refusal"] = "no-equivalence-evidence"
    return res
