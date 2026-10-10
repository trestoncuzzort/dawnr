# T74: applications beyond the UVa batch

Registered 2026-10-10 before application runs. Base: 9422625. The request is to
apply t to useful mathematical and repository problems. This machine has Dafny
4.11.0 and Lean 4.33.1; the other five columns are not claimed.

## Prior work and scope

Read ENGINE.md, SPEC.md, SYNTAX.md, T73 and the research landscape before writing.
The existing suites already cover sums, Fibonacci, gcd, basic search, full-array
reversal and PX4. This batch adds independent contracts and executable comparisons
for more arithmetic, binary search boundaries, prefix scans, indexing and data
batching. Reuse the existing lowerings, twin ladder and certificate adapters.

Sources: Python's [bisect contracts](https://docs.python.org/3/library/bisect.html),
[itertools](https://docs.python.org/3/library/itertools.html),
[importlib](https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly),
NumPy's [unequal partition rule](https://numpy.org/doc/stable/reference/generated/numpy.array_split.html),
[Dafny induction](https://dafny.org/dafny/OnlineTutorial/Lemmas.html), and
locallm at e81b5e456c5f1da6de2f70f7954dbc3de283e795 (`train_factorial.py`,
`token_shards.py`). Mathematical integer contracts do not prove machine arithmetic
or floating-point sampling. A restatement of repository arithmetic does not prove
the surrounding repository.

## Predictions and falsifiers

1. Attempt at least 32 distinct application tasks. Each remains in the report,
   including refusals and timeouts. At least 25 will be verified / refuted in
   Dafny, at least 12 in both Dafny and Lean. A proof alone never counts.
2. Compile each application's Dafny lowering and compare it with an independently
   written Python oracle on boundary, exhaustive small and seeded larger inputs.
   Zero disagreements is the bar. These comparisons are finite tests, not proofs.
3. Probe `judge.compile_task` twice in one process, including two different bodies
   with the same task name. Prediction: the import cache reuses the first module.
   Repair only after a failing regression; both callables must remain independent.
4. Probe locallm's actual batch generator with fewer examples than batch_size.
   Prediction: it yields no batch, while main retries epochs without advancing
   step. State its actual epoch-count expression in t and refute it at n=1,b=2.
   A fix must reject invalid/insufficient batches before model construction, keep
   full batches and deterministic order unchanged, and have a regression witness.
5. Save a reproducible runner, source identities, partial kernel table and test
   results. Re-run the application matrix from a clean local clone. Preserve the
   established seven-kernel tables and their README totals.

The 32 planned tasks: sum_squares, sum_odds, arithmetic_series, geometric_series,
integer_sqrt, triangular_inverse, choose_two, quotient_remainder, modular_add,
modular_multiply, bisect_left, bisect_right, prefix_sums, argmin_first, run_count,
horner, ceil_div, align_up, batch_bounds, shard_bounds, flatten2, unflatten2,
midpoint, checked_add, buffer_range, saturating_add, window_count, resume_position,
normalize_index, full_batches, range_length, decimal_digits.

## Read

First development pass: Dafny 27/32, Lean 14/32, both 13/32. The uncounted tasks
remain in the suite. The executable run exposed a second judge defect before
comparison: Dafny doubles underscores in Python identifiers. A failing regression
now pins that lookup too. Source: Dafny 4.11.0's PythonCodeGenerator.cs.

The first executable run also caught invalid top-level proof assertions in four
new tasks; SPEC permits assertions only inside lemmas. They were moved to proved
lemmas, and every task now passes the well-formedness check before compilation.

Before a second batch: add eight applications (40 total): extended_gcd,
peasant_multiply, binary_power, max_subarray, count_inversions, leap_year,
interval_intersection and rolling_context. Prediction: at least six count in
Dafny. max_subarray states the standard Kadane recurrence; exhaustive subarray
enumeration tests that modelling step. Sources: the Euclidean invariant in
SPEC.md, [Python calendar](https://docs.python.org/3/library/calendar.html),
and locallm's plain_generate.py context suffix. Existing integer_exponential
uses linear multiplication; binary_power tests a different logarithmic algorithm.

### T74 final read (2026-10-10 11:27Z): all bars held

Clean clone of **9ccd6ccbe6d61cc6e07037e69f3b7f939fbcede1**; clean before and after
the run. Dafny 4.11.0, Lean 4.33.1, Python 3.14.7. A systemd user scope capped the
matrix at 8 GiB. The command was:

```sh
python3 t/cli.py verify problems/applications --kernels dafny,lean --jobs 2 --flake 3 \
  --out /tmp/t-applications-clean-lowerings --table /tmp/t-applications-clean-table.md --json
```

1. **Held.** 40 attempted tasks; **40/40 Dafny, 18/40 Lean**, all counted cells
   verified / refuted. Every side repeated three times, with no flake. Lean's
   other 22 cells remain visible: 19 real programs unproved, 3 timed out. The
   command exits 1 because those cells do not count. No known-wrong twin verified.
   The eight-task addendum also held: all eight count in Dafny.
2. **Held.** `python3 problems/applications/check.py --json ...` passed **82,880
   of 82,880 cases**, covering all 40 compiled programs. This includes integers
   beyond machine width and independent exhaustive subarray/inversion oracles.
   These are finite tests, not proofs of the compiler or Python.
3. **Held.** Before repair, compiling `probe(x)=x+1`, then `probe(x)=x+2`, returned
   6 for both at x=5. A second task name could instead raise AttributeError.
   Loading each translation with its own module objects and restoring import
   state fixes both. Underscore escaping needed a separate correction. The new
   judge regressions and existing build tests pass **12/12** on the clean clone.
4. **Held.** The actual pinned locallm generator yields zero batches at n=1,b=2;
   its epoch expression returns one. Both Dafny and Lean accept the original
   body's refutation certificate at that input. Corrected full_batches counts
   in Dafny. The applied locallm fix, commit
   **3ec301f5f449bbf17f72f7e835bf078e251982ef**, rejects insufficient examples before
   model construction and validates direct generator use. Its full trainer suite
   passes **10 tests and 3 subtests** with CPU PyTorch 2.14.1. The original generator
   fails the new rejection regressions; valid-batch controls preserve its order.
5. **Held.** The clean-clone matrix, all 80 verdicts, executable receipts, task
   hashes and all 160 lowering hashes are saved under `problems/applications/`.
   `compare_repositories.py` passed **13,562** source comparisons/rejection checks:
   1,040 batch counts, 136 rejected empty epochs, 5,424 resume positions, 332 index
   normalizations, 1,235 window counts, 325 context suffixes and 5,070 NumPy
   partition endpoints. NumPy was 2.5.3; original source is pinned to locallm
   e81b5e4 and fixed source is hashed. This establishes the named code slices,
   not either whole repository. The existing seven-kernel tables were not replaced.

The last Dafny misses were solved by explicit arithmetic lemmas, without larger
budgets or weaker contracts: multiplication order and quotient uniqueness (using
the existing UVa 11526 proof and Dafny's DivMod library), a Bezout step, and the
halving/doubling identity. Lean still needs stronger automation for variable
division and some quantified or recursive goals. In particular, extended_gcd's
Lean real and twin both time out. That is an open proof obligation, not a false
program or a counted cell.
