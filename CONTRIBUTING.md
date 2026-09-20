# Contributing

This is a research repository under a research-use license (see LICENSE), not an open-source project taking
feature work. What is genuinely useful:

- **A number you could not reproduce.** Say which script, which machine, and what you got instead.
- **A counterexample.** A task all seven checkers accept whose specification does not hold, or a twin they fail
  to refute. That is the highest-value bug report here.
- **A lowering gap with a witness.** An abstain or a timeout that should be a verdict, with the task attached.

If you open a pull request, you agree that your contribution is licensed under LICENSE like the rest of the
Work, that you have the right to license it, and that the copyright holder may also relicense it as part of a
commercial license of the whole Work. Contributions that cannot be licensed on those terms cannot be merged.

Two conventions the repository holds to: no number without the script that measured it, and no em-dashes in
prose.

## Running the tests

```bash
cd t
ls test_*.py | grep -v test_lab_gui | sed 's/\.py$//' | xargs python3 -m unittest
```

**Exclude `test_lab_gui.py` when you want a number.** It passes on its own, but
inside a combined run its tkinter teardown raises `Tcl_AsyncDelete: async
handler deleted by the wrong thread`, the interpreter takes SIGABRT, and the
tally is never printed -- so `python3 -m unittest discover` ends with no count
at all rather than with a failure you can read.

Known-failing, so nobody goes hunting: one assertion in
`t/test_lower_spark_loop_cert.py` (the two-loop fallback emits `F_Cert` where
the test expects `F`), and three errors in `t/test_loop_train.py` on a machine
without `datasets` (see `t/requirements.txt`). Everything else passes.
