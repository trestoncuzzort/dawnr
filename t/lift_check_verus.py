#!/usr/bin/env python3
"""t/lift_check_verus.py -- prove, in Verus itself, that a task lifted from a Verus file
states the same contract as the file: the native equivalence check of the Verus track.

`t/lift_verus.py` renders a Verus function as Dafny and `t/lifter.py` lifts that; the
lifter's own check (`t/lift_check.py`) then proves the lifted task equivalent to the
RENDERING, in Dafny. This module closes the remaining gap, rendering against source, by
putting the source's own declarations (verbatim, as written) beside the lifted spec
lowered back to Verus by the repo's own `t/lower_verus.py` expression printer, and asking
Verus for two lemmas on the SOURCE's parameter types:

    proof fn t_eq_requires(<source params>)
        ensures (<source requires, as written>) <==> t_lift_pre(<view of each param>)
    proof fn t_eq_ensures(<source params>, <source result>)
        requires <source requires>
        ensures (<source ensures, as written>) <==> t_lift_post(<views>, <view of result>)

A view is how a source value reads as a t value: a machine integer `x as int`, a `Vec<T>`
or slice of integers `x@.map_values(|v: T| v as int)`, a nested vector one level more,
a bool itself (Verus guide, "Integer types": ghost code compares integers of every width
as `int`; research receipt 030fff794977). The lemmas quantify over every value of the
source types, so the lifted contract equals the source contract on the source's domain
-- the same notion as t/lift_check.py's per-clause lemmas (LIFTER-DESIGN.md section 9),
stated once for the whole requires and once for the whole ensures.

Recursive spec fns. SMT unfolds a recursive definition only to a bounded fuel, so a source
spec fn and its lifted copy are equal only by induction. For a source spec fn whose
parameters are all integers, sequences of integers or bools and whose lifted image the
lifter's rename map names, the harness adds a `broadcast proof fn` stating
`f(x) == t_lift_f(view x)` with the source's own `decreases`, proved by calling itself at
every recursive call site of `f` under that site's `if` path (the structural induction
the Verus guide's "Recursive exec and proof functions, proofs by induction" chapter
writes by hand), and brings it into both lemmas with `broadcast use` (guide,
"Adding Ambient Facts to the Proof Environment with broadcast", receipt 4b3bde0de487).

Verdicts: "proved" (verus exit 0, no error), "not-proved" (verus ran and reported an
error, with the first message kept), "no-harness" (a construct the harness cannot state
on the source's types, named), "error" (verus did not run to a verdict: timeout, crash).
A task keeps its lift either way; the verdict is its trust label (t/lift_vericoding.py).
"""
from __future__ import annotations

import copy
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

import lift_verus
import lower_verus
import names

VERUS_BIN = Path(os.environ.get("T_VERUS", Path.home() / ".local/verus/verus-x86-linux/verus"))
RLIMIT = 30
LIFT_PREFIX = "t_lift_"


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
    """The harness cannot state this contract on the source's types."""


RANGES = {"i8": (-128, 127), "i16": (-32768, 32767), "i32": (-2147483648, 2147483647),
          "i64": (-9223372036854775808, 9223372036854775807),
          "i128": (-(2 ** 127), 2 ** 127 - 1), "u8": (0, 255), "u16": (0, 65535),
          "u32": (0, 4294967295), "u64": (0, 18446744073709551615), "u128": (0, 2 ** 128 - 1),
          "usize": (0, None), "isize": (None, None), "nat": (0, None), "char": (0, 1114111)}


def _tid(type_text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "_", type_text)


class Views:
    """The view spec fns a harness needs, one family per source element type, each with
    the three broadcast facts SMT cannot find on its own (measured on probes, 2026-09-26:
    a sequence element's own type range is not in context, a quantifier over the viewed
    sequence needs a trigger on the source index `s[i]`, and equality of views implies
    equality of sequences only through extensionality)."""

    def __init__(self):
        self.fams: dict[str, str] = {}
        self.uses: list[str] = []

    def _range(self, t: str) -> str:
        lo, hi = RANGES.get(t, (None, None))
        parts = []
        if lo is not None:
            parts.append(f"{lo} <= (x as int)")
        if hi is not None:
            parts.append(f"(x as int) <= {hi}")
        return ", ".join(parts)

    def family(self, elem: lift_verus.VType) -> str:
        if elem.kind in ("int", "nat", "char"):
            t = elem.text
            n = _tid(t)
            if n not in self.fams:
                rng = self._range(t)
                rng_i = rng.replace("(x as int)", "(s[i] as int)")
                self.fams[n] = (
                    f"proof fn t_range_{n}(x: {t})\n    ensures {rng or 'true'},\n{{}}\n"
                    f"spec fn t_view_{n}(s: Seq<{t}>) -> Seq<int> {{ s.map_values(|v: {t}| v as int) }}\n"
                    f"broadcast proof fn t_view_{n}_len(s: Seq<{t}>)\n"
                    f"    ensures #[trigger] t_view_{n}(s).len() == s.len(),\n{{}}\n"
                    f"broadcast proof fn t_view_{n}_index(s: Seq<{t}>, i: int)\n"
                    f"    requires 0 <= i < s.len(),\n"
                    f"    ensures #![trigger t_view_{n}(s)[i]] #![trigger s[i]] t_view_{n}(s)[i] == s[i] as int"
                    + (f", {rng_i}" if rng_i else "") + ",\n"
                    f"{{\n    t_range_{n}(s[i]);\n}}\n"
                    f"broadcast proof fn t_view_{n}_eq(s: Seq<{t}>, u: Seq<{t}>)\n"
                    f"    ensures #![trigger t_view_{n}(s), t_view_{n}(u)] (s == u) <==> (t_view_{n}(s) == t_view_{n}(u)),\n"
                    "{\n"
                    f"    if t_view_{n}(s) == t_view_{n}(u) {{\n"
                    f"        t_view_{n}_len(s);\n        t_view_{n}_len(u);\n"
                    f"        assert forall|i: int| 0 <= i < s.len() implies s[i] == u[i] by {{\n"
                    f"            t_view_{n}_index(s, i);\n            t_view_{n}_index(u, i);\n"
                    f"            assert(t_view_{n}(s)[i] == t_view_{n}(u)[i]);\n        }}\n"
                    f"        assert(s =~= u);\n    }}\n}}\n"
                    # views commute with slicing and concatenation (each by extensionality)
                    f"broadcast proof fn t_view_{n}_sub(s: Seq<{t}>, a: int, b: int)\n"
                    f"    requires 0 <= a <= b <= s.len(),\n"
                    f"    ensures #[trigger] t_view_{n}(s).subrange(a, b) == t_view_{n}(s.subrange(a, b)),\n"
                    f"{{\n    assert(t_view_{n}(s).subrange(a, b) =~= t_view_{n}(s.subrange(a, b)));\n}}\n"
                    f"broadcast proof fn t_view_{n}_add(s: Seq<{t}>, u: Seq<{t}>)\n"
                    f"    ensures #[trigger] t_view_{n}(s + u) == t_view_{n}(s) + t_view_{n}(u),\n"
                    f"{{\n    assert(t_view_{n}(s + u) =~= t_view_{n}(s) + t_view_{n}(u));\n}}\n"
                    f"broadcast proof fn t_view_{n}_push(s: Seq<{t}>, x: {t})\n"
                    f"    ensures #[trigger] t_view_{n}(s.push(x)) == t_view_{n}(s).push(x as int),\n"
                    f"{{\n    assert(t_view_{n}(s.push(x)) =~= t_view_{n}(s).push(x as int));\n}}\n")
                self.uses += [f"t_view_{n}_len", f"t_view_{n}_index", f"t_view_{n}_eq", f"t_view_{n}_sub",
                              f"t_view_{n}_add", f"t_view_{n}_push"]
            return f"t_view_{n}"
        if elem.kind == "seq" and elem.elem is not None and elem.elem.kind in ("int", "nat", "char"):
            inner = self.family(elem.elem)
            t = elem.text
            n = "v2_" + _tid(t)
            get = "r" if t.startswith("Seq") else "r@"
            if n not in self.fams:
                self.fams[n] = (
                    f"spec fn t_view_{n}(s: Seq<{t}>) -> Seq<Seq<int>> {{ s.map_values(|r: {t}| {inner}({get})) }}\n"
                    f"broadcast proof fn t_view_{n}_len(s: Seq<{t}>)\n"
                    f"    ensures #[trigger] t_view_{n}(s).len() == s.len(),\n{{}}\n"
                    f"broadcast proof fn t_view_{n}_index(s: Seq<{t}>, i: int)\n"
                    f"    requires 0 <= i < s.len(),\n"
                    f"    ensures #![trigger t_view_{n}(s)[i]] #![trigger s[i]] t_view_{n}(s)[i] == {inner}(s[i]{'' if get == 'r' else '@'}),\n"
                    "{}\n")
                self.uses += [f"t_view_{n}_len", f"t_view_{n}_index"]
            return f"t_view_{n}"
        raise NoHarness(f"sequence of {elem.text}")

    def view(self, expr_text: str, vt: lift_verus.VType) -> str:
        """The t value a source value of type `vt` denotes, as Verus spec text."""
        k = vt.kind
        if k in ("int", "nat", "char"):
            return f"({expr_text} as int)"
        if k == "bool":
            return expr_text
        if k == "pair":
            return "(" + ", ".join(self.view(f"{expr_text}.{i}", vt.parts[i]) for i in (0, 1)) + ")"
        if k == "seq":
            base = expr_text if vt.text.startswith("Seq") else f"{expr_text}@"
            if vt.elem.kind in ("int", "nat") and vt.elem.text == "int":
                return base
            return f"{self.family(vt.elem)}({base})"
        raise NoHarness(f"type {vt.text}")


def _view(expr_text: str, vt: lift_verus.VType, _t_type=None, views: "Views" = None) -> str:
    return (views or Views()).view(expr_text, vt)


def _t_type(ty) -> str:
    return lower_verus._vty(ty)


def _prefixed(task: dict) -> tuple[dict, dict[str, str]]:
    """The task with every spec_fun renamed `t_lift_<name>` (calls included), and the map."""
    mapping = {sf["name"]: LIFT_PREFIX + sf["name"] for sf in task.get("spec_funs", [])}
    t2 = copy.deepcopy(task)
    t2["spec_funs"] = [{**sf, "name": mapping[sf["name"]],
                        "body": names._rename_walk(sf["body"], mapping),
                        **({"decreases": names._rename_walk(sf["decreases"], mapping)}
                           if "decreases" in sf else {})}
                       for sf in task.get("spec_funs", [])]
    t2["requires"] = names._rename_walk(task.get("requires", []), mapping)
    t2["ensures"] = names._rename_walk(task.get("ensures", []), mapping)
    return t2, mapping


_QUANT = re.compile(r"\b(forall|exists)\|([^|]*)\|(?!\s*#!\[)")


def _expr(e) -> str:
    """t's printer for one expression, with `#![auto]` on any quantifier it left without
    a trigger: Verus refuses a quantifier whose trigger it cannot choose, and the harness
    only states the lifted contract, so the solver may pick any trigger it finds (Verus
    guide, "Triggers": #![auto] asks it to)."""
    saved = lower_verus._SUFFIX_INT
    lower_verus._SUFFIX_INT = True
    try:
        text = lower_verus.expr(e)
    finally:
        lower_verus._SUFFIX_INT = saved
    return _QUANT.sub(lambda m: f"{m.group(1)}|{m.group(2)}| #![auto]", text)


def _drop_inner_attrs(text: str) -> str:
    """A clause's leading `#![trigger ...]` (the lemma's own trigger choice for callers)
    is not part of the formula and cannot sit inside parentheses; drop it, brackets
    balanced."""
    t = text.lstrip()
    while t.startswith("#!["):
        depth, k = 0, 2
        while k < len(t):
            if t[k] == "[":
                depth += 1
            elif t[k] == "]":
                depth -= 1
                if depth == 0:
                    break
            k += 1
        t = t[k + 1:].lstrip()
    return t


def _conj(texts: list[str]) -> str:
    return "(" + " && ".join(f"({t})" for t in texts) + ")" if texts else "true"


# ------------------------------------------------------------ induction --

def _self_calls(e, name: str, path: list, out: list, env: Optional[dict] = None) -> bool:
    """Collect (path conditions, argument tuples, let environment) of every call to `name`
    in a spec fn body tuple. A `let` is carried as a substitution, so a call whose argument
    names a let-bound variable is stated on the variable's definition. False when a call
    sits where the harness cannot reach it (under a quantifier or a closure)."""
    env = env or {}
    if isinstance(e, list):
        return all(_self_calls(x, name, path, out, env) for x in e)
    if not isinstance(e, tuple) or not e:
        return True
    tag = e[0]
    if tag == "if" and len(e) >= 4:
        cond = e[1]
        ok = _self_calls(cond, name, path, out, env)
        then = lift_verus._block_to_expr(e[2]) if isinstance(e[2], list) else e[2]
        ok &= _self_calls(then, name, path + [("pos", cond, dict(env))], out, env)
        if e[3] is not None:
            other = lift_verus._block_to_expr(e[3]) if isinstance(e[3], list) else e[3]
            ok &= _self_calls(other, name, path + [("neg", cond, dict(env))], out, env)
        return ok
    if tag in ("quant", "closure"):
        found: list = []
        _self_calls(e[-1], name, [], found)
        return not found
    if tag == "letin":
        ok = _self_calls(e[2], name, path, out, env)
        return ok and _self_calls(e[3], name, path, out, {**env, e[1]: (e[2], dict(env))})
    if tag == "block":
        return _self_calls(lift_verus._block_to_expr(e[1]), name, path, out, env)
    if tag == "call" and e[1] == name:
        out.append((list(path), e[2], dict(env)))
    return all(_self_calls(x, name, path, out, env) for x in e[1:] if isinstance(x, (tuple, list)))


def _vtext(e, env: Optional[dict] = None) -> str:
    """A Verus text for a parsed Verus expression tuple (used only for recursive-call
    arguments and `if` conditions inside an induction lemma, where Verus re-checks it)."""
    def V(x):
        return _vtext(x, env)
    tag = e[0]
    if tag == "int":
        return str(e[1])
    if tag == "bool":
        return "true" if e[1] else "false"
    if tag in ("char", "str"):
        return e[1]
    if tag == "var":
        if env and e[1] in env:
            val, venv = env[e[1]]
            return "(" + _vtext(val, venv) + ")"
        return e[1]
    if tag == "paren":
        return "(" + V(e[1]) + ")"
    if tag == "view":
        return V(e[1]) + "@"
    if tag == "cast":
        return f"({V(e[1])} as {e[2].text})"
    if tag == "not":
        return "!" + V(e[1])
    if tag == "neg":
        return "-" + V(e[1])
    if tag in ("and", "or"):
        op = " && " if tag == "and" else " || "
        return "(" + op.join(f"({V(x)})" for x in e[1]) + ")"
    if tag == "chain":
        parts = [V(e[2][0])]
        for o, x in zip(e[1], e[2][1:]):
            parts += [o, V(x)]
        return "(" + " ".join(parts) + ")"
    if tag == "bin":
        return f"({V(e[2])} {e[1]} {V(e[3])})"
    if tag == "index":
        return f"{V(e[1])}[{V(e[2])}]"
    if tag == "method":
        return f"{V(e[1])}.{e[2]}(" + ", ".join(V(a) for a in e[3]) + ")"
    if tag == "call":
        return f"{e[1]}(" + ", ".join(V(a) for a in e[2]) + ")"
    if tag == "path":
        return e[1]
    if tag == "block":
        return "(" + V(lift_verus._block_to_expr(e[1])) + ")"
    raise NoHarness(f"expression {tag} in an induction step")


def _induction_lemma(sf: lift_verus.SpecFn, lifted_name: str, views: "Views") -> Optional[str]:
    """`broadcast proof fn t_eq_fn_<f>` stating f == its lifted image, or None."""
    if not sf.decreases or sf.body is None:
        return None
    for p in sf.params:
        if p.type.kind not in ("int", "nat", "bool") and not (
                p.type.kind == "seq" and p.type.elem.kind in ("int", "nat") and p.type.text.startswith("Seq")):
            return None
    if sf.ret.kind not in ("int", "nat", "bool"):
        return None
    calls: list = []
    if not _self_calls(sf.body, sf.name, [], calls) or not calls:
        return None
    try:
        steps = []
        for path, args, env in calls:
            conds = [(_vtext(c, cenv) if pol == "pos" else f"!({_vtext(c, cenv)})") for pol, c, cenv in path]
            call = f"t_eq_fn_{sf.name}(" + ", ".join(_vtext(a, env) for a in args) + ");"
            steps.append(f"        if {' && '.join(f'({c})' for c in conds)} {{ {call} }}" if conds
                         else f"        {call}")
        dec = ", ".join(_vtext(d) for d in sf.decreases)
    except NoHarness:
        return None
    ps = ", ".join(f"{p.name}: {p.type.text}" for p in sf.params)
    args_src = ", ".join(p.name for p in sf.params)
    args_lift = ", ".join(views.view(p.name, p.type) for p in sf.params)
    lhs = f"(#[trigger] {sf.name}({args_src}))"
    rhs = f"{lifted_name}({args_lift})"
    if sf.ret.kind in ("int", "nat"):
        lhs = f"({lhs} as int)"
    if re.search(r"verifier\s*::\s*opaque", sf.text):
        steps.insert(0, f"        reveal({sf.name});")
    return (f"broadcast proof fn t_eq_fn_{sf.name}({ps})\n"
            f"    ensures {lhs} == {rhs},\n"
            f"    decreases {dec}\n"
            "{\n" + "\n".join(steps) + "\n}\n")


_MAP = re.compile(r"([A-Za-z_]\w*(?: @)?) \. (map|map_values) \( \| ([^|]*) \| ([^()]*?) \)")


def _map_bridges(fn: lift_verus.ExecFn, views: "Views", with_result: bool) -> str:
    """For every `p@.map(|i: int, x: T| x as int)` a source clause writes, the assertion that
    it is extensionally the view the harness uses (a separately written closure is another
    term to the solver; `=~=` asks for the elementwise proof, Verus guide "Extensional
    equality"). Matched on the clause's own token text, so the term is the source's."""
    types = {p.name: p.type for p in fn.params}
    if fn.ret_name and with_result:
        types[fn.ret_name] = fn.ret
    out = []
    for clause in list(fn.requires_src) + list(fn.ensures_src):
        for m in _MAP.finditer(clause):
            recv = m.group(1)
            name = recv.replace(" @", "")
            vt = types.get(name)
            if vt is None or vt.kind != "seq" or vt.elem.kind not in ("int", "nat", "char"):
                continue
            base = recv.replace(" @", "@")
            view = views.view(name, vt)
            line = f"    assert({m.group(0)} =~= {view});\n"
            if line not in out:
                out.append(line)
    return "".join(out)


# ------------------------------------------------------------------ build --

def build(source_text: str, task: dict, rename_map: dict, target: Optional[str] = None,
          lemma: bool = False) -> tuple[str, list[str]]:
    """(harness text, lemma names) for one lifted task and the Verus file it came from.
    `rename_map` is the lifter sidecar's (dafny name -> {"t_name": ...})."""
    r = lift_verus.render(source_text, target=target, lemma=lemma)
    if r.file is None or r.target is None or r.refusal is not None:
        raise NoHarness("the source does not render")
    vf, fn = r.file, r.file.exec_fns[r.target]
    tparams = task["params"]
    if len(tparams) != len(fn.params):
        raise NoHarness(f"{len(fn.params)} source parameters, {len(tparams)} lifted")
    tret = task["returns"][0]
    t2, spec_map = _prefixed(task)
    t2, _ = names.sanitize(t2, names.KEYWORDS["verus"], uppercase_ok=True, check_task_name=False)
    tparams, tret = t2["params"], t2["returns"][0]

    # source items the contract reaches, verbatim
    rd = lift_verus.Renderer(vf, {p.name: p.type for p in fn.params})
    for e in list(fn.requires) + list(fn.ensures):
        try:
            rd.expr(e, True)
        except lift_verus.VerusRefusal:
            pass
    reach = lift_verus._reach(vf, rd.called_specs)
    items = [vf.const_text[c] for c in sorted(vf.const_text)]
    items += [vf.spec_fns[n].text for n in reach]

    # lifted spec funs, lowered by the repo's own Verus expression printer
    lifted = []
    for sf in t2.get("spec_funs", []):
        ps = ", ".join(f"{p['name']}: {_t_type(p['type'])}" for p in sf["params"])
        lifted.append(f"spec fn {sf['name']}({ps}) -> {_t_type(sf['result'])}\n"
                      f"    decreases {_expr(sf['decreases'])},\n"
                      "{\n" f"    {_expr(sf['body'])}\n" "}\n")
    tps = ", ".join(f"{p['name']}: {_t_type(p['type'])}" for p in tparams)
    rname = tret["name"]
    lifted.append(f"spec fn t_lift_pre({tps}) -> bool {{\n    {_conj([_expr(e) for e in t2.get('requires', [])])}\n}}\n")
    rdecl = f"{rname}: {_t_type(tret['type'])}"
    post_params = ", ".join(x for x in (tps, rdecl) if x)
    lifted.append(f"spec fn t_lift_post({post_params}) -> bool {{\n"
                  f"    {_conj([_expr(e) for e in t2['ensures']])}\n}}\n")

    views = Views()
    # induction lemmas for recursive source spec fns whose lifted image is known
    t_of = {k: v.get("t_name", k) for k, v in (rename_map or {}).items()}
    lemmas, used = [], []
    for n in reach:
        tname = t_of.get(lift_verus.dn(n), lift_verus.dn(n))
        if tname in spec_map:
            lem = _induction_lemma(vf.spec_fns[n], spec_map[tname], views)
            if lem:
                lemmas.append(lem)
                used.append(f"t_eq_fn_{n}")

    sps = ", ".join(f"{p.name}: {p.type_src}" for p in fn.params)
    pviews = ", ".join(views.view(p.name, p.type) for p in fn.params)
    src_ret = fn.ret_name or "result"
    rview = views.view(src_ret, fn.ret)
    used = views.uses + used
    use = f"    broadcast use {', '.join(used)};\n" if used else ""
    # a source spec fn marked opaque is revealed for the equivalence (Verus guide,
    # "Opaque definitions": reveal(f) makes the body visible in one proof)
    use += "".join(f"    reveal({n});\n" for n in reach if re.search(r"verifier\s*::\s*opaque", vf.spec_fns[n].text))
    use_pre = use + _map_bridges(fn, views, False)
    use_post = use + _map_bridges(fn, views, True)
    req_src = _conj([_drop_inner_attrs(x) for x in fn.requires_src])
    eq = [f"proof fn t_eq_requires({sps})\n"
          f"    ensures {req_src} <==> t_lift_pre({pviews}),\n"
          "{\n" + use_pre + "}\n",
          f"proof fn t_eq_ensures({', '.join(x for x in (sps, f'{src_ret}: {fn.ret_src}') if x)})\n"
          f"    requires {req_src},\n"
          f"    ensures {_conj([_drop_inner_attrs(x) for x in fn.ensures_src])} <==> t_lift_post({', '.join(x for x in (pviews, rview) if x)}),\n"
          "{\n" + use_post + "}\n"]
    text = ("use vstd::prelude::*;\n\nverus! {\n\n"
            "// ---- the source's own declarations, as written\n"
            + "\n".join(items) + "\n\n"
            "// ---- the lifted contract, lowered by t/lower_verus.py\n"
            + (lower_verus.STRLIB_PRELUDE + "\n" if lower_verus._uses_strlib(t2) else "")
            + "\n".join(lifted) + "\n"
            "// ---- views: a source value as the t value it denotes\n"
            + "\n".join(views.fams.values()) + "\n"
            "// ---- induction: each recursive source spec fn equals its lifted image\n"
            + "\n".join(lemmas) + "\n"
            "// ---- the equivalence\n" + "\n".join(eq) + "\n} // verus!\n\nfn main() {}\n")
    return text, ["t_eq_requires", "t_eq_ensures"] + [u for u in used if u.startswith("t_eq_fn_")]


def run(text: str, workdir: Path, stem: str, timeout_s: float = 120.0) -> dict:
    """Run verus on the harness; {"verdict", "seconds", "message"}."""
    workdir.mkdir(parents=True, exist_ok=True)
    path = workdir / (re.sub(r"[^A-Za-z0-9_]", "_", stem) + "_eq.rs")
    path.write_text(text, encoding="utf-8")
    started = time.monotonic()
    try:
        p = subprocess.run(memory_capped([str(VERUS_BIN), "--output-json", "--no-cheating", "--rlimit", str(RLIMIT),
                            str(path)]), capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return {"verdict": "error", "seconds": round(time.monotonic() - started, 1), "message": "timeout"}
    except OSError as e:
        return {"verdict": "error", "seconds": 0.0, "message": f"verus did not start: {e}"}
    secs = round(time.monotonic() - started, 1)
    out = p.stdout + "\n" + p.stderr
    errors = None
    m = re.search(r'"errors"\s*:\s*(\d+)', p.stdout)
    if m:
        errors = int(m.group(1))
    mv = re.search(r'"verified"\s*:\s*(\d+)', p.stdout)
    verified = int(mv.group(1)) if mv else 0
    # positive evidence only (t/verifiers/verus.py's rule): both lemmas discharged, no error
    ok = (p.returncode == 0 and errors == 0 and verified >= 2
          and not re.search(r"^error", p.stderr, re.M))
    if ok:
        return {"verdict": "proved", "seconds": secs, "message": ""}
    first = next((ln for ln in p.stderr.splitlines() if ln.startswith("error")), "")
    where = re.search(r"-->\s*\S+:(\d+):", p.stderr)
    line = int(where.group(1)) if where else None
    lemma = None
    if line is not None:
        lines = text.splitlines()
        for k in range(min(line, len(lines)) - 1, -1, -1):
            mm = re.match(r"\s*(?:pub\s+)?(?:broadcast\s+)?(?:proof|spec)\s+fn\s+(\w+)", lines[k])
            if mm:
                lemma = mm.group(1)
                break
    verdict = "not-proved" if first else "error"
    return {"verdict": verdict, "seconds": secs, "message": first[:300], "at": lemma}


def check(source_path: Path, task: dict, rename_map: dict, workdir: Path, stem: str,
          timeout_s: float = 120.0, target: Optional[str] = None, lemma: bool = False) -> dict:
    try:
        text, lemmas = build(source_path.read_text(encoding="utf-8"), task, rename_map, target, lemma)
    except NoHarness as e:
        return {"verdict": "no-harness", "message": str(e)}
    except (lift_verus.VerusRefusal, KeyError, ValueError, NotImplementedError) as e:
        return {"verdict": "no-harness", "message": f"{type(e).__name__}: {e}"}
    res = run(text, workdir, stem, timeout_s)
    res["lemmas"] = lemmas
    return res


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("source")
    ap.add_argument("task")
    ap.add_argument("--sidecar")
    ap.add_argument("--work", default=tempfile.gettempdir())
    ap.add_argument("--print", action="store_true")
    a = ap.parse_args()
    task = json.loads(Path(a.task).read_text())
    rmap = json.loads(Path(a.sidecar).read_text()).get("rename_map", {}) if a.sidecar else {}
    if a.print:
        print(build(Path(a.source).read_text(), task, rmap)[0])
    else:
        print(json.dumps(check(Path(a.source), task, rmap, Path(a.work), Path(a.task).stem), indent=2))
