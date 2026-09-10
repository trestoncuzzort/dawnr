#!/usr/bin/env python3
"""nl_census.py: which constructs the nl/ corpus needs that t does not have,
problem by problem, and which gate opens the most problems, dated 2026-09-09.

    python3 nl_census.py --out COVERAGE-nl.md --json ~/t-corpora/nl-census/nl-census.json

t/coverage_census.py answers this question for 785 DafnyBench ground-truth
programs, a corpus of proofs already written in a verifier's own syntax. This
file answers it for the actual target: nl/, 24,748 natural-language
programming problems across MBPP (974), HumanEval (164), APPS (10,000) and
CodeContests (13,610), none of which was ever seen by a verifier. A problem
is tagged with its `shape` (`function`: a named function with typed or
test-inferred arguments, or `stdin`: whole-program text I/O), its `io_types`
(what its interface needs, read off its tests) and its `gaps` and `burdens`
(what its FIRST Python reference solution's AST needs, over-approximating
what a hand-written t answer would need, since a t answer can be written
differently from the reference). `in_fragment` is true only for a
function-shaped problem whose io-types all fit and whose solution tags no
gap; nothing stdin-shaped is in fragment today, so those are reported
separately as "in fragment once a signature is extracted".

This is a lexical and AST census of reference solutions, not a lifter and
not a kernel run: nothing here parses a solution into a t task or asks a
kernel to verify it, and nothing here claims a t answer to a problem needs
exactly what its reference solution's AST needs. nl/FIDELITY.md's gate on
corpus numbers (nothing counts until the lifter is shown to preserve meaning
on the simplest tasks first) is untouched by this file: it measures the
corpus's own shape, not the lifter's fidelity to it.

For MBPP, every test assertion is parsed with `mbpp_dfy.parse_assertion`
(imported, not reimplemented) exactly as `spec_experiment.pool()` does to
decide whether an MBPP problem's tests fit t's fragment; its refusal reasons
name what pushed the assertion out. For HumanEval, the typed signature in
`prompt`'s `def` line is read with `ast`. For APPS and CodeContests, at most
the FIRST Python solution is parsed (`ast`; a `SyntaxError`, usually a
Python 2 solution, is recorded as `py2-unparseable` and only the io-types
side is measured); APPS problems that carry a `fn_name` in `input_output`
are LeetCode-style function calls with typed JSON arguments, so they are
`function`-shaped like MBPP and HumanEval and their io-types are read from
the typed JSON values directly. Every other APPS and CodeContests problem is
`stdin`-shaped: its io-types are read lexically off the sample `input` and
`output` text, token by token (every token an integer fits int/seq of int;
a non-integer token means a string is needed; a decimal point means a real
is needed), which can only ever detect `string-as-seq` and `real` -- a stdin
sample cannot show a map, a set, a tuple or a nested sequence, so those gaps
are not attempted for stdin-shaped problems and the io-types side of the
census under-counts them there by construction.

Detection is approximate in both directions, exactly as coverage_census.py's
is: a `+` on two lists is not distinguished from a `+` on two ints (so
`seq-append`, sequence concatenation, is undercounted where a solution
prefers `+` to `.append`), and a break or continue inside a loop is always
tagged `unbounded-loop` even where a finer read (coverage_census.py's own
break-as-return exception, LIFTER-DECISIONS.md row 23) would let a
tail-position break through as t's early-exit return instead -- a
conservative choice, so `unbounded-loop` over-counts relative to that finer
rule. Every detector is listed in DETECTORS below and the Method section at
the end of the report names every approximation.

Stdlib only, deterministic (no randomness, no network, one Python solution
read from disk in file order per split).
"""
from __future__ import annotations

import argparse
import ast
import gzip
import json
import sys
import warnings
from collections import Counter, defaultdict
from pathlib import Path

# A solution string with an invalid escape (`"\w"` inside a non-raw string,
# common in competitive-programming regex code) makes CPython's compiler
# warn, harmlessly, at ast.parse time; this file parses thousands of such
# strings and never executes them, so the warning is silenced rather than
# left to spam stderr on the full run.
warnings.filterwarnings("ignore", category=SyntaxWarning)

# Some APPS/CodeContests sample io embeds integers thousands of digits long
# (measured: one over 9,000 digits); Python 3.11+'s int/str conversion
# guard would refuse to json.loads or int() them otherwise. This file never
# computes with these integers, only classifies their token shape, so the
# guard is disabled rather than sized to fit a corpus that keeps surprising.
if hasattr(sys, "set_int_max_str_digits"):
    sys.set_int_max_str_digits(0)

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import mbpp_dfy  # noqa: E402  (parse_assertion, reused rather than reimplemented)

NL_DATA = HERE.parent / "nl" / "data"

MBPP_SPLITS = ("mbpp.jsonl.gz", "mbpp_test.jsonl.gz",
               "mbpp_validation.jsonl.gz", "mbpp_prompt.jsonl.gz")
APPS_SPLITS = ("apps_raw_train.jsonl.gz", "apps_raw_test.jsonl.gz")
CC_SPLITS = ("codecontests_train.jsonl.gz", "codecontests_valid.jsonl.gz",
             "codecontests_test.jsonl.gz")

# The eight io-type gap names shared between the io-types channel (what the
# tests need) and the solution-constructs channel (what the reference
# solution's AST needs); the remaining gap and burden names below belong to
# the solution-constructs channel only. `string-as-seq` is also read off
# io-types (a str-typed argument, return, or stdin sample token) but is a
# BURDEN, not a gap (SPEC.md's "Strings as sequences of code points"), so
# it is tracked apart from this tuple, not inside it.
IO_GAP_NAMES = ("real", "nested-seq", "map", "set", "tuple",
                "multi-return", "none-type", "any-type")

# -------------------------------------------------------------- DETECTORS
# (kind, meaning), the same style as t/coverage_census.py's DETECTORS table.
# "gap" = outside t's fragment (SYNTAX.md / SPEC.md v1). "burden" =
# expressible in t at a translation cost. Detector FUNCTIONS live below;
# this table is the report's vocabulary, walked once per problem by
# `solution_tags()` and `io_type_tags()`.
DETECTORS: dict[str, tuple[str, str]] = {
    # gaps: outside t's fragment (io-types and/or solution AST)
    "string-lib": ("gap", "the Python string LIBRARY, not the seq-of-code-"
                   "points model SPEC.md's v1 covers: any str method call "
                   "(upper/lower/split/join/strip/replace/startswith/"
                   "endswith/find/count/isdigit/...), an f-string or "
                   "`.format()`, `str()` or a based `int(x, base)` "
                   "conversion of a string, or `sorted()` on a string"),
    "real": ("gap", "real numbers: a float literal, true division `/`, "
             "math.sqrt, float(), or a decimal-valued io token"),
    "nested-seq": ("gap", "a seq of seq, or a subscript of a subscript: "
                   "list of lists in the solution or in a sample io value"),
    "map": ("gap", "dict literal, dict(), defaultdict, Counter, or a "
            "dict-typed io value"),
    "set": ("gap", "set literal, set(), frozenset(), a set/dict "
            "comprehension's set form"),
    "tuple": ("gap", "a tuple of three or more elements, a nested tuple, "
              "a tuple with a string component (until strings-as-seq's "
              "seq-of-code-points model covers a pair component too), or "
              "a list of tuples (the nested-seq gap, tagged there): "
              "SPEC.md's 'Pairs (v1)' covers only the two-element case, "
              "the burden tuple-pair"),
    "multi-return": ("gap", "a function-shaped problem returning a tuple "
                      "(several return values; t returns exactly one)"),
    "none-type": ("gap", "Optional[..] or an explicit None return/argument"),
    "any-type": ("gap", "the interface's type could not be pinned to one of "
                 "the other named types: a bare Any annotation, a call "
                 "expression as a test argument, or an untyped io value"),
    "class": ("gap", "a class definition (t has no classes, no heap)"),
    "closure": ("gap", "a lambda, a nested def, or map/filter with a lambda"),
    "exception": ("gap", "try/except/raise"),
    "unbounded-loop": ("gap", "while True, or a break/continue (t has no "
                        "while-true, no continue, and a break is only in "
                        "the fragment as a tail-position return, decision "
                        "23 -- not distinguished here, see Method)"),
    "seq-slice-negative": ("gap", "a slice bound that is a negative "
                            "literal, s[-1:] or s[:-1]: t's slice is "
                            "defined only for 0 <= a <= b <= len(s), so a "
                            "negative index is measured apart from the "
                            "burden seq-slice"),
    "seq-slice-step": ("gap", "a slice with a step, s[a:b:c]: t's slice "
                        "form takes two bounds only, no step"),
    "generator": ("gap", "a generator expression or a generator function "
                  "(yield): t has no lazy or deferred evaluation"),
    "global": ("gap", "global or nonlocal: mutable state outside the "
               "function, which t's pure functions have no notion of"),
    "import": ("gap", "an import other than math, sys or typing: an "
               "unmodeled library the solution's meaning depends on"),
    "io": ("gap", "input()/print()/sys.stdin used INSIDE a function-shaped "
           "solution (for a stdin-shaped problem, I/O is the shape itself, "
           "not a separate gap)"),
    # burdens: t can say it another way, at a cost
    "seq-literal": ("burden", "a sequence literal [..] in an expression: "
                    "t's v1 already has seq (SPEC.md 'Sequences: literals, "
                    "concatenation, slices'), landed 2026-09-09, so this "
                    "is expressible directly, not a gap"),
    "seq-append": ("burden", "sequence concatenation `+` or "
                   ".append()/.extend()/.insert(): t's v1 already has + on "
                   "seqs (SPEC.md 'Sequences: literals, concatenation, "
                   "slices'), landed as r + [x] or r + s"),
    "seq-slice": ("burden", "slicing s[a:b], s[a:], s[:b] with "
                  "non-negative bounds and no step: t's v1 already has "
                  "slice (SPEC.md 'Sequences: literals, concatenation, "
                  "slices'); a negative bound or a step is measured "
                  "separately as the gaps seq-slice-negative / "
                  "seq-slice-step"),
    "tuple-pair": ("burden", "a tuple of exactly two values, each an int, "
                   "bool or seq of ints, built, returned, passed, "
                   "compared, or unpacked from such a pair: t's v1 "
                   "already has {\"pair\": [T1, T2]} (SPEC.md 'Pairs "
                   "(v1)'), landed 2026-09-10"),
    "string-as-seq": ("burden", "a string used only the way t's `seq` of "
                       "code points already covers: a str literal, a "
                       "str-typed io value, indexing/len/slicing/"
                       "concatenation/comparison of strings, `ord`/`chr`, "
                       "iterating over a string, or `in` on a string (a "
                       "bounded exists) -- SPEC.md's 'Strings as sequences "
                       "of code points'"),
    "recursion": ("burden", "the solution's function calls itself; t "
                  "supports this through spec functions (self-calls and "
                  "calls to earlier functions), so it is a burden, not a "
                  "gap"),
    "comprehension": ("burden", "a list/set/dict comprehension over ints; "
                       "t writes this as an explicit loop or a quantifier"),
    "sort": ("burden", "sorted() or .sort(); expressible in t but needs a "
             "spec, not a builtin"),
    "builtin-math": ("burden", "min, max, sum or abs; t can express each "
                      "but has no builtin for any of them"),
    "stdin-to-signature": ("burden", "a stdin-shaped problem carries no "
                            "function signature; one has to be extracted "
                            "from its input format before t can pose the "
                            "problem at all"),
    "py2-unparseable": ("burden", "the chosen Python solution does not "
                         "parse under Python 3's ast (typically a Python 2 "
                         "solution: print statement, raw_input, etc.); only "
                         "its io-types are measured, its AST is not"),
}

GAPS = [k for k, (kind, _) in DETECTORS.items() if kind == "gap"]
BURDENS = [k for k, (kind, _) in DETECTORS.items() if kind == "burden"]

STRING_METHODS = {"upper", "lower", "split", "join", "strip", "lstrip",
                   "rstrip", "replace", "startswith", "endswith", "format",
                   "capitalize", "title", "isdigit", "isalpha", "isupper",
                   "islower", "zfill", "center", "ljust", "rjust",
                   "partition", "splitlines", "encode", "swapcase",
                   "find", "count"}
MAP_CALLS = {"dict", "defaultdict", "Counter", "OrderedDict"}
SET_CALLS = {"set", "frozenset"}
SORT_CALLS = {"sorted"}
MATH_BUILTIN_CALLS = {"min", "max", "sum", "abs"}
APPEND_METHODS = {"append", "extend", "insert"}
ORD_CHR_CALLS = {"ord", "chr"}


# ---------------------------------------------------------- solution AST
def _call_name(node: ast.Call) -> str | None:
    f = node.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return None


def _is_self_call(node: ast.AST, fn_name: str) -> bool:
    return any(isinstance(n, ast.Call) and _call_name(n) == fn_name
               for n in ast.walk(node))


def _looks_stringy(node: ast.AST) -> bool:
    """Shallow syntactic check, no variable-type inference: does this
    expression obviously produce a str? Used only to decide whether
    `sorted(...)` is sorting a string (also tags `string-lib`, since
    Python's sorted() returns a list of characters, not a string, so
    reasoning about the result needs more than the seq-of-code-points
    model) versus sorting a list (`sort` burden only, untouched). A
    string held in a plain variable is not recognized this way and is
    undercounted here, see Method."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return True
    if isinstance(node, ast.JoinedStr):
        return True
    if isinstance(node, ast.Attribute) and node.attr in STRING_METHODS:
        return True
    if isinstance(node, ast.Call):
        name = _call_name(node)
        if name == "str":
            return True
        if isinstance(node.func, ast.Attribute) and node.func.attr in STRING_METHODS:
            return True
    return False


def _is_negative_slice_bound(node: ast.AST | None) -> bool:
    """A slice bound written as a negative literal, `-1` in `s[:-1]`:
    Python's `ast` reads `-1` as `UnaryOp(USub, Constant(1))`, never a
    `Constant` of a negative int, so this is the shape to check, not the
    value. A negative bound behind a variable or an expression (`s[:n-1]`)
    is not recognized this way and reads as a plain (non-negative)
    `seq-slice`, the same undercounting direction every other syntactic
    detector in this file accepts."""
    return isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub)


def _classify_tuple_literal_elts(elts: list[ast.AST]) -> str:
    """(SPEC.md 'Pairs (v1)') Exactly two elements, neither a nested tuple
    nor syntactically a string (`_looks_stringy`), reads as the burden
    `tuple-pair`: t's v1 pair type takes a component that is an int, a
    bool, or a seq of ints, and a bare non-string, non-tuple element is
    assumed to fit one of those without further type inference, the same
    approximation direction this file takes elsewhere. Three or more
    elements, a nested tuple, or a string element reads as the gap
    `tuple`; a LIST of tuples is a separate case, tagged `nested-seq`
    where a list literal's own elements are inspected, not here."""
    if len(elts) != 2:
        return "tuple"
    if any(isinstance(e, ast.Tuple) for e in elts):
        return "tuple"
    if any(_looks_stringy(e) for e in elts):
        return "tuple"
    return "tuple-pair"


def solution_tags(src: str, fn_name: str | None, function_shaped: bool) -> dict:
    """Tag one reference solution's AST. `fn_name` is the entry point for a
    function-shaped problem (used to detect self-recursion and multi-return
    on ITS OWN return statements); None for a stdin-shaped problem, where
    recursion is detected on any self-recursive def and multi-return is not
    attempted (SYNTAX.md's multi-return is defined here only for a function
    returning a tuple, not for a program printing several lines)."""
    tags: dict[str, bool] = defaultdict(bool)
    try:
        tree = ast.parse(src)
    except SyntaxError:
        tags["py2-unparseable"] = True
        return dict(tags)

    target_fn: ast.FunctionDef | None = None
    if fn_name:
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == fn_name:
                target_fn = n
                break

    top_level_defs = {n for n in ast.walk(tree)
                       if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    nested_defs: set[ast.AST] = set()

    def _mark_nested(node: ast.AST, inside_def: bool) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if inside_def:
                    nested_defs.add(child)
                _mark_nested(child, True)
            else:
                _mark_nested(child, inside_def)

    _mark_nested(tree, False)
    if nested_defs:
        tags["closure"] = True

    # A parallel assignment whose right-hand side is a tuple literal of
    # the same length as its tuple target (`a, b = b, a`, `a, b = 1, 2`)
    # is not a `tuple`/`tuple-pair` shape at all: t writes it as two
    # assignments, no pair value ever built. Both the target and value
    # Tuple nodes of such an assignment are recorded here so the generic
    # `ast.Tuple` check below (which every OTHER tuple anywhere in the
    # solution, built, returned, passed, compared, or unpacked, now
    # reaches) skips exactly this shape, matching what the old
    # assignment-only `tuple` detector already excluded.
    excluded_tuples: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Tuple):
            tgt, val = node.targets[0], node.value
            if isinstance(val, ast.Tuple) and len(val.elts) == len(tgt.elts):
                excluded_tuples.add(id(tgt))
                excluded_tuples.add(id(val))

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, str) and node.value != "":
                tags["string-as-seq"] = True
            elif isinstance(node.value, float):
                tags["real"] = True
        elif isinstance(node, ast.JoinedStr):  # f-string
            tags["string-lib"] = True
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            tags["real"] = True
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            if isinstance(node.left, ast.List) or isinstance(node.right, ast.List):
                tags["seq-append"] = True
        elif isinstance(node, ast.Subscript):
            if isinstance(node.slice, ast.Slice):
                sl = node.slice
                if sl.step is not None:
                    tags["seq-slice-step"] = True
                elif _is_negative_slice_bound(sl.lower) or _is_negative_slice_bound(sl.upper):
                    tags["seq-slice-negative"] = True
                else:
                    tags["seq-slice"] = True
            if isinstance(node.value, ast.Subscript):
                tags["nested-seq"] = True
        elif isinstance(node, ast.List):
            tags["seq-literal"] = True
            if any(isinstance(e, (ast.List, ast.Tuple)) for e in node.elts):
                tags["nested-seq"] = True
        elif isinstance(node, ast.Tuple):
            if id(node) not in excluded_tuples:
                tags[_classify_tuple_literal_elts(node.elts)] = True
        elif isinstance(node, (ast.Dict,)):
            tags["map"] = True
        elif isinstance(node, (ast.Set, ast.SetComp)):
            tags["set"] = True
        elif isinstance(node, ast.DictComp):
            tags["map"] = True
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp)):
            tags["comprehension"] = True
        elif isinstance(node, ast.GeneratorExp):
            tags["generator"] = True
        elif isinstance(node, ast.ClassDef):
            tags["class"] = True
        elif isinstance(node, ast.Lambda):
            tags["closure"] = True
        elif isinstance(node, (ast.Try, ast.Raise)):
            tags["exception"] = True
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            tags["global"] = True
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            mods = [node.module] if isinstance(node, ast.ImportFrom) else [a.name for a in node.names]
            for m in mods:
                base = (m or "").split(".")[0]
                if base not in ("math", "sys", "typing", ""):
                    tags["import"] = True
        elif isinstance(node, ast.While):
            test = node.test
            if isinstance(test, ast.Constant) and test.value is True:
                tags["unbounded-loop"] = True
        elif isinstance(node, (ast.Break, ast.Continue)):
            tags["unbounded-loop"] = True
        elif isinstance(node, ast.Attribute):
            if node.attr in STRING_METHODS:
                tags["string-lib"] = True
            if node.attr in APPEND_METHODS:
                tags["seq-append"] = True
            if node.attr == "sort":
                tags["sort"] = True
            if node.attr == "sqrt":
                tags["real"] = True
        elif isinstance(node, ast.Call):
            name = _call_name(node)
            if name in MAP_CALLS:
                tags["map"] = True
            elif name in SET_CALLS:
                tags["set"] = True
            elif name in SORT_CALLS:
                tags["sort"] = True
                if node.args and _looks_stringy(node.args[0]):
                    tags["string-lib"] = True
            elif name in MATH_BUILTIN_CALLS:
                tags["builtin-math"] = True
            elif name == "float":
                tags["real"] = True
            elif name in ORD_CHR_CALLS:
                tags["string-as-seq"] = True
            elif name == "str":
                tags["string-lib"] = True
            elif name == "int" and len(node.args) >= 2:
                tags["string-lib"] = True
            elif name in ("map", "filter") and any(isinstance(a, ast.Lambda) for a in node.args):
                tags["closure"] = True
            elif name == "print":
                if function_shaped:
                    tags["io"] = True
            elif name == "input":
                if function_shaped:
                    tags["io"] = True

    # recursion and multi-return, read off the entry point specifically for
    # a function-shaped problem; off any self-recursive def for stdin.
    if function_shaped and target_fn is not None:
        if _is_self_call(target_fn, fn_name):
            tags["recursion"] = True
        for n in ast.walk(target_fn):
            if isinstance(n, ast.Return) and isinstance(n.value, ast.Tuple):
                tags["multi-return"] = True
            if isinstance(n, ast.Return) and isinstance(n.value, ast.Constant) \
                    and n.value.value is None and n is not None:
                # an explicit `return None` in a function-shaped solution
                tags["none-type"] = True
    else:
        for n in top_level_defs:
            if n.name and _is_self_call(n, n.name):
                tags["recursion"] = True

    return dict(tags)


# ------------------------------------------------------------- io-types
def _mbpp_arg_kind_gap(why: str) -> str | None:
    """Map one mbpp_dfy.parse_assertion refusal reason to an io-type gap or
    burden name, where the reason names a type mbpp_dfy's own _literal()
    refused. Every mapped name is a gap except `str`, which maps to the
    burden `string-as-seq` (mbpp_io_tags sorts gap from burden by
    DETECTORS' own kind). Structural refusals (a comparison other than ==,
    an unparseable assertion shape, a keyword argument, ...) name no type
    and map to nothing; they are still recorded as raw refusals in the
    JSON."""
    if ":" not in why:
        return None
    prefix, rest = why.split(":", 1)
    if prefix not in ("arg", "expected"):
        return None
    rest = rest.split("(")[0]
    if rest.startswith("negated-"):
        rest = rest[len("negated-"):]
    if rest.startswith("seq-of-"):
        rest = rest[len("seq-of-"):]
        if rest == "seq":
            return "nested-seq"
    mapping = {
        "str": "string-as-seq", "float": "real", "dict": "map", "set": "set",
        "tuple": "tuple", "bool": None, "NoneType": "none-type",
    }
    if rest in mapping:
        return mapping[rest]
    if rest.startswith("call"):
        return "any-type"
    return "any-type"


def _mbpp_assert_tuple_kind(a: str, prefix: str) -> str:
    """Re-reads one MBPP assert line to classify a 'tuple' refusal by
    arity and component shape. `mbpp_dfy._Unsupported` carries no arity,
    its message is the bare word 'tuple' whatever length or shape tripped
    it (mbpp_dfy.py is reused, not reimplemented, so it is not widened to
    say more), so this file re-parses the SAME assert text independently
    with its own `ast`, finds the literal tuple on the side `prefix`
    ('arg' or 'expected') names, and applies `_classify_tuple_literal_elts`
    to it. Falls back to the gap `tuple` whenever the assert does not have
    the plain `f(...) == expected` shape this reads (or the tuple cannot
    be found there), the same conservative default the io-types side
    already takes elsewhere in this file."""
    try:
        tree = ast.parse(a.strip())
    except SyntaxError:
        return "tuple"
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.Assert):
        return "tuple"
    test = tree.body[0].test
    if not isinstance(test, ast.Compare) or len(test.ops) != 1 or len(test.comparators) != 1:
        return "tuple"
    left, right = test.left, test.comparators[0]
    call = left if isinstance(left, ast.Call) else (right if isinstance(right, ast.Call) else None)
    expected = right if call is left else left
    node = None
    if prefix == "arg" and isinstance(call, ast.Call):
        node = next((n for n in call.args if isinstance(n, ast.Tuple)), None)
    elif prefix == "expected":
        node = expected if isinstance(expected, ast.Tuple) else None
    return _classify_tuple_literal_elts(node.elts) if node is not None else "tuple"


def mbpp_io_tags(test_list: list[str]) -> tuple[set[str], set[str], set[str], list[str], bool, str | None]:
    """(io_types, gaps, burdens, raw_refusals, all_ok, fn_name) for one MBPP
    problem's test_list, using mbpp_dfy.parse_assertion on every assertion
    (reused, not reimplemented). `all_ok` and a single `fn_name` across
    every assertion mirror spec_experiment.pool()'s own admission rule."""
    io_types: set[str] = set()
    gaps: set[str] = set()
    burdens: set[str] = set()
    refusals: list[str] = []
    fns: set[str] = set()
    all_ok = bool(test_list)
    for a in test_list:
        parsed = mbpp_dfy.parse_assertion(a)
        if parsed["ok"]:
            fns.add(parsed["fn"])
            for kind, _ in parsed["args"]:
                io_types.add(kind if kind != "seq" else "seq<int>")
            ek, _ = parsed["expected"]
            io_types.add(ek if ek != "seq" else "seq<int>")
            if ek not in ("int", "bool"):
                all_ok = False
        else:
            all_ok = False
            refusals.append(parsed["why"])
            g = _mbpp_arg_kind_gap(parsed["why"])
            if g == "tuple":
                prefix = parsed["why"].split(":", 1)[0]
                g = _mbpp_assert_tuple_kind(a, prefix)
            if g:
                (burdens if g in BURDENS else gaps).add(g)
    single_fn = len(fns) == 1
    fn_name = next(iter(fns)) if single_fn else None
    if not single_fn:
        all_ok = False
    return io_types, gaps, burdens, refusals, all_ok, fn_name


TYPING_REAL = {"float", "Decimal"}
TYPING_STR = {"str"}


def _annotation_kinds(ann: ast.AST | None) -> set[str]:
    """One type annotation -> the io-type gap names it needs (empty set if
    it fits int/bool/seq<int>, or if there is no annotation to read)."""
    if ann is None:
        return {"any-type"}
    out: set[str] = set()

    def walk(node: ast.AST, depth: int) -> None:
        if isinstance(node, ast.Constant):
            if node.value is None:
                out.add("none-type")
            return
        if isinstance(node, ast.Subscript):
            base = node.value
            base_name = getattr(base, "id", None) or getattr(base, "attr", None)
            slc = node.slice
            args = slc.elts if isinstance(slc, ast.Tuple) else [slc]
            if base_name in ("List", "list", "Sequence", "Iterable", "Iterator"):
                if depth >= 1:
                    out.add("nested-seq")
                else:
                    for a in args:
                        walk(a, depth + 1)
            elif base_name in ("Dict", "dict", "Mapping", "DefaultDict"):
                out.add("map")
            elif base_name in ("Set", "set", "FrozenSet"):
                out.add("set")
            elif base_name in ("Tuple", "tuple"):
                # SPEC.md 'Pairs (v1)': exactly two components, each
                # itself annotated as fitting int/bool/seq of ints (no
                # gap or burden of its own from the recursive read) is
                # the burden `tuple-pair`; anything else (arity != 2, a
                # component that is itself a gap or burden such as a
                # string, a nested seq, or another tuple) stays the gap
                # `tuple`.
                if len(args) == 2 and not any(_annotation_kinds(a) for a in args):
                    out.add("tuple-pair")
                else:
                    out.add("tuple")
            elif base_name == "Optional":
                out.add("none-type")
                for a in args:
                    walk(a, depth)
            elif base_name == "Union":
                for a in args:
                    walk(a, depth)
            else:
                out.add("any-type")
            return
        if isinstance(node, ast.Name):
            if node.id == "int":
                return
            if node.id == "bool":
                return
            if node.id in TYPING_STR:
                out.add("string-as-seq")
                return
            if node.id in TYPING_REAL:
                out.add("real")
                return
            if node.id == "Any":
                out.add("any-type")
                return
            if node.id == "None":
                out.add("none-type")
                return
            out.add("any-type")
            return
        if isinstance(node, ast.Attribute):
            out.add("any-type")
            return
        out.add("any-type")

    walk(ann, 0)
    return out


def humaneval_io_tags(prompt: str, entry_point: str) -> tuple[set[str], set[str], set[str]]:
    """(io_types, gaps, burdens) read off the typed def line in `prompt`;
    an annotation kind is sorted into gaps or burdens by DETECTORS' own
    kind (`string-as-seq`, from a `str` annotation, is the only burden
    `_annotation_kinds` can produce)."""
    io_types: set[str] = set()
    gaps: set[str] = set()
    burdens: set[str] = set()
    try:
        tree = ast.parse(prompt)
    except SyntaxError:
        return io_types, {"any-type"}, burdens
    fn = None
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == entry_point:
            fn = n
            break
    if fn is None:
        return io_types, {"any-type"}, burdens
    args = list(fn.args.args)
    for a in args:
        ks = _annotation_kinds(a.annotation)
        if not ks:
            io_types.add("param")
        gaps |= {k for k in ks if k in GAPS}
        burdens |= {k for k in ks if k in BURDENS}
    ret_ks = _annotation_kinds(fn.returns)
    if "tuple" in ret_ks or "tuple-pair" in ret_ks:
        # a Tuple[..] RETURN type means several return values, not a
        # tuple-shaped value in the data: that shape is the pre-existing
        # gap `multi-return` (unchanged by the tuple/tuple-pair split),
        # regardless of whether the tuple's own arity would otherwise
        # have qualified as the pair burden.
        ret_ks.discard("tuple")
        ret_ks.discard("tuple-pair")
        ret_ks.add("multi-return")
    gaps |= {k for k in ret_ks if k in GAPS}
    burdens |= {k for k in ret_ks if k in BURDENS}
    return io_types, gaps, burdens


def _json_value_kinds(v, depth: int = 0) -> set[str]:
    """One decoded JSON value (from APPS's typed `fn_name` io) -> io-type
    gap or burden names, or empty if it fits int/bool/seq<int> (a str value
    yields the burden `string-as-seq`)."""
    if isinstance(v, bool):
        return set()
    if isinstance(v, int):
        return set()
    if isinstance(v, float):
        return {"real"}
    if isinstance(v, str):
        return {"string-as-seq"}
    if v is None:
        return {"none-type"}
    if isinstance(v, list):
        if not v:
            return set()
        out: set[str] = set()
        for el in v:
            if isinstance(el, list):
                out.add("nested-seq")
            else:
                out |= _json_value_kinds(el, depth + 1)
        return out
    if isinstance(v, dict):
        return {"map"}
    return {"any-type"}


def _flatten_text(x, depth: int = 0) -> str:
    """APPS's `inputs`/`outputs` are usually `list[str]` (one string per
    test case) but sometimes `list[list[str]]` (one line per element,
    upstream's own inconsistency, measured on apps_raw_train id 514); this
    flattens either shape, and anything more nested, to whitespace-joined
    text for the lexical scan."""
    if isinstance(x, str):
        return x
    if isinstance(x, (list, tuple)) and depth < 4:
        return " ".join(_flatten_text(e, depth + 1) for e in x)
    return "" if x is None else str(x)


def _lexical_tokens_kinds(text: str) -> set[str]:
    """Stdin sample text -> io-type gap/burden names found lexically: every
    whitespace token tried as an int, then a float, else it is a string
    token (the burden `string-as-seq`, not a gap: a stdin-shaped problem's
    sample text needing a string does not by itself block
    `would_be_in_fragment_with_signature`, only a decimal token does)."""
    out: set[str] = set()
    for tok in text.split():
        try:
            int(tok)
            continue
        except ValueError:
            pass
        try:
            float(tok)
            out.add("real")
            continue
        except ValueError:
            pass
        out.add("string-as-seq")
    return out


# ----------------------------------------------------------------- shape
def function_in_fragment(io_gaps: set[str], sol_gaps: set[str]) -> bool:
    return not (io_gaps | sol_gaps)


def make_record(source: str, pid: str, shape: str, io_types, gaps: set[str],
                 burdens: set[str], in_fragment: bool, extra: dict | None = None) -> dict:
    rec = {
        "source": source,
        "id": pid,
        "shape": shape,
        "io_types": sorted(io_types),
        "gaps": sorted(gaps),
        "burdens": sorted(burdens),
        "in_fragment": bool(in_fragment),
    }
    if extra:
        rec.update(extra)
    return rec


# ------------------------------------------------------------- streaming
def _stream(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def process_mbpp(limit: int | None = None) -> list[dict]:
    out = []
    for split in MBPP_SPLITS:
        path = NL_DATA / split
        if not path.exists():
            continue
        stub = split[: -len(".jsonl.gz")]
        n = 0
        for rec in _stream(path):
            if limit is not None and n >= limit:
                break
            n += 1
            task_id = rec["task_id"]
            test_list = rec.get("test_list") or []
            io_types, io_gaps, io_burdens, refusals, all_ok, fn_name = mbpp_io_tags(test_list)
            sol_tags = solution_tags(rec.get("code", ""), fn_name, function_shaped=True)
            sol_gaps = {k for k in sol_tags if k in GAPS}
            burdens = {k for k in sol_tags if k in BURDENS} | io_burdens
            gaps = io_gaps | sol_gaps
            in_frag = all_ok and function_in_fragment(io_gaps, sol_gaps)
            out.append(make_record(
                "MBPP", f"{stub}:{task_id}", "function", io_types, gaps, burdens, in_frag,
                {"split": stub, "refusals": refusals}))
    return out


def process_humaneval(limit: int | None = None) -> list[dict]:
    path = NL_DATA / "humaneval.jsonl.gz"
    out = []
    if not path.exists():
        return out
    n = 0
    for rec in _stream(path):
        if limit is not None and n >= limit:
            break
        n += 1
        entry = rec["entry_point"]
        io_types, io_gaps, io_burdens = humaneval_io_tags(rec["prompt"], entry)
        full_src = rec["prompt"] + rec.get("canonical_solution", "")
        sol_tags = solution_tags(full_src, entry, function_shaped=True)
        sol_gaps = {k for k in sol_tags if k in GAPS}
        burdens = {k for k in sol_tags if k in BURDENS} | io_burdens
        gaps = io_gaps | sol_gaps
        in_frag = function_in_fragment(io_gaps, sol_gaps)
        out.append(make_record(
            "HumanEval", rec["task_id"], "function", io_types, gaps, burdens, in_frag))
    return out


def process_apps(limit: int | None = None) -> list[dict]:
    out = []
    for split in APPS_SPLITS:
        path = NL_DATA / split
        if not path.exists():
            continue
        stub = split[: -len(".jsonl.gz")]
        n = 0
        for rec in _stream(path):
            if limit is not None and n >= limit:
                break
            n += 1
            pid = f"{stub}:{rec.get('id')}"
            try:
                io = json.loads(rec.get("input_output") or "{}")
            except (json.JSONDecodeError, TypeError):
                io = {}
            fn_name = io.get("fn_name")
            try:
                sols = json.loads(rec.get("solutions") or "[]")
            except (json.JSONDecodeError, TypeError):
                sols = []
            first_sol = sols[0] if sols else None
            burdens: set[str] = set()
            if fn_name:
                # LeetCode-style: function-shaped, typed JSON io.
                io_types: set[str] = set()
                io_gaps: set[str] = set()
                inputs = io.get("inputs") or []
                outputs = io.get("outputs") or []
                for row in inputs[:5]:
                    for v in (row if isinstance(row, list) else [row]):
                        ks = _json_value_kinds(v)
                        io_gaps |= {k for k in ks if k in GAPS}
                        burdens |= {k for k in ks if k in BURDENS}
                for row in outputs[:5]:
                    ks = _json_value_kinds(row)
                    io_gaps |= {k for k in ks if k in GAPS}
                    burdens |= {k for k in ks if k in BURDENS}
                if first_sol is None:
                    sol_tags = {}
                else:
                    sol_tags = solution_tags(first_sol, fn_name, function_shaped=True)
                sol_gaps = {k for k in sol_tags if k in GAPS}
                burdens |= {k for k in sol_tags if k in BURDENS}
                gaps = io_gaps | sol_gaps
                parsed_ok = first_sol is not None and "py2-unparseable" not in sol_tags
                in_frag = function_in_fragment(io_gaps, sol_gaps) and parsed_ok
                out.append(make_record(
                    "APPS", pid, "function", io_types, gaps, burdens, in_frag,
                    {"split": stub, "has_solution": first_sol is not None}))
            else:
                raw_in = io.get("inputs")
                raw_out = io.get("outputs")
                sample_in = _flatten_text(raw_in[:3]) if isinstance(raw_in, list) else ""
                sample_out = _flatten_text(raw_out[:3]) if isinstance(raw_out, list) else ""
                lex = _lexical_tokens_kinds(sample_in) | _lexical_tokens_kinds(sample_out)
                io_gaps = {k for k in lex if k in GAPS}
                burdens.add("stdin-to-signature")
                burdens |= {k for k in lex if k in BURDENS}
                if first_sol is None:
                    sol_tags = {}
                else:
                    sol_tags = solution_tags(first_sol, None, function_shaped=False)
                sol_gaps = {k for k in sol_tags if k in GAPS}
                burdens |= {k for k in sol_tags if k in BURDENS}
                gaps = io_gaps | sol_gaps
                io_sample_ok = "real" not in io_gaps
                parsed_ok = first_sol is not None and "py2-unparseable" not in sol_tags
                would_be_in_fragment = io_sample_ok and not sol_gaps and parsed_ok
                out.append(make_record(
                    "APPS", pid, "stdin", set(), gaps, burdens, False,
                    {"split": stub, "has_solution": first_sol is not None,
                     "would_be_in_fragment_with_signature": would_be_in_fragment}))
    return out


def process_codecontests(limit: int | None = None) -> list[dict]:
    out = []
    for split in CC_SPLITS:
        path = NL_DATA / split
        if not path.exists():
            continue
        stub = split[: -len(".jsonl.gz")]
        n = 0
        for rec in _stream(path):
            if limit is not None and n >= limit:
                break
            n += 1
            pid = f"{stub}:{rec.get('name')}"
            first_sol = None
            for s in rec.get("solutions") or []:
                if s.get("language") in ("PYTHON3", "PYTHON"):
                    first_sol = s.get("solution")
                    break
            tests = rec.get("public_tests") or []
            sample_in = " ".join(t.get("input", "") for t in tests[:3])
            sample_out = " ".join(t.get("output", "") for t in tests[:3])
            lex = _lexical_tokens_kinds(sample_in) | _lexical_tokens_kinds(sample_out)
            io_gaps = {k for k in lex if k in GAPS}
            burdens = {"stdin-to-signature"} | {k for k in lex if k in BURDENS}
            if first_sol is None:
                sol_tags = {}
            else:
                sol_tags = solution_tags(first_sol, None, function_shaped=False)
            sol_gaps = {k for k in sol_tags if k in GAPS}
            burdens |= {k for k in sol_tags if k in BURDENS}
            gaps = io_gaps | sol_gaps
            io_sample_ok = "real" not in io_gaps
            parsed_ok = first_sol is not None and "py2-unparseable" not in sol_tags
            would_be_in_fragment = io_sample_ok and not sol_gaps and parsed_ok
            out.append(make_record(
                "CodeContests", pid, "stdin", set(), gaps, burdens, False,
                {"split": stub, "has_solution": first_sol is not None,
                 "would_be_in_fragment_with_signature": would_be_in_fragment}))
    return out


# --------------------------------------------------------------- greedy
def greedy(programs: list[dict]) -> list[tuple[str, int, int]]:
    """Open gates one at a time, each time the one that unlocks the most
    still-blocked FUNCTION-shaped programs; returns (gate, newly unlocked,
    cumulative). Same algorithm as coverage_census.py's greedy(), over
    `gaps` instead of DafnyBench's tag set. Stdin-shaped problems are not
    in this population: opening gates does not put them in fragment, since
    stdin-to-signature is not a gate any DETECTORS entry opens."""
    func = [p for p in programs if p["shape"] == "function"]
    open_gates: set[str] = set()
    covered = sum(1 for p in func if p["in_fragment"])
    steps = []
    remaining = [p for p in func if not p["in_fragment"]]
    while remaining:
        best, best_n = None, 0
        for g in GAPS:
            if g in open_gates:
                continue
            n = sum(1 for p in remaining if set(p["gaps"]) <= open_gates | {g})
            if n > best_n:
                best, best_n = g, n
        if best is None or best_n == 0:
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


# ---------------------------------------------------------------- report
def render(programs: list[dict], elapsed_s: float) -> str:
    n = len(programs)
    by_source: dict[str, list[dict]] = defaultdict(list)
    for p in programs:
        by_source[p["source"]].append(p)
    func = [p for p in programs if p["shape"] == "function"]
    stdin_p = [p for p in programs if p["shape"] == "stdin"]
    in_frag = [p for p in programs if p["in_fragment"]]
    would_be = [p for p in stdin_p if p.get("would_be_in_fragment_with_signature")]

    gap_count = Counter(g for p in programs for g in p["gaps"])
    burden_count = Counter(b for p in programs for b in p["burdens"])
    one_gap = Counter(p["gaps"][0] for p in func if len(p["gaps"]) == 1)

    steps = greedy(programs)

    lines: list[str] = []
    w = lines.append
    w(f"# t coverage census: nl ({n} problems)")
    w("")
    w("What the nl/ corpus needs that t does not have, problem by problem,")
    w("and which gate opens the most problems. Lexical and AST census of")
    w("reference solutions, no lifter and no kernel run: a solution's")
    w("constructs over-approximate what a t answer would need, since a t")
    w("answer can be written differently from the reference. nl/FIDELITY.md's")
    w("gate on corpus numbers is untouched by this file. Method and")
    w("detectors at the end.")
    w("")
    w("## Headline")
    w("")
    w(f"- problems: {n}")
    for src in ("MBPP", "HumanEval", "APPS", "CodeContests"):
        ps = by_source.get(src, [])
        w(f"  - {src}: {len(ps)}")
    w(f"- function-shaped: {len(func)}; stdin-shaped: {len(stdin_p)}")
    w(f"- in t's fragment today: **{len(in_frag)}** of {len(func)} "
      f"function-shaped ({100 * len(in_frag) / max(1, len(func)):.1f}%)")
    w(f"- stdin-shaped, in fragment once a signature is extracted (all-int "
      f"sample io, solution tags no gap): **{len(would_be)}** of "
      f"{len(stdin_p)} ({100 * len(would_be) / max(1, len(stdin_p)):.1f}%)")
    w(f"- function-shaped problems blocked by exactly one gap: {sum(one_gap.values())}")
    w("")
    w("## Gaps, by problems that need them")
    w("")
    w("| gap | problems | sole blocker for (function-shaped) | meaning |")
    w("|---|---|---|---|")
    for g, c in gap_count.most_common():
        w(f"| {g} | {c} | {one_gap.get(g, 0)} | {DETECTORS[g][1]} |")
    w("")
    w("## Greedy gate order, whole corpus (function-shaped population)")
    w("")
    w("| step | gate | newly unlocked | cumulative in fragment | of function-shaped |")
    w("|---|---|---|---|---|")
    for i, (g, k, cum) in enumerate(steps, 1):
        w(f"| {i} | {g} | {k} | {cum} | {100 * cum / max(1, len(func)):.1f}% |")
    w("")
    w("A step with 0 newly unlocked is a gate that unlocks nothing alone but")
    w("is the most frequent remaining gap; the programs it belongs to need")
    w("more than one gate.")
    w("")
    for src in ("MBPP", "HumanEval", "APPS", "CodeContests"):
        ps = by_source.get(src, [])
        ps_func = [p for p in ps if p["shape"] == "function"]
        if not ps_func:
            w(f"### {src}: no function-shaped problems")
            w("")
            continue
        src_steps = greedy(ps)
        src_in_frag = sum(1 for p in ps_func if p["in_fragment"])
        w(f"### {src} greedy gate order ({len(ps_func)} function-shaped, "
          f"{src_in_frag} in fragment today)")
        w("")
        w("| step | gate | newly unlocked | cumulative | of function-shaped |")
        w("|---|---|---|---|---|")
        for i, (g, k, cum) in enumerate(src_steps, 1):
            w(f"| {i} | {g} | {k} | {cum} | {100 * cum / max(1, len(ps_func)):.1f}% |")
        w("")
    w("## By source")
    w("")
    w("| source | problems | function-shaped | stdin-shaped | in fragment | "
      "stdin in fragment once signature extracted |")
    w("|---|---|---|---|---|---|")
    for src in ("MBPP", "HumanEval", "APPS", "CodeContests"):
        ps = by_source.get(src, [])
        pf = [p for p in ps if p["shape"] == "function"]
        pst = [p for p in ps if p["shape"] == "stdin"]
        pin = sum(1 for p in ps if p["in_fragment"])
        pwb = sum(1 for p in pst if p.get("would_be_in_fragment_with_signature"))
        w(f"| {src} | {len(ps)} | {len(pf)} | {len(pst)} | {pin} | {pwb} |")
    w("")
    w("## Burdens (expressible in t at a translation cost)")
    w("")
    w("| burden | problems | meaning |")
    w("|---|---|---|")
    for b, c in burden_count.most_common():
        w(f"| {b} | {c} | {DETECTORS[b][1]} |")
    w("")
    w("## Method")
    w("")
    w(f"Run time: {elapsed_s:.1f}s. Every source's first Python solution "
      f"only; APPS and CodeContests carry many, all but the first are")
    w("unread. `mbpp_dfy.parse_assertion` is reused for every MBPP")
    w("assertion (spec_experiment.py's `pool()` uses the same function to")
    w("decide the same question, whether a problem's tests fit t's")
    w("fragment); its refusal reasons are recorded verbatim in the JSON")
    w("beside this report and mapped to a gap name only where the reason")
    w("names a type (`arg:str`, `expected:float`, ...); a structural")
    w("refusal (a comparison other than `==`, an unparseable assertion")
    w("shape, a keyword argument) names no type and contributes no gap,")
    w("though it is still counted toward `all_ok` and can keep a problem")
    w("out of fragment on its own.")
    w("")
    w("HumanEval's io-types come from `ast`-parsing the typed `def` line in")
    w("`prompt` (always present, always parses: measured 164 of 164).")
    w("APPS problems whose `input_output` carries a `fn_name` are")
    w("LeetCode-style function calls (`class Solution: def f(self, ...)`)")
    w("with typed JSON arguments and a typed JSON return in the SAME field")
    w("that other APPS problems use for raw stdin text; these are counted")
    w("as `function`-shaped, like MBPP and HumanEval, and their io-types")
    w("are read directly off the decoded JSON values of up to 5 sample")
    w("input rows and 5 sample outputs, not lexically. Every other APPS")
    w("problem, and every CodeContests problem, is `stdin`-shaped: its")
    w("io-types come from a lexical scan of up to 3 sample `input`/`output`")
    w("blocks (`public_tests` for CodeContests), token by token on")
    w("whitespace -- every token that parses as `int` needs nothing, a")
    w("token that parses as `float` but not `int` needs `real`, anything")
    w("else needs the burden `string-as-seq`. A lexical scan cannot show a")
    w("map, a set, a tuple or a nested sequence, so those four gaps are")
    w("never attempted for a stdin-shaped problem's io-types; only its")
    w("SOLUTION's AST can still tag them.")
    w("")
    w("A stdin-shaped problem is never `in_fragment`: SYNTAX.md and the")
    w("brief for this file agree a signature has to exist before a")
    w("problem can be posed to t at all, which is the `stdin-to-signature`")
    w("burden every stdin-shaped problem carries. `would_be_in_fragment_"
      "with_signature` in the JSON (and the by-source table above) marks")
    w("the ones whose sample io has no decimal-valued (`real`) token and")
    w("whose solution tags no gap -- everything BUT the missing signature")
    w("already fits; a string token in the sample is no longer")
    w("disqualifying on its own, since `string-as-seq` is a burden, not a")
    w("gap. A problem with no Python solution, or whose chosen solution is")
    w("`py2-unparseable`, is never marked this way even when its sample io")
    w("has no `real` token: the solution side is unmeasured, not measured")
    w("clean.")
    w("")
    w("Solution-construct detection walks the parsed `ast` once per")
    w("solution; each DETECTORS entry below is either a node-type check")
    w("(a `try`/`raise` is `exception`, a `ClassDef` is `class`) or a")
    w("narrower check on a `Call`, `Attribute`, `Subscript` or `Tuple`")
    w("node. It is approximate in both directions, and the approximations")
    w("are named rather than hidden:")
    w("")
    w("- `seq-append` (a burden since SPEC.md's 'Sequences: literals,")
    w("  concatenation, slices' landed) only fires on")
    w("  `.append`/`.extend`/`.insert` or a `+` where at least one operand")
    w("  is a literal list; a `+` between two names typed as lists earlier")
    w("  in the function is not traced and is undercounted here, the same")
    w("  undercounting coverage_census.py notes for `+` on Dafny")
    w("  sequences;")
    w("- `seq-slice` (a burden, same landing) fires on `s[a:b]`, `s[a:]`,")
    w("  `s[:b]` read off the AST `Slice` node's own shape, not a")
    w("  computed value: a step present on the slice tags `seq-slice-step`")
    w("  instead, and a bound written as a negative literal (`s[:-1]`,")
    w("  `ast`'s own `UnaryOp(USub, ..)` shape for a negative number) tags")
    w("  `seq-slice-negative` instead; a negative bound reached through a")
    w("  variable or an expression (`s[:n-1]`) is not recognized this way")
    w("  and reads as the plain (non-negative) burden, an undercount of")
    w("  the two gaps in the same direction every other syntactic detector")
    w("  here accepts;")
    w("- `unbounded-loop` fires on EVERY `break` and `continue`, not only")
    w("  the ones outside coverage_census.py's tail-position exception")
    w("  (LIFTER-DECISIONS.md row 23: a break whose loop is the tail of the")
    w("  function, with a straight-line continuation, lifts to a return);")
    w("  replicating that exception needs the same control-flow reach")
    w("  coverage_census.py's `_break_as_return` scanner has, which this")
    w("  file does not build, so `unbounded-loop` OVER-counts relative to")
    w("  that finer rule;")
    w("- `tuple` and `tuple-pair` (SPEC.md's 'Pairs (v1)' split, landed")
    w("  2026-09-10) fire on EVERY `ast.Tuple` node found anywhere in the")
    w("  solution, built, returned, passed, compared, or the target or")
    w("  value of an unpacking assignment: exactly two elements, neither a")
    w("  nested tuple nor syntactically a string, is `tuple-pair`; three")
    w("  or more elements, a nested tuple, or a string element is `tuple`")
    w("  (a list of tuples is the separate gap `nested-seq`, tagged where")
    w("  a list literal's own elements are inspected); a parallel")
    w("  assignment whose right-hand side is a tuple literal of the same")
    w("  length as its target (`a, b = b, a`, `a, b = 1, 2`) is excluded")
    w("  from both, the same exception the detector has always made,")
    w("  since t writes it as two plain assignments, no pair value ever")
    w("  built; neither check resolves a bare variable's element type, so")
    w("  a tuple carrying a string held in a variable, not a literal, is")
    w("  undercounted into `tuple-pair` here. MBPP's channel is different:")
    w("  `mbpp_dfy.parse_assertion`'s own refusal for a tuple argument or")
    w("  expected value names no arity (`_Unsupported(\"tuple\")` whatever")
    w("  the tuple's shape), so this file re-parses that SAME assert line")
    w("  a second time with its own `ast` (`_mbpp_assert_tuple_kind`,")
    w("  mbpp_dfy.py untouched) to recover the literal tuple and apply the")
    w("  same pair/arity rule; an assert whose shape that second parse")
    w("  cannot read (not a plain `f(...) == expected`, or no literal")
    w("  tuple on the named side) falls back to the gap `tuple`, not the")
    w("  burden, the same conservative default the io-types side takes")
    w("  elsewhere in this file. HumanEval's typed `Tuple[T1, T2]`")
    w("  annotation takes the exact recursive read instead: two")
    w("  components, each itself annotated with no gap or burden of its")
    w("  own, is `tuple-pair`; anything else is `tuple`; a `Tuple[..]`")
    w("  RETURN annotation is `multi-return` regardless, unchanged from")
    w("  before the split, since a tuple-typed return means several")
    w("  return values, not a tuple-shaped value in the data;")
    w("- `recursion` and `multi-return` are read off the entry-point")
    w("  function specifically for a function-shaped problem (matching it")
    w("  by name), and off any self-recursive top-level `def` for a")
    w("  stdin-shaped one, where there is no single entry point;")
    w("- `io` is tagged for `print`/`input` only in a function-shaped")
    w("  solution; a stdin-shaped solution's I/O calls are the shape, not a")
    w("  separate gap, so they are never tagged there;")
    w("- Python's own `int` is unbounded, like t's, so no `bigint` detector")
    w("  exists and no problem is ever blocked on integer width;")
    w("- an f-string, `.format()`, and every string method in a fixed list")
    w("  (`STRING_METHODS` in nl_census.py) all tag the single `string-lib`")
    w("  gap rather than each having a name of their own, since all three")
    w("  need the Python string LIBRARY, not just the seq-of-code-points")
    w("  model SPEC.md's v1 covers; a bare str/f-string/char literal, by")
    w("  contrast, tags only the burden `string-as-seq`;")
    w("- `count` is in `STRING_METHODS` even though `list.count(..)` uses")
    w("  the same attribute name; a solution counting occurrences in a")
    w("  list, not a string, is over-counted into `string-lib` here, the")
    w("  same name-only approximation `.sort` already accepts elsewhere;")
    w("- `ord`/`chr` calls tag `string-as-seq` (a burden: t already has")
    w("  the code point, this is only the name Python gives it);")
    w("- `str(..)` is tagged `string-lib` unconditionally, the same")
    w("  treatment `float(..)` already gets; `int(..)` is tagged only when")
    w("  called with an explicit base (`int(x, 16)`), unambiguous string")
    w("  parsing -- a bare `int(x)` is NOT tagged even when x is a string,")
    w("  since the common `int(input())` idiom would otherwise swamp")
    w("  `string-lib` on nearly every stdin-shaped solution with input-")
    w("  parsing boilerplate a signature-extraction step would remove, not")
    w("  the algorithmic core; this undercounts genuine string-to-int")
    w("  parsing written without a base argument;")
    w("- `sorted(..)` always tags the `sort` burden, and additionally tags")
    w("  `string-lib` only when its argument is SYNTACTICALLY a string (a")
    w("  literal, an f-string, a `str(..)` call, or a chained string-")
    w("  method call) -- `sorted(a_variable)` is not resolved to a type")
    w("  and is undercounted when the variable holds a string;")
    w("- iterating over a string, and `in` on a string, are not detected")
    w("  as their own AST shape (both look identical to the same")
    w("  operation on a list without type inference); a solution doing")
    w("  only this and nothing else stringy is invisible to")
    w("  `string-as-seq`, an undercount left as-is rather than built out;")
    w("- a `SyntaxError` on `ast.parse` (most often Python 2: a `print`")
    w("  statement, `raw_input`, an octal literal) is recorded as the")
    w("  `py2-unparseable` burden and stops solution-construct detection")
    w("  for that problem; its io-types are still measured from the tests")
    w("  or samples, which do not require parsing Python.")
    w("")
    w("Every problem's full tag set, including MBPP's raw parse_assertion")
    w("refusals and the split each record came from, is in the JSON beside")
    w("this report when `--json` is given, so any row can be checked")
    w("against the source it came from.")
    w("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None, help="write the markdown report here")
    ap.add_argument("--json", default=None, help="write one JSON record per problem here")
    ap.add_argument("--limit", type=int, default=None,
                     help="cap records read per split (development only)")
    a = ap.parse_args()

    import time
    t0 = time.time()

    programs: list[dict] = []
    programs += process_mbpp(a.limit)
    programs += process_humaneval(a.limit)
    programs += process_apps(a.limit)
    programs += process_codecontests(a.limit)

    elapsed = time.time() - t0
    text = render(programs, elapsed)

    if a.out:
        out = Path(a.out).expanduser()
        out.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {out}")
    else:
        print(text)

    if a.json:
        jpath = Path(a.json).expanduser()
        jpath.parent.mkdir(parents=True, exist_ok=True)
        jpath.write_text(json.dumps(programs, indent=1), encoding="utf-8", newline="\n")
        print(f"wrote {jpath}")

    print(f"{len(programs)} problems in {elapsed:.1f}s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
