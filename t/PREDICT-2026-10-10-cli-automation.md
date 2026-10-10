# T82: make command-line verification dependable for automation

Registered before new controls or implementation changes. Static inspection
of cli._verify_dir suggests that progress output can enter --json stdout,
declared task names can be substituted for actual input filenames, and the
directory exit status can count an incomplete repetition set or omit an
explicitly requested but unavailable kernel. These are hypotheses until
reproduced, not claims about incorrect kernel proofs.

Bars: JSON mode emits independently parseable JSON records with the actual
source path; progress belongs on stderr. Explicitly requested unavailable
kernels fail before dispatch. A run with fewer than three repetitions cannot
report complete agreement. Invalid worker counts fail before dispatch. A
failed report replacement preserves the previous complete report. Default
three-repeat text output and the existing committed-matrix guards retain their
semantics. Exercise the public command with installed kernels as well as
controlled failure injection.

Prior work: T75's invalid-input and provisional-verdict gates, T79's editor
identity checks, cli.py, run_par.py, cache.py and the existing CLI tests.
The standard JSON decoder provides the independent output-format control:
https://docs.python.org/3/library/json.html. Python documents atomic successful
replacement with os.replace:
https://docs.python.org/3/library/os.html#os.replace.

The initial controlled run failed twelve checks, including subcases. It
reproduced progress mixed into JSON, false success with a requested missing
kernel, agreement tables with one or two repetitions, work dispatched before
empty/minimum-kernel refusals, nonpositive worker counts accepted, invented
source paths, and output-directory state retained between CLI calls. The
report replacement control showed that the writer did not use an atomic
replacement, so the injected replacement failure was never reached.

The repairs keep progress on stderr in JSON mode, retain actual input paths,
validate execution requirements before dispatch, and atomically replace a
completed table. Directory runs require at least three repetitions; single-file
provisional checks retain their existing behavior. The previous output
directory is restored when the invocation finishes.

An additional control caught a regression in the first atomic writer: replacing
a report symlink removed the link instead of updating its target. Resolving the
target before replacement preserves the existing path behavior. The final
affected regression command passed 42 tests and 131 subtests:

```sh
python -m pytest -q t/test_cli_automation.py t/test_validation_gate.py \
  t/test_verify_names.py t/test_run_par_guards.py t/test_verdict_cache.py \
  t/test_library_concurrency.py
```

A real three-repeat Dafny/Lean run on the committed abs task, copied to a
filename different from its task name, exited zero. Its stdout parsed as
exactly two JSON records naming the real input path, both verified/refuted;
progress appeared only on stderr. No specification, lowering or proof budget
changed. Clean-checkout replication remains the next measurement.
