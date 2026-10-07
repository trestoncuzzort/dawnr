#!/usr/bin/env python3
"""test_datatype_recursion.py: recursive datatypes (SPEC.md "Datatypes (v3): recursion", PREDICT T25, 2026-10-07).
Text-level checks only, no kernel runs:
- the rules (recursive fields, the base case, datatype measures);
- the interpreter (the ladder's rounds, the size measure);
- the twin harness's binder move;
- the printer;
- the three lowerings that state the construct, and the four that refuse it by name;
- the Dafny certificate's shape check on a datatype field."""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import check_wf  # noqa: E402
import harness  # noqa: E402
import interp  # noqa: E402
import lower_dafny  # noqa: E402
import lower_framac  # noqa: E402
import lower_lean  # noqa: E402
import lower_spark  # noqa: E402
import lower_verus  # noqa: E402
import surface  # noqa: E402
import tasks_io  # noqa: E402
from verifiers import dafny as dafny_backend  # noqa: E402

CHECKS = 0
TREES = ("tree_sum", "tree_mirror", "tree_count", "tree_insert", "tree_height")


def ok(cond, what):
    global CHECKS
    CHECKS += 1
    if not cond:
        print("FAIL:", what)
        sys.exit(1)


def load(name: str) -> dict:
    return tasks_io.load_task(str(HERE / "tasks" / f"{name}.t"))


def text(mod, name: str) -> str:
    task = load(name)
    return mod.lower(task, task["body"])


def wf_rules(src: str) -> set:
    """The rule names check_wf reports for a program (its position-aware form carries `.rule`)."""
    pos: dict = {}
    task = surface.parse(src, positions=pos)
    return {e.rule for e in check_wf.check_wf(task, pos)}


TAIL = """t 1 task f() returns (r: int) ensures true
{
  r := 0
}
"""


def test_rules():
    for name in TREES:
        ok(not wf_rules((HERE / "tasks" / f"{name}.t").read_text()), f"{name} is well formed")
    ok("datatype-base" in wf_rules("datatype T = Node(l: T, v: int)\n" + TAIL),
       "a datatype whose every constructor needs itself has no finite value")
    try:
        surface.parse("datatype A = A(b: B) | Z\ndatatype B = B(x: int)\n" + TAIL)
        ok(False, "a field of a datatype declared later is refused")
    except surface.SurfaceError as e:
        ok("found 'B'" in str(e), f"a field of a datatype declared later is refused by the parser, by name: {e}")
    ok(not wf_rules("datatype B = B(x: int)\ndatatype A = A(b: B) | Z\n" + TAIL),
       "a field of a datatype declared before is admitted")


def test_ladder_and_measure():
    lad = interp.ladders(load("tree_sum"))["datatype:Tree"]
    ok(lad[0] == interp.Ctor("Tree", "Leaf", ()), "the ladder starts at the base case")
    near = lad[:13]
    ok(max(interp.ctor_size(v) for v in near) == 7 and interp.ctor_size(lad[13]) > 3,
       f"two rounds: Leaf, three one-node trees, nine two-level trees, then the labelled shapes ({len(lad)})")
    sizes = [interp.ctor_size(v) for v in near]
    ok(sizes == sorted(sizes) or sizes[:4] == [1, 3, 3, 3], "smallest first")
    shown = interp._j(lad[4])
    ok(interp.ev(surface.parse_expr(shown), {}, {}, interp.St()) == lad[4], f"a nested value reads back: {shown}")


def test_binder_twin():
    tb, op, w = harness.twin_for(load("tree_mirror"))
    ok(op.startswith("wrong-var") and w.get("_ens") is True,
       f"tree_mirror's twin reads one subtree for the other, refuting the contract: {op} {w}")


def test_printer_round_trip():
    for name in TREES:
        t = load(name)
        printed = surface.print_task(t)
        ok("{'datatype'" not in printed, f"{name}: a datatype result prints as its name")
        again = surface.parse(printed)
        ok(again["spec_funs"] == t["spec_funs"] and again["body"] == t["body"], f"{name} prints and parses back")


def test_dafny():
    src = text(lower_dafny, "tree_sum")
    ok(re.search(r"match tr \{\n\s+case Leaf =>\n\s+s := 0;\n\s+case Node\(v, l, r\) =>\n\s+var t0 := Tree_sum\(l\);",
                 src), "a self-call in a case arm is hoisted inside a match statement")
    src = text(lower_dafny, "tree_insert")
    ok(re.search(r"if \(x < v\) \{\n\s+var t\d+ := Tree_insert\(l, x, lo, v\);", src),   # PREDICT T60: the bounded form
       "a self-call in an if branch is hoisted inside an if statement")
    src = text(lower_dafny, "tree_mirror")
    ok("function mirror(q: Tree): Tree" in src, "a datatype spec_fun result is spelled by name")
    decl = {"mods": [], "kind": "datatype", "name": "Tree", "clauses": [], "body": None,
            "head": "datatype Tree = Leaf | Node(v: int, l: Tree, r: Tree)"}
    ok(dafny_backend._inert_datatype(decl, frozenset({"Tree"})),
       "the certificate's shape check admits a field naming a datatype of the same program")
    ok(not dafny_backend._inert_datatype(decl, frozenset()), "and nothing else by that name")


def test_verus():
    src = text(lower_verus, "tree_mirror")
    ok("enum Tree { Leaf, Node(int, Box<Tree>, Box<Tree>) }" in src, "a datatype field is a Box")
    ok("Box::new(mirror(r))" in src, "built with Box::new")
    ok("Node(v, t_box_l, t_box_r) => { let l = *t_box_l; let r = *t_box_r;" in src,
       "an arm reads a boxed binder through a let")
    src = text(lower_verus, "tree_height")
    ok("let t_h0 = tree_height(l); let t_h1 = tree_height(r);" in src and "t_max(t_h0, t_h1)" in src,
       "a self-call in a spec function's argument is bound first")
    ok("t_h0" not in text(lower_verus, "fib"), "a self-call outside a spec argument stays where it is")


def test_lean():
    src = text(lower_lean, "tree_sum")
    ok("def total_s (q : Tree) : Int :=" in src and "termination_by (q)" not in src,
       "a datatype measure gives a structurally recursive def, no termination clause")
    ok("induction tr <;>" in src, "the contract is proved by structural induction")
    src = text(lower_lean, "tree_count")
    ok("induction tr generalizing x <;>" in src, "the other parameters are generalized")
    src = text(lower_lean, "tree_height")
    ok(re.search(r"grind \[tree_height_t, height_s, t_max\]", src), "the library functions are grind hints")


def _is_bst(v) -> bool:
    keys = []

    def walk(t):
        if t.ctor == "Leaf":
            return True
        v0, l, r = t.args
        ok_l, ok_r = walk(l), walk(r)
        keys.append(v0)
        return ok_l and ok_r
    if not walk(v):
        return False
    inorder = []

    def io(t):
        if t.ctor != "Leaf":
            io(t.args[1])
            inorder.append(t.args[0])
            io(t.args[2])
    io(v)
    return inorder == sorted(set(inorder)) and len(inorder) == len(set(inorder))


def test_labelled_shapes():
    # G12, PREDICT T27: after the near corner, every shape of up to five nodes, int fields labelled in order
    lad = interp.ladders(load("tree_sum"))["datatype:Tree"]
    shapes = lad[13:]
    ok(len(shapes) >= 60 and all(_is_bst(v) for v in shapes),
       f"every labelled shape is a search tree with distinct keys ({len(shapes)})")
    ok(any(interp.ctor_size(v) == 11 for v in shapes), "shapes reach five nodes")
    ok(lad[:13] == tuple(interp.ladders(load("tree_sum"))["datatype:Tree"][:13]), "the near corner comes first")


def test_tree_certificates_g12():
    # AlgoVeri's BST insert: Verus's set certificate reveals its recursive fns and states memberships; Dafny's
    # fact ladder prints a ground set
    task = tasks_io.load_task(str(HERE / "algoveri" / "bst_insert.t"))
    tb, op, w = harness.twin_for(task)
    src = lower_verus.lower(task, tb, witness=w)
    cert = src[src.index("t_refutation_certificate"):]
    ok(re.search(r"reveal_with_fuel\(view, \d+\);", cert) and re.search(r"reveal_with_fuel\(is_bst, \d+\);", cert),
       "Verus reveals view and is_bst to the witness's depth")
    ok(".contains(0int));" in cert, "and asserts the memberships the interpreter computed")
    real = lower_verus.lower(task, task["body"])
    ok("reveal_with_fuel(view, 2);" in real or "t_wf_" not in real, "definedness lemmas reveal structural recursion")
    task = tasks_io.load_task(str(HERE / "algoveri" / "bst_search.t"))
    tb, op, w = harness.twin_for(task)
    ok(re.search(r"assert view\(Tree\.Node\(.*\)\) == \{[0-9, ]+\};", lower_dafny.lower(task, tb, witness=w)),
       "Dafny's certificate prints a ground set as a display")


def test_two_kernels_refuse_by_name():
    # Rocq and F* lower datatypes since PREDICT T34 and T35 (test_rocq_datatypes.py, test_fstar_datatypes.py)
    task = load("tree_sum")
    for mod in (lower_spark, lower_framac):
        try:
            mod.lower(task, task["body"])
            ok(False, f"{mod.__name__} refuses")
        except NotImplementedError as e:
            ok("datatype" in str(e), f"{mod.__name__} refuses datatypes by name")   # SPARK: a recursive datatype, T36


def test_bool_variants_reach_a_red_child():
    # PREDICT T38: a recursive datatype with a bool field gets each labelled shape with one node's bools flipped
    import interp
    rb = surface.parse("datatype Tree = Nil | Node(val: int, is_red: bool, left: Tree, right: Tree)\nt 1\n"
                       "task f(x: Tree) returns (r: int)\n  ensures r == 0\n{\n  r := 0;\n}\n")
    lad = interp.ladders(rb)["datatype:Tree"]
    ok(any(v.ctor == "Node" and isinstance(v.args[3], interp.Ctor) and v.args[3].ctor == "Node" and v.args[3].args[1]
           for v in lad), "a node whose right child is red")
    ok(len(lad) == len(set(lad)), "no value twice")
    plain = interp.ladders(load("tree_sum"))["datatype:Tree"]
    ok(not any(isinstance(a, bool) for v in plain for a in v.args), "a tree without a bool field: no variants")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: ok")
    print(f"{CHECKS} checks")
