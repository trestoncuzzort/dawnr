"""Type information belongs to one witness search, including parallel searches."""
from concurrent.futures import ThreadPoolExecutor
from contextvars import Context
import threading
import unittest

import harness


def task(result_type):
    return {"spec_funs": [{"name": "value", "params": [], "result": result_type}],
            "datatypes": [{"name": "Box", "ctors": [
                {"name": "Wrap", "fields": [{"name": "item", "type": result_type}]}]}]}


CALL = {"call": {"fun": "value", "args": []}}
ARMS = [{"ctor": "Wrap", "binders": ["item"], "body": {"var": "item"}}]


class WitnessContextTests(unittest.TestCase):
    def test_two_threads_retain_their_function_types(self):
        barrier = threading.Barrier(2)

        def work(result_type):
            harness._set_ctx(task(result_type))
            barrier.wait(timeout=5)
            return harness._etype(CALL, [])

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(work, typ) for typ in ("int", "bool")]
            self.assertEqual([future.result(timeout=10) for future in futures], ["int", "bool"])

    def test_two_threads_retain_their_constructor_field_types(self):
        barrier = threading.Barrier(2)

        def work(result_type):
            harness._set_ctx(task(result_type))
            barrier.wait(timeout=5)
            return harness._arm_types(ARMS)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(work, typ) for typ in ("int", "bool")]
            self.assertEqual([future.result(timeout=10) for future in futures],
                             [{"Wrap": ["int"]}, {"Wrap": ["bool"]}])

    def test_nested_context_does_not_change_its_callers_declarations(self):
        harness._set_ctx(task("int"))
        Context().run(harness._set_ctx, task("bool"))
        self.assertEqual(harness._etype(CALL, []), "int")


if __name__ == "__main__":
    unittest.main()
