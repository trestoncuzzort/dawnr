"""persons.py: synthetic people with fixed, distinct preferences, for measuring whether dawnr learns each one.

A real person's preferences are latent: they show only in what the person
accepts and how they edit. PRELUDE (Gao et al., arXiv:2404.15269) measures
learning from edits with simulated users whose latent preference drives every
edit (bullet points, brevity, a tone), and scores a learner by the edit
distance between its answer and the user's edit, round after round. The same
protocol is used here, with two differences that keep it offline and exact:
each person is a deterministic program over t's syntax tree rather than a
prompted large model, and every version a person produces is checked by the
t tool on the prompt's own Example lines before it is used.

A person's preferences, each a real matter of taste in a program that does not
change what the program computes:

* naming of local variables: `my-camel` (myIndex), `k-numbered` (k1, k2),
  `cur-snake` (cur_index) or `upper` (INDEX). A rename is capture-free: the new
  name collides with no other identifier in the program, compared without
  case (SPARK, one of the seven kernels, does not distinguish case), and a
  local that a quantifier's bound variable shadows is left alone;
* semicolons at the end of statements, or none (t's grammar makes them optional);
* indentation of 2 or 4 spaces;
* `x := if c then a else b` for a two-way assignment, or the if statement;
* one line before the program saying the approach ("Approach: 1 loop with 2
  invariants; locals myI; the result is s."), or nothing;
* the program shown through the t tool with its verdict, or as plain text.

The rename, the if form and the formatting are checked to be what they claim:
formatting must leave the parse tree unchanged (surface.canon), and the whole
restyled program must pass the t tool wherever the original did.

Only training-side problems are ever given to a person (measure.py), and
every example they produce passes the held-out gates before a sleep trains on
it (sleep.gate_examples).
"""
from __future__ import annotations

import copy
import re
import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOCALLM = HERE.parent
for p in (str(LOCALLM), str(LOCALLM.parent / "t")):
    if p not in sys.path:
        sys.path.insert(0, p)

NAMINGS = ("my-camel", "k-numbered", "cur-snake", "upper")
CONFORMS = {"my-camel": re.compile(r"^my[A-Z0-9][A-Za-z0-9]*$"), "k-numbered": re.compile(r"^k[0-9]+$"),
            "cur-snake": re.compile(r"^cur_[a-z0-9_]+$"), "upper": re.compile(r"^[A-Z][A-Z0-9_]*$")}
APPROACH = "Approach:"


@dataclass(frozen=True)
class Person:
    name: str
    naming: str
    semicolons: bool
    indent: int
    if_expression: bool
    explain: bool
    tool: bool
    about: str

    def __post_init__(self):
        if self.naming not in NAMINGS or self.indent not in (2, 4):
            raise ValueError(f"unknown naming {self.naming!r} or indent {self.indent}")
        if self.explain and not self.tool:
            # an explanation in the text beside a program in the text would make the text itself the answer;
            # a person who explains shows the program through the tool, so the answer's program is unambiguous
            raise ValueError("a person who explains also shows the program through the tool")


PERSONS = {p.name: p for p in (
    Person("ada", "my-camel", True, 2, False, True, True,
           "explains the approach first, wants the checker's verdict shown, names locals myThing"),
    Person("bo", "k-numbered", False, 2, False, False, False,
           "terse: the program alone, no semicolons, locals k1, k2, ..."),
    Person("cy", "cur-snake", True, 2, True, False, True,
           "likes `x := if c then a else b`, wants the verdict shown, names locals cur_thing"),
    Person("di", "upper", True, 4, False, False, False,
           "four-space indentation, upper-case locals, the program alone"),
    # eve is the pilot: used only to try the code and choose the learning rate before the registered run
    Person("eve", "cur-snake", False, 4, True, True, True,
           "the pilot person: never part of a reported result"),
)}


# ----------------------------------------------------------- the tree --

def _names(node, out: set) -> set:
    """Every identifier anywhere in a task (declared, referenced, bound, called, the task's own)."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k in ("name", "fun") and isinstance(v, str):
                out.add(v)
            elif k == "var" and isinstance(v, str):
                out.add(v)
            elif k in ("assign", "return") and isinstance(v, list) and v and isinstance(v[0], str):
                out.add(v[0])
            _names(v, out)
    elif isinstance(node, list):
        for v in node:
            _names(v, out)
    return out


def _binders(node, out: set) -> set:
    """Names bound by forall / exists anywhere in the node."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k in ("forall", "exists") and isinstance(v, dict) and isinstance(v.get("var"), str):
                out.add(v["var"])
            _binders(v, out)
    elif isinstance(node, list):
        for v in node:
            _binders(v, out)
    return out


def _stmts(stmts):
    """Every statement in a block, nested blocks included, in order."""
    for s in stmts:
        yield s
        if "if" in s:
            yield from _stmts(s["if"]["then"])
            yield from _stmts(s["if"]["else"])
        if "while" in s:
            yield from _stmts(s["while"]["body"])


def locals_of(task: dict) -> list[str]:
    """The task body's local variables, in declaration order."""
    out = []
    for s in _stmts(task.get("body", [])):
        if isinstance(s.get("var"), dict) and s["var"].get("name") not in out:
            out.append(s["var"]["name"])
    return out


def _words(name: str) -> list[str]:
    name = re.sub(r"_v([0-9]*)$", r"\1", name) if len(name) > 2 else name
    pieces = [p for p in re.split(r"_+", name) if p]
    words = []
    for p in pieces:
        words += [w for w in re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|[0-9]+", p) if w]
    return words or [name]


def conform(naming: str, name: str) -> str:
    """The name this convention gives a local (unchanged when it already conforms), before collisions."""
    if CONFORMS[naming].match(name):
        return name
    words = _words(name)
    if naming == "my-camel":
        return "my" + "".join(w[:1].upper() + w[1:] for w in words)
    if naming == "cur-snake":
        return "cur_" + "_".join(w.lower() for w in words)
    if naming == "upper":
        return "_".join(w.upper() for w in words)
    return ""                                  # k-numbered: numbered by the caller


def rename_locals(task: dict, naming: str) -> dict:
    """The task with its locals renamed to the convention; capture-free, case-insensitively distinct."""
    if any(k in task for k in ("methods", "lemmas", "method", "lemma")):
        return task                                         # other scopes: not renamed, not risked
    task = copy.deepcopy(task)
    local = locals_of(task)
    # a quantifier inside the body that binds a local's name shadows it there: that local is left alone.
    # One in requires/ensures does not (the body's locals are not in scope there), but its name stays taken.
    renamable = [n for n in local if n not in _binders(task.get("body", []), set())]
    taken = {n.lower() for n in _names(task, set()) if n not in renamable}
    import surface
    taken |= {k.lower() for k in surface.KEYWORDS} | {n.lower() for n in _binders(task, set())}
    mapping, k = {}, 1
    for name in renamable:
        want = conform(naming, name)
        if naming == "k-numbered" and not want:
            while f"k{k}" in taken:
                k += 1
            want = f"k{k}"
        new, n = want, 2
        while new.lower() in taken:
            new, n = f"{want}{n}" if naming != "cur-snake" else f"{want}_{n}", n + 1
        taken.add(new.lower())
        mapping[name] = new
    if all(a == b for a, b in mapping.items()):
        return task

    def rn(node):
        if isinstance(node, dict):
            if set(node) == {"var"} and isinstance(node["var"], str):
                return {"var": mapping.get(node["var"], node["var"])}
            out = {}
            for key, v in node.items():
                if key == "var" and isinstance(v, dict) and "name" in v:
                    v = dict(v, name=mapping.get(v["name"], v["name"]))
                    out[key] = {kk: rn(vv) if kk != "name" else vv for kk, vv in v.items()}
                elif key in ("assign", "return") and isinstance(v, list) and v and isinstance(v[0], str):
                    out[key] = [mapping.get(v[0], v[0])] + [rn(x) for x in v[1:]]
                else:
                    out[key] = rn(v)
            return out
        if isinstance(node, list):
            return [rn(v) for v in node]
        return node

    task["body"] = rn(task["body"])
    return task


def if_form(task: dict, expression: bool) -> dict:
    """Two-way assignments as `x := if c then a else b` (expression=True) or as an if statement.

    The if expression is a t v1 form (SPEC.md: ite is v1), so a `t 0` task keeps its if statements."""
    if expression and int(task.get("t", 0)) < 1:
        return task
    task = copy.deepcopy(task)

    def block(stmts):
        out = []
        for s in stmts:
            if "if" in s:
                s = {"if": dict(s["if"], then=block(s["if"]["then"]), **{"else": block(s["if"]["else"])})}
                th, el = s["if"]["then"], s["if"]["else"]
                if (expression and len(th) == 1 and len(el) == 1 and "assign" in th[0] and "assign" in el[0]
                        and th[0]["assign"][0] == el[0]["assign"][0]):
                    s = {"assign": [th[0]["assign"][0], {"ite": {"cond": s["if"]["cond"], "then": th[0]["assign"][1],
                                                                  "else": el[0]["assign"][1]}}]}
            elif "while" in s:
                s = {"while": dict(s["while"], body=block(s["while"]["body"]))}
            elif (not expression and "assign" in s and isinstance(s["assign"][1], dict)
                  and set(s["assign"][1]) == {"ite"}):
                x, ite = s["assign"][0], s["assign"][1]["ite"]
                s = {"if": {"cond": ite["cond"], "then": [{"assign": [x, ite["then"]]}],
                            "else": [{"assign": [x, ite["else"]]}]}}
            out.append(s)
        return out

    task["body"] = block(task["body"])
    return task


def format_text(text: str, semicolons: bool, indent: int) -> str:
    """t's printed form (2 spaces, semicolons) re-indented and with or without statement semicolons."""
    lines = []
    for line in text.split("\n"):
        stripped = line.lstrip(" ")
        depth = (len(line) - len(stripped)) // 2
        line = " " * (depth * indent) + stripped
        if not semicolons:
            line = re.sub(r";\s*$", "", line)
        lines.append(line)
    return "\n".join(lines)


def restyle_program(program: str, person: Person) -> str | None:
    """The program as this person writes it, or None when it does not parse. Checked: formatting keeps the tree."""
    import surface
    try:
        task = surface.parse(program)
    except Exception:                                   # noqa: BLE001  (a program that does not parse has no style)
        return None
    task = if_form(rename_locals(task, person.naming), person.if_expression)
    text = format_text(surface.print_task(task), person.semicolons, person.indent)
    if surface.canon(surface.parse(text)) != surface.canon(task):
        raise AssertionError("formatting changed the parse tree; this is a bug in format_text")
    return text if text.endswith("\n") else text + "\n"


def explanation(program: str) -> str:
    """The one line a person who explains writes before the program, computed from the program's tree."""
    import surface
    task = surface.parse(program)
    stmts = list(_stmts(task.get("body", [])))
    loops = [s for s in stmts if "while" in s]
    invariants = sum(len(s["while"].get("invariants", [])) for s in loops)
    branches = sum(1 for s in stmts if "if" in s) + sum(
        1 for s in stmts if "assign" in s and isinstance(s["assign"][1], dict) and set(s["assign"][1]) == {"ite"})
    pieces = [f"{len(loops)} loop{'s' if len(loops) != 1 else ''} with {invariants} "
              f"invariant{'s' if invariants != 1 else ''}" if loops else "no loop"]
    if branches:
        pieces.append(f"{branches} branch{'es' if branches != 1 else ''}")
    local = locals_of(task)
    if local:
        pieces.append(f"local{'s' if len(local) != 1 else ''} {', '.join(local)}")
    result = task["returns"][0]["name"] if task.get("returns") else "nothing"
    return f"{APPROACH} {'; '.join(pieces)}; the result is {result}."


def person_answer(person: Person, program: str, user: str):
    """The whole answer this person wants for this prompt, built on `program`; None when it cannot be built
    or when the restyled program fails the t tool on the prompt's examples."""
    import t_tool
    from dawnr_harness.checker import check
    styled = restyle_program(program, person)
    if styled is None:
        return None
    ok, verdict = check(styled, user)
    if not ok:
        return None
    if not person.tool:
        return styled
    parts = [{"type": "text", "text": explanation(styled) + "\n"}] if person.explain else []
    return parts + [{"type": "t", "text": styled}, {"type": "t_output", "text": t_tool.call(styled, user)}]


# -------------------------------------------------------- the reaction --

def levenshtein(a: list, b: list) -> int:
    """Edit distance between two token sequences (insert, delete, substitute; PRELUDE's cost)."""
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        current = [i]
        for j, y in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (x != y)))
        previous = current
    return previous[-1]


def react(person: Person, user: str, answer, reference: str, tokenizer=None) -> dict:
    """What this person does with dawnr's answer: up, edit, or wrong with a correction; and the edit cost.

    The answer's own program is kept when it passes the t tool on the prompt's
    examples (the person restyles it); otherwise the person says it is wrong
    and gives the reference program in their style. The cost is the token
    edit distance between the answer and what the person wanted (0 for up)."""
    from dawnr_harness.checker import check
    from .feedback import content_text, final_program
    program = final_program(answer) if answer else None
    ok = bool(program) and check(program, user)[0]
    if ok:
        # the person keeps dawnr's working program in their own style; if it cannot be restyled (it passes
        # the tool but a transform would not), they rewrite it from the reference instead: still an edit
        target = person_answer(person, program, user) or person_answer(person, reference, user)
        kind = "up" if target is not None and content_text(target) == content_text(answer) else "edit"
        if kind == "up":
            target = answer
    else:
        target = person_answer(person, reference, user)
        kind = "wrong"
    if target is None:
        return {"feedback": None, "target": None, "cost": None, "answer_ok": ok, "target_tokens": 0}
    a, b = content_text(answer or ""), content_text(target)
    if tokenizer is not None:
        a, b = tokenizer.encode(a), tokenizer.encode(b)
    return {"feedback": kind, "target": target, "cost": 0 if kind == "up" else levenshtein(list(a), list(b)),
            "answer_ok": ok, "target_tokens": len(b)}


def style_report(person: Person, answer) -> dict:
    """How far an answer follows this person's preferences, feature by feature (None: does not apply)."""
    import surface
    from .feedback import final_program, parts_of
    parts = parts_of(answer)
    calls = [i for i, p in enumerate(parts) if p.get("type") == "t"]
    first_call = calls[0] if calls else len(parts)
    text_before = "".join(p.get("text", "") for p in parts[:first_call] if p.get("type") == "text")
    features = {"tool": bool(calls) == person.tool,
                "explain": text_before.strip().startswith(APPROACH) == person.explain}
    program = final_program(answer)
    task = None
    if program:
        try:
            task = surface.parse(program)
        except Exception:                                   # noqa: BLE001
            task = None
    if task is not None:
        body_bound = _binders(task.get("body", []), set())
        local = [n for n in locals_of(task) if n not in body_bound]     # the locals a person can rename
        features["naming"] = (sum(bool(CONFORMS[person.naming].match(n)) for n in local) / len(local)
                              if local else None)
        body = program.split("{", 1)[1] if "{" in program else ""
        stmt_lines = [ln for ln in body.split("\n") if re.match(r"^\s*(var\s|[A-Za-z_][A-Za-z0-9_]*\s*:=)", ln)]
        if stmt_lines:
            with_semi = sum(ln.rstrip().endswith(";") for ln in stmt_lines)
            features["semicolons"] = (with_semi if person.semicolons else len(stmt_lines) - with_semi) / len(
                stmt_lines)
        else:
            features["semicolons"] = None
        first = next((ln for ln in body.split("\n")[1:] if ln.strip() and ln.strip() != "}"), None)
        features["indent"] = None if first is None else (len(first) - len(first.lstrip(" ")) == person.indent)
        stmts = list(_stmts(task.get("body", [])))
        convertible = sum(1 for s in stmts if "if" in s and len(s["if"]["then"]) == 1 and len(s["if"]["else"]) == 1
                          and "assign" in s["if"]["then"][0] and "assign" in s["if"]["else"][0]
                          and s["if"]["then"][0]["assign"][0] == s["if"]["else"][0]["assign"][0])
        ite = sum(1 for s in stmts if "assign" in s and isinstance(s["assign"][1], dict)
                  and set(s["assign"][1]) == {"ite"})
        features["if_form"] = None if convertible + ite == 0 or (person.if_expression and int(task.get("t", 0)) < 1) \
            else ((ite / (ite + convertible)) if person.if_expression else (convertible / (ite + convertible)))
    else:
        features.update(naming=None, semicolons=None, indent=None, if_form=None)
    values = [float(v) for v in features.values() if v is not None]
    return {"features": features, "adherence": sum(values) / len(values) if values else None,
            "parses": task is not None}
