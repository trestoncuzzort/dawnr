# T80: isolate concurrent witness type contexts

Registered before the new probes and changes, at `1a8fe63`. The witness ladder
stores the current task's function and datatype declarations in a mutable
module dictionary. Library/editor callers can enter the ladder concurrently.
Prediction: after two tasks install contexts using the same helper or
constructor name with different types, one caller observes the other's types.
This is a witness-selection reliability hypothesis, not an already established
false kernel verdict.

Bars: coordinated threads reproduce cross-task function/datatype contamination
before repair; each caller retains its own context afterward; an isolated
asynchronous context cannot modify its caller's declarations. Preserve the
sequential witness ladder byte-for-byte on all committed tasks, comparing the
selected body, operator and measured witness before and after. Run the existing
witness/type/concurrency regression tests. A missing twin remains a refusal.

Prior work: `harness._set_ctx`, `_etype`, `_arm_types`, T75's source-file
isolation and T79's asynchronous editor workers. Python's context variables
provide context-local state for threads and asynchronous tasks:
https://docs.python.org/3.14/library/contextvars.html.

All three coordinated controls failed before repair: both worker threads
observed the last installed function/datatype types, and entering a separate
context changed the caller's declarations. The repair stores a fresh task
dictionary in a ContextVar instead of mutating the module dictionary.

After repair, the affected regression command passed 40 tests:

```sh
python -m pytest -q t/test_witness_context.py t/test_twin_rule.py \
  t/test_real_witness.py t/test_vacuous_requires.py t/test_compositional_types.py \
  t/test_datatype_recursion.py t/test_library_concurrency.py
```

Calling `harness.twin_for(tasks_io.load_task(path))` over every committed task and
comparing the selected body, operator and measured witness before and after
found 114 tasks and zero changes. No lowering or kernel contract changed.
Both serialized snapshots have SHA-256
`dee7e3ec02e6fbeea0857e819ff5c86d88d0051d58bbf5a7ed78cd592f173549`.
This establishes context isolation and sequential compatibility; it does not
establish that every concurrent execution is free of other defects.
