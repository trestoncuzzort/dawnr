# T76: restore the missing Landlock launcher

Registered before the packaging regression or restoration. T75's clean checkout
skipped all five Landlock tests because `py_sandbox.LANDLOCK_EXEC` names a file
that is absent. The launcher still exists in the engine's source repository,
dawnr commit `ca6bc234547e3d73a50af923e1cc73b0fabf2864`, at `t/landlock_exec.py`.
The AppArmor helper is already present; this is one missing runtime file.

Prediction: restoring the existing launcher unchanged makes the Landlock probe
available on this Linux host and permits the existing containment tests to run.
Bars: a kernel-independent packaging regression fails before restoration and
passes afterwards; all five runtime controls execute rather than skip here;
filesystem/process/network denial and the positive local-write control retain
their expected outcomes; a simulated unsupported kernel executes no payload.
No host policy or sandbox selection is changed.

Two group-signal tests currently request SIGKILL. Change those probes to signal
zero, which asks the kernel to check permission without sending a signal. Keep
their PermissionError assertions. The explicitly owned child-process control
still checks a real signal. This avoids broad destructive effects if a future
regression disables the sandbox being tested.

Prior work: `t/py_sandbox.py`, `t/test_py_sandbox_landlock.py`, the missing-file
skip recorded in T75, and the existing dawnr launcher; the
[Linux Landlock documentation](https://docs.kernel.org/userspace-api/landlock.html)
defines ABI detection, ruleset inheritance and the need to handle supported
access rights explicitly. The launcher also pairs Landlock with a seccomp
filter for operations outside Landlock's coverage. This is a packaging repair,
not a newly designed security policy or a proof of sandbox completeness.

The packaging test failed before restoration because the advertised launcher
did not exist. The restored file is byte-identical to the pinned dawnr source:
SHA-256 `5099f8a4ec58d6099c939ae6af5019c04d9c6bef6880b342c24690c676d26e3d`.

`python -m pytest -q -rs t/test_sandbox_packaging.py t/test_py_sandbox_landlock.py
t/test_py_sandbox.py` passed **22 tests with no skips**. All five previously
skipped Landlock controls executed, including the unsupported-kernel refusal.
Clean checkout `f7384c4` then passed the full collected suite: **842 passed,
40 skipped, one expected failure, 150 passing subtests, five existing warnings**.
The five missing-launcher skips are gone. Commands and source hashes are in
`t/evidence/2026-10-10-sandbox.json`. These finite controls do not establish
completeness of the syscall policy or the host kernel's correctness.
