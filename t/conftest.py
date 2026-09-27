"""pytest is not this project's test runner (most files here are driven by
their own `if __name__ == "__main__":`, run as `python3 test_x.py`, per
AGENTS.md); CI uses it anyway to collect plain `test_*` functions and
unittest.TestCase files uniformly in one pass. This bridges one of the
project's own conventions into pytest without changing any test file:

`--slow` mirrors the flag test_lift_check.py and test_lift_report.py already
define for their own `if __name__ == "__main__":` entry point (see their
`run(slow: bool = False)`): fixture-injected here so pytest can call their
`test_x(slow)` functions at all. Default False keeps CI on the fast path,
which is dafny- and corpus-free by the tests' own design (`if not slow:
print("skipped (pass --slow)"); return`).

pytest.ini beside this file makes the other adjustment (python_functions),
since ini options cannot be set from a conftest.
"""
import pytest


def pytest_addoption(parser):
    parser.addoption("--slow", action="store_true", default=False,
                      help="also run the dafny-invoking checks (see test_lift_check.py)")


@pytest.fixture
def slow(request):
    return request.config.getoption("--slow")
