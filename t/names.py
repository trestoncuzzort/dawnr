"""t/names.py: one sanitizing pass, shared by every lowering.

ROADMAP 13.2 "Names": "A lowering may refuse what it cannot express; it
may not refuse a name it can rename." Before this file, only three of the
seven lowerings (fstar, rocq, spark) carried a RESERVED set at all, and
only fstar actually renamed a collision away (`_rename_reserved`, added
2026-09-10 for the v1pairs fuzz family's `val` locals); the other three
kernels (dafny, verus, framac) and the fourth un-checking one (lean) simply
emitted the task's own identifier verbatim, so a param or local spelled
like one of THEIR keywords (`function`, `fn`, `match`, ...) produced source
that the kernel's own compiler/checker refuses to parse -- an unlabelled
ABSTAIN with no `_ck`-style message naming the cause. 2026-09-11: this file
generalizes fstar's `_rename_reserved` (same rename mechanism, same
`t_`-prefix-then-numeric-suffix collision rule, same structural,
shape-matched rewrite -- never a blind string substitution, because an op
tag such as `{"op": "and"}` can legitimately spell a reserved word too)
into one kernel-independent pass, `sanitize(task, reserved, uppercase_ok)`,
and gives every lowering its own populated `KEYWORDS[kernel]` entry to
call it with.

MEASURED 2026-09-11 (see test_names.py and the dated notes in each
lower_*.py `lower()`): every one of the 26 tasks committed under
t/tasks/*.json before this file lowers BYTE-IDENTICAL through the wired-in
`sanitize()` call as it did before, in all seven lowerings (`python3
test_names.py`, `test_old_tasks_byte_identical`) -- none of their
identifiers collides with any kernel's KEYWORDS entry, so `sanitize`
returns `(task, {})`/`(body, {})` unchanged (`is`, not merely `==`) on
every one, exactly the identity guarantee `_rename_reserved` already gave
fstar alone.

MEASURED 2026-09-11 (ROADMAP 13.2's own DONE WHEN): eight probe tasks
(t/tasks/probe_names_{dafny,verus,spark,framac,lean,rocq,fstar,upper}.json
-- one per kernel's reserved words, plus one uppercase-initial task),
graded with `python3 t/grade.py --tasks <dir-holding-only-the-eight>
--flake 3 --out <out>` from the repo root, read FULL AGREEMENT: every one
of the 8 x 7 = 56 cells `verified / refuted`, not merely the task's own
matching kernel column -- see `<out>/table.md`. Getting there also fixed
two pre-existing gaps this wave's own dated notes name in place: F*'s
RESERVED set was missing the two bare built-in type names `int`/`bool`
(lower_fstar.py, `int` param shadowing the type `int` for a LATER
parameter's own `: int` annotation -- probe_names_framac), and Lean's
KEYWORDS entry (below) was missing `forall`/`exists` (probe_names_rocq's
`forall` param). A certificate that declares its own fresh locals spelled
after the witness's own keys (lower_framac.py's `int {n} = ...;`,
lower_rocq.py's `set`/`pose`) needs those locals RENAMED to match the rest
of the file, not left at the witness's original, possibly keyword-
colliding spelling -- see `remap_witness`'s own docstring for the fix and
what it replaced (a second, un-renamed Ctx/Lower, which was actively wrong
for exactly this certificate shape, not merely unnecessary).

WHAT IS RENAMED: every user identifier -- task name, param names, return
names, spec_fun names and their own param names, a local `var`
declaration's name, a quantifier's (`forall`/`exists`) bound `var` -- that
either collides with the kernel's reserved-word set (`reserved`, matched
case-INsensitively: SPARK's own collision check is case-insensitive since
its `cap()` capitalizes every t name into Ada's case-insensitive
namespace, and matching case-insensitively everywhere else only ever
renames a name that needed no rename at all under a case-SENSITIVE check,
which SPEC.md's "be generous, a rename costs nothing" already blesses) or,
when `uppercase_ok` is False, starts with anything but a lowercase letter.

WHAT IS NOT RENAMED: an op tag (`{"op": "and"}`), a type tag, a fuzz-
harness label (`_shape`/`_family`/`_twin_op`), or anything else that is
not one of the six declaration/use shapes above -- see `_rename_walk`'s
own docstring for why a blind string substitution over `_collect_names`'s
"every string might be a name" superset would be wrong here even though
that same superset is exactly right for the FRESHNESS check `sanitize`
needs (a false positive there only wastes a candidate spelling; a false
positive in the rewrite corrupts an unrelated tag).

THE RENAME MAP: `sanitize` returns it (`old -> new`, only the entries that
actually fired) so a caller can record it in the emitted source as a
comment line, `t renames: a -> t_a, ...`, keeping a graded table readable
against the source even when the identifier on the page is not the one in
t/tasks/*.json.
"""

# --------------------------------------------------------------- KEYWORDS --
# Generous on purpose (SPEC.md, and the ROADMAP 13.2 bar quoted above): a
# name in here that a task never uses costs nothing, so each set below
# errs toward "every reserved word documented for the language/dialect
# the kernel actually parses", not the minimal set needed to pass today's
# committed tasks.

KEYWORDS: dict[str, frozenset[str]] = {
    # Dafny 4.x reference manual, "Reserved Words".
    "dafny": frozenset({
        "abstract", "allocated", "as", "assert", "assume", "bool", "break",
        "by", "calc", "case", "char", "class", "codatatype", "colemma",
        "const", "constructor", "continue", "datatype", "decreases",
        "default", "else", "ensures", "exists", "export", "extends",
        "export", "false", "for", "forall", "fresh", "function", "ghost",
        "if", "imap", "import", "in", "include", "int", "invariant",
        "is", "iset", "iterator", "label", "lemma", "map", "match",
        "method", "modifies", "modify", "module", "multiset", "nameonly",
        "nat", "new", "newtype", "null", "object", "old", "opaque",
        "opened", "ORDINAL", "predicate", "print", "provides", "reads",
        "real", "refines", "requires", "return", "returns", "reveal",
        "seq", "set", "static", "string", "then", "this", "trait", "true",
        "twostate", "type", "unchanged", "var", "where", "while", "witness",
        "yield", "yields",
    }),
    # Verus (verus! macro, Rust keywords Verus turns into DSL syntax) plus
    # Rust's own reserved words, since generated code is still a Rust
    # source file the rustc frontend parses.
    "verus": frozenset({
        "as", "assert", "assume", "async", "await", "become", "box",
        "break", "broadcast", "by", "calc", "checked", "closed", "const",
        "continue", "crate", "decreases", "do", "dyn", "else", "ensures",
        "enum", "exec", "exists", "extern", "false", "final", "fn", "for",
        "forall", "ghost", "has", "if", "impl", "implies", "in", "int",
        "invariant", "is", "let", "loop", "macro", "match", "mod", "move",
        "mut", "nat", "open", "opens_invariants", "override", "priv",
        "proof", "pub", "ref", "requires", "return", "self", "Self",
        "spec", "static", "struct", "super", "tracked", "trait", "true",
        "try", "type", "typeof", "unsafe", "use", "via", "virtual", "when",
        "where", "while", "yeet", "yield",
    }),
    # GNAT/SPARK reference manual, Ada 2012 reserved words -- checked
    # case-insensitively by `sanitize` (see the module docstring), so the
    # lowercase spellings below already cover every capitalization
    # lower_spark.cap() can produce.
    "spark": frozenset({
        "abort", "abs", "abstract", "accept", "access", "aliased", "all",
        "and", "array", "at", "begin", "body", "case", "constant",
        "declare", "delay", "delta", "digits", "do", "else", "elsif",
        "end", "entry", "exception", "exit", "for", "function", "generic",
        "goto", "if", "in", "interface", "is", "limited", "loop", "mod",
        "new", "not", "null", "of", "or", "others", "out", "overriding",
        "package", "parallel", "pragma", "private", "procedure",
        "protected", "raise", "range", "record", "rem", "renames",
        "requeue", "return", "reverse", "select", "separate", "some",
        "subtype", "synchronized", "tagged", "task", "terminate", "then",
        "type", "until", "use", "when", "while", "with", "xor",
    }),
    # ACSL (Frama-C's spec language) keywords plus the ISO C keywords the
    # generated function body is written in -- a name reserved in either
    # language can break the emitted `.c` file.
    "framac": frozenset({
        "assert", "assigns", "assumes", "axiom", "axiomatic", "behavior",
        "behaviors", "boolean", "break", "case", "char", "complete",
        "const", "continue", "decreases", "default", "disjoint", "do",
        "double", "else", "ensures", "enum", "exits", "extern", "false",
        "float", "for", "forall", "frees", "global", "goto", "if",
        "inductive", "int", "integer", "invariant", "logic", "long",
        "loop", "lemma", "predicate", "reads", "real", "register",
        "requires", "return", "short", "signed", "sizeof", "static",
        "struct", "switch", "terminates", "true", "type", "typedef",
        "union", "unsigned", "variant", "void", "volatile", "while",
        "wrt",
    }),
    # Lean 4 reserved keywords/tokens (documented reference + tactic
    # names this file's prelude relies on, `grind` included since it is
    # the tactic every generated proof calls).
    "lean": frozenset({
        "abbrev", "at", "axiom", "by", "calc", "class", "def", "deriving",
        "do", "else", "end", "example", "exists", "extends", "for",
        "forall", "from", "fun", "have", "hiding", "if", "import", "in",
        "inductive", "infix", "infixl", "infixr", "instance", "into",
        "irreducible", "lemma", "let", "macro", "match", "mut", "mutual",
        "namespace", "nomatch", "notation", "obtain", "omega", "open",
        "opaque", "partial", "postfix", "prefix", "prelude", "private",
        "protected", "rec", "renaming", "section", "set_option", "show",
        "simp", "structure", "suffices", "syntax", "term", "then",
        "theorem", "this", "trans", "try", "unif_hint", "universe",
        "unsafe", "variable", "variables", "where", "with", "grind",
        # the bare type and structure names every emitted signature uses;
        # a parameter named `Int` shadowed the type in the same signature
        # (found 2026-09-11 by the names probe check, the same class of
        # gap fstar's RESERVED had for int/bool)
        "Int", "Nat", "Bool", "String", "List", "Array", "Prop", "Type",
        "Sort", "Unit", "Option", "true", "false",
    }),
    # lower_rocq.RESERVED's own language keywords (Rocq/Coq vernacular and
    # term syntax) -- the lowering's OWN namespace collisions (sf_/t_/
    # _len prefixes/suffixes, `fuel`/`fu`/`s_len`/`rflag`/`rf` helper
    # names) stay lower_rocq._ck's job, unaffected by this shared set;
    # see lower_rocq.py's own dated note at its `lower()` call site.
    "rocq": frozenset({
        "at", "in", "fun", "if", "then", "else", "let", "forall", "exists",
        "match", "with", "end", "fix", "Prop", "Set", "Type", "as", "cofix",
        "for", "return", "struct", "wf", "measure", "Fixpoint", "Definition",
        "Lemma", "Theorem", "Proof", "Qed", "Inductive", "Record", "mod",
    }),
    # lower_fstar.RESERVED verbatim (F* syntax keywords, plus the two
    # bare built-in type names `int`/`bool` -- see that set's own dated
    # note). lower_fstar.py actually sanitizes against its own module-
    # level `RESERVED` directly (`_rename_reserved_map`), not through this
    # entry; kept here, matched, only so a reader of this table sees
    # fstar's true reserved set in one place with the other six.
    "fstar": frozenset({
        "abstract", "admit", "and", "assert", "assume", "attributes",
        "begin", "by", "calc", "class", "decreases", "default", "effect",
        "eliminate", "else", "end", "ensures", "exception", "exists",
        "false", "forall", "friend", "fun", "function", "if", "in",
        "include", "inline", "instance", "introduce", "irreducible",
        "let", "logic", "magic", "match", "module", "new", "noeq", "not",
        "of", "open", "opaque", "private", "rec", "requires", "returns",
        "then", "total", "true", "try", "type", "unfold", "unfoldable",
        "val", "when", "with", "int", "bool",
    }),
}


# ------------------------------------------------------------- the walker --

def _collect_names(obj) -> set[str]:
    """Every string anywhere in the task/body JSON, a superset of every
    identifier in scope, so a name absent from it is fresh everywhere.
    Ported verbatim from lower_fstar._collect_names."""
    out: set[str] = set()
    if isinstance(obj, dict):
        for v in obj.values():
            out |= _collect_names(v)
    elif isinstance(obj, list):
        for v in obj:
            out |= _collect_names(v)
    elif isinstance(obj, str):
        out.add(obj)
    return out


def _declared_in(node) -> set[str]:
    """Every LOCAL `var` declaration's name and quantifier bound `var`
    inside an expression/statement tree. Ported from
    lower_fstar._declared_in."""
    out: set[str] = set()
    if isinstance(node, dict):
        v = node.get("var")
        if isinstance(v, dict) and "name" in v:
            out.add(v["name"])
        for kind in ("forall", "exists"):
            q = node.get(kind)
            if isinstance(q, dict) and "var" in q:
                out.add(q["var"])
        for val in node.values():
            out |= _declared_in(val)
    elif isinstance(node, list):
        for val in node:
            out |= _declared_in(val)
    return out


def _declared_names(task: dict, body: list, check_task_name: bool = True) -> set[str]:
    """Every identifier declared anywhere in `task` or `body` (task name,
    params, returns, spec_funs and their params, every local `var`, every
    quantifier's bound `var`). `check_task_name=False` omits the task's OWN
    top-level name (only its params/returns/locals/spec_funs are checked):
    lower_spark.py's package name is always `T_{cap(name)}`, never the bare
    name itself, so a task named e.g. `abs` (colliding with Ada's `abs`
    reserved word, RESERVED, only because the raw t identifier happens to
    spell it) needs no rename there -- the name never reaches the emitted
    Ada source unprefixed. Every other kernel renders the task's own name
    as (or into) a real identifier of its own (a Verus `proof fn {name}`,
    an F* `let {name}`, ...) and keeps the default."""
    declared: set[str] = {task["name"]} if check_task_name else set()
    for p in task["params"]:
        declared.add(p["name"])
    for r in task["returns"]:
        declared.add(r["name"])
    for sf in task.get("spec_funs", []):
        declared.add(sf["name"])
        for p in sf["params"]:
            declared.add(p["name"])
        declared |= _declared_in(sf["body"])
        if "decreases" in sf:
            declared |= _declared_in(sf["decreases"])
    declared |= _declared_in(task.get("requires", []))
    declared |= _declared_in(task.get("ensures", []))
    if "decreases" in task:
        declared |= _declared_in(task["decreases"])
    declared |= _declared_in(body)
    return declared


def _rename_walk(node, mapping: dict[str, str]):
    """`node` with every identifier `mapping` renames substituted at
    exactly the six shapes a declaration or a use of a name can take: a
    `{"var": ...}` reference or declaration, an `assign`/`return`
    statement's target, a `call`'s `fun`, a `forall`/`exists`'s bound
    `var`. A STRUCTURAL rewrite (matched by JSON shape), never a blind
    string substitution: `{"op": "and"}`/`{"op": "not"}` are ordinary t op
    tags that happen to spell a reserved word on plenty of kernels, and a
    blind rewrite would corrupt them into a dead op no lowering can
    dispatch. Ported from lower_fstar._rename_walk."""
    if isinstance(node, list):
        return [_rename_walk(v, mapping) for v in node]
    if not isinstance(node, dict):
        return node
    if "var" in node:
        v = node["var"]
        if isinstance(v, dict):
            new_v = dict(v)
            new_v["name"] = mapping.get(v["name"], v["name"])
            if "init" in new_v:
                new_v["init"] = _rename_walk(new_v["init"], mapping)
            return {**node, "var": new_v}
        return {**node, "var": mapping.get(v, v)}
    if "assign" in node:
        tgt, expr = node["assign"]
        return {**node, "assign": [mapping.get(tgt, tgt),
                                   _rename_walk(expr, mapping)]}
    if "return" in node:
        tgt, expr = node["return"]
        return {**node, "return": [mapping.get(tgt, tgt),
                                   _rename_walk(expr, mapping)]}
    if "forall" in node or "exists" in node:
        kind = "forall" if "forall" in node else "exists"
        q = dict(node[kind])
        q["var"] = mapping.get(q["var"], q["var"])
        for k in ("lo", "hi", "body"):
            if k in q:
                q[k] = _rename_walk(q[k], mapping)
        return {**node, kind: q}
    if "call" in node:
        c = dict(node["call"])
        c["fun"] = mapping.get(c["fun"], c["fun"])
        if "args" in c:
            c["args"] = _rename_walk(c["args"], mapping)
        return {**node, "call": c}
    return {k: _rename_walk(v, mapping) for k, v in node.items()}


def sanitize(task: dict, reserved: set[str], uppercase_ok: bool,
             prefix: str = "t_",
             check_task_name: bool = True) -> tuple[dict, dict[str, str]]:
    """(task2, renames): `task` with every user identifier that collides
    with `reserved` (matched case-insensitively -- see the module
    docstring) or, when `uppercase_ok` is False, starts with anything but
    a lowercase letter, replaced by a fresh `prefix`-spelling, checked
    against every string already in `task` (so a rename can never shadow
    an existing name) with a numeric suffix on a further collision. `task`
    itself is returned unchanged (`is`, not a copy) when nothing needs a
    rename, so `sanitize(task, ...) is task` holds for every task with no
    colliding identifier -- every previously-committed task, for every
    kernel's KEYWORDS entry, since none of the 26 collides.

    `task["body"]` is renamed in place (the returned task carries its own
    renamed `body`); callers pass `task["body"]` again as `body` only
    because `lower()`'s signature already takes body separately (a real
    body or a twin's mutated one) -- `task2["body"]` and the returned body
    are consistent because both come from the SAME mapping.

    Callers that need only the rename map without re-deriving `task2`'s
    body separately should read `task2["body"]`; a second positional
    return is not needed."""
    reserved_lc = {r.lower() for r in reserved}

    def needs_rename(name: str) -> bool:
        if name.lower() in reserved_lc:
            return True
        if not uppercase_ok and not (name[:1].islower()):
            return True
        return False

    body = task.get("body", [])
    bad = sorted(n for n in _declared_names(task, body, check_task_name)
                if needs_rename(n))
    if not bad:
        return task, {}

    used = _collect_names(task)
    mapping: dict[str, str] = {}
    for n in bad:
        cand = f"{prefix}{n}"
        if cand in used or cand in mapping.values():
            k = 1
            while f"{cand}{k}" in used or f"{cand}{k}" in mapping.values():
                k += 1
            cand = f"{cand}{k}"
        mapping[n] = cand
        used.add(cand)

    def rn(n: str) -> str:
        return mapping.get(n, n)

    new_task = dict(task)
    new_task["name"] = rn(task["name"])
    new_task["params"] = [{**p, "name": rn(p["name"])} for p in task["params"]]
    new_task["returns"] = [{**r, "name": rn(r["name"])} for r in task["returns"]]
    new_task["spec_funs"] = [
        {**sf, "name": rn(sf["name"]),
         "params": [{**p, "name": rn(p["name"])} for p in sf["params"]],
         "body": _rename_walk(sf["body"], mapping),
         **({"decreases": _rename_walk(sf["decreases"], mapping)}
            if "decreases" in sf else {})}
        for sf in task.get("spec_funs", [])]
    new_task["requires"] = _rename_walk(task.get("requires", []), mapping)
    new_task["ensures"] = _rename_walk(task.get("ensures", []), mapping)
    if "decreases" in task:
        new_task["decreases"] = _rename_walk(task["decreases"], mapping)
    new_task["body"] = _rename_walk(body, mapping)
    return new_task, mapping


def rename_body(body: list, mapping: dict[str, str]) -> list:
    """A twin body (harness's mutated copy of `task["body"]`) renamed under
    the SAME mapping `sanitize` produced for the task, so `lower()` keeps
    the real task and the twin body as two objects. Added 2026-09-11 after
    the wave A matrix gate: the first wiring replaced the task's body with
    the twin body before sanitizing, so every lowering that tells a twin
    from the real by comparing the two (the invariant-drop certificate,
    which evaluates the dropped invariant at the exit witness) saw no
    difference and emitted no certificate: 13 loop tasks read twin
    unproved in dafny and verus and timeout in framac. Identity is kept
    when nothing renames (`body` itself is returned)."""
    return _rename_walk(body, mapping) if mapping else body


def remap_witness(witness: dict | None, mapping: dict[str, str]) -> dict | None:
    """The twin witness `w` (harness.twin_cached's own dict: param/local
    names as keys, plus underscore-prefixed metadata keys `_kind`/`_real`/
    `_twin`/`_ens`/...) with every non-metadata key renamed the same way
    `mapping` renamed the task -- so a lowering's certificate builder can
    be called on the SAME sanitized task/body it already rendered the
    rest of the source from, instead of a second, un-renamed one.

    MEASURED 2026-09-11 (probe_names_framac): the alternative -- building
    the certificate against the un-renamed task/witness while the rest of
    the file uses the renamed one -- is actively WRONG for a lowering
    whose certificate declares fresh LOCALS spelled after the witness's
    own keys (lower_framac.py's `int int = 0;` for a param literally
    named `int`), not merely a lowering whose certificate fully
    substitutes ground values into a formula with no leftover identifier
    (lower_dafny.py/lower_rocq.py/lower_fstar.py's `subst`/`specialize`):
    the FIRST kind needs the RENAMED spelling in its own declarations,
    the SECOND kind never renders the name as an identifier at all so
    renaming its keys costs nothing either way. Remapping the witness and
    always building the certificate from the single, already-sanitized
    task is correct for both kinds, at the cost of never needing a second
    Ctx/Lower/env at all."""
    if not witness or not mapping:
        return witness
    return {(mapping[k] if k in mapping else k): v for k, v in witness.items()}


def rename_comment(mapping: dict[str, str]) -> str:
    """`t renames: a -> t_a, b -> t_b` (or `""` when `mapping` is empty),
    the plain-text record `lower()` puts in the emitted source, wrapped in
    whatever comment syntax the target language uses, so a graded table
    can still be read against t/tasks/*.json even when the identifier on
    the page is not the task's own. Each lowering wraps this text in its
    own comment token (`// `, `-- `, `(* ... *)`) rather than this
    function choosing one, since no single token is a comment in all
    seven target languages."""
    if not mapping:
        return ""
    body = ", ".join(f"{old} -> {new}" for old, new in sorted(mapping.items()))
    return f"t renames: {body}"
