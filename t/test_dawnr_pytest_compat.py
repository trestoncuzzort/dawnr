"""Exercise cleanup semantics, including a setUp that never completes."""
from contextlib import contextmanager
import unittest
from unittest import mock

import dawnr_pytest_compat as compat


def test_cleanup_runs_in_reverse_order_after_setup_fails():
    events = []

    @contextmanager
    def resource(name):
        events.append(("enter", name))
        try:
            yield name
        finally:
            events.append(("exit", name))

    class BrokenSetup(unittest.TestCase):
        def setUp(self):
            assert compat.enter_context(self, resource("first")) == "first"
            compat.enter_context(self, resource("second"))
            raise RuntimeError("setup failed")

        def runTest(self):
            raise AssertionError("test body must not run")

    result = unittest.TestResult()
    BrokenSetup().run(result)
    assert len(result.errors) == 1
    assert events == [("enter", "first"), ("enter", "second"), ("exit", "second"), ("exit", "first")]


def test_failed_enter_does_not_register_exit():
    events = []

    class BrokenEnter:
        def __enter__(self):
            raise ValueError("acquisition failed")

        def __exit__(self, *args):
            events.append(args)

    case = unittest.TestCase()
    with case.assertRaises(ValueError):
        compat.enter_context(case, BrokenEnter())
    case.doCleanups()
    assert events == []


def test_plugin_leaves_native_implementation_alone():
    class Native:
        enterContext = object()

    original = Native.enterContext
    with mock.patch.object(compat, "TestCase", Native):
        compat.pytest_configure(None)
    assert Native.enterContext is original


def test_plugin_installs_only_when_missing():
    class Older:
        pass

    with mock.patch.object(compat, "TestCase", Older):
        compat.pytest_configure(None)
        compat.pytest_configure(None)
    assert Older.enterContext is compat.enter_context
