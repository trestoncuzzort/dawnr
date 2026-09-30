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


# The shell scripts and the lab tools (2026-09-30). These modules test bash scripts (the data
# queue, gen_fleet, lab_mode, lab_gpu, the run tree's exit paths) or the lab's process table
# (os.sysconf, stall_check, lab_status): their subject is the Linux side, and on a machine whose
# only bash is Windows' WSL launcher without a distribution they fail on the launcher's message,
# not on anything they test. They are skipped where `bash -c true` does not run; the model and
# proof-engine tests run everywhere.
SHELL_AND_LAB_MODULES = {"test_r12_data_queue.py", "test_gen_fleet.py", "test_lab_mode.py", "test_lab_gpu.py",
                         "test_run_tree_exit_paths.py", "test_stall_check.py", "test_lab_status.py",
                         "test_ci_workflow.py", "test_preflight_local.py", "test_preflight_scope.py"}


def _bash_runs() -> bool:
    import shutil
    import subprocess
    bash = shutil.which("bash")
    if bash is None:
        return False
    try:
        return subprocess.run([bash, "-c", "true"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              timeout=30).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def pytest_collection_modifyitems(config, items):
    if _bash_runs():
        return
    skip = pytest.mark.skip(reason="a shell-script or lab-tool test; this machine has no bash that runs a command")
    for item in items:
        if item.path.name in SHELL_AND_LAB_MODULES:
            item.add_marker(skip)
