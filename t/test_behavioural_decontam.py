"""Behavioural decontamination (t/behavioural_decontam.py) and the merged policy loader (t/loop_filter.py)."""
import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import behavioural_decontam as bd
import loop_filter

HERE = Path(__file__).resolve().parent


def entry(fn: str, code: str, points: list, text: str = "") -> dict:
    """A pool entry the way spec_experiment.pool() shapes one, from (args, expected) pairs of t values."""
    kinds = lambda v: ("bool" if isinstance(v, bool) else "int" if isinstance(v, int)  # noqa: E731
                       else "seq-of-seq" if v and isinstance(v[0], list) else "seq")
    pts = [{"ok": True, "fn": fn, "args": [(kinds(a), a) for a in args], "expected": (kinds(exp), exp)}
           for args, exp in points]
    tests = [f"assert {fn}({', '.join(repr(a) for a in args)}) == {exp!r}" for args, exp in points]
    return {"rec": {"task_id": 0, "text": text or fn, "code": code, "test_list": tests}, "points": pts, "fn": fn}


MIN_A = entry("min_a", "def min_a(a, b):\n    return a if a < b else b\n", [([3, 5], 3), ([9, 2], 2), ([4, 4], 4)])
MIN_B = entry("min_b", "def min_b(x, y):\n    return min(x, y)\n", [([1, 8], 1), ([7, 6], 6), ([0, 3], 0)])
MAX_A = entry("max_a", "def max_a(a, b):\n    return max(a, b)\n", [([3, 5], 5), ([9, 2], 9), ([4, 4], 4)])
LEN_A = entry("len_a", "def len_a(a):\n    return len(a)\n", [([[1, 2, 3]], 3), ([[5, 6]], 2), ([[9]], 1)])
DISTINCT = entry("distinct", "def distinct(a):\n    return len(set(a))\n", [([[1, 2, 3]], 3), ([[5, 6]], 2), ([[9]], 1)])
HEAD = entry("head", "def head(a):\n    return a[0]\n", [([[4, 2]], 4), ([[7, 1, 1]], 7), ([[3]], 3)])
HEAD_OR_ZERO = entry("head_or_zero", "def head_or_zero(a):\n    return a[0] if a else 0\n",
                     [([[4, 2]], 4), ([[7, 1, 1]], 7), ([[3]], 3)])
BROKEN = entry("broken", "def broken(a, b)\n    return a\n", [([1, 2], 1), ([3, 4], 3), ([5, 6], 5)])
RAISES = entry("raises", "def raises(a, b):\n    raise ValueError('never')\n", [([1, 2], 1), ([3, 4], 3), ([5, 6], 5)])
UPPER = entry("upper", "def upper(s):\n    return s.upper()\n",
              [([[104, 105]], [72, 73]), ([[97, 98, 99]], [65, 66, 67]), ([[120]], [88])])
UPPER["rec"]["test_list"] = ["assert upper('hi') == 'HI'", "assert upper('abc') == 'ABC'", "assert upper('x') == 'X'"]
UPPER["points"][2]["args"] = [("int", 120)]      # a one-character string is a t character
STRLEN = entry("strlen", "def strlen(s):\n    return len(s)\n", [([[104, 105]], 2), ([[97, 98, 99]], 3), ([[120]], 1)])
STRLEN["rec"]["test_list"] = ["assert strlen('hi') == 2", "assert strlen('abc') == 3", "assert strlen('x') == 1"]
STRLEN["points"][2]["args"] = [("int", 120)]
LEN_LIST = entry("len_list", "def len_list(a):\n    return len(a)\n", [([[104, 105]], 2), ([[97]], 1), ([[]], 0)])
# answers its own small inputs at once and spins on anything larger
SLOW = entry("slow", "def slow(n):\n    while n > 100:\n        pass\n    return n\n", [([5], 5), ([7], 7), ([9], 9)])
BIG = entry("big", "def big(n):\n    return n\n", [([1000], 1000), ([2000], 2000), ([50], 50)])
# agrees with min on its own inputs, spins on most of a wider shape's draws
FEW = entry("few", "def few(a, b):\n    if a + b > 6:\n        while True:\n            pass\n    return a if a < b else b\n",
            [([3, 2], 2), ([1, 4], 1), ([2, 2], 2)])
DIE = entry("die", "import os\ndef die(a, b):\n    os._exit(0)\n", [([1, 2], 1), ([3, 4], 3), ([5, 6], 5)])


class CanonTests(unittest.TestCase):
    def test_bool_is_not_int_and_strings_read_as_t_does(self):
        self.assertNotEqual(bd.canon(True), bd.canon(1))
        self.assertEqual(bd.canon("a"), bd.canon(97))
        self.assertEqual(bd.canon("ab"), bd.canon([97, 98]))
        self.assertEqual(bd.canon(["ab", "c"]), bd.canon([[97, 98], [99]]))
        self.assertEqual(bd.canon(["a", "b"]), bd.canon([97, 98]))
        self.assertEqual(bd.canon(20.0), bd.canon(20))          # MBPP 76's `/ 6` against 347's `// 6`
        self.assertNotEqual(bd.canon(2.5), bd.canon(2))
        self.assertNotEqual(bd.canon(float("nan")), bd.canon(0))
        self.assertEqual(bd.canon((1, 2)), bd.canon([1, 2]))

    def test_render_writes_t_values_in_the_reference_native_shape(self):
        self.assertEqual(bd.render([104, 105], ("str",)), "hi")
        self.assertEqual(bd.render(120, ("str",)), "x")
        self.assertEqual(bd.render([[97, 98], [99]], ("list", ("str",))), ["ab", "c"])
        self.assertEqual(bd.render([1, 2], ("tuple", ("scalar",))), (1, 2))
        self.assertEqual(bd.render([[1], [2, 3]], None), [[1], [2, 3]])
        with self.assertRaises(bd.Unrenderable):
            bd.render(True, ("str",))
        with self.assertRaises(bd.Unrenderable):
            bd.render(5, ("list", None))

    def test_shapes_come_from_the_assertion_text(self):
        self.assertEqual(bd.arg_shapes(UPPER), [("str",)])
        self.assertEqual(bd.arg_shapes(MIN_A), [("scalar",), ("scalar",)])
        json_style = entry("j", "def j(a, b): return a", [([True, [1]], 1)])
        json_style["rec"]["test_list"] = ["assert j(true, [1]) == 1"]
        self.assertEqual(bd.arg_shapes(json_style), [("scalar",), ("list", ("scalar",))])
        unreadable = entry("u", "def u(a): return a", [([1], 1)])
        unreadable["rec"]["test_list"] = ["assert u(math.pi) == 1"]
        self.assertEqual(bd.arg_shapes(unreadable), [None])
        self.assertEqual(bd.arg_shapes({"rec": {"test_list": []}, "points": [{"args": [("int", 1)]}]}), [None])


class PairTests(unittest.TestCase):
    def pool(self, **entries):
        return {tid: e for tid, e in entries.items()}

    def compare(self, pool, train_id, eval_id):
        runner = bd.Runner(pool)
        draws = {tid: bd.draws_for(tid, e) for tid, e in pool.items()}
        inputs = bd.pair_inputs(pool[train_id], pool[eval_id], draws[train_id], draws[eval_id])
        return bd.compare_pair(runner, train_id, eval_id, inputs), runner

    def test_the_same_function_written_twice_is_a_duplicate(self):
        result, _ = self.compare({1: MIN_A, 2: MIN_B}, 1, 2)
        self.assertEqual(result["verdict"], "duplicate")
        self.assertEqual(result["own_inputs"], 6)
        self.assertEqual(result["own_agreed"], 6)
        self.assertGreaterEqual(result["draws_agreed"], bd.MIN_DRAWS_AGREED)
        self.assertEqual(result["draws_agreed"], result["draws"])
        self.assertEqual(result["differences"], 0)

    def test_the_same_refusal_of_the_same_input_counts_as_alike(self):
        # both raise IndexError on every list shorter than two, which the draws produce often
        second = entry("second", "def second(a):\n    return a[1]\n", [([[4, 2]], 2), ([[7, 1, 1]], 1), ([[3, 9]], 9)])
        second_b = entry("second_b", "def second_b(a):\n    x = list(a)\n    return x[1]\n",
                         [([[5, 6]], 6), ([[8, 8, 8]], 8), ([[0, 1]], 1)])
        result, _ = self.compare({1: second, 2: second_b}, 1, 2)
        self.assertEqual(result["verdict"], "duplicate")
        self.assertGreater(result["draws_refused_alike"], 0)
        self.assertGreaterEqual(result["draws_agreed"], bd.MIN_DRAWS_VALUED)
        self.assertEqual(result["differences"] + result["one_sided"], 0)
        # a stored pair is re-judged from its counts, so the thresholds live here and not in the run
        self.assertEqual(bd.verdict_of(dict(result, draws_agreed=bd.MIN_DRAWS_VALUED - 1)), "undecided")
        self.assertEqual(bd.verdict_of(dict(result, train_answered=0)), "not run")

    def test_a_pair_separated_only_by_a_draw_is_a_minimal_pair_and_kept(self):
        result, _ = self.compare({1: LEN_A, 2: DISTINCT}, 1, 2)
        self.assertEqual(result["verdict"], "minimal pair")
        self.assertEqual(result["own_agreed"], result["own_inputs"])
        self.assertIn(result["difference"]["where"], ("draw_eval", "draw_train"))
        self.assertEqual(result["difference"]["kind"], "disagree")
        self.assertGreater(result["differences"], 0)

    def test_a_pair_that_differs_on_an_own_input_is_different(self):
        result, _ = self.compare({1: MIN_A, 2: MAX_A}, 1, 2)
        self.assertEqual(result["verdict"], "different")
        self.assertIn(result["difference"]["where"], ("own_train", "own_eval"))

    def test_one_sided_raise_is_a_difference_not_agreement(self):
        result, _ = self.compare({1: HEAD, 2: HEAD_OR_ZERO}, 1, 2)
        self.assertNotEqual(result["verdict"], "duplicate")
        self.assertEqual(result["verdict"], "minimal pair")
        self.assertEqual(result["difference"]["kind"], "one raised")
        self.assertEqual(result["difference"]["input"], [[]])
        self.assertGreater(result["one_sided"], 0)

    def test_a_reference_that_does_not_load_is_reported_never_agreeing(self):
        result, runner = self.compare({1: BROKEN, 2: MIN_B}, 1, 2)
        self.assertEqual(result["verdict"], "no reference")
        self.assertEqual(result["agreed_inputs"], 0)
        self.assertIn("does not load", runner.why_not_run(1))
        self.assertIsNone(runner.why_not_run(2))

    def test_a_reference_that_raises_on_every_input_is_reported_never_agreeing(self):
        result, runner = self.compare({1: RAISES, 2: MIN_B}, 1, 2)
        self.assertEqual(result["verdict"], "not run")
        self.assertEqual(result["agreed_inputs"], 0)
        self.assertEqual(runner.why_not_run(1), "reference raised on every input it was given")

    def test_string_references_get_strings_and_compare_as_code_points(self):
        pool = {1: UPPER, 2: entry("up2", "def up2(s):\n    return ''.join(c.upper() for c in s)\n",
                                   [([[104, 105]], [72, 73]), ([[97]], 65)])}
        pool[2]["rec"]["test_list"] = ["assert up2('hi') == 'HI'", "assert up2('a') == 'A'"]
        pool[2]["points"][1]["args"] = [("int", 97)]
        result, runner = self.compare(pool, 2, 1)
        self.assertIsNone(runner.why_not_run(1))
        self.assertEqual(result["verdict"], "duplicate")
        # the references were handed str, never a list of code points
        self.assertEqual(runner.call(1, [[104, 105]]), ("ok", bd.canon("HI")))
        # a one-character result reads as a t character, so 'X' and ['X'] are different values in t
        self.assertNotEqual(bd.canon("X"), bd.canon(["X"]))

    def test_a_small_domain_is_exhausted_by_the_draws_not_short_of_them(self):
        # examples of 2 draw from 0..4: a handful of distinct values, each drawn many times
        even_a = entry("even_a", "def even_a(n):\n    return n % 2 == 0\n", [([2], True), ([3], False), ([4], True)])
        even_b = entry("even_b", "def even_b(n):\n    return not (n & 1)\n", [([2], True), ([1], False), ([0], True)])
        pool = {1: even_a, 2: even_b}
        draws = {tid: bd.draws_for(tid, e) for tid, e in pool.items()}
        inputs = bd.pair_inputs(pool[1], pool[2], draws[1], draws[2])
        self.assertEqual(sum(w for tag, _a, w in inputs if tag.startswith("draw")), 2 * bd.DRAWS_PER_PROBLEM)
        self.assertLess(len([1 for tag, _a, _w in inputs if tag.startswith("draw")]), 12)
        result = bd.compare_pair(bd.Runner(pool), 1, 2, inputs)
        self.assertEqual(result["draws"], 2 * bd.DRAWS_PER_PROBLEM)
        self.assertEqual(result["verdict"], "duplicate")

    def test_signature_kinds_decide_which_pairs_exist(self):
        pool = {1: MIN_A, 2: LEN_A, 3: MIN_B, 4: DISTINCT}
        tasks = dict(bd.group_by_signature(pool, [3, 4], [1, 2]))
        self.assertEqual(tasks, {3: [1], 4: [2]})

    def test_a_reference_that_never_finishes_is_reported(self):
        loop = entry("spin", "def spin(a, b):\n    while True:\n        pass\n", [([1, 2], 1), ([3, 4], 3)])
        runner = bd.Runner({1: loop}, timeout_s=0.2, max_timeouts=1)
        self.assertEqual(runner.call(1, [1, 2]), ("timeout",))
        self.assertEqual(runner.call(1, [5, 6]), ("timeout",))      # not run again: the budget is spent
        self.assertEqual(runner.calls[1], 1)
        self.assertIn("did not finish", runner.why_not_run(1))
        self.assertIn("did not finish", runner.exhausted(1))

    def test_run_reference_leaves_no_timer_armed_and_the_streams_as_they_were(self):
        import signal
        import sys
        streams = (sys.stdin, sys.stdout, sys.stderr)
        self.assertEqual(bd.run_reference(lambda a: a + 1, [1]), ("ok", bd.canon(2)))
        self.assertEqual(bd.run_reference(lambda a: print(a) or a, [1]), ("ok", bd.canon(1)))
        self.assertEqual(bd.run_reference(lambda a: sys.exit(3), [1]), ("raised", "SystemExit"))

        def spin(a):
            while True:
                pass
        self.assertEqual(bd.run_reference(spin, [1], timeout_s=0.2), ("timeout",))
        self.assertEqual(signal.getitimer(signal.ITIMER_VIRTUAL), (0.0, 0.0))
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL), (0.0, 0.0))
        self.assertEqual(signal.getsignal(signal.SIGVTALRM), signal.SIG_IGN)
        self.assertEqual((sys.stdin, sys.stdout, sys.stderr), streams)

    def test_a_worker_failure_is_reported_by_held_out_id_not_swallowed(self):
        pool = {1: MIN_A, 2: MIN_B}
        bd._worker_init(pool, {1: bd.draws_for(1, MIN_A), 2: bd.draws_for(2, MIN_B)}, 0.2, 0)
        bd._WORKER["runner"].pool = None                        # every lookup now raises inside the comparison
        result = bd._worker((2, [1]))
        self.assertEqual(result["eval_id"], 2)
        self.assertIn("error", result)
        self.assertNotIn("pairs", result)

    def test_an_own_input_a_reference_did_not_answer_leaves_the_count(self):
        # The train example is large, so its draws are large and the held-out
        # reference spins on them; the held-out example is small, so its own
        # inputs and draws are answered by both. Schema 1 required every own
        # input to agree, so the two timed-out own inputs (1000, 2000) made a
        # duplicate impossible although nothing ever differed; now they leave
        # the count (HyClone, https://arxiv.org/html/2508.01357v1, drops such inputs).
        pool = {1: BIG, 2: SLOW}
        runner = bd.Runner(pool, timeout_s=0.2)
        draws = {tid: bd.draws_for(tid, e) for tid, e in pool.items()}
        result = bd.compare_pair(runner, 1, 2, bd.pair_inputs(pool[1], pool[2], draws[1], draws[2]))
        self.assertEqual(result["differences"], 0)
        self.assertEqual(result["one_sided"], 0)
        self.assertEqual(result["own_inputs"], 6)
        self.assertEqual(result["own_agreed"], 4)                       # 5, 7, 9 and 50
        self.assertEqual(result["own_unanswered"], 2)                   # 1000 and 2000: the held-out reference spun
        self.assertEqual(result["own_eval_agreed"], 3)
        self.assertGreaterEqual(result["draws_agreed"], bd.DRAWS_PER_PROBLEM)    # the held-out shape's draws, all answered
        self.assertEqual(result["verdict"], "duplicate")
        self.assertNotIn("difference", result)
        # own inputs never stop a pair's draws; the draw allowance is per draw shape
        self.assertEqual(runner.timeouts[2], 2 + bd.PAIR_TIMEOUTS)
        self.assertEqual(bd.verdict_of(dict(result, own_eval_agreed=0)), "undecided")
        self.assertEqual(bd.verdict_of(dict(result, own_agreed=3)), "undecided")

    def test_a_reference_slow_on_the_other_shape_is_still_asked_its_own(self):
        # the train reference spins on the held-out problem's large draws but
        # answers its own; schema 1 skipped every draw after two timeouts anywhere
        pool = {1: SLOW, 2: BIG}
        runner = bd.Runner(pool, timeout_s=0.2)
        draws = {tid: bd.draws_for(tid, e) for tid, e in pool.items()}
        result = bd.compare_pair(runner, 1, 2, bd.pair_inputs(pool[1], pool[2], draws[1], draws[2]))
        self.assertEqual(result["own_unanswered"], 2)
        self.assertEqual(result["own_eval_agreed"], 1)                  # 50
        self.assertEqual(runner.timeouts[1], 2 + bd.PAIR_TIMEOUTS)      # then the held-out shape's draws were skipped
        self.assertGreaterEqual(result["draws_agreed"], bd.DRAWS_PER_PROBLEM)    # its own shape's draws were not
        self.assertLess(result["draws_agreed"], 2 * bd.DRAWS_PER_PROBLEM)
        self.assertEqual(result["verdict"], "duplicate")

    def test_an_input_the_other_shape_cannot_hold_says_nothing(self):
        # 'x' is the t character 120: the list-shaped reference cannot be handed
        # it, which schema 1 counted as a one-sided raise, a difference
        result, _ = self.compare({1: STRLEN, 2: LEN_LIST}, 1, 2)
        self.assertEqual(result["unrenderable"], 1)
        self.assertEqual(result["own_unanswered"], 1)
        self.assertEqual(result["own_agreed"], result["own_inputs"] - 1)
        self.assertEqual(result["differences"] + result["one_sided"], 0)
        self.assertNotIn("difference", result)
        self.assertEqual(result["verdict"], "duplicate")

    def test_running_out_of_recursion_depth_is_unanswered_not_a_raise(self):
        def deep(n):
            return deep(n + 1)
        self.assertEqual(bd.run_reference(deep, [1]), ("exhausted", "RecursionError"))
        self.assertEqual(sys.getrecursionlimit(), bd.RECURSION_LIMIT)
        # a reference that raised the limit at load time does not change what the next one can answer
        import sys as _sys
        _sys.setrecursionlimit(bd.RECURSION_LIMIT * 4)
        try:
            self.assertEqual(bd.run_reference(deep, [1]), ("exhausted", "RecursionError"))
            self.assertEqual(_sys.getrecursionlimit(), bd.RECURSION_LIMIT * 4)   # put back after the call
        finally:
            _sys.setrecursionlimit(bd.RECURSION_LIMIT)

    def test_a_timeout_escapes_a_reference_that_catches_exception(self):
        # spec_check.Timeout is an Exception; a corpus solution's `except Exception`
        # swallowed it and the call returned a value after the budget
        def swallows(n):
            try:
                while True:
                    n = (n * 31 + 1) % 1000003
            except Exception:                                   # noqa: BLE001
                return 0
        self.assertEqual(bd.run_reference(swallows, [1], timeout_s=0.2), ("timeout",))
        self.assertTrue(issubclass(bd.ReferenceTimeout, BaseException))
        self.assertFalse(issubclass(bd.ReferenceTimeout, Exception))

    def test_a_reference_that_swallows_the_timeout_and_returns_late_is_a_timeout(self):
        def swallows_everything(n):
            try:
                while True:
                    n = (n * 31 + 1) % 1000003
            except BaseException:                               # noqa: BLE001
                pass
            end = time.process_time() + 0.2                     # keeps working past the budget, then answers
            while time.process_time() < end:
                pass
            return n
        self.assertEqual(bd.run_reference(swallows_everything, [1], timeout_s=0.2), ("timeout",))

    def test_a_reference_that_swallows_every_timeout_exits_the_worker_and_is_named(self):
        # nothing in the process can stop a bare except around a busy loop; the
        # wall-clock backstop names the reference and exits (pytest-timeout's
        # thread method does the same with os._exit)
        with tempfile.TemporaryDirectory() as tmp:
            sidecar = Path(tmp) / "v5.jsonl.hung"
            code = (
                "import sys\n"
                "sys.path.insert(0, sys.argv[1])\n"
                "import behavioural_decontam as bd\n"
                "bd._TIMER.update(tid=7, name='mbpp_7__spin', eval_id=5, hung_path=sys.argv[2])\n"
                "def spin(n):\n"
                "    while True:\n"
                "        try:\n"
                "            for i in range(1000):\n"
                "                n = (n * 31 + i) % 1000003\n"
                "        except BaseException:\n"
                "            pass\n"
                "print(bd.run_reference(spin, [1], timeout_s=0.1))\n")
            done = subprocess.run([sys.executable, "-c", code, str(HERE), str(sidecar)], capture_output=True,
                                  text=True, timeout=30)
            self.assertEqual(done.returncode, bd.HUNG_EXIT, done.stderr[-500:])
            self.assertNotIn("timeout", done.stdout)
            self.assertIn("worker exiting", done.stderr)
            self.assertIn("mbpp_7__spin", done.stderr)
            self.assertEqual(bd.read_hung(sidecar), {7: bd.HUNG_WHY})
            self.assertEqual(bd.read_hung(Path(tmp) / "absent"), {})


class RunTests(unittest.TestCase):
    POOL = {1: MIN_A, 2: MAX_A, 3: LEN_A, 4: HEAD, 5: MIN_B, 6: DISTINCT, 7: HEAD_OR_ZERO, 8: RAISES}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.split = self.root / "split-v5.json"
        self.split.write_text(json.dumps({"pool": "v5", "pool_size": len(self.POOL), "eval_ids": [5, 6, 7],
                                          "train_ids": [1, 2, 3, 4, 8]}), encoding="utf-8")
        self.a2 = self.root / "a2.json"
        self.a2.write_text(json.dumps({"exclude_future_train_ids": [1, 4, 99], "overlap_ids": [5],
                                       "drop_documents": {}, "weak_test_eval_ids": []}), encoding="utf-8")
        self.progress = self.root / "v5.jsonl"

    def test_run_writes_a_resumable_progress_file_and_the_policy_follows(self):
        result = bd.run_pool("v5", self.split, self.progress, jobs=1, log=open(self.root / "log", "w"), pool=self.POOL)
        self.assertEqual(json.loads(self.progress.read_text().splitlines()[0])["schema"], 2)
        self.assertEqual(result["progress"], str(self.progress))
        lines = [json.loads(l) for l in self.progress.read_text().splitlines()]
        self.assertEqual(lines[0]["kind"], "header")
        self.assertEqual({l["eval_id"] for l in lines[1:]}, {5, 6, 7})
        # a second run recomputes nothing and appends nothing
        again = bd.run_pool("v5", self.split, self.progress, jobs=1, log=open(self.root / "log", "w"), pool=self.POOL)
        self.assertEqual(len(self.progress.read_text().splitlines()), len(lines))
        self.assertIn("progress", again)
        run = bd.read_progress(self.progress)
        verdict = {(p["train_id"], p["eval_id"]): p["verdict"] for p in run["pairs"]}
        self.assertEqual(verdict[(1, 5)], "duplicate")
        self.assertEqual(verdict[(2, 5)], "different")
        self.assertEqual(verdict[(8, 5)], "not run")
        self.assertEqual(verdict[(3, 6)], "minimal pair")
        self.assertEqual(verdict[(4, 7)], "minimal pair")
        self.assertNotIn((1, 6), verdict)                       # a different signature is never compared
        self.assertEqual(run["not_run"], {8: "reference raised on every input it was given"})
        policy = bd.build_policy([run], {"v5": self.POOL}, a2_policy=self.a2)
        self.assertEqual(policy["exclude_train_ids"], [1])
        self.assertEqual(policy["exclude_train_ids_by_eval"], {"1": [5]})
        self.assertEqual(policy["behavioural_overlap_eval_ids"], [5])
        self.assertEqual(policy["rediscovered_from_2026_09_21"], [1])
        self.assertEqual(policy["new_exclusions"], [])
        self.assertEqual(policy["not_rediscovered_from_2026_09_21"], [4, 99])
        self.assertEqual([r["train"] for r in policy["duplicates"]], ["mbpp_1__min_a"])
        self.assertEqual({(r["train_id"], r["eval_id"]) for r in policy["minimal_pairs"]}, {(3, 6), (4, 7)})
        self.assertEqual(policy["references_not_run"], [{"pool": "v5", "id": 8, "name": "mbpp_8__raises",
                                                         "why": "reference raised on every input it was given"}])
        self.assertEqual(policy["pools"]["v5"]["pairs"], 7)
        self.assertEqual(policy["undecided"], [])
        self.assertEqual(policy["read_by_hand"], [])
        self.assertEqual(policy["exclude_train_ids_by_reading"], [])
        self.assertEqual(policy["exclusions_by_class"]["all"], {"mbpp": 1, "humaneval": 0, "apps": 0, "stdin": 0})
        self.assertEqual(policy["exclusions_by_class"]["new"], {"mbpp": 0, "humaneval": 0, "apps": 0, "stdin": 0})
        self.assertEqual(policy["schema"], 2)
        report = self.root / "report.md"
        bd.write_report(policy, [run], {"v5": self.POOL}, report)
        text = report.read_text()
        self.assertIn("mbpp_1__min_a", text)
        self.assertIn("| v5 |", text)
        self.assertIn("- 4: ", text)

    def test_a_later_pool_copies_the_pairs_an_earlier_run_measured(self):
        bd.run_pool("v5", self.split, self.progress, jobs=1, log=open(self.root / "log", "w"), pool=self.POOL)
        wider = {**self.POOL, 9: entry("min_c", "def min_c(a, b):\n    return -max(-a, -b)\n",
                                       [([2, 3], 2), ([5, 1], 1), ([4, 4], 4)])}
        split6 = self.root / "split-v6.json"
        split6.write_text(json.dumps({"pool": "v6", "pool_size": len(wider), "eval_ids": [5, 6, 7],
                                      "train_ids": [1, 2, 3, 4, 8, 9]}), encoding="utf-8")
        progress6 = self.root / "v6.jsonl"
        bd.run_pool("v6", split6, progress6, jobs=1, log=open(self.root / "log", "w"), pool=wider,
                    known_path=self.progress)
        run = bd.read_progress(progress6)
        self.assertEqual(run["header"]["known_from"]["pool"], "v5")
        copied = {(p["train_id"], p["eval_id"]) for p in run["pairs"] if p.get("copied_from") == "v5"}
        fresh = {(p["train_id"], p["eval_id"]) for p in run["pairs"] if not p.get("copied_from")}
        self.assertEqual(fresh, {(9, 5)})
        self.assertEqual(len(copied), 7)
        verdict = {(p["train_id"], p["eval_id"]): p["verdict"] for p in run["pairs"]}
        self.assertEqual(verdict[(9, 5)], "duplicate")
        self.assertEqual(verdict[(1, 5)], "duplicate")
        self.assertEqual(run["not_run"], {8: "reference raised on every input it was given"})   # carried over
        policy = bd.build_policy([bd.read_progress(self.progress), run], {"v5": self.POOL, "v6": wider}, a2_policy=self.a2)
        self.assertEqual(policy["exclude_train_ids"], [1, 9])
        self.assertEqual(policy["pools"]["v6"]["pairs_copied_from"]["pairs"], 7)
        # the same pool, or a later one, cannot be the known file
        with self.assertRaises(SystemExit):
            bd.run_pool("v5", self.split, self.root / "again.jsonl", jobs=1, log=open(self.root / "log", "w"),
                        pool=self.POOL, known_path=progress6)

    def test_a_partial_progress_file_is_refused_by_the_writer(self):
        bd.run_pool("v5", self.split, self.progress, jobs=1, log=open(self.root / "log", "w"), pool=self.POOL)
        lines = self.progress.read_text().splitlines()
        self.progress.write_text("\n".join(lines[:-1]) + "\n")
        with self.assertRaises(SystemExit) as caught:
            bd.read_progress(self.progress)
        self.assertIn("did not finish", str(caught.exception))

    def test_a_split_of_another_pool_size_is_refused(self):
        with self.assertRaises(SystemExit) as caught:
            bd.load_split(dict(list(self.POOL.items())[:3]), "v5", self.split)
        self.assertIn("REFUSED", str(caught.exception))
        self.split.write_text(json.dumps({"pool": "v6", "pool_size": len(self.POOL), "eval_ids": [5], "train_ids": [1]}))
        with self.assertRaises(SystemExit):
            bd.load_split(self.POOL, "v5", self.split)

    def test_a_progress_file_from_other_settings_is_refused(self):
        self.progress.write_text(json.dumps({"kind": "header", "schema": bd.SCHEMA, "pool": "v5", "split_sha256": "0" * 64,
                                             "seed": bd.SEED, "draws_per_problem": 50, "min_draws_agreed": 50}) + "\n")
        with self.assertRaises(SystemExit) as caught:
            bd.run_pool("v5", self.split, self.progress, jobs=1, log=open(self.root / "log", "w"), pool=self.POOL)
        self.assertIn("split_sha256", str(caught.exception))

    def test_a_schema_1_progress_file_is_refused_not_reread(self):
        # schema 1 records lack own_unanswered: the verdicts cannot be re-derived from them
        bd.run_pool("v5", self.split, self.progress, jobs=1, log=open(self.root / "log", "w"), pool=self.POOL)
        lines = self.progress.read_text().splitlines()
        header = json.loads(lines[0])
        header["schema"] = 1
        self.progress.write_text("\n".join([json.dumps(header)] + lines[1:]) + "\n")
        with self.assertRaises(SystemExit) as caught:
            bd.read_progress(self.progress)
        self.assertIn("schema 1", str(caught.exception))
        with self.assertRaises(SystemExit) as caught:
            bd.run_pool("v5", self.split, self.progress, jobs=1, log=open(self.root / "log", "w"), pool=self.POOL)
        self.assertIn("schema", str(caught.exception))
        with self.assertRaises(SystemExit):
            bd.verdict_of({"train_answered": 1, "eval_answered": 1, "differences": 0, "one_sided": 0,
                           "own_inputs": 3, "own_agreed": 3, "draws_agreed": 60, "draws_refused_alike": 0})

    def test_an_undecided_pair_must_be_read_before_the_policy_is_written(self):
        pool = {1: FEW, 5: MIN_B}
        split = self.root / "split-u.json"
        split.write_text(json.dumps({"pool": "v5", "pool_size": 2, "eval_ids": [5], "train_ids": [1]}))
        progress = self.root / "u.jsonl"
        bd.run_pool("v5", split, progress, jobs=1, timeout_s=0.2, log=open(self.root / "log", "w"), pool=pool)
        run = bd.read_progress(progress)
        (pair,) = run["pairs"]
        self.assertEqual(pair["verdict"], "undecided")
        self.assertEqual(pair["differences"] + pair["one_sided"], 0)
        self.assertGreater(pair["own_unanswered"], 0)
        self.assertIn("draws", bd.why_undecided(pair))
        with self.assertRaises(SystemExit) as caught:
            bd.build_policy([run], {"v5": pool}, a2_policy=self.a2)
        self.assertIn("1:5", str(caught.exception))
        self.assertIn("no reading", str(caught.exception))
        draft = bd.build_policy([run], {"v5": pool}, a2_policy=self.a2, unread_ok=True)
        self.assertEqual(draft["exclude_train_ids"], [])
        self.assertEqual(draft["distinct"]["undecided_unread"], 1)
        self.assertNotIn("reading", draft["undecided"][0])
        # a reading for a pair the rule decided, or never compared, is refused
        with self.assertRaises(SystemExit):
            bd.build_policy([run], {"v5": pool}, a2_policy=self.a2,
                            readings={(1, 5): {"reading": "same function", "note": "min"},
                                      (2, 5): {"reading": "same function", "note": "stray"}})
        readings = bd.parse_readings(["1:5=both return the smaller of two integers"], [])
        self.assertEqual(readings, {(1, 5): {"reading": "same function", "note": "both return the smaller of two integers"}})
        policy = bd.build_policy([run], {"v5": pool}, a2_policy=self.a2, readings=readings)
        self.assertEqual(policy["exclude_train_ids"], [1])
        self.assertEqual(policy["exclude_train_ids_by_reading"], [1])
        self.assertEqual(policy["exclude_train_ids_by_eval"], {"1": [5]})
        self.assertEqual(policy["behavioural_overlap_eval_ids"], [5])
        self.assertEqual(policy["duplicates"], [])
        self.assertEqual(policy["read_by_hand"][0]["reading"], "same function")
        self.assertEqual(policy["read_by_hand"][0]["train"], "mbpp_1__few")
        self.assertIn("train_text", policy["read_by_hand"][0])
        self.assertEqual(policy["undecided"][0]["note"], "both return the smaller of two integers")
        report = self.root / "report.md"
        bd.write_report(policy, [run], {"v5": pool}, report)
        text = report.read_text()
        self.assertIn("**same function**", text)
        self.assertIn("1 read by hand as the same function", text)
        kept = bd.build_policy([run], {"v5": pool}, a2_policy=self.a2,
                               readings=bd.parse_readings([], ["1:5=a different function"]))
        self.assertEqual(kept["exclude_train_ids"], [])
        self.assertEqual(kept["distinct"]["undecided_read_as_different"], 1)
        for bad in (["1:5"], ["1:5="], ["1-5=x"], ["a:5=x"]):
            with self.assertRaises(SystemExit):
                bd.parse_readings(bad, [])
        with self.assertRaises(SystemExit):
            bd.parse_readings(["1:5=x"], ["1:5=y"])

    def test_a_lost_worker_is_named_not_waited_on(self):
        # a worker that dies mid-task leaves multiprocessing.Pool waiting forever
        # (CPython issue 66587, open); the run gives up after inactivity_s and
        # names the held-out ids it never got
        pool = {1: MIN_A, 5: MIN_B, 9: DIE}
        split = self.root / "split-d.json"
        split.write_text(json.dumps({"pool": "v5", "pool_size": 3, "eval_ids": [5], "train_ids": [1, 9]}))
        progress = self.root / "d.jsonl"
        started = time.time()
        with self.assertRaises(SystemExit) as caught:
            bd.run_pool("v5", split, progress, jobs=2, timeout_s=0.2, inactivity_s=3.0,
                        log=open(self.root / "log", "w"), pool=pool)
        self.assertLess(time.time() - started, 25)
        self.assertIn("[5]", str(caught.exception))
        self.assertIn("no held-out id finished", str(caught.exception))
        self.assertEqual(len(progress.read_text().splitlines()), 1)     # the header only: nothing was invented

    def test_a_reference_named_in_the_sidecar_is_refused_by_name_on_the_next_run(self):
        hung = bd.hung_path_for(self.progress)
        hung.write_text(json.dumps({"kind": "hung", "eval_id": 5, "tid": 1, "name": "mbpp_1__min_a",
                                    "why": bd.HUNG_WHY}) + "\n")
        log = self.root / "log"
        bd.run_pool("v5", self.split, self.progress, jobs=1, log=open(log, "w"), pool=self.POOL)
        self.assertIn("refusing 1 reference", log.read_text())
        run = bd.read_progress(self.progress)
        verdict = {(p["train_id"], p["eval_id"]): p["verdict"] for p in run["pairs"]}
        self.assertEqual(verdict[(1, 5)], "no reference")
        self.assertEqual(run["not_run"][1], bd.HUNG_WHY)
        policy = bd.build_policy([run], {"v5": self.POOL}, a2_policy=self.a2)
        self.assertEqual(policy["exclude_train_ids"], [])
        self.assertIn({"pool": "v5", "id": 1, "name": "mbpp_1__min_a", "why": bd.HUNG_WHY}, policy["references_not_run"])


class LoaderTests(unittest.TestCase):
    """loop_filter.decontamination() merges the behavioural file into exclude_train_ids with provenance."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.a2 = self.root / "decontamination-a2.json"
        self.a2.write_text(json.dumps({"drop_documents": {"positive:mbpp_1__x": [5]},
                                       "exclude_future_train_ids": [1, 2], "overlap_ids": [5]}))
        self.behavioural = self.root / "decontamination-behavioural.json"
        self.policy = {
            "schema": 2, "rule": {"text": "..."}, "exclude_train_ids": [2, 3, 4],
            "duplicates": [{"train_id": 2, "eval_id": 5}, {"train_id": 3, "eval_id": 6}],
            "read_by_hand": [{"train_id": 4, "eval_id": 6, "reading": "same function", "note": "read"}],
            "undecided": [{"train_id": 4, "eval_id": 6, "reading": "same function", "note": "read"},
                          {"train_id": 7, "eval_id": 6, "reading": "different function", "note": "read"}],
            "behavioural_overlap_eval_ids": [5, 6]}
        self.behavioural.write_text(json.dumps(self.policy))

    def test_exclusions_are_merged_and_each_id_names_the_file_that_excluded_it(self):
        policy = loop_filter.decontamination(self.a2, self.behavioural)
        self.assertEqual(policy.exclude_train_ids, frozenset({1, 2, 3, 4}))     # 4: read by hand as the same function
        self.assertEqual(policy.overlap_eval_ids, frozenset({5}))        # the clean 200 are unchanged
        self.assertEqual(policy.behavioural_overlap_eval_ids, frozenset({5, 6}))
        self.assertEqual(dict(policy.excluded_by), {1: ("decontamination-a2.json",),
                                                    2: ("decontamination-a2.json", "decontamination-behavioural.json"),
                                                    3: ("decontamination-behavioural.json",),
                                                    4: ("decontamination-behavioural.json",)})
        self.assertEqual(policy.drop_document_names, frozenset({"mbpp_1__x"}))
        with self.assertRaises(TypeError):
            policy.excluded_by[9] = ("x",)

    def test_a_missing_or_malformed_behavioural_file_is_refused_not_skipped(self):
        with self.assertRaises(ValueError) as caught:
            loop_filter.decontamination(self.a2, self.root / "absent.json")
        self.assertIn("absent.json", str(caught.exception))
        self.behavioural.write_text(json.dumps({**self.policy, "duplicates": [{"train_id": 2, "eval_id": 5}]}))
        with self.assertRaises(ValueError):
            loop_filter.decontamination(self.a2, self.behavioural)     # exclusions and duplicates disagree
        for schema in (1, 3):
            self.behavioural.write_text(json.dumps({**self.policy, "schema": schema}))
            with self.assertRaises(ValueError):
                loop_filter.decontamination(self.a2, self.behavioural)
        # an undecided pair without a reading: the file is refused, the pair is not admitted quietly
        self.behavioural.write_text(json.dumps({**self.policy, "undecided": [{"train_id": 8, "eval_id": 6}]}))
        with self.assertRaises(ValueError) as caught:
            loop_filter.decontamination(self.a2, self.behavioural)
        self.assertIn("no reading", str(caught.exception))
        # a same-function reading whose id is missing from exclude_train_ids
        self.behavioural.write_text(json.dumps({**self.policy, "exclude_train_ids": [2, 3]}))
        with self.assertRaises(ValueError):
            loop_filter.decontamination(self.a2, self.behavioural)
        without = {k: v for k, v in self.policy.items() if k != "read_by_hand"}
        self.behavioural.write_text(json.dumps(without))
        with self.assertRaises(ValueError):
            loop_filter.decontamination(self.a2, self.behavioural)

    def test_the_gate_refuses_a_behavioural_twin_by_id_and_by_name(self):
        policy = loop_filter.decontamination(self.a2, self.behavioural)
        doc = "t 1\ntask mbpp_3__twin(a: int) returns (r: int)\n{\n  r := a;\n}\n"
        result = loop_filter.validate_training_data(doc, {5}, policy=policy)
        self.assertFalse(result.ok)
        self.assertEqual(result.same_task_ids, frozenset({3}))
        row = loop_filter.validate_training_data("t 1\ntask renamed(a: int) returns (r: int)\n{\n  r := a;\n}\n",
                                                 {5}, task_ids=[3], policy=policy)
        self.assertEqual(row.same_task_ids, frozenset({3}))

    def test_the_checked_in_files_load_together(self):
        policy = loop_filter.decontamination()
        a2 = json.loads((HERE / "decontamination-2026-09-21.json").read_text())
        behavioural = json.loads((HERE / "decontamination-behavioural-2026-09-25.json").read_text())
        self.assertEqual(policy.exclude_train_ids,
                         frozenset(a2["exclude_future_train_ids"]) | frozenset(behavioural["exclude_train_ids"]))
        self.assertEqual(set(policy.excluded_by), set(policy.exclude_train_ids))
        self.assertEqual(behavioural["schema"], bd.SCHEMA)
        self.assertEqual(behavioural["distinct"]["undecided_unread"], 0)
        for row in behavioural["undecided"]:
            self.assertIn(row["reading"], ("same function", "different function"), row)
            self.assertTrue(row["note"])
        self.assertEqual(sorted(behavioural["exclude_train_ids_by_reading"]),
                         sorted({r["train_id"] for r in behavioural["read_by_hand"] if r["reading"] == "same function"}))
        self.assertEqual(sorted(behavioural["rediscovered_from_2026_09_21"]),
                         sorted(set(a2["exclude_future_train_ids"]) & set(behavioural["exclude_train_ids"])))
        for row in behavioural["duplicates"]:
            self.assertIn(row["eval_id"], set(json.loads((HERE / "out" / "loop" / "split-v3.json").read_text())["eval_ids"])
                          if (HERE / "out" / "loop" / "split-v3.json").exists() else {row["eval_id"]})


if __name__ == "__main__":
    unittest.main()
