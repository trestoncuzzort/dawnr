"""Checks for concrete execution telemetry, not proof certificates."""
import unittest
from copy import deepcopy

import interp


def val(n):
    return {"int": n}


def var(name):
    return {"var": name}


def op(name, *args):
    return {"op": name, "args": list(args)}


class ExecutionTraceTests(unittest.TestCase):
    def test_loop_states_match_independent_python(self):
        body = [{"assign": ["i", val(0)]}, {"assign": ["r", val(0)]},
                {"while": {"cond": op("<", var("i"), var("n")),
                           "body": [
                               {"assign": ["r", op("+", var("r"), var("i"))]},
                               {"assign": ["i", op("+", var("i"), val(1))]}]}}]
        for n in range(-2, 21):
            events, old_hooks = [], []
            env = {"n": n, "xs": [1, 2]}
            control = deepcopy(env)
            traced, plain = interp.St(), interp.St()
            interp.exec_body(body, env, {}, traced,
                             lambda s, e: old_hooks.append(deepcopy(e)),
                             trace=events.append)
            interp.exec_body(body, control, {}, plain)
            self.assertEqual(env, control)
            self.assertEqual(traced.n, plain.n)
            self.assertEqual(env["r"], sum(range(max(0, n))))
            guards = [e for e in events if e["kind"] == "guard"]
            self.assertEqual([e["state"]["r"] for e in guards],
                             [sum(range(i)) for i in range(max(0, n) + 1)])
            self.assertEqual([e["taken"] for e in guards],
                             [True] * max(0, n) + [False])
            self.assertEqual(len(old_hooks), 1)
            self.assertTrue(all(e["path"] == [2] for e in guards))
            events[0]["state"]["xs"].append(3)
            self.assertEqual(env["xs"], [1, 2])
            self.assertEqual(events[-1]["state"]["xs"], [1, 2])

    def test_nested_return_has_no_later_execution(self):
        body = [{"while": {"cond": {"bool": True}, "body": [
            {"if": {"cond": {"bool": True},
                    "then": [{"return": ["r", val(17)]}], "else": []}},
            {"assign": ["r", val(99)]}]}}, {"assign": ["r", val(88)]}]
        events, env = [], {}
        self.assertTrue(interp.exec_body(body, env, {}, interp.St(), trace=events.append))
        self.assertEqual(env, {"r": 17})
        exits = [e for e in events if e["kind"] == "exit"]
        self.assertEqual([e["path"] for e in exits],
                         [[0, "body", 0, "then", 0], [0, "body", 0], [0]])
        self.assertTrue(all(e["returned"] for e in exits))

    def test_undefined_expression_has_no_success_event(self):
        events = []
        with self.assertRaises(interp.Undef):
            interp.exec_body([{"assign": ["r", var("missing")]}], {}, {},
                             interp.St(), trace=events.append)
        self.assertEqual([e["kind"] for e in events], ["enter"])


if __name__ == "__main__":
    unittest.main()
