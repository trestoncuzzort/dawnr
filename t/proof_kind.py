#!/usr/bin/env python3
"""t/proof_kind.py -- what a proof is of: an algorithm held to a separate statement, or a program that is its own
specification written again (2026-10-05).

    python3 t/proof_kind.py --split t/out/loop/split-v5.json --panel clean-182 --verdicts PATH [--larger] TAG [TAG ...]
    python3 t/proof_kind.py --file ANSWER.t

A proof says the program meets its specification. How much that says depends on the specification. CLEVER
(Thakur et al., arXiv:2505.13938) found that when a specification can be computed, a model copies it into the
implementation and proves it "via rewriting", and wrote its own specifications so that they cannot be computed.
`t` allows both kinds, and the gate tests a specification against a solution before it proves the program against
the specification; so for a program that restates its specification, what stands behind the answer is those
tests, and the proof adds that the two writings agree. This sorts proved answers by which they are, so that a
count of "proved" can be read. Research receipt ed73ba495bb3.

A specification is a FORMULA when some clause gives the result: `r == E`, outright or as the conclusion of a
case (`condition ==> r == E`). Otherwise it is a PROPERTY: it constrains the result (a quantifier over its
elements, its length, an inequality, a list of allowed values) without saying what it is.

  an algorithm    the specification is a property; or it is a formula and the program reaches it another way: a
                  loop (the prover needed an invariant), or a recursion that is not the specification's own
  a restatement   the specification is a formula and the program is that formula again: the same expression or
                  cases with no loop, or the same recursion as the specification function it is held to

Also noted: `through its specification function`, when the program calls a `spec fun` to compute (the part it
calls was defined, not derived). The reading is of the text of the answer, by rule; it runs nothing.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

ALGORITHM, RESTATEMENT = "an algorithm", "a restatement"


def _walk(node):
    """Every dict node of an expression or statement tree."""
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def _mentions(expr, name: str) -> bool:
    return any(n.get("var") == name for n in _walk(expr))


def _gives(clause, result: str):
    """E when the clause is `result == E` or `E == result` with E not mentioning the result, else None."""
    if not isinstance(clause, dict) or clause.get("op") != "==":
        return None
    a, b = clause["args"]
    if a == {"var": result} and not _mentions(b, result):
        return b
    if b == {"var": result} and not _mentions(a, result):
        return a
    return None


def formula(task: dict) -> list | None:
    """The expressions the specification gives the result as, when it is a formula: every `r == E` that a clause
    states outright or concludes under conditions (`c ==> r == E`, `c ==> d ==> r == E`). None when no clause
    does, which is a property. One such clause is enough: a bound or a list of allowed values beside it does not
    stop a program from being read off it."""
    if len(task.get("returns") or []) != 1:
        return None
    r, given = task["returns"][0]["name"], []
    for clause in task.get("ensures") or []:
        while isinstance(clause, dict) and clause.get("op") == "implies":
            clause = clause["args"][1]
        e = _gives(clause, r)
        if e is not None:
            given.append(e)
    return given or None


def _calls(node, name: str) -> list:
    return [n["call"]["args"] for n in _walk(node) if isinstance(n.get("call"), dict) and n["call"].get("fun") == name]


def _renamed(expr, names: dict):
    """The expression with variables renamed by `names`, as JSON, for comparing two writings."""
    def go(n):
        if isinstance(n, dict):
            if set(n) == {"var"}:
                return {"var": names.get(n["var"], n["var"])}
            return {k: go(v) for k, v in n.items()}
        return [go(v) for v in n] if isinstance(n, list) else n
    return json.dumps(go(expr), sort_keys=True)


def _same_recursion(task: dict, given: list) -> bool:
    """Whether the program recurses exactly as the specification function it is held to does: it calls itself the
    same number of times, with the same arguments."""
    held = {n["call"]["fun"] for e in given for n in _walk(e) if isinstance(n.get("call"), dict)}
    for f in task.get("spec_funs") or []:
        if f["name"] not in held or len(f["params"]) != len(task["params"]):
            continue
        to_task = {p["name"]: q["name"] for p, q in zip(f["params"], task["params"])}
        theirs = sorted(_renamed(args, to_task) for args in _calls(f["body"], f["name"]))
        mine = sorted(_renamed(args, {}) for args in _calls(task["body"], task["name"]))
        if theirs and theirs == mine:
            return True
    return False


def kind(task: dict) -> dict:
    """{"kind": ALGORITHM | RESTATEMENT, "specification": "a property" | "a formula", "why", "through its
    specification function": bool}."""
    given = formula(task)
    loop = any("while" in n for n in _walk(task.get("body") or []))
    recursive = bool(_calls(task.get("body") or [], task["name"]))
    spec_names = {f["name"] for f in task.get("spec_funs") or []}
    body_only = [s for s in _walk(task.get("body") or [])]
    # a call inside an invariant or a decreases clause is a statement about the program, not a computation in it
    ghost = [n for s in body_only if "while" in s for part in (s["while"].get("invariants") or [], s["while"].get("decreases"))
             for n in _walk(part)]
    through = any(isinstance(n.get("call"), dict) and n["call"].get("fun") in spec_names and not any(n is g for g in ghost)
                  for n in body_only)
    out = {"specification": "a property" if given is None else "a formula", "through its specification function": through}
    if given is None:
        return dict(out, kind=ALGORITHM, why="the specification constrains the result without giving it")
    if loop:
        return dict(out, kind=ALGORITHM, why="a loop is proved to reach what the specification defines")
    if recursive and not _same_recursion(task, given):
        return dict(out, kind=ALGORITHM, why="a recursion other than the specification's own is proved to reach what it defines")
    if recursive:
        return dict(out, kind=RESTATEMENT, why="the program recurses exactly as the specification function it is held to")
    return dict(out, kind=RESTATEMENT, why="the program has no loop and the specification gives its result as a formula or by cases")


RESTS_ON = {"ask": "which was held to an independent solution on drawn inputs and is printed to be read",
            "verify": "which was held to your own function's answers on drawn inputs and is printed to be read",
            "prove": "which is the one you wrote"}


def sentence(task: dict, command: str = "ask") -> str:
    """One line for the person shown this answer by `dawnr ask`, `verify` or `prove`."""
    k = kind(task)
    if k["kind"] == ALGORITHM:
        return "What the proof is of: " + k["why"] + "."
    return ("What the proof is of: " + k["why"] + ". The proof says the two writings agree; what this answer rests on is the "
            "specification, " + RESTS_ON[command] + ".")


def said(program: str, command: str = "ask") -> str | None:
    """`sentence` for a program's text, or None when it cannot be read (the answer is shown either way)."""
    try:
        import surface
        return sentence(surface.parse(program), command)
    except Exception:                                           # noqa: BLE001 -- a remark, never a reason to fail
        return None


def counted_kinds(tag: str, ids: set[int], verdicts: dict, level: int, min_completeness: float | None, larger: bool) -> dict[int, dict]:
    """problem -> kind() of the tag's counted answer to it, for the problems counted at `level` or above."""
    import score_levels
    import spec_experiment as se
    lv = score_levels.tag_levels(tag, ids, verdicts, min_completeness, larger)
    d = se.OUT_ROOT / se.model_tag(tag)
    ext = json.loads((d / "extract.json").read_text(encoding="utf-8")) if (d / "extract.json").exists() else {}
    tests = json.loads((d / "tests.json").read_text(encoding="utf-8")) if (d / "tests.json").exists() else {}
    out = {}
    for tid, v in lv.items():
        if v[0] < level:
            continue
        name = (tests.get(str(tid)) or {}).get("name") or (ext.get(str(tid)) or {}).get("name") or ""
        out[tid] = kind(json.loads((d / "tasks" / f"{name}.json").read_text(encoding="utf-8")))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("tags", nargs="*")
    ap.add_argument("--file", type=Path, help="classify one t program and say why")
    ap.add_argument("--split", type=Path)
    ap.add_argument("--panel", choices=("clean-182", "clean-200", "all-232"), default="clean-182")
    ap.add_argument("--ids-file", type=Path)
    ap.add_argument("--verdicts", type=Path)
    ap.add_argument("--min-completeness", type=float, default=0.6)
    ap.add_argument("--larger", action="store_true")
    ap.add_argument("--json", type=Path)
    a = ap.parse_args(argv)
    if a.file:
        import surface
        print(sentence(surface.parse(a.file.read_text(encoding="utf-8")), "prove"))
        return 0
    if not a.tags or not a.verdicts:
        raise SystemExit("proof_kind: give --file, or --verdicts and at least one tag")
    import score_levels
    ids = score_levels.panel_ids(a.split, a.panel, a.ids_file)
    verdicts = json.loads(a.verdicts.read_text(encoding="utf-8")).get("results", {})
    print("| answer set | proved by at least one | an algorithm | a restatement | proved by all seven | an algorithm | a restatement |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    best: dict[int, dict[int, str]] = {1: {}, 7: {}}
    record = {}
    for tag in a.tags:
        cells = []
        for level in (1, 7):
            kinds = counted_kinds(tag, ids, verdicts, level, a.min_completeness, a.larger)
            n_alg = sum(1 for k in kinds.values() if k["kind"] == ALGORITHM)
            cells += [len(kinds), n_alg, len(kinds) - n_alg]
            for tid, k in kinds.items():                        # pooled: a problem is an algorithm if any set proves one for it
                if best[level].get(tid) != ALGORITHM:
                    best[level][tid] = k["kind"]
            record.setdefault(tag, {})[str(level)] = {str(t): k for t, k in sorted(kinds.items())}
        print(f"| {tag} | " + " | ".join(str(c) for c in cells) + " |")
    if len(a.tags) > 1:
        cells = []
        for level in (1, 7):
            n_alg = sum(1 for k in best[level].values() if k == ALGORITHM)
            cells += [len(best[level]), n_alg, len(best[level]) - n_alg]
        print("| **pooled** | " + " | ".join(str(c) for c in cells) + " |")
    if a.json:
        a.json.write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":                                      # pragma: no cover
    raise SystemExit(main())
