"""t.string_census: which members of the Python string library the nl/
problems actually use, and in which argument forms.

COVERAGE-nl.md tags one gap, `string-lib`, for any of nl_census.py's
STRING_METHODS, an f-string or `.format()`, `str()`, or `int(x, base)`; it
never says which members. This instrument re-runs the census's own corpus
readers (nl_census.process_*), watches every solution the census tags, and
records per problem the set of members used and the argument form of each
call (split with no argument is Python's whitespace split, split(sep) keeps
empties; strip() against strip(chars); join's receiver a literal or a
variable), then reports: members by problems using them, the same among
the problems string-lib alone keeps out of t's fragment (the census's sole
blockers), the argument forms, and the greedy order in which adding
members unlocks those sole-blocked problems (each step the member that
lets the most problems' whole member set be covered).

    python3 string_census.py --out COVERAGE-string-lib.md

Written 2026-09-11 for the string-library design (ROADMAP 12.7, the wave
after nested sequences); reads the same files nl_census.py reads.

Updated 2026-09-11, later the same day: nl_census.py split the tag into the
burden `string-lib-v1` and the narrowed gap `string-lib`; this instrument
now counts a problem as using the library when it carries either, so the
member tables keep covering all library use, while the sole set follows the
narrowed gap. The pre-split reading is kept in the table's own dated line.
"""
from __future__ import annotations
import argparse, ast, collections, sys, time
from pathlib import Path
import nl_census

MEMBERS: list[dict] = []          # one entry per solution_tags call, in order

def _form(node: ast.Call, m: str) -> str:
    n = len(node.args) + len(node.keywords)
    if m == "split":
        if n == 0: return "split()"
        a = node.args[0] if node.args else None
        if isinstance(a, ast.Constant) and isinstance(a.value, str):
            return "split(lit)" if len(a.value) == 1 else "split(lit-multi)"
        return "split(expr)" if n == 1 else "split(sep,max)"
    if m == "join":
        r = node.func.value if isinstance(node.func, ast.Attribute) else None
        if isinstance(r, ast.Constant) and isinstance(r.value, str):
            return "lit.join" if r.value in ("", " ", ",", "\n") else "lit.join(other)"
        return "expr.join"
    if m in ("strip", "lstrip", "rstrip"):
        return f"{m}()" if n == 0 else f"{m}(chars)"
    if m in ("replace", "count", "find", "startswith", "endswith", "index"):
        a = node.args[0] if node.args else None
        lit = isinstance(a, ast.Constant) and isinstance(a.value, str)
        return f"{m}({'lit' if lit else 'expr'}{',n' if n > 1 else ''})"
    return f"{m}({n})"

def _scan(src: str) -> dict:
    out = {"members": set(), "forms": collections.Counter()}
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return out
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            out["members"].add("f-string"); out["forms"]["f-string"] += 1
        elif isinstance(node, ast.Call):
            name = nl_census._call_name(node)
            if name == "str":
                out["members"].add("str()"); out["forms"]["str()"] += 1
            elif name == "int" and len(node.args) >= 2:
                out["members"].add("int(x,base)"); out["forms"]["int(x,base)"] += 1
            elif isinstance(node.func, ast.Attribute) and node.func.attr in nl_census.STRING_METHODS:
                m = node.func.attr
                out["members"].add(m); out["forms"][_form(node, m)] += 1
        elif isinstance(node, ast.Attribute) and node.attr in nl_census.STRING_METHODS:
            pass  # a bare attribute (a method passed as a value) is counted at its call, if any
    return out

# The pairing: process_* calls solution_tags for a problem that has a
# solution, then make_record for every problem; the scan waits in PENDING
# and make_record's wrapper attaches it (or an empty scan) to that record.
PENDING: list[dict] = []
_orig = nl_census.solution_tags
def _tap(src, fn_name, function_shaped):
    PENDING.append(_scan(src))
    return _orig(src, fn_name, function_shaped)
nl_census.solution_tags = _tap
_orig_rec = nl_census.make_record
def _rec(*args, **kw):
    rec = _orig_rec(*args, **kw)
    rec["_scan"] = PENDING.pop() if PENDING else {"members": set(), "forms": collections.Counter()}
    return rec
nl_census.make_record = _rec

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    t0 = time.time()
    programs = []
    for proc in (nl_census.process_mbpp, nl_census.process_humaneval,
                 nl_census.process_apps, nl_census.process_codecontests):
        programs.extend(proc(a.limit))
    assert not PENDING, "a scan without a record"
    rows = [(p, p["_scan"]) for p in programs]
    lib = [(p, m) for p, m in rows
           if "string-lib" in p.get("gaps", []) or "string-lib-v1" in p.get("burdens", [])]
    sole_all = [(p, m) for p, m in lib if set(p.get("gaps", [])) == {"string-lib"}]
    sole_fn = [(p, m) for p, m in sole_all if p.get("shape") == "function"]
    sole = sole_all
    by_member = collections.Counter(); by_member_sole = collections.Counter()
    by_member_fn = collections.Counter(); forms = collections.Counter(); forms_sole = collections.Counter()
    for p, m in lib:
        for x in m["members"]:
            by_member[x] += 1
            if p.get("shape") == "function": by_member_fn[x] += 1
        forms.update(m["forms"])
    for p, m in sole:
        for x in m["members"]: by_member_sole[x] += 1
        forms_sole.update(m["forms"])
    # greedy unlock over the sole set, with the function-shaped count alongside
    chosen: list[str] = []; covered = 0; order = []
    remaining = [(p, m) for p, m in sole if m["members"]]
    nomember = len(sole) - len(remaining)
    while True:
        best, gain = None, 0
        for cand in by_member_sole:
            if cand in chosen: continue
            c = set(chosen) | {cand}
            k = sum(1 for p, m in remaining if m["members"] <= c)
            if k - covered > gain: best, gain = cand, k - covered
        if best is None: break
        chosen.append(best); covered += gain
        c = set(chosen)
        fn_cov = sum(1 for p, m in remaining if m["members"] <= c and p.get("shape") == "function")
        order.append((best, gain, covered, fn_cov))
    elapsed = time.time() - t0
    w = []
    w.append(f"# The string library, member by member (nl/ census, {time.strftime('%Y-%m-%d')})\n")
    w.append(f"{len(programs)} problems read the way COVERAGE-nl.md reads them; {len(lib)} use the library "
             f"(tagged `string-lib`, the gap, or `string-lib-v1`, the burden, since the 2026-09-11 split); "
             f"{len(sole)} with the gap `string-lib` as their only gap ({len(sole_fn)} function-shaped, "
             f"the census's sole blockers, and {len(sole) - len(sole_fn)} stdin-shaped, which also wait on a signature); "
             f"{nomember} of those use no member this scan sees (an f-string-free `str()`-free tag "
             f"the census gives for `sorted` on a string, or a method reached through a value). "
             f"Run time {elapsed:.1f}s.\n")
    w.append("## Members, by problems using them\n")
    w.append("First read on 2026-09-11 before nl_census.py split the tag (13,266 tagged, 3,103 sole: 298 "
             "function-shaped, 2,805 stdin; the greedy order that fixed v1's members was taken over that sole set, "
             "ROADMAP 12.7). Since the split this table counts the gap and the burden together as library use, "
             "and the sole set is the narrowed gap's: the members v1 covers no longer keep anything out.\n")
    w.append("| member | problems (all string-lib) | of which function-shaped | among the sole blockers |")
    w.append("|---|---:|---:|---:|")
    for x, c in by_member.most_common():
        w.append(f"| {x} | {c} | {by_member_fn[x]} | {by_member_sole[x]} |")
    w.append("\n## The greedy order over the sole blockers\n")
    w.append("Each step adds the member that covers the most sole-blocked problems whose whole member set is then covered.\n")
    w.append("| step | member | newly unlocked | cumulative | of which function-shaped |")
    w.append("|---|---|---:|---:|---:|")
    for i, (x, g, cum, fc) in enumerate(order, 1):
        w.append(f"| {i} | {x} | {g} | {cum} | {fc} |")
    w.append("\n## Argument forms (call sites, all string-lib problems / among sole blockers)\n")
    w.append("| form | calls | calls among sole blockers |")
    w.append("|---|---:|---:|")
    for f, c in forms.most_common():
        w.append(f"| {f} | {c} | {forms_sole[f]} |")
    w.append("\n## Method\n")
    w.append("Reuses nl_census.py's readers by tapping its `solution_tags`; a member is a call `x.m(..)` with m in "
             "STRING_METHODS, an f-string, `str(..)`, or `int(x, base)`; `sorted` on a string is not seen here. "
             "Forms: `split()` is Python's whitespace split (runs collapsed, no empties), `split(lit)` a one-code-point "
             "separator, `split(lit-multi)` a longer literal, `split(expr)` a non-literal; `lit.join` a literal separator "
             "among the four common ones; `strip()` whitespace against `strip(chars)`.\n")
    text = "\n".join(w) + "\n"
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8", newline="\n"); print(f"wrote {a.out}")
    else:
        print(text)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
