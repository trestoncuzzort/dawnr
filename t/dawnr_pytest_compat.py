"""Compatibility for dawnr's Python 3.10 CI: pytest -p dawnr_pytest_compat.

The pinned engine's CLI tests use TestCase.enterContext (new in Python 3.11).
Keep those tests intact and preserve their cleanup semantics on dawnr's older
supported interpreter. This extends test infrastructure, not the engine.

Sources: https://docs.python.org/3.11/library/unittest.html#unittest.TestCase.enterContext
https://docs.python.org/3/library/contextlib.html#contextlib.ExitStack
Local precedent: test_r12_generate.TempDirTestCase.
"""
from contextlib import ExitStack
from unittest import TestCase


def enter_context(case, manager):
    stack = ExitStack()
    result = stack.enter_context(manager)
    case.addCleanup(stack.close)
    return result


def pytest_configure(config):
    if not hasattr(TestCase, "enterContext"):
        TestCase.enterContext = enter_context
