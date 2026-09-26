"""Relabeling verified-but-wrong programs: the population, the gates, the one-target rule, the rows."""
import copy
import io
import json
import random
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import loop_dataset as dataset
import loop_filter
import relabel
import spec_check
import spec_experiment as se
import surface

# fixture ids: MBPP-shaped (below the HumanEval base) and outside every real list
TRAIN_INC, TRAIN_DBL, TRAIN_ADD, TRAIN_INC_TWIN = 1001, 1002, 1003, 1004
HELD_OUT, LISTED, DEV = 2001, 3001, 4001
LISTED_POLICY = loop_filter.Decontamination(frozenset(), frozenset({LISTED}), frozenset())


def entry(tid, fn, code, points, text="Write a function."):
    pts = [{"ok": True, "fn": fn, "args": [("int", a) for a in args], "expected": ("int", expected)}
           for args, expected in points]
    tests = [f"assert {fn}({', '.join(str(a) for a in args)}) == {expected}" for args, expected in points]
    return {"rec": {"task_id": tid, "text": text, "code": code, "test_list": tests}, "points": pts, "fn": fn}


def fixture_pool(with_twin=True):
    # a + 2, not a + 1: "first argument plus one" is one of spec_check's lazy programs, and a
    # problem a lazy program answers at every point is refused as a target on purpose
    pool = {
        TRAIN_INC: entry(TRAIN_INC, "inc", "def inc(a):\n    return a + 2\n", [((1,), 3), ((5,), 7), ((0,), 2)],
                         "Write a function to add two."),
        TRAIN_DBL: entry(TRAIN_DBL, "dbl", "def dbl(a):\n    return a * 2\n", [((1,), 2), ((3,), 6), ((0,), 0)],
                         "Write a function to double a number."),
        TRAIN_ADD: entry(TRAIN_ADD, "add", "def add(a, b):\n    return a + b\n",
                         [((1, 2), 3), ((5, 5), 10), ((0, 0), 0)], "Write a function to add two numbers."),
        HELD_OUT: entry(HELD_OUT, "inc_eval", "def inc_eval(a):\n    return a + 2\n", [((2,), 4), ((4,), 6)]),
        LISTED: entry(LISTED, "inc_listed", "def inc_listed(a):\n    return a + 2\n", [((2,), 4), ((4,), 6)]),
        DEV: entry(DEV, "inc_dev", "def inc_dev(a):\n    return a + 2\n", [((2,), 4), ((4,), 6)]),
    }
    if with_twin:
        pool[TRAIN_INC_TWIN] = entry(TRAIN_INC_TWIN, "plus_two", "def plus_two(a):\n    return a + 2\n",
                                     [((2,), 4), ((7,), 9), ((0,), 2)], "Write a function that adds 2.")
    return pool


def task(text):
    return surface.parse("t 0\n" + text.strip() + "\n")


TRAIN_TENS = 1009


def tens_entry():
    # triples, with examples at 10, 0 and 30: draws shaped like them reach 0..20, 0..2 and 0..60
    return entry(TRAIN_TENS, "tens", "def tens(a):\n    return a * 3\n", [((10,), 30), ((0,), 0), ((30,), 90)],
                 "Write a function to triple a multiple of ten.")


# passes dbl's three points, its ensures holds of every reference output, and the body computes a
# different function above 3: only executing it on the draws catches that (review of 2026-09-25,
# mbpp_577 last_Digit_Factorial: `ensures r == 0 or ... or r == 7` admitted a body returning n)
WEAK = ("fail", "task mbpp_2011__weak(a: int) returns (r: int)\n  ensures r >= 0\n"
                "{ if a <= 3 { r := a * 2; } else { r := a; } }")
# right on every draw inside its precondition, and the precondition admits one draw in ten
NARROW = ("fail", "task mbpp_2012__tens(a: int) returns (r: int)\n"
                  "  requires a == 0 or a == 10 or a == 20 or a == 30 or a == 40 or a == 50 or a == 60\n"
                  "  ensures r == a * 3\n{ r := a * 3; }")


PROGRAMS = {
    # written for the held-out problem, fails its tests there, computes a + 2: the relabel candidate
    "mbpp_2001__foo": ("fail", "task mbpp_2001__foo(a: int) returns (r: int)\n  ensures r == a + 2\n{ r := a + 2; }"),
    # doubles: the only train problem it fits is dbl
    "mbpp_2002__bar": ("fail", "task mbpp_2002__bar(a: int) returns (r: int)\n  ensures r == a * 2\n{ r := a * 2; }"),
    # passes inc's points but its specification says a + 3: the reference disagrees on a draw
    "mbpp_2003__baz": ("fail", "task mbpp_2003__baz(a: int) returns (r: int)\n  ensures r == a + 3\n{ r := a + 2; }"),
    # tests pass: not wrong, not in the population
    "mbpp_2004__ok": ("pass", "task mbpp_2004__ok(a: int) returns (r: int)\n  ensures r == a\n{ r := a; }"),
    # one decorative cell: not proven in seven, not in the population
    "mbpp_2005__six": ("fail", "task mbpp_2005__six(a: int) returns (r: int)\n  ensures r == a\n{ r := a; }"),
    # a signature failure on its own problem, fits add
    "mbpp_2006__two": ("signature", "task mbpp_2006__two(a: int, b: int) returns (r: int)\n"
                                    "  ensures r == a + b\n{ r := a + b; }"),
    # counted wrong-but-proven, task file deliberately missing
    "mbpp_2007__gone": ("fail", None),
}


def write_tag(root: Path, tag: str, programs=PROGRAMS, clean_all=True):
    d = root / tag
    (d / "tasks").mkdir(parents=True)
    (d / "raw").mkdir()
    cols = list(spec_check.KERNELS)
    lines = ["| task | " + " | ".join(cols) + " |", "|---|" + "---|" * 7]
    tests = {}
    for name, (overall, text) in programs.items():
        cells = ["verified / refuted"] * 7
        if name.endswith("__six"):
            cells[3] = "verified / decorative"
        lines.append("| " + name + " | " + " | ".join(cells) + " |")
        tid = loop_filter.problem_id(name)
        tests[str(tid)] = {"name": name, "overall": overall, "points": []}
        if text is not None:
            (d / "tasks" / f"{name}.json").write_text(json.dumps(task(text)))
    (d / "kernels.md").write_text("\n".join(lines) + "\n")
    (d / "tests.json").write_text(json.dumps(tests))
    return d


def gates(split_ids=(HELD_OUT,)):
    return relabel.Gates(frozenset(split_ids), frozenset({LISTED}), frozenset({DEV}))


def train_ids():
    return {TRAIN_INC, TRAIN_DBL, TRAIN_ADD, TRAIN_INC_TWIN, LISTED, DEV}


class PopulationTests(unittest.TestCase):
    def test_wrong_but_proven_is_clean_seven_with_failing_tests(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = write_tag(Path(tmp), "arm")
            programs, info = relabel.wrong_but_proven("arm", d)
        names = [p["name"] for p in programs]
        self.assertEqual(names, ["mbpp_2001__foo", "mbpp_2002__bar", "mbpp_2003__baz", "mbpp_2006__two"])
        self.assertEqual(info["wrong_but_proven"], 5)
        self.assertEqual(info["no_task_file"], ["mbpp_2007__gone"])
        self.assertTrue(info["seven_kernels"])
        self.assertEqual(programs[0]["source_id"], HELD_OUT)
        self.assertEqual(programs[3]["tests"], "signature")

    def test_sets_are_read_from_every_root_and_a_tag_graded_twice_differently_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_tag(root / "lab", "arm")
            write_tag(root / "desk", "other")
            sets = relabel.graded_sets([root / "lab", root / "desk"])
            self.assertEqual(sorted(sets), ["arm", "other"])
            write_tag(root / "desk", "arm")                                  # identical copy: one set
            self.assertEqual(relabel.graded_sets([root / "lab", root / "desk"])["arm"], root / "lab" / "arm")
            (root / "desk" / "arm" / "tests.json").write_text("{}")
            with self.assertRaisesRegex(SystemExit, "arm: graded differently"):
                relabel.graded_sets([root / "lab", root / "desk"])

    def test_a_table_without_the_seven_kernels_contributes_nothing_and_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = write_tag(Path(tmp), "arm")
            (d / "kernels.md").write_text("| task | lean |\n|---|---|\n| mbpp_2001__foo | verified / refuted |\n")
            programs, info = relabel.wrong_but_proven("arm", d)
        self.assertEqual(programs, [])
        self.assertFalse(info["seven_kernels"])

    def test_copies_of_one_program_are_tested_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            same = {"mbpp_2001__foo": PROGRAMS["mbpp_2001__foo"],
                    "mbpp_2008__other": ("fail", "task mbpp_2008__other(a: int) returns (r: int)\n"
                                                 "  ensures r == a + 2\n{ r := a + 2; }")}
            programs = []
            for tag in ("arm-a", "arm-b"):
                programs += relabel.wrong_but_proven(tag, write_tag(root, tag, same))[0]
        distinct = relabel.distinct_programs(programs)
        self.assertEqual(len(distinct), 1)
        self.assertEqual(distinct[0]["copies"], [("arm-a", "mbpp_2001__foo"), ("arm-a", "mbpp_2008__other"),
                                                ("arm-b", "mbpp_2001__foo"), ("arm-b", "mbpp_2008__other")])


class GateTests(unittest.TestCase):
    def test_index_never_holds_a_held_out_listed_or_dev_id(self):
        index = relabel.target_index(fixture_pool(), train_ids() | {HELD_OUT}, gates())
        ids = {tid for tids in index.values() for tid in tids}
        self.assertEqual(ids, {TRAIN_INC, TRAIN_DBL, TRAIN_ADD, TRAIN_INC_TWIN})
        self.assertEqual(index[(("int",), "int")], [TRAIN_INC, TRAIN_DBL, TRAIN_INC_TWIN])
        self.assertEqual(index[(("int", "int"), "int")], [TRAIN_ADD])

    def test_a_gated_candidate_that_reaches_admission_is_refused_by_name(self):
        program = {"tag": "arm", "name": "mbpp_2001__foo", "task": task(PROGRAMS["mbpp_2001__foo"][1])}
        for poison, why in ((HELD_OUT, "held-out"), (LISTED, "listed"), (DEV, "dev-split")):
            with self.subTest(poison=poison):
                index = {(("int",), "int"): [TRAIN_INC, poison]}
                with self.assertRaisesRegex(SystemExit, f"problem {poison}: it is a {why}"):
                    relabel.targets_for(program, index, gates())

    def test_a_problem_whose_points_a_lazy_program_answers_is_never_a_target(self):
        pool = fixture_pool(with_twin=False)
        # one recorded point, [3] -> 3: the identity answers it, and so would `r := n`
        pool[1005] = entry(1005, "nth", "def nth(n):\n    return n\n", [((3,), 3)])
        pool[1006] = entry(1006, "always", "def always(a):\n    return 1\n", [((0,), 1), ((9,), 1)])
        # a + 1 at every point is "first argument plus one", one of the lazy programs, so refused too
        pool[1007] = entry(1007, "succ", "def succ(a):\n    return a + 1\n", [((1,), 2), ((5,), 6)])
        lazy = relabel.undiscriminating(pool, {1005, 1006, 1007, TRAIN_INC, TRAIN_DBL, TRAIN_ADD})
        self.assertEqual(lazy, {1005: ["returns its first argument"], 1006: ["constant one"],
                                1007: ["first argument plus one"]})
        index = relabel.target_index(pool, train_ids() | {1005, 1006, 1007}, gates(), frozenset(lazy))
        self.assertEqual(index[(("int",), "int")], [TRAIN_INC, TRAIN_DBL])
        self.assertEqual(relabel.lazy_points(pool[TRAIN_INC]), [])
        self.assertEqual(relabel.lazy_points({"points": []}), [])

    def test_seq_of_seq_points_fold_onto_a_seq_parameter(self):
        e = {"points": [{"args": [("seq-of-seq", [[1]]), ("int", 1)], "expected": ("seq-of-seq", [[1]])}]}
        self.assertEqual(relabel.problem_signature(e), (("seq", "int"), "seq"))
        self.assertIsNone(relabel.problem_signature({"points": []}))


class RelabelTests(unittest.TestCase):
    def outcomes(self, pool, programs=PROGRAMS):
        with tempfile.TemporaryDirectory() as tmp:
            d = write_tag(Path(tmp), "arm", programs)
            found, _info = relabel.wrong_but_proven("arm", d)
        index = relabel.target_index(pool, train_ids(), gates())
        return {p["name"]: relabel.relabel_program(p, relabel.targets_for(p, index, gates()), pool, 20, 1)
                for p in relabel.distinct_programs(found)}

    def test_exactly_one_qualifying_target_admits_a_row_for_that_problem(self):
        pool = fixture_pool(with_twin=False)
        out = self.outcomes(pool)
        foo = out["mbpp_2001__foo"]
        self.assertEqual(foo["kind"], "admitted")
        self.assertEqual(foo["targets_tried"], 2)                       # inc and dbl share the signature
        self.assertEqual(foo["tally"], {"qualifies": 1, "tests-fail": 1})
        row = relabel.pool_row(foo, pool, "v5", 20, 1, "v5")
        self.assertEqual((row["task_id"], row["task"], row["source"]), (TRAIN_INC, "mbpp_1001__inc", "relabel"))
        self.assertIn("task mbpp_1001__inc(a: int) returns (r: int)", row["chosen"])
        self.assertNotIn("2001", row["chosen"])
        self.assertEqual(row["prompt"][1]["role"], "user")
        self.assertIn("Write a function to add two.", row["prompt"][1]["content"])
        prov = row["relabel"]
        self.assertEqual((prov["tag"], prov["from_problem_id"], prov["copies"], prov["targets_tried"]),
                         ("arm", HELD_OUT, 1, 2))
        self.assertEqual((prov["targets_passed_tests"], prov["points"], prov["draws"], prov["shapes"],
                          prov["pool"]), (1, 3, 60, 3, "v5"))
        self.assertEqual((prov["executed"], prov["executed_excluded"], prov["executed_reference_raised"],
                          prov["executed_total"], prov["executed_fraction"]), (60, 0, 0, 60, 1.0))
        self.assertEqual(prov["task_sha256"], spec_check.task_sha256(foo["qualifying"][0]["task"]))
        # the row names the held-out source only as an integer: no alias anywhere in it
        check = loop_filter.validate_training_data(json.dumps(row), {HELD_OUT}, names=[row["task"]],
                                                   task_ids=[row["task_id"]], policy=LISTED_POLICY)
        self.assertTrue(check.ok)
        self.assertEqual(out["mbpp_2002__bar"]["kind"], "admitted")
        self.assertEqual(out["mbpp_2002__bar"]["qualifying"][0]["task_id"], TRAIN_DBL)
        self.assertEqual(out["mbpp_2006__two"]["kind"], "admitted")
        self.assertEqual(out["mbpp_2006__two"]["qualifying"][0]["name"], "mbpp_1003__add")

    def test_a_specification_the_reference_disagrees_with_is_not_relabeled(self):
        out = self.outcomes(fixture_pool(with_twin=False))
        baz = out["mbpp_2003__baz"]
        self.assertEqual(baz["kind"], "no-target")
        self.assertEqual(baz["tally"], {"spec-disagrees": 1, "tests-fail": 1})

    def test_two_qualifying_targets_are_a_duplicate_pair_and_nothing_is_admitted(self):
        out = self.outcomes(fixture_pool(with_twin=True))
        foo = out["mbpp_2001__foo"]
        self.assertEqual(foo["kind"], "ambiguous")
        dup = relabel.duplicate_row(foo, "v5")
        self.assertEqual(dup["problem_ids"], [TRAIN_INC, TRAIN_INC_TWIN])
        self.assertEqual(dup["kind"], "one-program-solves-both")
        self.assertEqual([e["draws"] for e in dup["evidence"]], [60, 60])

    def test_every_stated_example_shapes_the_draws_so_a_lookup_table_is_caught(self):
        """The reference is n > 10; the points are 1 -> false, 7 -> false, 16 -> true. A table that
        says only 16 passes the points and agrees on every draw shaped like the first example
        (0..2), and is caught by the draws shaped like the second (0..14: 11 to 14 are true)."""
        pool = fixture_pool(with_twin=False)
        pool[1008] = entry(1008, "big", "def big(n):\n    return n > 10\n", [((1,), False), ((7,), False), ((16,), True)])
        pool[1008]["points"] = [{"ok": True, "fn": "big", "args": [("int", a)], "expected": ("bool", e)}
                                for a, e in ((1, False), (7, False), (16, True))]
        table = task("task mbpp_2009__table(n: int) returns (r: bool)\n  ensures r == (n == 16)\n{ r := n == 16; }")
        honest = task("task mbpp_2010__gt(n: int) returns (r: bool)\n  ensures r == (n > 10)\n{ r := n > 10; }")
        caught = relabel.qualify(table, pool[1008], 1008, 50, 1)
        self.assertEqual((caught["status"], caught["shape"]), ("spec-disagrees", 1))
        first_only = relabel.qualify(table, {**pool[1008], "points": pool[1008]["points"][:1]}, 1008, 50, 1)
        self.assertEqual(first_only["status"], "qualifies")       # the old evidence, one shape, let it through
        ok = relabel.qualify(honest, pool[1008], 1008, 50, 1)
        self.assertEqual((ok["status"], ok["shapes"], ok["draws"]), ("qualifies", 3, 150))

    def test_a_weak_specification_that_hides_a_different_function_is_caught_by_executing_the_program(self):
        """The specification check alone (check_task) agrees with the reference on every draw, because
        `r >= 0` is true of every doubled value; the program still returns a, not 2a, above 3."""
        pool = fixture_pool(with_twin=False)
        weak = task(WEAK[1])
        spec_only = spec_check.check_task(se.rename_task(copy.deepcopy(weak), "mbpp_1002__dbl"), pool[TRAIN_DBL],
                                          20, random.Random(1))
        self.assertEqual(spec_only["status"], "agrees")                # the old gate let it through
        out = relabel.qualify(weak, pool[TRAIN_DBL], TRAIN_DBL, 20, 1)
        self.assertEqual(out["status"], "exec-fail")
        self.assertEqual(out["shape"], 1)                              # draws shaped like 3 reach 4..6
        w = out["witness"]
        self.assertEqual((w["args"], w["reference_said"], w["program_said"]), (w["args"], 2 * w["args"][0], w["args"][0]))
        self.assertGreater(w["args"][0], 3)
        honest = relabel.qualify(task(PROGRAMS["mbpp_2002__bar"][1]), pool[TRAIN_DBL], TRAIN_DBL, 20, 1)
        self.assertEqual(honest["status"], "qualifies")
        self.assertEqual((honest["executed"], honest["executed_excluded"], honest["executed_reference_raised"],
                          honest["executed_total"]), (60, 0, 0, 60))
        # through relabel_program the verdict is a refusal with its own name, not a silent no-target
        found = relabel.distinct_programs([{"tag": "arm", "name": "mbpp_2011__weak", "task": weak,
                                            "source_id": 2011, "tests": "fail"}])
        index = relabel.target_index(pool, train_ids(), gates())
        outcome = relabel.relabel_program(found[0], relabel.targets_for(found[0], index, gates()), pool, 20, 1)
        self.assertEqual((outcome["kind"], outcome["tally"]), ("no-target", {"tests-fail": 1, "exec-fail": 1}))

    def test_a_program_the_reference_cannot_run_on_any_draw_is_refused_not_admitted_on_its_points(self):
        pool = fixture_pool(with_twin=False)
        pool[TRAIN_DBL]["rec"]["code"] = "def dbl(a):\n    raise ValueError(a)\n"
        out = relabel.qualify(task(PROGRAMS["mbpp_2002__bar"][1]), pool[TRAIN_DBL], TRAIN_DBL, 20, 1)
        self.assertEqual(out["status"], "spec-no valid draws")         # check_task refuses first
        pool[TRAIN_DBL]["rec"]["code"] = "def dbl(a):\n    return a * 2\n"
        with patch.object(spec_check, "check_task", return_value={"status": "agrees", "draws": 5}):
            pool[TRAIN_DBL]["rec"]["code"] = "def dbl(a):\n    raise ValueError(a)\n"
            out = relabel.qualify(task(PROGRAMS["mbpp_2002__bar"][1]), pool[TRAIN_DBL], TRAIN_DBL, 20, 1)
        self.assertEqual(out["status"], "exec-no valid draws")
        self.assertEqual(out["executed_reference_raised"], 60)

    def test_a_narrow_precondition_is_recorded_not_refused(self):
        pool = fixture_pool(with_twin=False)
        pool[TRAIN_TENS] = tens_entry()
        out = relabel.qualify(task(NARROW[1]), pool[TRAIN_TENS], TRAIN_TENS, 50, 1)
        self.assertEqual(out["status"], "qualifies")
        self.assertEqual(out["executed"] + out["executed_excluded"], out["executed_total"])
        self.assertEqual(out["executed_total"], 150)
        self.assertLess(out["executed_fraction"], 0.25)
        self.assertGreater(out["executed"], 0)

    def test_a_candidate_the_oracles_cannot_decide_blocks_admission_elsewhere(self):
        """foo (a + 2) qualifies for inc; the twin's reference raises on every draw, so the twin's pair is
        undecided, not refused: foo passed every one of the twin's points and may solve it too, and one
        target plus one undecided candidate is not "exactly one target". The lab run of 2026-09-26 found
        the case for real: eight Fibonacci programs qualified for mbpp_960 and exceeded the interpreter's
        budget on the larger draws of mbpp_873 and he_55, which they also solve at every point."""
        pool = fixture_pool(with_twin=True)
        pool[TRAIN_INC_TWIN]["rec"]["code"] = "def plus_two(a):\n    raise ValueError(a)\n"
        out = self.outcomes(pool)
        foo = out["mbpp_2001__foo"]
        self.assertEqual(foo["kind"], "undecided")
        self.assertEqual(foo["tally"], {"qualifies": 1, "spec-no valid draws": 1, "tests-fail": 1})
        self.assertEqual([r["task_id"] for r in foo["undecided"]], [TRAIN_INC_TWIN])
        self.assertEqual(out["mbpp_2002__bar"]["kind"], "admitted")
        self.assertEqual(out["mbpp_2002__bar"]["undecided"], [])
        # the budget is an undecided verdict too, and a refused pair (a disagreement) is not
        for status, expect in (("exec-budget", True), ("exec-no valid draws", True), ("spec-reference did not finish", True),
                               ("exec-fail", False), ("exec-crash", False), ("exec-undefined", False),
                               ("spec-disagrees", False), ("spec-contradicts-example", False), ("tests-fail", False),
                               ("signature", False), ("qualifies", False)):
            self.assertEqual(relabel.undecided(status), expect, status)

    def test_verdicts_do_not_depend_on_visiting_order(self):
        pool = fixture_pool(with_twin=False)
        a = self.outcomes(pool)
        b = self.outcomes(pool, dict(reversed(list(PROGRAMS.items()))))
        for name in a:
            self.assertEqual(a[name]["kind"], b[name]["kind"])
            self.assertEqual([r["draws"] for r in a[name]["qualifying"]],
                             [r["draws"] for r in b[name]["qualifying"]])


class MainTests(unittest.TestCase):
    def test_main_writes_rows_duplicates_and_report(self):
        pool = fixture_pool(with_twin=True)
        pool[TRAIN_TENS] = tens_entry()
        programs = {**PROGRAMS, "mbpp_2011__weak": WEAK, "mbpp_2012__tens": NARROW}
        with tempfile.TemporaryDirectory() as tmp:
            here = Path(tmp)
            write_tag(here / "sets", "arm", programs)
            write_tag(here / "sets", "cmp-arm", {"mbpp_2002__bar": PROGRAMS["mbpp_2002__bar"]})
            split = here / "split.json"
            split.write_text(json.dumps({"pool": "v5", "pool_size": len(pool),
                                         "train_ids": sorted(train_ids() | {TRAIN_TENS}), "eval_ids": [HELD_OUT]}))
            out, report = here / "loop" / "relabel-x.jsonl", here / "REPORT.md"
            argv = ["--split", str(split), "--out", str(out), "--root", str(here / "sets"), "--n", "50",
                    "--report", str(report), "--exclude-tags", "cmp-*"]
            with patch.object(relabel.se, "pool", return_value=pool), \
                    patch.object(loop_filter, "decontamination", return_value=LISTED_POLICY), \
                    patch.object(loop_filter, "r12_dev_ids", return_value=frozenset({DEV})), \
                    redirect_stdout(io.StringIO()):
                self.assertEqual(relabel.main(argv), 0)
                rows = [json.loads(line) for line in out.read_text().splitlines()]
                dups = [json.loads(line) for line in (here / "loop" / "relabel-duplicates-x.jsonl").read_text().splitlines()]
                text = report.read_text()
                # a pattern that excludes nothing that exists is a typo, and is refused
                with self.assertRaisesRegex(SystemExit, "--exclude-tags"):
                    relabel.main(argv[:-1] + ["nothing-*"])
                # a pool that shrank is refused, not silently searched
                split.write_text(json.dumps({"pool": "v5", "pool_size": len(pool) + 5,
                                             "train_ids": sorted(train_ids()), "eval_ids": [HELD_OUT]}))
                with self.assertRaisesRegex(SystemExit, "pool"):
                    relabel.main(argv)
        self.assertEqual([(r["task_id"], r["task"]) for r in rows],
                         [(TRAIN_DBL, "mbpp_1002__dbl"), (TRAIN_ADD, "mbpp_1003__add"), (TRAIN_TENS, "mbpp_1009__tens")])
        self.assertTrue(all(r["relabel"]["executed"] > 0 for r in rows))
        self.assertEqual([d["problem_ids"] for d in dups], [[TRAIN_INC, TRAIN_INC_TWIN]])
        self.assertIn("| **programs admitted (exactly one target)** | **3** |", text)
        self.assertIn("| programs with two or more targets (duplicate pairs, not admitted) | 1 |", text)
        self.assertIn("| programs with one target and a candidate the oracles could not decide (not admitted) | 0 |", text)
        self.assertIn("| wrong-but-proven rows | 7 |", text)
        self.assertIn("| exec-fail | 1 |", text)
        self.assertIn("`arm/mbpp_2007__gone`", text)
        self.assertIn("## The 10 largest per-signature groups", text)
        self.assertIn("38/400", text)
        self.assertIn("| candidates refused: their own points cannot reject a lazy program | 0 |", text)
        self.assertIn("## What was learned", text)
        # the source ids 2002, 2006 and 2012 are in neither half of the split: said so, not called train
        self.assertIn("| not in the split (neither a train nor an eval id) | 3 |", text)
        self.assertNotIn("| train |", text)
        # the narrow row is listed with its counts, and admitted
        self.assertIn("### Admitted rows whose draws mostly fell outside the program's precondition", text)
        self.assertIn(f"| {TRAIN_TENS} | `mbpp_1009__tens` | arm |", text)
        self.assertIn("filter_too_much", text)
        # one positive per problem on the samples path, every distinct program here: said in the report
        self.assertIn("one positive per (task_id, source, task)", text)
        # the excluded set is named, and absent from the per-set table
        self.assertIn("excluded by `--exclude-tags cmp-*`: cmp-arm", text)
        self.assertNotIn("| cmp-arm |", text)
        self.assertNotIn(str(Path.home()), text)


# ----------------------------------------------------------- loop_dataset --

def relabel_row(tid=1, name="mbpp_1__g", body=None, pool="v5", **provenance):
    text = body or f"task {name}(a: int) returns (r: int)\n  ensures r == a + 1\n{{ r := a + 1; }}"
    t = task(text)
    return {"task_id": tid, "task": name, "source": "relabel",
            "prompt": [{"role": "user", "content": "Problem: add one"}],
            "chosen": dataset.fence(surface.print_task(t)),
            "relabel": {"tag": "arm", "from_problem_id": 2, "from_task_sha256": "0" * 64, "copies": 1,
                        "targets_tried": 1, "task_sha256": spec_check.task_sha256(t), "pool": pool,
                        **provenance}}


class RelabelRowsInputTests(unittest.TestCase):
    def load(self, rows, train=(1, 3), evals=(2,), pool=(1, 2, 3), pool_name="v5"):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "relabel.jsonl"
            path.write_text("".join(json.dumps(r) + "\n" for r in rows))
            with patch.object(loop_filter, "decontamination", return_value=loop_filter.Decontamination(
                        frozenset(), frozenset({3}), frozenset())), \
                    patch.object(loop_filter, "r12_dev_ids", return_value=frozenset({5})):
                return dataset.load_relabel_rows(path, set(train), set(evals), {tid: {} for tid in pool},
                                                 pool_name, None)

    def test_rows_are_read_with_their_provenance(self):
        rows = self.load([relabel_row()])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source"], "relabel")

    def test_a_row_for_a_gated_or_foreign_problem_stops_the_build_by_name(self):
        cases = [
            (relabel_row(tid=2, name="mbpp_2__g"), "held-out"),
            (relabel_row(tid=3, name="mbpp_3__g"), "listed same-task"),
            (relabel_row(tid=5, name="mbpp_5__g"), "dev-split"),
            (relabel_row(tid=9, name="mbpp_9__g"), "not a train-split id"),
            (relabel_row(tid=1, name="mbpp_4__g"), "does not name problem 1"),
            (relabel_row(tid=1, pool="v6"), "pool"),
            ({**relabel_row(), "source": "samples"}, "not a relabel row"),
            ({**relabel_row(), "relabel": {**relabel_row()["relabel"], "task_sha256": "stale"}}, "task_sha256"),
            ({**relabel_row(), "relabel": {**relabel_row()["relabel"], "note": "was mbpp_2__g"}}, "held-out"),
            ({**relabel_row(), "prompt": None}, "no prompt"),
        ]
        for row, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(SystemExit, message):
                    self.load([row], train=(1, 3, 5, 7), pool=(1, 2, 3, 5, 7, 9))

    def test_a_row_for_a_train_id_outside_the_pool_is_refused(self):
        with self.assertRaisesRegex(SystemExit, "not in pool"):
            self.load([relabel_row(tid=7, name="mbpp_7__g")], train=(1, 7), pool=(1,))

    def test_rows_join_the_sft_set_with_source_kept_and_are_not_doubled(self):
        row = relabel_row()
        sft = [{"prompt": ["p"], "chosen": "x", "source": "samples", "task_id": 1, "task": "mbpp_1__f"}]
        counts = dataset.append_relabel_rows(sft, [row, row])
        self.assertEqual(counts, {"read": 2, "appended": 1, "already_positive": 1, "per_problem": {1: 1}})
        self.assertEqual([s["source"] for s in sft], ["relabel", "samples"])
        self.assertEqual(sft[0]["relabel"]["pool"], "v5")
        same = dict(sft[1], source="relabel", chosen=row["chosen"])
        counts = dataset.append_relabel_rows([same], [row])
        self.assertEqual(counts["already_positive"], 1)

    def test_from_samples_build_appends_relabel_rows_after_its_own_positives(self):
        import test_loop_dataset as fixture
        with tempfile.TemporaryDirectory() as tmp:
            here = Path(tmp)
            tag = here / "tag"
            (tag / "tasks").mkdir(parents=True)
            (tag / "raw").mkdir()
            s = fixture.sample(tid=1)
            (tag / "tasks" / f"{s['name']}.json").write_text(json.dumps(s["task"]))
            (tag / "raw" / "1.json").write_text(json.dumps({"messages": s["prompt"]}))
            (tag / "extract.json").write_text(json.dumps({"1": {"stage": "task", "name": s["name"]}}))
            (tag / "tests.json").write_text(json.dumps({"1": {"overall": "pass"}}))
            cols = spec_check.KERNELS
            (tag / "kernels.md").write_text("| task | " + " | ".join(cols) + " |\n|---|" + "---|" * 7 + "\n"
                                            + "| " + s["name"] + " | " + " | ".join(["verified / refuted"] * 7) + " |\n")
            out = here / "out/loop"
            out.mkdir(parents=True)
            (here / "out/spec-disagree.json").write_text(json.dumps({"results": fixture.evidence(s)}))
            split_path = here / "split.json"
            split_path.write_text(json.dumps({"pool": "v5", "train_ids": [1, 3], "eval_ids": [2]}))
            rows_path = here / "relabel.jsonl"
            rows_path.write_text(json.dumps(relabel_row(tid=3, name="mbpp_3__g")) + "\n")
            args = SimpleNamespace(from_samples=["checked"], split=str(split_path), min_kernels=7, include=None,
                                   out_suffix="fixture", relabel_rows=str(rows_path))

            def negative(sample, _, *_evidence):
                p = fixture.pair(sample)
                return [{key: p[key] for key in ("kind", "operator", "witness", "rejected", "neg_tag", "neg_sample_index")}]

            with patch.object(dataset, "HERE", here), patch.object(dataset, "OUT", out), \
                    patch.object(dataset.spec_experiment, "outdir", return_value=tag), \
                    patch.object(dataset.spec_experiment, "pool", return_value={1: {}, 2: {}, 3: {}}), \
                    patch.object(dataset, "negatives_for_positive", side_effect=negative), \
                    patch.object(loop_filter, "r12_dev_ids", return_value=frozenset()), \
                    redirect_stdout(io.StringIO()):
                self.assertEqual(dataset.run_from_samples(args), 0)
                sft = [json.loads(line) for line in (out / "sft-fixture.jsonl").read_text().splitlines()]
                pairs = [json.loads(line) for line in (out / "pairs-fixture.jsonl").read_text().splitlines()]
                report = (out / "DATASET-fixture.md").read_text()
                # a relabel row for the held-out id stops the build, and no file is written
                rows_path.write_text(json.dumps(relabel_row(tid=2, name="mbpp_2__g")) + "\n")
                args.out_suffix = "refused"
                with self.assertRaisesRegex(SystemExit, "held-out"):
                    dataset.run_from_samples(args)
                self.assertFalse((out / "sft-refused.jsonl").exists())
        self.assertEqual([(r["task_id"], r["source"]) for r in sft], [(1, "samples"), (3, "relabel")])
        self.assertEqual([p["task_id"] for p in pairs], [1])
        self.assertIn("appended 1 to `sft-fixture.jsonl` with `source: relabel` kept", report)
        self.assertIn("one positive per (task_id, source, task)", report)
        self.assertIn("1 relabeled row(s) on 1 problem(s); the most loaded: 3 (1)", report)
        self.assertIn("--relabel-rows", report)


if __name__ == "__main__":
    unittest.main()
