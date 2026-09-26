"""The lift's twin gate on drawn inputs: t/twin_draws.py, lift_corpora.twin_of and lift_corpora --recover-twins.

The gate refused a lifted program as the behavioural twin of a gated pool problem (held-out, dev split,
listed) when the program passed every one of that problem's test points. Those problems carry one to
three points, so the gate refused coincidences too. The rule now also runs the program against the
problem's reference on 100 inputs drawn like the problem's first point (EvalPlus's differential testing
against the ground truth on generated inputs of the seeds' shape, https://ar5iv.labs.arxiv.org/html/2305.01210):
one input both answer differently clears the program of that problem; agreement on every input both
answer, a reference that will not run, or no draw at all keeps the refusal. Fixture pools and programs
written in t; nothing is read from outside the test's own directory.
"""
import contextlib
import hashlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lift_corpora                                              # noqa: E402
import relabel                                                   # noqa: E402
import spec_experiment as se                                     # noqa: E402
import surface                                                   # noqa: E402
import twin_draws                                                # noqa: E402


def entry(fn: str, code: str, points: list, tests: list | None = None) -> dict:
    """A pool entry the way spec_experiment.pool() shapes one, from (args, expected) pairs of t values."""
    def kind(v):
        return ("bool" if isinstance(v, bool) else "int" if isinstance(v, int)
                else "seq-of-seq" if v and isinstance(v[0], list) else "seq")
    pts = [{"ok": True, "fn": fn, "args": [(kind(a), a) for a in args], "expected": (kind(exp), exp)}
           for args, exp in points]
    tests = tests or [f"assert {fn}({', '.join(repr(a) for a in args)}) == {exp!r}" for args, exp in points]
    return {"rec": {"task_id": 0, "text": fn, "code": code, "test_list": tests}, "points": pts, "fn": fn}


def program(name: str, params: str, returns: str, body: str) -> dict:
    """A t task from its surface text."""
    return surface.parse(f"t 1\ntask {name}({params}) returns ({returns})\n{{\n{body}\n}}\n")


# identity passes cube's three points (1, 0, -1); the draws shaped like 1 are 0, 1 and 2, and at 2 they differ
CUBE = entry("cube", "def cube(n):\n    return n * n * n\n", [([1], 1), ([0], 0), ([-1], -1)])
TWICE = entry("twice", "def twice(n):\n    return 2 * n\n", [([2], 4), ([0], 0), ([7], 14)])
BROKEN_SQUARE = entry("square", "def square(n)\n    return n * n\n", [([2], 4), ([0], 0), ([3], 9)])  # no colon
RAISES = entry("raises", "def raises(n):\n    raise ValueError('never')\n", [([2], 2), ([0], 0), ([7], 7)])
DISTINCT = entry("distinct", "def distinct(a):\n    return len(set(a))\n", [([[1, 2, 3]], 3), ([[5, 6]], 2), ([[9]], 1)])
LENGTH = entry("length", "def length(a):\n    return len(a)\n", [([[1, 2, 3]], 3), ([[5, 6]], 2), ([[9]], 1)])
EVEN_HALF = entry("even_half", "def even_half(n):\n    if n % 2:\n        raise ValueError('odd')\n    return n // 2\n",
                  [([4], 2), ([0], 0), ([2], 1)])
UPPER = entry("upper", "def upper(s):\n    return s.upper()\n", [([[104, 105]], [72, 73]), ([[97, 98, 99]], [65, 66, 67])],
              tests=["assert upper('hi') == 'HI'", "assert upper('abc') == 'ABC'"])

IDENTITY = program("vericoding_dx0001__identity", "x: int", "y: int", "  y := x;")
DOUBLE = program("vericoding_dx0002__double", "x: int", "y: int", "  y := x + x;")
SQUARE = program("humaneval_dafny_007_square__square", "x: int", "y: int", "  y := x * x;")
COUNT = program("vericoding_dx0003__count", "s: seq", "y: int", "  y := len(s);")
HALF_UP = program("vericoding_dx0004__half_up", "x: int", "y: int", "  y := (x + 1) / 2;")
ECHO = program("vericoding_dx0005__echo", "s: seq", "r: seq", "  r := s;")


def decide(task: dict, pool: dict):
    gates = relabel.Gates(held_out=frozenset(pool), listed=frozenset(), dev=frozenset())
    evidence: list = []
    twin = lift_corpora.twin_of(task, lift_corpora.gated_index(pool, gates), pool, gates,
                                twin_draws.runner(pool), evidence)
    return twin, evidence


class TwinRuleTests(unittest.TestCase):
    def test_three_points_matched_and_one_draw_differing_is_not_the_twin(self):
        twin, evidence = decide(IDENTITY, {1001: CUBE})
        self.assertIsNone(twin)
        [check] = evidence
        self.assertEqual((check["problem"], check["verdict"], check["twin"]), (1001, "differs", False))
        self.assertEqual(check["draws"], twin_draws.DRAWS)
        self.assertGreater(check["differed"], 0)
        self.assertEqual(check["agreed"] + check["differed"], check["answered_by_both"])
        self.assertEqual(check["witness"], {"input": [2], "program": 2, "reference": 8})

    def test_a_difference_on_too_few_draws_is_a_near_twin_and_stays_refused(self):
        # identity and cube differ on about a third of the draws shaped like 1; a line above
        # that fraction makes the same pair a near twin: refused, with the fraction recorded
        twin, [check] = decide(IDENTITY, {1001: CUBE})
        self.assertIsNone(twin)
        self.assertGreaterEqual(check["differ_fraction"], twin_draws.NEAR_TWIN_FRACTION)
        with mock.patch.object(twin_draws, "NEAR_TWIN_FRACTION", 0.9):
            twin, [check] = decide(IDENTITY, {1001: CUBE})
        self.assertEqual(twin, (1001, "held-out"))
        self.assertEqual((check["verdict"], check["twin"]), ("near twin", True))
        self.assertLess(check["differ_fraction"], 0.9)
        self.assertIn("near-equivalent", check["why"])

    def test_a_program_that_agrees_on_every_draw_stays_the_twin(self):
        twin, [check] = decide(DOUBLE, {1002: TWICE})
        self.assertEqual(twin, (1002, "held-out"))
        self.assertEqual((check["verdict"], check["twin"]), ("agrees", True))
        self.assertEqual(check["agreed"], check["answered_by_both"])
        self.assertGreater(check["agreed"], 0)
        self.assertEqual(check["differed"], 0)

    def test_a_reference_that_cannot_run_keeps_the_refusal(self):
        twin, [check] = decide(SQUARE, {1003: BROKEN_SQUARE})
        self.assertEqual(twin, (1003, "held-out"))
        self.assertEqual((check["verdict"], check["twin"]), ("no reference", True))
        self.assertEqual(check["answered_by_both"], 0)
        self.assertIn("does not load", check["why"])
        # a reference that loads and refuses every input is no evidence either: still the twin
        twin, [check] = decide(IDENTITY, {1007: RAISES})
        self.assertEqual(twin, (1007, "held-out"))
        self.assertEqual((check["verdict"], check["twin"]), ("no draw answered by both", True))
        self.assertEqual(check["reference_silent"], twin_draws.DRAWS)

    def test_a_program_matching_two_problems_and_twin_of_one_stays_refused(self):
        twin, evidence = decide(COUNT, {1004: DISTINCT, 1005: LENGTH})
        self.assertEqual(twin, (1005, "held-out"))
        self.assertEqual([(c["problem"], c["verdict"]) for c in evidence], [(1004, "differs"), (1005, "agrees")])

    def test_an_input_only_one_side_answers_is_dropped_never_a_difference(self):
        # the reference refuses odd numbers; on the even draws both answer, and alike
        twin, [check] = decide(HALF_UP, {1006: EVEN_HALF})
        self.assertEqual(twin, (1006, "held-out"))
        self.assertEqual(check["verdict"], "agrees")
        self.assertGreater(check["reference_silent"], 0)
        self.assertEqual(check["differed"], 0)

    def test_no_draw_possible_keeps_the_refusal(self):
        # a kind spec_check.draw cannot produce: the check cannot run, so the program stays the twin
        real = {"rec": {"task_id": 0, "text": "real", "code": "def real(x):\n    return x\n",
                        "test_list": ["assert real(5) == 5"]},
                "points": [{"ok": True, "fn": "real", "args": [("real", 5)], "expected": ("real", 5)}], "fn": "real"}
        task = json.loads(json.dumps(IDENTITY))
        task["params"][0]["type"] = task["returns"][0]["type"] = "real"
        twin, [check] = decide(task, {1008: real})
        self.assertEqual(twin, (1008, "held-out"))
        self.assertEqual((check["verdict"], check["twin"]), ("cannot draw", True))

    def test_a_string_problem_hands_the_reference_strings_and_reads_its_answer_as_the_programs_type(self):
        # upper('hi') is 'HI': the echo program passes neither point, so it is no candidate at all
        twin, evidence = decide(ECHO, {1009: UPPER})
        self.assertIsNone(twin)
        self.assertEqual(evidence, [])
        # a program answering like upper does agree with it, including on one-character draws
        upper = program("vericoding_dx0006__upper", "s: seq", "r: seq",
                        "  r := [];\n  var i: int := 0;\n  while i < len(s)\n    decreases len(s) - i\n  {\n"
                        "    if 97 <= s[i] and s[i] <= 122 {\n      r := r + [s[i] - 32];\n    } else {\n"
                        "      r := r + [s[i]];\n    }\n    i := i + 1;\n  }")
        twin, [check] = decide(upper, {1009: UPPER})
        self.assertEqual((twin, check["verdict"]), ((1009, "held-out"), "agrees"))
        self.assertEqual(check["answered_by_both"] + check["no_t_reading"] + check["program_silent"]
                         + check["reference_silent"] + check["unfaithful"], twin_draws.DRAWS)
        self.assertEqual(check["no_t_reading"], 0)


class ReadingTests(unittest.TestCase):
    """A reference's answer read as a value of the program's own type (the pool's own reading of an
    assertion's literal, plus the leniencies Python's == grants); no reading drops the draw."""

    def read(self, answer, like):
        return twin_draws.read_answer(twin_draws.answer_form(answer), like)

    def test_a_string_reads_by_the_programs_type(self):
        self.assertEqual(self.read("a", 97), 97)                 # a t character where the program returns an int
        self.assertEqual(self.read("a", (97,)), (97,))           # a one-character string where it returns a seq
        self.assertEqual(self.read("", ()), ())
        self.assertEqual(self.read(["a", "b"], (97, 98)), (97, 98))
        self.assertEqual(self.read(["a", "bc"], ((97,), (98, 99))), ((97,), (98, 99)))
        self.assertEqual(self.read(["a", "b"], ((97,), (98,))), ((97,), (98,)))
        self.assertIsNone(self.read("ab", 97))
        self.assertIsNone(self.read("ab", ((97, 98),)))

    def test_python_equality_leniencies_and_answers_with_no_reading(self):
        self.assertEqual(self.read(True, 1), 1)
        self.assertIs(self.read(1, True), True)
        self.assertIsNone(self.read(2, True))
        self.assertEqual(self.read(20.0, 20), 20)
        self.assertIsNone(self.read(2.5, 2))
        self.assertIsNone(self.read(float("nan"), 2))
        self.assertIsNone(self.read(None, 0))
        self.assertIsNone(self.read([1, 2], 5))
        self.assertIsNone(self.read({1: 2}, (1,)))
        self.assertIsNone(self.read([[1]], (1,)))                # a nested answer where the program returns a flat seq
        self.assertEqual(self.read([[1], []], ()), ((1,), ()))   # the program's empty seq says nothing of depth

    def test_a_code_point_the_reference_cannot_be_handed_drops_the_draw(self):
        self.assertTrue(twin_draws.faithful([97, 98], ("str",)))
        self.assertFalse(twin_draws.faithful([-1, 98], ("str",)))
        self.assertFalse(twin_draws.faithful([[97], [-3]], ("list", ("str",))))
        self.assertTrue(twin_draws.faithful([-3, 5], ("list", ("scalar",))))
        self.assertTrue(twin_draws.faithful(-3, None))


def digest(root: Path, skip: tuple = ()) -> str:
    """Every path and byte under root, leaving out the top-level entries named in skip."""
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if rel.parts[0] in skip:
            continue
        h.update(str(rel).encode())
        if p.is_file():
            h.update(p.read_bytes())
    return h.hexdigest()


class RecoverTests(unittest.TestCase):
    """--recover-twins re-decides an existing lift's twin refusals and writes only the recovered tasks."""

    POOL = {1001: CUBE, 1002: TWICE, 1003: BROKEN_SQUARE, 1004: DISTINCT, 1005: LENGTH}
    # staged stem: (method, task, the problem the old rule named in refused.jsonl)
    PROGRAMS = {"vericoding_DX0001": ("identity", IDENTITY, 1001),
                "vericoding_DX0002": ("double", DOUBLE, 1002),
                "humaneval_dafny_007_square": ("square", SQUARE, 1003),
                "vericoding_DX0003": ("count", COUNT, 1004)}

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))
        self.out = self.tmp / "out" / "lifted-tasks-x"
        self.meta = self.out.with_name(self.out.name + ".meta")
        for d in (self.out, self.meta / "lift", self.meta / "staged", self.meta / "sidecars"):
            d.mkdir(parents=True)
        self.vericoding = self.tmp / "vericoding-benchmark"
        self.humaneval = self.tmp / "HumanEval-Dafny"
        (self.vericoding / "vericoded").mkdir(parents=True)
        (self.vericoding / "jsonl").mkdir()
        (self.humaneval / "text-descriptions").mkdir(parents=True)
        rows, refused = [], [{"name": "humaneval_dafny_013_gcd__gcd", "source": "humaneval-dafny",
                              "reason": "names HumanEval 13, a listed (same-task exclusion) id"}]
        for stem, (method, task, named) in self.PROGRAMS.items():
            dfy = f"method {method}(x: int) returns (y: int) {{ y := x; }}\n"
            (self.meta / "staged" / f"{stem}.dfy").write_text(dfy)
            (self.meta / "lift" / f"{stem}.{method}.json").write_text(json.dumps(task))
            (self.meta / "lift" / f"{stem}.{method}.lift.json").write_text(json.dumps({"method": method}))
            if stem.startswith("vericoding_"):
                vid = stem[len("vericoding_"):]
                (self.vericoding / "vericoded" / f"{vid}_vericoded.dfy").write_text(dfy)
                rows.append({"id": vid, "source": "apps", "source-id": f"apps_test_{vid}",
                             "vc-description": f"Describe\n{method}."})
            else:
                (self.humaneval / "007-square.dfy").write_text(dfy)
                (self.humaneval / "text-descriptions" / "007-square.txt").write_text(
                    "The description is as follows:\nfunction `square`: Square the number.\n")
            refused.append({"name": task["name"], "source": lift_corpora.source_of(stem),
                            "reason": f"passes every test point of gated problem {named} (held-out)"})
        (self.vericoding / "jsonl" / "dafny_tasks.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        (self.meta / "refused.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in refused))
        (self.meta / "heads.jsonl").write_text("")
        self.split = self.tmp / "split.json"
        self.split.write_text(json.dumps({"pool": "v5", "pool_size": len(self.POOL), "eval_ids": sorted(self.POOL),
                                          "train_ids": []}))
        self.census = {"schema": 1, "when": "2026-09-26T07:32:07Z", "pool": "v5", "split": str(self.split),
                       "lifter_checks_run": False, "accepted": 0, "heads": 0, "refused": 5,
                       "per_source": {"vericoding": {"lifted": 3, "refused: twin": 3},
                                      "humaneval-dafny": {"lifted": 2, "refused: twin": 1,
                                                          "refused: a listed (same-task exclusion) id": 1}}}
        (self.meta / "lift-census.json").write_text(json.dumps(self.census))
        self.recovered = self.out.with_name(self.out.name + "-recovered")

    def written(self) -> tuple:
        """What a recovery may write beside the lift: its directory, its .meta, and the hung-reference record."""
        name = self.recovered.name
        return (name, name + ".meta", name + ".twin-hung.jsonl")

    def recover(self, pool: dict | None = None, *extra: str) -> dict:
        argv = ["--recover-twins", "--out", str(self.out), "--split", str(self.split), "--pool", "v5",
                "--vericoding", str(self.vericoding), "--humaneval-dafny", str(self.humaneval), *extra]
        with mock.patch.object(se, "pool", lambda name: dict(self.POOL if pool is None else pool)), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(lift_corpora.main(argv), 0)
        rmeta = self.recovered.with_name(self.recovered.name + ".meta")
        return {"census": json.loads((rmeta / "lift-census.json").read_text()),
                "decisions": [json.loads(line) for line in (rmeta / "twin-decisions.jsonl").read_text().splitlines()],
                "heads": [json.loads(line) for line in (rmeta / "heads.jsonl").read_text().splitlines()],
                "meta": rmeta}

    def test_only_the_recovered_tasks_are_written_and_every_twin_refusal_is_decided(self):
        before = digest(self.out.parent)
        got = self.recover()
        self.assertEqual(sorted(p.name for p in self.recovered.iterdir()), ["vericoding_DX0001.identity.json"])
        self.assertEqual(json.loads((self.recovered / "vericoding_DX0001.identity.json").read_text()), IDENTITY)
        self.assertEqual(sorted(p.name for p in (got["meta"] / "sidecars").iterdir()),
                         ["vericoding_DX0001.identity.lift.json"])
        self.assertEqual(sorted(p.name for p in (got["meta"] / "staged").iterdir()), ["vericoding_DX0001.dfy"])
        # the heads in the lift's own row format
        self.assertEqual(got["heads"], [{"name": "vericoding_dx0001__identity", "problem": "Describe identity.",
                                         "examples": [], "source": "vericoding", "curation": "source-statement",
                                         "origin": "APPS problem statement (vericoding's own numbering, not the "
                                                   "pool's), apps_test_DX0001"}])
        decisions = {d["name"]: d for d in got["decisions"]}
        self.assertEqual(len(got["decisions"]), 4)           # the four twin refusals, not the HumanEval-index one
        self.assertEqual([d["name"] for d in got["decisions"]],
                         ["vericoding_dx0001__identity", "vericoding_dx0002__double",
                          "humaneval_dafny_007_square__square", "vericoding_dx0003__count"])
        verdicts = {name: [(c["problem"], c["verdict"]) for c in d["candidates"]] for name, d in decisions.items()}
        self.assertEqual(verdicts, {"vericoding_dx0001__identity": [(1001, "differs")],
                                    "vericoding_dx0002__double": [(1002, "agrees")],
                                    "humaneval_dafny_007_square__square": [(1003, "no reference")],
                                    "vericoding_dx0003__count": [(1004, "differs"), (1005, "agrees")]})
        self.assertEqual({name: (d["decision"], d["twin_of"]) for name, d in decisions.items()},
                         {"vericoding_dx0001__identity": ("recovered", None),
                          "vericoding_dx0002__double": ("refused", 1002),
                          "humaneval_dafny_007_square__square": ("refused", 1003),
                          "vericoding_dx0003__count": ("refused", 1005)})
        self.assertIn("gated problem 1004", decisions["vericoding_dx0003__count"]["refused_as"])
        census = got["census"]
        self.assertEqual(census["kind"], lift_corpora.RECOVERY_KIND)
        self.assertEqual((census["twin_refusals_read"], census["accepted"], census["refused"], census["heads"]),
                         (4, 1, 3, 1))
        self.assertEqual(census["candidate_verdicts"], {"differs": 2, "agrees": 2, "no reference": 1})
        self.assertEqual((census["pool"], census["pool_size"], census["draws_per_problem"]), ("v5", 5, twin_draws.DRAWS))
        self.assertFalse(census["lifter_checks_run"])
        # the lift that was read, its directory and its .meta, is byte for byte what it was
        self.assertEqual(digest(self.out.parent, skip=self.written()), before)

    def test_a_second_run_rewrites_the_recovered_directory_and_nothing_else(self):
        self.recover()
        stale = self.recovered / "stale.json"
        stale.write_text("{}")
        self.recover()
        self.assertEqual(sorted(p.name for p in self.recovered.iterdir()), ["vericoding_DX0001.identity.json"])
        self.assertEqual([p.name for p in self.out.parent.glob("*.partial-*")], [])
        # the lift's report writer refuses a recovery rather than overwrite the lift's report
        with self.assertRaises(SystemExit):
            lift_corpora.write_report(self.recovered)

    def refused(self, *argv, pool=None) -> str:
        with mock.patch.object(se, "pool", lambda name: dict(self.POOL if pool is None else pool)), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()), \
                self.assertRaises(SystemExit) as caught:
            lift_corpora.main(["--recover-twins", "--out", str(self.out), "--split", str(self.split), "--pool", "v5",
                               "--vericoding", str(self.vericoding), "--humaneval-dafny", str(self.humaneval), *argv])
        self.assertFalse(self.recovered.exists(), "a refused recovery must write nothing")
        return str(caught.exception)

    def test_a_pool_that_is_not_all_here_is_refused(self):
        shrunk = {k: v for k, v in self.POOL.items() if k != 1005}
        self.assertIn("pool", self.refused(pool=shrunk))

    def test_a_twin_refusal_with_no_lift_record_is_refused(self):
        (self.meta / "lift" / "vericoding_DX0002.double.json").unlink()
        self.assertIn("vericoding_dx0002__double", self.refused())

    def test_a_count_that_disagrees_with_the_census_is_refused(self):
        self.census["per_source"]["vericoding"]["refused: twin"] = 4
        (self.meta / "lift-census.json").write_text(json.dumps(self.census))
        self.assertIn("census", self.refused())

    def test_a_named_problem_the_program_no_longer_passes_is_refused(self):
        changed = dict(self.POOL)
        changed[1001] = entry("cube", "def cube(n):\n    return n * n * n\n", [([2], 8), ([0], 0), ([-1], -1)])
        self.assertIn("1001", self.refused(pool=changed))

    def test_another_pool_or_split_than_the_lifts_is_refused(self):
        self.census["pool"] = "v4"
        (self.meta / "lift-census.json").write_text(json.dumps(self.census))
        self.assertIn("v4", self.refused())

    def test_the_heads_need_both_sources_and_the_same_staged_bytes(self):
        with mock.patch.object(se, "pool", lambda name: dict(self.POOL)), contextlib.redirect_stdout(io.StringIO()), \
                self.assertRaises(SystemExit):
            lift_corpora.main(["--recover-twins", "--out", str(self.out), "--split", str(self.split), "--pool", "v5",
                               "--vericoding", str(self.vericoding)])
        self.assertFalse(self.recovered.exists())
        (self.vericoding / "vericoded" / "DX0001_vericoded.dfy").write_text("method other() {}\n")
        self.assertIn("vericoding_DX0001", self.refused())

    def test_the_recovered_directory_is_never_the_lift_itself_or_a_directory_it_did_not_write(self):
        self.assertIn("REFUSED", self.refused("--recovered", str(self.out)))
        other = self.tmp / "out" / "somebody-elses"
        other.mkdir()
        (other / "keep.json").write_text("{}")
        with mock.patch.object(se, "pool", lambda name: dict(self.POOL)), contextlib.redirect_stdout(io.StringIO()), \
                self.assertRaises(SystemExit):
            lift_corpora.main(["--recover-twins", "--out", str(self.out), "--split", str(self.split), "--pool", "v5",
                               "--vericoding", str(self.vericoding), "--humaneval-dafny", str(self.humaneval),
                               "--recovered", str(other)])
        self.assertTrue((other / "keep.json").exists())


if __name__ == "__main__":
    unittest.main()
