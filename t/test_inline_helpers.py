"""Typed inline expansion: semantic oracles, rejection and source round trips.

Uses the repository's seeded-generator convention; no new test dependency.
Run on the lab: python3 -m unittest discover -s t -p test_inline_helpers.py -v
"""
import json
from pathlib import Path
import random
import unittest

import check_wf
import expand_helpers
import interp
import surface


def program(defs, expr, params="x: int", result="int", ensures="true"):
    return (f"t 1 task main({params}) returns (r: {result}) ensures {ensures}\n"
            f"{defs}\n{{ r := {expr}; }}")


def run(task, **inputs):
    env = dict(inputs, r=None)
    interp.exec_body(task["body"], env, interp.funs_of(task, task["body"]), interp.St())
    return env["r"]


class InlineHelpers(unittest.TestCase):
    def test_scalar_composition_and_sequence_pair_results(self):
        task = surface.parse(program(
            "inline fun inc(a: int): int = a + 1\n"
            "inline fun twice(a: int): int = inc(inc(a))\n"
            "inline fun pack(a: int): (int, seq) = (twice(a), [a])",
            "pack(x)", result="(int, seq)"))
        self.assertEqual([], check_wf.check_wf(task))
        self.assertEqual(interp.Pair(5, (3,)), run(task, x=3))
        self.assertNotIn('"call"', json.dumps(task))
        self.assertEqual(task, surface.parse(surface.print_task(task)))

    def test_hygiene_and_semantic_oracle_generated(self):
        rng = random.Random(20260919)
        for _ in range(150):
            name = rng.choice(["j", "inlineVar0", "inlineVar1", "z"])
            bound = rng.randrange(1, 8)
            source = program(
                f"inline fun above(a: int): bool = forall {name} in [0, {bound}) . a >= {name}",
                f"above({name})", params=f"{name}: int", result="bool")
            task = surface.parse(source)
            self.assertEqual(task, surface.parse(surface.print_task(task)))
            self.assertEqual([], check_wf.check_wf(task))
            for value in [-1, 0, bound - 1, bound, rng.randrange(-10, 11)]:
                self.assertEqual(value >= bound - 1, run(task, **{name: value}))

    def test_nested_sequence_empty_context_is_preserved(self):
        for expr in ("empty()", "idrows([])", "idrows(if x > 0 then [] else [])"):
            task = surface.parse(program(
                "inline fun empty(): seq<seq> = []\n"
                "inline fun idrows(rows: seq<seq>): seq<seq> = rows",
                expr, result="seq<seq>"))
            self.assertEqual([], check_wf.check_wf(task))
            self.assertEqual((), run(task, x=0))
            self.assertEqual(task, surface.parse(surface.print_task(task)))
        task = surface.parse(program("inline fun empty(): seq<seq> = []",
                                     "empty() + [[x]]", result="seq<seq>"))
        self.assertEqual(((3,),), run(task, x=3))

    def test_short_circuit_and_unused_argument_definedness(self):
        task = surface.parse(program("inline fun keep(a: int): int = 7", "keep(1 / 0)"))
        self.assertEqual(7, run(task, x=0))  # documented substitution, not eager call
        task = surface.parse(program(
            "inline fun choose(ok: bool, a: int): int = if ok then a else 0",
            "choose(x > 0, 1 / x)"))
        self.assertEqual(0, run(task, x=0))
        self.assertEqual(1, run(task, x=1))
        task = surface.parse(program("inline fun use(a: int): int = a", "use(1 / x)"))
        with self.assertRaises(interp.Undef):
            run(task, x=0)

    def test_unused_definitions_and_arguments_are_checked(self):
        bad = [
            ("inline fun keep(a: int): int = 7", "keep(true)"),
            ("inline fun keep(a: int): int = 7", "keep(missing)"),
            ("inline fun keep(a: int): int = 7", "keep(1, 2)"),
            ("inline fun keep(a: int): int = 7", "keep()"),
            ("inline fun bad(a: int): bool = a", "x"),
            ("inline fun bad(a: int): int = x", "x"),
            ("inline fun bad(a: int, a: int): int = a", "x"),
            ("inline fun bad(a: int): int = bad(a)", "x"),
            ("inline fun a(x: int): int = b(x)\ninline fun b(x: int): int = x", "x"),
            ("inline fun a(x: int): int = x\ninline fun a(x: int): int = x", "x"),
            ("inline fun main(x: int): int = x", "x"),
        ]
        for defs, expr in bad:
            with self.subTest(defs=defs, expr=expr), self.assertRaises(surface.SurfaceError):
                surface.parse(program(defs, expr))

    def test_spec_helpers_can_use_inline_helpers(self):
        task = surface.parse(program(
            "inline fun inc(a: int): int = a + 1\n"
            "spec fun twice(a: int): int decreases 0 = inc(inc(a))",
            "twice(x)", ensures="r == x + 2"))
        self.assertEqual(5, run(task, x=3))
        self.assertEqual([], check_wf.check_wf(task))
        for defs in (
            "spec fun foo(a: int): int decreases 0 = a\ninline fun foo(a: int): int = a",
            "spec fun foo(a: int): int decreases 0 = a\ninline fun bar(a: int): int = foo(a)",
        ):
            with self.assertRaises(surface.SurfaceError):
                surface.parse(program(defs, "x"))

    def test_source_positions_survive_expansion(self):
        positions = {}
        task = surface.parse(program("inline fun inc(a: int): int = a + 1", "inc(x)"),
                             positions=positions)
        self.assertIn(id(task["body"][0]["assign"][1]), positions)
        with self.assertRaises(surface.SurfaceError) as raised:
            surface.parse(program("inline fun bad(a: int): bool = a", "x"))
        self.assertEqual("InlineFun", raised.exception.production)
        self.assertEqual(2, raised.exception.line)

    def test_contextual_keyword_and_version(self):
        text = "t 0 task inline(inline: int) returns (r: int) ensures r == inline { r := inline; }"
        self.assertEqual(4, run(surface.parse(text), inline=4))
        with self.assertRaises(surface.SurfaceError):
            surface.parse(program("inline fun inc(a: int): int = a + 1", "inc(x)").replace("t 1", "t 0", 1))

    def test_expansion_budget(self):
        task = surface.parse(program("", "x"))
        helper = {"name": "inc", "params": [{"name": "a", "type": "int"}],
                  "result": "int", "body": {"var": "a"}}
        with self.assertRaisesRegex(expand_helpers.ExpansionError, "budget"):
            expand_helpers.expand_task(task, [helper], max_nodes=2)

    def test_probe_sources_round_trip(self):
        for path in sorted((Path(__file__).parent / "inline-probes").glob("*.t")):
            with self.subTest(path=path.name):
                task = surface.parse_file(str(path))
                self.assertEqual([], check_wf.check_wf(task))
                self.assertEqual(task, surface.parse(surface.print_task(task)))

    def test_probes_expand_to_handwritten_core_expressions(self):
        # Independent source forms establish that the backend inputs are the
        # same old constructs, including the probes the current suite refuses.
        references = {
            "inline_scalar": "(x + 1) + 1",
            "inline_seq": "[x] + [x + 1]",
            "inline_pair": "(x / y, x % y)",
            "inline_nested": "[[x]]",
            "inline_hygiene": "forall inlineVar0 in [0, 1) . j >= inlineVar0",
            "inline_guard": "if len(s) > 0 then s[0] else 0",
            "inline_spec": "twice(x)",
        }
        for name, expression in references.items():
            task = surface.parse_file(str(Path(__file__).parent / "inline-probes" / (name + ".t")))
            self.assertEqual(surface.parse_expr(expression), task["body"][0]["assign"][1], name)
            if name == "inline_spec":
                self.assertEqual(surface.parse_expr("(a + 1) + 1"), task["spec_funs"][0]["body"])

    def test_grammar_accepts_helper_syntax(self):
        try:
            from xgrammar import Grammar
            from xgrammar.testing import _is_grammar_accept_string
        except ImportError:
            self.skipTest("xgrammar is in the lab ML environment")
        root = Path(__file__).parent
        grammar = Grammar.from_ebnf("\n".join(
            s for s in (root / "t.gbnf").read_text().splitlines()
            if not s.lstrip().startswith("#")))
        for path in sorted((root / "inline-probes").glob("*.t")):
            with self.subTest(path=path.name):
                self.assertTrue(_is_grammar_accept_string(grammar, path.read_text()))


if __name__ == "__main__":
    unittest.main()
