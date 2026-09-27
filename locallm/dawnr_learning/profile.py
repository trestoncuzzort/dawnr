"""profile.py: the mechanical part of a person's taste, inferred from their own edits, visible and editable.

The adapter (sleep.py) can learn anything a person's examples show, but a
small model pays for it: the pilot of 2026-09-27 (DAWNR-LEARNING.md) fitted a
person's style and broke the programs. Some of a person's taste is mechanical
and can be learned without touching any weights at all. CIPHER (Gao et al.,
PRELUDE, arXiv:2404.15269) keeps the base frozen, infers a preference from
each of the user's edits, aggregates the preferences of past contexts and
applies them to the next answer, and the user can read and change what was
inferred. The same shape here, with no language model in the loop (a 92M model
cannot describe a preference): a closed set of dimensions, each observed in the
person's own versions of answers (their edits and the answers they approved),
aggregated by vote, and applied to dawnr's next answer by the same
semantics-preserving rewrites the synthetic persons use (persons.py), which
the t tool re-checks. What it cannot see, it does not guess: a dimension is
decided only with at least MIN_VOTES examples of which at least AGREEMENT
agree, and a person can pin any dimension by hand.

    dimension      values                                  observed in a target
    naming         my-camel | k-numbered | cur-snake | upper   the convention most of its locals follow
    semicolons     true | false                            whether its statements end with ';'
    indent         2 | 4                                   its body's indentation
    if_expression  true | false                            its two-way assignments (t v1 programs only)
    tool           true | false                            whether it shows the program through the t tool

Stored as <person>/profile.json: {"inferred": {...}, "pinned": {...}}; a pinned
value wins. `python3 locallm/dawnr_learning profile NAME` shows it.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import persons as P
from .feedback import final_program, parts_of

DIMENSIONS = ("naming", "semicolons", "indent", "if_expression", "tool")
MIN_VOTES = 3
AGREEMENT = 0.75
PROFILE_FILE = "profile.json"


def observe(target) -> dict:
    """One target's vote on each dimension it shows evidence for."""
    import surface
    parts = parts_of(target)
    votes = {"tool": any(p.get("type") == "t" for p in parts)}
    program = final_program(target)
    if not program:
        return votes
    try:
        task = surface.parse(program)
    except Exception:                                            # noqa: BLE001  (no program, no program votes)
        return votes
    bound = P._binders(task.get("body", []), set())
    local = [n for n in P.locals_of(task) if n not in bound]
    if local:
        counts = {name: sum(bool(rx.match(n)) for n in local) for name, rx in P.CONFORMS.items()}
        best = max(counts, key=counts.get)
        if counts[best] * 2 > len(local):
            votes["naming"] = best
        else:
            votes["naming"] = "other"
    body = program.split("{", 1)[1] if "{" in program else ""
    stmts = [ln for ln in body.split("\n") if re.match(r"^\s*(var\s|[A-Za-z_][A-Za-z0-9_]*\s*:=)", ln)]
    if stmts:
        with_semi = sum(ln.rstrip().endswith(";") for ln in stmts)
        votes["semicolons"] = with_semi * 2 > len(stmts)
    first = next((ln for ln in body.split("\n")[1:] if ln.strip() and ln.strip() != "}"), None)
    if first is not None:
        votes["indent"] = len(first) - len(first.lstrip(" "))
    if int(task.get("t", 0)) >= 1:
        rows = list(P._stmts(task.get("body", [])))
        ite = sum(1 for s in rows if "assign" in s and isinstance(s["assign"][1], dict) and set(s["assign"][1]) == {"ite"})
        two_way = sum(1 for s in rows if "if" in s and len(s["if"]["then"]) == 1 and len(s["if"]["else"]) == 1
                      and "assign" in s["if"]["then"][0] and "assign" in s["if"]["else"][0]
                      and s["if"]["then"][0]["assign"][0] == s["if"]["else"][0]["assign"][0])
        if ite + two_way:
            votes["if_expression"] = ite > two_way
    return votes


def infer(examples: list[dict]) -> dict:
    """{dimension: {"value", "votes", "agree"}} for every dimension the examples decide; the rest are absent."""
    tallies: dict[str, dict] = {}
    for ex in examples:
        target = ex["messages"][-1]["content"]
        for dim, value in observe(target).items():
            tallies.setdefault(dim, {})
            key = json.dumps(value)
            tallies[dim][key] = tallies[dim].get(key, 0) + 1
    decided = {}
    for dim, counts in tallies.items():
        total = sum(counts.values())
        key, agree = max(counts.items(), key=lambda kv: kv[1])
        value = json.loads(key)
        if total >= MIN_VOTES and agree / total >= AGREEMENT and value not in ("other",) and \
                not (dim == "indent" and value not in (2, 4)):
            decided[dim] = {"value": value, "votes": total, "agree": agree}
    return decided


def effective(profile: dict) -> dict:
    """{dimension: value} the answer is rewritten with: pinned values first, then inferred ones."""
    out = {dim: v["value"] for dim, v in profile.get("inferred", {}).items()}
    out.update(profile.get("pinned", {}))
    return {k: v for k, v in out.items() if k in DIMENSIONS}


def restyle(program: str, prefs: dict) -> str | None:
    """The program rewritten on the decided dimensions only; None when it does not parse."""
    import surface
    try:
        task = surface.parse(program)
    except Exception:                                            # noqa: BLE001
        return None
    if prefs.get("naming") in P.NAMINGS:
        task = P.rename_locals(task, prefs["naming"])
    if "if_expression" in prefs:
        task = P.if_form(task, bool(prefs["if_expression"]))
    text = P.format_text(surface.print_task(task), bool(prefs.get("semicolons", True)), int(prefs.get("indent", 2)))
    if surface.canon(surface.parse(text)) != surface.canon(task):
        raise AssertionError("formatting changed the parse tree; this is a bug in persons.format_text")
    return text if text.endswith("\n") else text + "\n"


def apply(profile: dict, content, user: str):
    """dawnr's answer rewritten to the person's profile, never made worse: a rewrite that the t tool fails
    where the original passed is not used, and an answer with no program is returned as it was."""
    import t_tool
    from dawnr_harness.checker import check
    prefs = effective(profile)
    if not prefs or not content:
        return content
    parts = parts_of(content)
    program = final_program(content)
    if not program:
        return content
    passed, verdict = check(program, user)
    if "well formed: yes" not in verdict.split("\n"):
        # a rename is capture-free only in a well-formed program: in one whose local shadows a parameter
        # (found by the first run of arm P, DAWNR-LEARNING.md) renaming would choose which name each use
        # meant, and so change the program. An ill-formed answer is shown as dawnr wrote it.
        return content
    styled = restyle(program, prefs) or program
    if styled != program and passed and not check(styled, user)[0]:
        styled = program
    calls = [i for i, p in enumerate(parts) if p.get("type") == "t"]
    show_tool = prefs.get("tool", bool(calls))
    if calls:
        before = [dict(p) for p in parts[:calls[-1]]]
    else:
        text = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
        lead = text.split(program.strip().split("\n", 1)[0], 1)[0].strip() if program.strip() else ""
        before = [{"type": "text", "text": lead + "\n"}] if lead else []
    if not show_tool:
        prose = "".join(p.get("text", "") for p in before if p.get("type") == "text")
        return (prose + styled) if prose else styled
    return before + [{"type": "t", "text": styled}, {"type": "t_output", "text": t_tool.call(styled, user)}]


def load(person_dir: Path) -> dict:
    path = Path(person_dir) / PROFILE_FILE
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"inferred": {}, "pinned": {}}


def save(person_dir: Path, profile: dict) -> None:
    Path(person_dir).mkdir(parents=True, exist_ok=True)
    tmp = Path(person_dir) / (PROFILE_FILE + ".tmp")
    tmp.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
    tmp.replace(Path(person_dir) / PROFILE_FILE)


def refresh(store) -> dict:
    """Re-infer the person's profile from their current examples (checked, as for a sleep); keep their pins."""
    examples, _excluded = store.training_examples(check=True)
    profile = load(store.dir)
    profile["inferred"] = infer(examples)
    profile["examples"] = len(examples)
    save(store.dir, profile)
    return profile


def describe(profile: dict) -> list[str]:
    """What dawnr believes about this person's taste, one line per dimension, with its evidence."""
    words = {"naming": "local names", "semicolons": "semicolons", "indent": "indentation",
             "if_expression": "two-way assignment as `if c then a else b`", "tool": "show the checker's verdict"}
    lines = []
    for dim in DIMENSIONS:
        if dim in profile.get("pinned", {}):
            lines.append(f"{words[dim]}: {profile['pinned'][dim]} (set by you)")
        elif dim in profile.get("inferred", {}):
            v = profile["inferred"][dim]
            lines.append(f"{words[dim]}: {v['value']} ({v['agree']} of {v['votes']} of your examples)")
        else:
            lines.append(f"{words[dim]}: not known yet")
    return lines
