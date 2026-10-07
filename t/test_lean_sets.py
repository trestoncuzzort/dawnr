#!/usr/bin/env python3
"""test_lean_sets.py: finite sets in Lean (SPEC.md "Finite sets", PREDICT T29, 2026-10-07). Text-level checks only,
no kernel runs. A set is core Std's extensional tree set of ints, `Std.ExtTreeSet Int compare`, whose `=` is
extensional; the lowering imports exactly that module, which the Lean adapter allows and nothing else."""
from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import lower_lean  # noqa: E402
import tasks_io  # noqa: E402
from verifiers import lean as lean_backend  # noqa: E402

CHECKS = 0
TS = "(Std.ExtTreeSet Int compare)"


def ok(cond, what):
    global CHECKS
    CHECKS += 1
    if not cond:
        print("FAIL:", what)
        sys.exit(1)


def load(name: str) -> dict:
    return tasks_io.load_task(str(HERE / "tasks" / f"{name}.t"))


def lean(name: str) -> str:
    task = load(name)
    return lower_lean.lower(task, task["body"])


def refusal(name: str) -> str:
    task = load(name)
    try:
        lower_lean.lower(task, task["body"])
    except NotImplementedError as e:
        return str(e)
    return ""


def test_the_type_and_operations():
    src = lean("set_toggle")
    lines = [l for l in src.splitlines() if l.strip() and not l.startswith("--")]
    ok(lines[0] == "import Std.Data.ExtTreeSet", "the one import comes first")
    ok(f"(a : {TS})" in src, "a set is the extensional tree set of ints")
    ok("(a.erase x)" in src and "(a.insert x)" in src, "a singleton difference and union are erase and insert")
    ok("((a.size : Int))" in src, "card is the size as an Int")
    ok("theorem t_set_size_pos" in src and "t_set_size_pos]" in src, "the size fact is proved once and handed to grind")
    src = lean("set_collect")
    ok(f"(∅ : {TS})" in src, "the empty set display")
    src = lean("members_upto")
    ok("(Std.ExtTreeSet.ofList" in src, "toset is ofList")


def test_what_is_still_refused_by_name():
    ok("compound element type" in refusal("words_seen") or "set<seq>" in refusal("words_seen"),
       "a set of seqs is refused by name")
    ok(refusal("all_pos_set") == "", "a set-ranged quantifier is lowered since T30")


def test_set_ranged_quantifiers():
    # PREDICT T30: in a Prop, membership is the range; computed as a Bool, the set's list of members; a connective
    # over one is a Bool; the closers carry the simp bridge
    src = lean("all_pos_set")
    ok(".toList.all (fun (" in src, "computed as toList.all")
    ok("∈ s → (" in src, "and stated as a membership range in the contract")
    ok("List.all_eq_true" in src and "Std.ExtTreeSet.mem_toList" in src, "the closers carry the bridge")
    av = tasks_io.load_task(str(HERE / "algoveri" / "bst_zig.t"))
    src = lower_lean.lower(av, av["body"])
    ok(".toList.all (fun (" in src and " && (is_bst_s left) && " in src, "is_bst is a Bool conjunction")
    ok("deriving DecidableEq, Inhabited" in src, "a field read's default needs Inhabited")
    ok("deriving DecidableEq, Inhabited" not in lean("tree_sum"), "and only then")


def test_the_adapter_allows_exactly_one_import():
    def banned(src):
        st = lean_backend._strip_comments_strings(src)
        return [m.group(0) for m in lean_backend.BANNED.finditer(
            lean_backend._ALLOWED_IMPORT_LINE.sub("", unicodedata.normalize("NFKC", st)))]
    ok(banned("import Std.Data.ExtTreeSet\ntheorem a : True := trivial") == [], "the allowed line")
    ok(banned("import Mathlib\n") == ["import"], "any other module is banned")
    ok(banned("import Std.Data.ExtTreeSet.Lemmas\n") == ["import"], "a submodule is banned")
    ok(banned("theorem a : True := by\n  import Std.Data.ExtTreeSet") == ["import"], "not at a line start is banned")


def test_ground_sets_in_certificates():
    lw = lower_lean.Lower(load("set_toggle"), load("set_toggle")["body"])
    ok(lw._gterm([1, 3], "set") == f"(((∅ : {TS}).insert (1 : Int)).insert (3 : Int))",
       "a ground set witness is its insert chain")
    ok(lw._unshow([1, 3], "set") == frozenset({1, 3}), "and the interpreter reads it back as a set")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: ok")
    print(f"{CHECKS} checks")
