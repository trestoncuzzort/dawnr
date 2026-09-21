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

And the model builder's own tests, which the command above does not reach
because it only looks inside `t/`:

```bash
cd locallm
ls test_*.py | sed 's/\.py$//' | xargs python3 -m unittest
```

On a machine without torch that reports 102 tests and 20 errors, and every one of
the 20 is `ModuleNotFoundError: No module named 'torch'` raised while *importing*
the test module, not a failure in anything. The two that cover the window's own
look and its front page are written to need neither torch nor a display, so they
run anywhere:

```bash
cd locallm && python3 -m unittest test_look test_home
```

### On macOS, and why it is not optional

The portable tests run on Apple's system Python, which is 3.9 with **Tk 8.5**, the
oldest Tk of the three platforms. Measured 2026-09-21: 139 tests, OK.

Run them there before believing a GUI change. Two bugs landed that day that no
test on Linux could have caught, because both are Tk 8.5 against Tk 8.6:

* `configure(style=...)` on a `ttk.Scrollbar` answers `unknown option "-style"`
  and took the whole window down on launch. Set a ttk style at construction,
  which every platform accepts.
* `create_text(..., angle=90)` answers `unknown option "-angle"`, because canvas
  text rotation arrived in Tk 8.6. It did not crash; the label simply never drew,
  and only the log knew.

The rule that follows: a widget option that works here is not a widget option that
works. Check it against Tk 8.5 or set it at construction.

**Exclude `test_lab_gui.py` when you want a number.** It passes on its own, but
inside a combined run its tkinter teardown raises `Tcl_AsyncDelete: async
handler deleted by the wrong thread`, the interpreter takes SIGABRT, and the
tally is never printed -- so `python3 -m unittest discover` ends with no count
at all rather than with a failure you can read. Run it on its own, because it
is the only test that builds the real window:

```bash
cd t && python3 -m unittest test_lab_gui
```

Known-failing, so nobody goes hunting: one assertion in
`t/test_lower_spark_loop_cert.py` (the two-loop fallback emits `F_Cert` where
the test expects `F`), and three errors in `t/test_loop_train.py` on a machine
without `datasets` (see `t/requirements.txt`). Everything else passes.
