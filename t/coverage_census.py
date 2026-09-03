#!/usr/bin/env python3
"""coverage_census.py: which constructs a verification corpus needs that t
does not have, program by program, and which gate opens the most programs.

    python3 t/coverage_census.py <dir of .dfy files> [--out t/COVERAGE-<name>.md]
                                 [--json <per-file tags>]

The corpus is read as Dafny source (DafnyBench ground_truth, 785 programs,
Apache-2.0, is the first one; ROADMAP 10.4). Each program is tagged with the
GAPS it needs, constructs outside t's fragment (SYNTAX.md), with the BURDENS
it carries, things t can express another way at some translation cost, and
with the HINTS it uses, proof scaffolding a kernel might or might not need
(t has no assert statement and no lemma). A program is IN FRAGMENT when its
gap set is empty and it carries at least one method with an ensures; a gap
set, not a verdict, because nothing here runs a kernel. The greedy curve at
the end answers the question this file exists for: opening which gate next
unlocks the most programs, given the gates already open.

Detection is lexical, on source with comments and string/char literals
masked (their presence is recorded first). Lexical means approximate, so the
report names every detector and the census is checked by sampling (see the
Method section of the report) rather than trusted. Where a detector cannot
tell two things apart (a `+` on sequences from a `+` on integers) it says so
and tags the cheaper reading, so the census can UNDER-count a gap but the
detectors that fire are real.

Stdlib only, like every instrument in t/.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# -------------------------------------------------------------- masking
_STR = re.compile(r'@"(?:[^"]|"")*"|"(?:[^"\\\n]|\\.)*"')
_CHR = re.compile(r"'(?:[^'\\\n]|\\.)'")


def mask(src: str) -> tuple[str, dict]:
    """Comments and literals blanked (newlines kept); returns the masked text
    and what was seen: string literals, char literals."""
    seen = {"string_lit": False, "char_lit": False}
    out = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        nxt = src[i + 1] if i + 1 < n else ""
        if c == "/" and nxt == "/":
            j = src.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i))
            i = j
        elif c == "/" and nxt == "*":
            depth, j = 1, i + 2
            while j < n and depth:
                if src.startswith("/*", j):
                    depth, j = depth + 1, j + 2
                elif src.startswith("*/", j):
                    depth, j = depth - 1, j + 2
                else:
                    j += 1
            out.append("".join(ch if ch == "\n" else " " for ch in src[i:j]))
            i = j
        elif c == '"' or (c == "@" and nxt == '"'):
            m = _STR.match(src, i)
            if m:
                seen["string_lit"] = True
                out.append(" " * (m.end() - i))
                i = m.end()
            else:
                out.append(c)
                i += 1
        elif c == "'":
            m = _CHR.match(src, i)
            if m:
                seen["char_lit"] = True
                out.append(" " * (m.end() - i))
                i = m.end()
            else:
                out.append(c)
                i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out), seen


# -------------------------------------------------------------- detectors
# Each entry: name -> (kind, regex or callable, one-line meaning).
# kind: "gap" (outside t), "burden" (expressible at a cost), "hint" (proof
# scaffolding), "shape" (structural facts used by the in-fragment rule).
IDENT = r"[A-Za-z_][A-Za-z0-9_']*"

def _has(rx: str, flags=re.M):
    r = re.compile(rx, flags)
    return lambda s: r.search(s) is not None


def _seq_literal(s: str) -> bool:
    # `[` not preceded by an identifier char, `]` or `)` (those are indexing
    # or slicing), and not the empty `[]` of a type; `[1, 2]`, `[x]`, `[]`.
    s = re.sub(r"\s+\[", "[", s)
    for m in re.finditer(r"(?<![A-Za-z0-9_\]\)>])\[", s):
        j = s.find("]", m.end())
        if j < 0:
            continue
        inner = s[m.end():j]
        if ".." in inner:
            continue
        if inner.strip() == "" or re.search(r"[A-Za-z0-9_]", inner):
            # exclude attribute-ish and declaration contexts
            pre = s[max(0, m.start() - 12):m.start()]
            if re.search(r"(?:array\d*|:)\s*$", pre):
                continue
            return True
    return False


def _unbounded_quantifier(s: str) -> bool:
    # A quantifier whose bound variables are not all int-typed-with-a-range:
    # a non-int declared type, or no `<`, `<=`, `in` bound on the variable
    # before the `==>` / `&&` that starts the body.
    for m in re.finditer(r"\b(forall|exists)\b([^:]*?)::", s):
        decl = m.group(2)
        if re.search(r":\s*(?!int\b|nat\b)" + IDENT, decl) and not re.search(r"\bin\b", s[m.start():m.end() + 120]):
            return True
        pipe = decl.split("|", 1)
        names = [n for n in re.findall(IDENT, re.sub(r":\s*" + IDENT, "", pipe[0]))
                 if n not in ("int", "nat")]
        body = s[m.end():m.end() + 200]
        head = (pipe[1] if len(pipe) > 1 else "") + " " + re.split(r"==>|&&", body, 1)[0]
        if not any(re.search(r"\b" + re.escape(n) + r"\b", head) for n in names):
            return True
        if not re.search(r"<=|<|\bin\b|>=|>", head):
            return True
    return False


def strip_main(s: str) -> str:
    """Blank the body of `method Main` (a test harness, not the program) so
    its prints, arrays and calls do not tag the program."""
    m = re.search(r"\bmethod\s+Main\b", s)
    if not m:
        return s
    i = s.find("{", m.end())
    if i < 0:
        return s
    depth, j = 0, i
    while j < len(s):
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                break
        j += 1
    return s[:m.start()] + "".join(c if c == "\n" else " " for c in s[m.start():j + 1]) + s[j + 1:]


def _returns(s: str) -> tuple[bool, bool]:
    """(early, trailing): a return/break/continue inside a nested block or
    not at the end of the method body counts as early; a `return ...;`
    that is the last statement of a method body is trailing (style)."""
    early = trailing = False
    if re.search(r"\bbreak\b|\bcontinue\b|\blabel\b", s):
        early = True
    for m in re.finditer(r"\breturn\b", s):
        start = max((x.start() for x in re.finditer(r"\bmethod\b", s[:m.start()])), default=0)
        body = s.find("{", start)
        depth = s[body:m.start()].count("{") - s[body:m.start()].count("}") if body >= 0 else 2
        semi = s.find(";", m.end())
        after = s[semi + 1:semi + 200].lstrip() if semi >= 0 else ""
        if depth == 1 and after.startswith("}"):
            trailing = True
        else:
            early = True
    return early, trailing


def _lambda(s: str) -> bool:
    for m in re.finditer(r"(?<![=<>!])=>", s):
        line = s[s.rfind("\n", 0, m.start()) + 1:m.start()]
        if not re.search(r"\bcase\b", line):
            return True
    return re.search(r"\s->\s", s) is not None


def _method_count(s: str) -> int:
    return len(re.findall(r"\bmethod\b(?!\s+Main\b)", s))


DETECTORS: dict[str, tuple[str, object, str]] = {
    # gaps: outside t's fragment
    "array": ("gap", _has(r"\barray\d*\b|\bnew\s+" + IDENT + r"\s*\["), "array type or allocation"),
    "array-mutation": ("gap", _has(IDENT + r"\s*\[[^\]]+\]\s*:=(?!=)"), "element assignment a[i] := e"),
    "div-mod": ("gap", _has(r"(?<![/*])/(?![/*=])|%"), "integer division or modulo"),
    "string-char": ("gap", _has(r"\bstring\b|\bchar\b|\bseq<char>"), "string or char type"),
    "set": ("gap", _has(r"\bi?set<|\bmultiset\b|\bset\s+" + IDENT + r"\s*(?::|\|)|\{\s*(?:-?\d+|" + IDENT + r")(?:\s*,\s*(?:-?\d+|" + IDENT + r"))*\s*\}"), "set, iset, multiset, set comprehension or set literal"),
    "map": ("gap", _has(r"\bi?map<|\bmap\s+" + IDENT + r"\s*(?::|\|)|\bmap\s*\["), "map, imap, map comprehension or map literal"),
    "heap": ("gap", _has(r"\bclass\b|\btrait\b|\bfresh\b|\bthis\b|\bnew\s+" + IDENT + r"\s*[(;]"), "classes, object allocation, this"),
    "datatype": ("gap", _has(r"\b(?:co)?datatype\b|\bmatch\b|\bcase\b"), "algebraic datatypes and match"),
    "multi-method": ("gap", lambda s: _method_count(s) > 1, "more than one method (Main excluded)"),
    "multi-return": ("gap", _has(r"\breturns\s*\([^)]*,"), "several return values"),
    "early-exit": ("gap", lambda s: _returns(s)[0], "return inside a block, break, continue"),
    "seq-return": ("gap", _has(r"\breturns\s*\([^)]*:\s*seq\b"), "sequence-valued return"),
    "seq-literal": ("gap", _seq_literal, "sequence literal [..] in an expression"),
    "seq-slice": ("gap", _has(r"\[[^\]]*\.\.[^\]]*\]"), "slicing s[a..b]"),
    "seq-update": ("gap", _has(r"\[[^\]]+:=[^\]]+\]"), "functional update s[i := v]"),
    "seq-comprehension": ("gap", _has(r"\bseq\s*\("), "seq(n, i => e)"),
    "nested-seq": ("gap", _has(r"\bseq<\s*seq<|\bseq<\s*(?!int\b|nat\b)" + IDENT), "seq of non-int elements"),
    "unbounded-quantifier": ("gap", _unbounded_quantifier, "quantifier without an int range"),
    "real": ("gap", _has(r"\breal\b|\d\.\d"), "real numbers"),
    "bitvector": ("gap", _has(r"\bbv\d+\b|\bas\s+bv\d|(?<!&)&(?!&)|\^|<<"), "bit vectors or bitwise operators"),
    "higher-order": ("gap", _lambda, "lambdas or function types"),
    "generics": ("gap", _has(r"\b(?:method|function|predicate|lemma|datatype|class)\s+" + IDENT + r"\s*<"), "type parameters"),
    "tuple": ("gap", _has(r"(?<=[A-Za-z_)\]])\.\d\b|\bvar\s*\(|\(\s*" + IDENT + r"\s*,[^()]*\)\s*:=|:\s*\(\s*" + IDENT + r"\s*,"), "tuples"),
    "type-decl": ("gap", _has(r"^\s*(?:newtype|type)\s+" + IDENT), "newtype, type synonyms, subset types"),
    "io": ("gap", _has(r"\bprint\b|\bexpect\b"), "print or expect"),
    "iterator": ("gap", _has(r"\biterator\b"), "iterators"),
    "module": ("gap", _has(r"\bmodule\b|\bimport\b|\binclude\b"), "modules and imports"),
    "function-method": ("gap", _has(r"\bfunction\s+method\b|\bby\s+method\b|\bpredicate\s+method\b"), "compiled functions"),
    "decreases-star": ("gap", _has(r"\bdecreases\s+\*"), "decreases * (a loop or call allowed not to terminate)"),
    "char-arith": ("gap", _has(r"\bas\s+char\b|\bchar\s*\("), "char arithmetic"),
    # burdens: t can say it another way
    "nat": ("burden", _has(r"\bnat\b"), "nat, as int with a >= 0 clause"),
    "for-loop": ("burden", _has(r"\bfor\s+" + IDENT + r"\s*:="), "for loop (a while with a bound)"),
    "iff": ("burden", _has(r"<==>"), "<==> (== on bools)"),
    "seq-membership": ("burden", _has(r"\b!?in\b"), "in / !in (a bounded exists over a seq; set and map membership are their own gaps)"),
    "as-cast": ("burden", _has(r"\bas\s+(?:int|nat)\b"), "as int / as nat casts"),
    "parallel-assign": ("burden", _has(IDENT + r"\s*,\s*" + IDENT + r"\s*:=(?!=)"), "x, y := a, b (sequenced through a temporary)"),
    "untyped-var": ("burden", _has(r"\bvar\s+" + IDENT + r"\s*:="), "var without a type (t declares every type)"),
    "no-if-no-loop": ("burden", lambda s: not re.search(r"\bif\b|\bwhile\b", s), "straight-line body: the twin ladder has only its extensional operators to try"),
    "frame-clause": ("burden", _has(r"\bmodifies\b|\breads\b"), "modifies / reads (array frames when no class is present)"),
    "trailing-return": ("burden", lambda s: _returns(s)[1], "a return as the last statement (assign the result instead)"),
    "main-harness": ("burden", _has(r"\bmethod\s+Main\b"), "a Main test harness (stripped before tagging)"),
    "while-no-decreases": ("burden", lambda s: any(
        "decreases" not in s[m.end():m.end() + 400].split("{", 1)[0]
        for m in re.finditer(r"\bwhile\b", s)), "a loop without its decreases (t requires one)"),
    "if-no-else": ("burden", lambda s: bool(re.search(r"\bif\b[^{]*\{", s)) and not re.search(r"\belse\b", s), "if without else"),
    "function-or-predicate": ("burden", _has(r"\bfunction\b|\bpredicate\b"), "pure functions, as spec_funs when first-order over int and seq"),
    "spec-only-quantifier": ("burden", _has(r"\bforall\b|\bexists\b"), "quantifiers (bounded ones are in t)"),
    # hints: proof scaffolding
    "assert": ("hint", _has(r"\bassert\b"), "assert statements"),
    "lemma": ("hint", _has(r"\blemma\b"), "lemmas"),
    "ghost": ("hint", _has(r"\bghost\b"), "ghost code"),
    "calc": ("hint", _has(r"\bcalc\b"), "calc proofs"),
    "forall-statement": ("hint", _has(r"^\s*forall\b[^:]*(?:ensures|\{)"), "forall statements"),
    "assume": ("hint", _has(r"\bassume\b"), "assume (unsound as a hint; refused by every t adapter)"),
    "reveal-opaque": ("hint", _has(r"\breveal\b|\bopaque\b"), "reveal / opaque"),
    "assign-such-that": ("hint", _has(r":\|"), "assign-such-that"),
    "attribute": ("hint", _has(r"\{:"), "attributes"),
    "ghost-var": ("hint", _has(r"\bghost\s+var\b"), "ghost variables"),
    "assert-by": ("hint", _has(r"\bassert\b[^;]*\bby\b"), "assert ... by { }"),
    "old": ("hint", _has(r"\bold\s*\("), "old() (two-state; heap or array frames)"),
    # shape
    "has-method": ("shape", _has(r"\bmethod\b"), "at least one method"),
    "has-ensures": ("shape", _has(r"\bensures\b"), "at least one ensures"),
}

GAPS = [k for k, (kind, _, _) in DETECTORS.items() if kind == "gap"]


def tag(src: str) -> dict:
    masked, seen = mask(src)
    has_main = re.search(r"\bmethod\s+Main\b", masked) is not None
    if has_main:
        # mask() preserves offsets, so the Main span found on the masked
        # text blanks the same bytes of the source; literals inside Main
        # (print strings) must not tag the program either.
        stripped = strip_main(masked)
        src_wo_main = "".join(c if m != " " or c in " \n" else " "
                              for c, m in zip(src, stripped)) if len(stripped) == len(src) else src
        _, seen = mask(src_wo_main)
        masked = stripped
    tags = {k: bool(fn(masked)) for k, (_, fn, _) in DETECTORS.items()}
    tags["main-harness"] = has_main
    if seen["string_lit"] or seen["char_lit"]:
        tags["string-char"] = True
    tags["gaps"] = sorted(k for k in GAPS if tags[k])
    tags["in_fragment"] = (not tags["gaps"]) and tags["has-method"] and tags["has-ensures"]
    return tags


# -------------------------------------------------------------- families
def family(name: str) -> str:
    """The sub-corpus a DafnyBench file came from, read off its name."""
    head = name.split("_")[0]
    head = re.sub(r"\d+$", "", head) or head
    low = head.lower()
    if low.startswith("dafny-synthesis"):
        return "MBPP-DFY (dafny-synthesis)"
    if low.startswith("clover"):
        return "Clover"
    return "GitHub (" + head + ")"


def greedy(programs: list[dict]) -> list[tuple[str, int, int]]:
    """Open gates one at a time, each time the one that unlocks the most
    still-blocked programs; returns (gate, newly unlocked, cumulative)."""
    open_gates: set[str] = set()
    covered = sum(1 for p in programs if p["in_fragment"])
    steps = []
    remaining = [p for p in programs if not p["in_fragment"]
                 and p["has-method"] and p["has-ensures"]]
    while remaining:
        best, best_n = None, 0
        for g in GAPS:
            if g in open_gates:
                continue
            n = sum(1 for p in remaining if set(p["gaps"]) <= open_gates | {g})
            if n > best_n:
                best, best_n = g, n
        if best is None or best_n == 0:
            # no single gate unlocks anything: open the most frequent gap
            cnt = Counter(g for p in remaining for g in p["gaps"] if g not in open_gates)
            if not cnt:
                break
            best, best_n = cnt.most_common(1)[0][0], 0
        open_gates.add(best)
        unlocked = [p for p in remaining if set(p["gaps"]) <= open_gates]
        remaining = [p for p in remaining if p not in unlocked]
        covered += len(unlocked)
        steps.append((best, len(unlocked), covered))
    return steps


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus")
    ap.add_argument("--name", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    corpus = Path(a.corpus)
    files = sorted(corpus.glob("*.dfy"))
    if not files:
        print(f"no .dfy files under {corpus}", file=sys.stderr)
        return 2
    name = a.name or corpus.resolve().parent.parent.parent.name or corpus.name
    programs = []
    for f in files:
        t = tag(f.read_text(encoding="utf-8", errors="replace"))
        t["file"] = f.name
        t["family"] = family(f.name)
        programs.append(t)
    n = len(programs)
    graded = [p for p in programs if p["has-method"] and p["has-ensures"]]
    in_frag = [p for p in programs if p["in_fragment"]]
    gap_count = Counter(g for p in programs for g in p["gaps"])
    burden_count = Counter(k for p in programs for k, (kind, _, _) in DETECTORS.items() if kind == "burden" and p[k])
    hint_count = Counter(k for p in programs for k, (kind, _, _) in DETECTORS.items() if kind == "hint" and p[k])
    steps = greedy(programs)
    fam = defaultdict(lambda: [0, 0, 0])
    for p in programs:
        fam[p["family"]][0] += 1
        fam[p["family"]][1] += p["in_fragment"]
        fam[p["family"]][2] += p["has-method"] and p["has-ensures"]
    one_gap = Counter(p["gaps"][0] for p in programs if len(p["gaps"]) == 1)

    lines = []
    w = lines.append
    w(f"# t coverage census: {name} ({n} programs)")
    w("")
    w("What this corpus needs that t does not have, program by program, and")
    w("which gate opens the most programs. Lexical census, no kernel run; the")
    w("in-fragment count says a program's constructs fit SYNTAX.md, not that")
    w("seven kernels verify its t rendering. Method and detectors at the end.")
    w("")
    w("## Headline")
    w("")
    w(f"- programs: {n}; with a method and an ensures (gradable): {len(graded)}")
    w(f"- in t's fragment today: **{len(in_frag)}** of {len(graded)} gradable "
      f"({100 * len(in_frag) / max(1, len(graded)):.1f}%)")
    w(f"- programs blocked by exactly one gap: {sum(one_gap.values())}")
    w("")
    w("## Gaps, by programs that need them")
    w("")
    w("| gap | programs | sole blocker for | meaning |")
    w("|---|---|---|---|")
    for g, c in gap_count.most_common():
        w(f"| {g} | {c} | {one_gap.get(g, 0)} | {DETECTORS[g][2]} |")
    w("")
    w("## Greedy gate order (open the gate that unlocks the most programs)")
    w("")
    w("| step | gate | newly unlocked | cumulative in fragment | of gradable |")
    w("|---|---|---|---|---|")
    for i, (g, k, cum) in enumerate(steps, 1):
        w(f"| {i} | {g} | {k} | {cum} | {100 * cum / max(1, len(graded)):.1f}% |")
    w("")
    mb = [p for p in programs if p["family"].startswith("MBPP")]
    if mb:
        mb_graded = [p for p in mb if p["has-method"] and p["has-ensures"]]
        w("")
        w(f"### The same order on the MBPP-DFY family alone ({len(mb_graded)} gradable, the LLM-shaped subset)")
        w("")
        w("| step | gate | newly unlocked | cumulative | of gradable |")
        w("|---|---|---|---|---|")
        for i, (g, k, cum) in enumerate(greedy(mb), 1):
            w(f"| {i} | {g} | {k} | {cum} | {100 * cum / max(1, len(mb_graded)):.1f}% |")
        w("")
    w("A step with 0 newly unlocked is a gate that unlocks nothing alone but")
    w("is the most frequent remaining gap; the programs it belongs to need")
    w("more than one gate.")
    w("")
    w("## By family")
    w("")
    w("| family | programs | gradable | in fragment |")
    w("|---|---|---|---|")
    for k, (tot, inf, gr) in sorted(fam.items(), key=lambda x: -x[1][0]):
        w(f"| {k} | {tot} | {gr} | {inf} |")
    w("")
    w("## Burdens (expressible at a translation cost)")
    w("")
    w("| burden | programs | meaning |")
    w("|---|---|---|")
    for g, c in burden_count.most_common():
        w(f"| {g} | {c} | {DETECTORS[g][2]} |")
    w("")
    w("## Hints (proof scaffolding a kernel may need; t has none)")
    w("")
    w("| hint | programs | meaning |")
    w("|---|---|---|")
    for g, c in hint_count.most_common():
        w(f"| {g} | {c} | {DETECTORS[g][2]} |")
    w("")
    w("## In fragment today")
    w("")
    for p in in_frag:
        w(f"- {p['file']}")
    w("")
    w("## Method")
    w("")
    w("Source is masked (comments, string and char literals blanked, their")
    w("presence recorded) and each detector is a regular expression or a small")
    w("scanner over the masked text; `coverage_census.py` lists every one.")
    w("Lexical detection is approximate in both directions: `+` on sequences")
    w("is not distinguished from `+` on integers (concatenation is not tagged,")
    w("so seq needs are under-counted), `nat` is a burden not a gap, and a")
    w("quantifier is read as unbounded when its variables carry a non-int type")
    w("or no comparison bounds them before the body. Every file's tag set is")
    w("in the JSON beside this report when `--json` is given, so any row can")
    w("be checked against its source.")
    w("")
    out = Path(a.out) if a.out else None
    text = "\n".join(lines)
    if out:
        out.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {out}")
    else:
        print(text)
    if a.json:
        Path(a.json).write_text(json.dumps(programs, indent=1), encoding="utf-8", newline="\n")
        print(f"wrote {a.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
