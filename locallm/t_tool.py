"""t_tool.py: dawnr's first tool, the t interpreter, called by the model on its own draft.

nanochat's engine (https://github.com/karpathy/nanochat, nanochat/engine.py)
lets the model write <|python_start|> expr <|python_end|>, evaluates the
expression with a restricted eval under a 3-second alarm, and forces the
result back into the stream between <|output_start|> and <|output_end|>.
dawnr's tool is the fastest part of the proof engine instead: the draft t
program is parsed (t/surface.py), type checked (the same check_wf the RL
reward and the grader use), and run in t's interpreter (t/interp.py) on every
`Example:` line the user gave, and the tool answers with the verdicts. It is
the standard library only, runs in-process, and needs no alarm: the
interpreter has its own step budget (interp.Budget).

What the tool answers, one line each, stopping at the first failure:

    parses: yes | parses: no: <why>
    well formed: yes | well formed: no: <why>
    specification: spec changed: <why>            (only when the prompt gave one, and only on a change)
    example 1: pass | example 1: fail: got 5, expected 6 | example 1: <verdict>: <why>

Values compare as JSON (true is not 1), the way the grader keeps int and bool
apart (interp._tv).

examples_from_program() computes Example lines from a PROVED program: inputs
from the interpreter's own ladders over the task's literals (interp.domain),
kept where the task's `requires` holds, and the program's output on them.
Seven kernels proved that program meets its specification, so each line is a
true statement about the specification, not a guess.

FINDINGS-repair-2026-09-26.md ("The t tool has a hole on specification
prompts"): 101 of 285 fold drafts that passed every example were not the
proved program because they had changed the specification the user gave (the
declaration, requires or ensures) -- `run()` only executes the body and
compares the result to the example's value; `requires` is evaluated only to
decide whether an example is excluded, and `ensures` is never evaluated at
all, so a draft that narrows `requires` past what the (typically one or two)
given examples exercise, or drops or reweakens an `ensures` conjunct, can
satisfy every example while promising less than what was asked. Clover (Sun
et al., "Clover: Closed-Loop Verifiable Code Generation", arXiv:2310.17807)
names exactly this triangle -- code, formal specification and informal
description must agree, not just code and tests -- and checks it by
re-deriving each from the others and comparing; t has no natural-language
description to re-derive from, so `spec_changed` below instead compares the
draft's declaration/requires/ensures/spec funs against the specification
already given in the prompt (`spec_header_from_context`), directly, by
normalized (alpha-equivalent, clause-order-independent) AST equality. `call`
runs this before the examples, exactly where that finding said it belonged,
and on a change it reports "specification: spec changed: <why>" and does not
run the examples: they would be measuring the wrong task. It is silent (adds
no line) when the context carries nothing to compare against ("Problem:"
prompts, plain chat) or when the specification is unchanged, so every
existing caller that never had a formal specification in its context sees
byte-identical output.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

T = Path(__file__).resolve().parents[1] / "t"
if str(T) not in sys.path:
    sys.path.insert(0, str(T))

EXAMPLE = re.compile(r"^Example:\s*([A-Za-z_][A-Za-z0-9_]*)\((.*)\)\s*==\s*(.+?)\s*$", re.M)
MAX_WHY = 160
RUNNABLE_TYPES = ("int", "bool", "seq")

# a bare `t 0`/`t 1` line, exactly what a printed t program starts with
# (surface.print_task's first line) and what checker.find_programs' T_HEAD
# also matches; used here to read a specification back out of a prompt, not
# to find a whole program (see spec_header_from_context).
_T_HEAD_LINE = re.compile(r"^t[ \t]+\d+[ \t]*$", re.M)
_EMPTY_BODY = "\n{\n}\n"


def _short(text: str) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= MAX_WHY else text[:MAX_WHY - 3] + "..."


def parse_examples(text: str) -> list[dict]:
    """Every `Example: f(a, b) == v` line in text, as {"fn", "args", "expected", "line"}.
    A line whose values are not JSON is kept with "error", so the tool can say so."""
    out = []
    for m in EXAMPLE.finditer(text or ""):
        row = {"fn": m.group(1), "line": m.group(0).strip()}
        try:
            row["args"] = json.loads("[" + m.group(2) + "]")
            row["expected"] = json.loads(m.group(3))
        except ValueError as e:
            row["error"] = f"not JSON: {e}"
        out.append(row)
    return out


def _value(ty: str, v):
    """A JSON value as the interpreter holds a value of t type `ty` (a seq is a tuple, rows too)."""
    if ty == "seq":
        if isinstance(v, str):
            return tuple(ord(c) for c in v)
        if not isinstance(v, list):
            raise TypeError(f"expected a list for a seq, got {json.dumps(v)}")
        return tuple(_value("seq", x) if isinstance(x, (list, str)) else x for x in v)
    if ty == "bool":
        if not isinstance(v, bool):
            raise TypeError(f"expected a bool, got {json.dumps(v)}")
        return v
    if ty == "int":
        if isinstance(v, bool) or not isinstance(v, int):
            raise TypeError(f"expected an int, got {json.dumps(v)}")
        return v
    raise TypeError(f"the tool cannot pass a {ty} argument")


def run(task: dict, args: list) -> dict:
    """Run a parsed task on positional interpreter values: {"verdict": ok|requires-excluded|
    undefined|budget|crash, "got": <JSON value>}."""
    import interp
    params = task["params"]
    if len(args) != len(params):
        return {"verdict": "arity", "why": f"{len(args)} arguments for {len(params)} parameters"}
    env = {p["name"]: a for p, a in zip(params, args)}
    ret = task["returns"][0]["name"]
    funs = interp.funs_of(task, task["body"])
    st = interp.St()
    try:
        if not all(interp.ev(c, env, funs, st) for c in task.get("requires", [])):
            return {"verdict": "requires-excluded"}
        env2 = dict(env)
        env2[ret] = None
        interp.exec_body(task["body"], env2, funs, st)
    except interp.Undef as u:
        return {"verdict": "undefined", "why": _short(u)}
    except (interp.Budget, RecursionError) as b:
        return {"verdict": "budget", "why": _short(b)}
    except (TypeError, ValueError, KeyError, IndexError, AttributeError) as c:
        return {"verdict": "crash", "why": _short(f"{type(c).__name__}: {c}")}
    if env2[ret] is None:
        return {"verdict": "undefined", "why": "no path assigned the return"}
    return {"verdict": "ok", "got": interp._j(env2[ret])}


def check(program: str) -> tuple[dict | None, list[str]]:
    """Parse and type check a draft; return (task or None, the tool's lines so far)."""
    import surface
    import fuzz_lower
    try:
        task = surface.parse(program)
    except Exception as e:                                       # noqa: BLE001  (any parse failure is the answer)
        return None, [f"parses: no: {_short(f'{type(e).__name__}: {e}')}"]
    try:
        errs = fuzz_lower.check_wf(task)
    except Exception as e:                                       # noqa: BLE001
        errs = [f"check_wf raised {type(e).__name__}: {e}"]
    if errs:
        return None, ["parses: yes", f"well formed: no: {_short('; '.join(errs))}"]
    return task, ["parses: yes", "well formed: yes"]


# ------------------------------------------- specification preservation --
#
# Whether a draft kept the specification the prompt gave it: the task's own
# declaration (arity, each parameter's type, the return type), its
# `requires`, its `ensures`, and any `spec_funs` -- everything
# chat_data.spec_text prints, i.e. everything the prompt showed the model of
# the task except its body -- compared by normalized AST equality: the same
# up to one consistent renaming of the task's own name, its parameters, its
# return, each spec fun's own parameters and every quantifier's bound
# variable (a t quantifier's bound variable is fresh and scoped to its own
# body, SYNTAX.md's "Quantifiers", so shadowing never has to be considered),
# and up to reordering the requires list and, separately, the ensures list
# (each is a set of conditions, not a sequence). Lemmas and methods (SPEC.md
# v1) are refused rather than compared: never seen in a "spec" prompt across
# the 358-document corpus or the repair run's 281 (checked 2026-09-27), and
# a lemma's or method's body is a statement block, not the pure expression
# _alpha_eq below knows how to walk.

def spec_header_from_context(context: str) -> str | None:
    """The specification header a "spec" prompt embeds (chat_data.SPEC_PROMPT
    followed by chat_data.spec_text's printed declaration/requires/ensures/
    spec-funs, with no body) read back out of `context`: from the first line
    that looks like a t program's own first line (`_T_HEAD_LINE` -- the
    *first* one, since the prompt always states the specification before any
    draft appears anywhere later in the conversation) up to the following
    `Example:` line, which always comes right after it in a built
    conversation (chat_data.conversation), or to the end of `context` when
    none follows. None when `context` carries no such line at all: a
    "Problem:" prompt states no formal specification, and plain chat may
    carry no t program either; callers must read None as "nothing to
    compare", never as a difference to report."""
    m = _T_HEAD_LINE.search(context or "")
    if not m:
        return None
    rest = context[m.start():]
    end = rest.find("\nExample:")
    return rest if end < 0 else rest[:end]


def parse_spec_header(header: str) -> dict | None:
    """The task `header` (as spec_header_from_context returns it, ending
    where a body would begin) describes, parsed by appending back exactly
    the empty body chat_data.spec_text cut off -- the same trivial body
    every prompt's real answer replaces -- so it reads through the one
    parser (surface.parse) everything else here does. None on anything that
    does not parse: an honest "cannot compare", not a crash and not a claim
    of a difference `spec_changed` cannot support."""
    import surface
    try:
        return surface.parse(header + _EMPTY_BODY)
    except Exception:                                              # noqa: BLE001  (unparseable is "nothing to compare")
        return None


def _alpha_eq(a, b, env: dict[str, str]) -> bool:
    """`a` and `b` (t expression JSON, SYNTAX.md's Expr) are equal up to the
    bijection `env` (a name on `a`'s side -> the name that stands for it on
    `b`'s side), already fixed by the caller for the names in scope where
    `a`/`b` sit (a task's own name, its parameters, its return, a spec fun's
    own parameters) and extended here, immutably, for a `forall`/`exists`'s
    own bound variable.

    The shapes checked are exactly t/names.py's own inventory of every place
    a *pure expression* can bind or use a name (`_rename_walk`,
    `_declared_in`): a `{"var": ...}` reference, a `forall`/`exists` binder,
    a `call`'s `fun`, a `lemma`'s `name`. That inventory also covers a local
    `var` declaration and an `assign`/`return` target, which never occur
    here because requires, ensures and a spec fun's body are all Expr, never
    a statement block (SYNTAX.md's grammar; a lemma's or method's body is
    the one exception, and spec_changed refuses rather than reaching here
    for either). Every other shape (an `op`, a literal, a type) has no name
    in it to rename, so it is compared by ordinary recursive equality --
    which is also what makes an op tag or a literal that DIFFERS a real
    difference: nothing here ever treats "<" and "<=" as a renaming of one
    another."""
    if isinstance(a, dict) and isinstance(b, dict):
        if "var" in a or "var" in b:
            if "var" not in a or "var" not in b:
                return False
            av, bv = a["var"], b["var"]
            if not (isinstance(av, str) and isinstance(bv, str)):
                return False                                       # a declaration's shape, not a reference: not equal here
            return env.get(av, av) == bv
        for kind in ("forall", "exists"):
            if kind in a or kind in b:
                if kind not in a or kind not in b:
                    return False
                qa, qb = a[kind], b[kind]
                if not (_alpha_eq(qa.get("lo"), qb.get("lo"), env) and
                        _alpha_eq(qa.get("hi"), qb.get("hi"), env)):
                    return False
                child = dict(env)
                child[qa["var"]] = qb["var"]
                return _alpha_eq(qa["body"], qb["body"], child)
        if "call" in a or "call" in b:
            if "call" not in a or "call" not in b:
                return False
            ca, cb = a["call"], b["call"]
            if env.get(ca["fun"], ca["fun"]) != cb["fun"]:
                return False
            return _alpha_eq(ca.get("args", []), cb.get("args", []), env)
        if "lemma" in a or "lemma" in b:
            if "lemma" not in a or "lemma" not in b:
                return False
            la, lb = a["lemma"], b["lemma"]
            if env.get(la["name"], la["name"]) != lb["name"]:
                return False
            return _alpha_eq(la.get("args", []), lb.get("args", []), env)
        return set(a) == set(b) and all(_alpha_eq(a[k], b[k], env) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_alpha_eq(x, y, env) for x, y in zip(a, b))
    return a == b


def _clauses_differ(prompt_list: list, draft_list: list, env: dict[str, str]) -> str | None:
    """None when `draft_list` is *some* reordering of clauses each alpha-
    equal (under `env`, via _alpha_eq) to one clause of `prompt_list` --
    requires and ensures are each a set of conditions, so a bipartite match
    is the right comparison, not a positional one; a plain backtracking
    search is fast enough at the size these lists actually reach (a handful
    of clauses). A short reason otherwise."""
    if len(prompt_list) != len(draft_list):
        return f"has {len(draft_list)} clauses, the specification has {len(prompt_list)}"
    used = [False] * len(draft_list)

    def match(i: int) -> bool:
        if i == len(prompt_list):
            return True
        for j, taken in enumerate(used):
            if not taken and _alpha_eq(prompt_list[i], draft_list[j], env):
                used[j] = True
                if match(i + 1):
                    return True
                used[j] = False
        return False

    return None if match(0) else "changed (no reordering of the specification's clauses matches the draft's)"


def spec_changed(prompt_task: dict, draft_task: dict) -> str | None:
    """None when `draft_task` keeps `prompt_task`'s declaration, requires,
    ensures and spec funs (up to a consistent renaming and reordered
    clauses; see the section docstring above); otherwise the short reason a
    person or the model can read. Both must be tasks surface.parse itself
    produced (e.g. via check() or parse_spec_header), never hand-built,
    since this trusts their shape (each has "params", "returns", ...)."""
    pp, dp = prompt_task.get("params", []), draft_task.get("params", [])
    if len(pp) != len(dp):
        return f"{len(dp)} parameters for {len(pp)} in the specification"
    for i, (a, b) in enumerate(zip(pp, dp)):
        if a["type"] != b["type"]:
            return f"parameter {i + 1} is {b['type']}, the specification says {a['type']}"
    pr, dr = prompt_task["returns"][0], draft_task["returns"][0]
    if pr["type"] != dr["type"]:
        return f"returns {dr['type']}, the specification says {pr['type']}"
    if prompt_task.get("lemmas") or draft_task.get("lemmas"):
        return "a lemma differs (not compared)"
    if prompt_task.get("methods") or draft_task.get("methods"):
        return "a method differs (not compared)"

    env = {prompt_task["name"]: draft_task["name"]}
    for a, b in zip(pp, dp):
        env[a["name"]] = b["name"]
    env[pr["name"]] = dr["name"]

    psf = {sf["name"]: sf for sf in prompt_task.get("spec_funs", [])}
    dsf = {sf["name"]: sf for sf in draft_task.get("spec_funs", [])}
    if set(psf) != set(dsf):
        bits = [f"added spec fun {n}" for n in sorted(set(dsf) - set(psf))]
        bits += [f"removed spec fun {n}" for n in sorted(set(psf) - set(dsf))]
        return "; ".join(bits)
    for name, a in psf.items():
        b = dsf[name]
        pparams, dparams = a["params"], b["params"]
        if len(pparams) != len(dparams) or any(x["type"] != y["type"] for x, y in zip(pparams, dparams)):
            return f"spec fun {name} has a different signature"
        child = dict(env)
        for x, y in zip(pparams, dparams):
            child[x["name"]] = y["name"]
        if len(child) != len(set(child.values())):
            return f"spec fun {name}'s parameters do not rename it one-to-one from the specification's"
        if not _alpha_eq(a["body"], b["body"], child):
            return f"spec fun {name}'s definition changed"
        if ("decreases" in a) != ("decreases" in b) or \
                ("decreases" in a and not _alpha_eq(a["decreases"], b["decreases"], child)):
            return f"spec fun {name}'s decreases changed"

    if len(env) != len(set(env.values())):
        return "does not rename the specification's names one-to-one"

    if ("decreases" in prompt_task) != ("decreases" in draft_task) or \
            ("decreases" in prompt_task and
             not _alpha_eq(prompt_task["decreases"], draft_task["decreases"], env)):
        return "decreases changed"

    for clause in ("requires", "ensures"):
        reason = _clauses_differ(prompt_task.get(clause, []), draft_task.get(clause, []), env)
        if reason is not None:
            return f"{clause} {reason}"
    return None


def call(program: str, context: str = "") -> str:
    """The tool: check the draft, compare its specification with the
    prompt's own when `context` states one (before running anything, and
    skipped silently when it does not -- see the section above), then run
    it on every Example line in `context`."""
    task, lines = check(program)
    if task is None:
        return "\n".join(lines)
    header = spec_header_from_context(context)
    if header is not None:
        prompt_task = parse_spec_header(header)
        if prompt_task is not None:
            reason = spec_changed(prompt_task, task)
            if reason is not None:
                lines.append(f"specification: spec changed: {reason}")
                return "\n".join(lines)
    types = [p["type"] for p in task["params"]]
    for i, ex in enumerate(parse_examples(context), 1):
        if "error" in ex:
            lines.append(f"example {i}: unreadable: {_short(ex['error'])}")
            continue
        try:
            args = [_value(ty, v) for ty, v in zip(types, ex["args"])]
        except TypeError as e:
            lines.append(f"example {i}: cannot run: {_short(e)}")
            continue
        if len(ex["args"]) != len(types):
            lines.append(f"example {i}: arity: {len(ex['args'])} arguments for {len(types)} parameters")
            continue
        got = run(task, args)
        if got["verdict"] != "ok":
            lines.append(f"example {i}: {got['verdict']}" + (f": {got['why']}" if got.get("why") else ""))
        elif json.dumps(got["got"]) == json.dumps(ex["expected"]):
            lines.append(f"example {i}: pass")
        else:
            lines.append(f"example {i}: fail: got {json.dumps(got['got'])}, expected {json.dumps(ex['expected'])}")
    return "\n".join(lines)


def examples_from_program(program: str, n: int = 2, limit: int = 256) -> list[str]:
    """Up to n `Example:` lines computed by running a proved program.

    Inputs come from interp.domain (ladders over the task's literals, shell
    order); an input the `requires` excludes is skipped, as is one the
    interpreter cannot finish. Distinct outputs are required and inputs from
    the median size up come first, so the lines separate programs rather than
    all showing f(0).
    Only int, bool and seq parameters are shown (what parse_examples reads
    back); anything else gives no examples.
    """
    import interp
    import surface
    task = surface.parse(program)
    names = [(p["name"], p["type"]) for p in task["params"]]
    if not names or any(ty not in RUNNABLE_TYPES for _, ty in names):
        return []
    rows = []
    for env in interp.domain(task, names, limit):
        args = [env[name] for name, _ in names]
        got = run(task, args)
        if got["verdict"] == "ok":
            rows.append(([interp._j(a) for a in args], got["got"]))
    if not rows:
        return []

    def size(row):
        return len(json.dumps(row[0]))

    # from the median input size upward, then the smaller ones: the smallest
    # inputs (0, []) rarely separate programs and the largest are the ladders'
    # 2**31 boundary values
    ordered = sorted(rows, key=size)
    ordered = ordered[len(ordered) // 2:] + ordered[:len(ordered) // 2]
    chosen, seen = [], set()
    for row in ordered:
        key = json.dumps(row[1])
        if key not in seen:
            chosen.append(row)
            seen.add(key)
        if len(chosen) == n:
            break
    fn = task["name"]
    return [f"Example: {fn}({', '.join(json.dumps(a) for a in args)}) == {json.dumps(out)}"
            for args, out in chosen]
