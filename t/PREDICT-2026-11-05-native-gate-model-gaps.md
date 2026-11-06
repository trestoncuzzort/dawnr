# Native gate: limits of the model are not defects; heap inputs; bounds, 2026-11-05

The gate from `t/PREDICT-2026-11-05-native-cases.md` found real defects, but writing a case
cost hours, and the working brief for case authors had grown a list of rules "that cost time
if you learn them by trial". This work removes the rules a tool can apply by itself. While
reading the gate to do that, probes of CBMC 6.11.0 found a false verdict in it.

## What the probes showed before this file was written

These were found by running the tool. They are recorded as measurements, not predictions.

| probe | result |
|---|---|
| Correct recursive code, `--unwind 1`, through the unchanged gate | verdict `counterexample`, confirmed witnesses 0, replay `not_reproduced` |
| A callee with no body, through the unchanged gate | verdict `counterexample`, no witness |
| A suspected hole: `complete` over a callee with no body | **did not exist.** CBMC 6.11.0 fails a `no-body` property, so `complete` cannot be reached |
| `malloc` and `free` in a harness, assumption coverage | 2 extra goals, located in `<builtin-library-malloc>`; the harness's own goals are unchanged |
| Pointer comparisons into `malloc` memory of symbolic size | no false violation (44 properties, success) |
| A function under test that allocates: sound, then broken | success on 76 properties; failure at the out-of-bounds write |
| `RLIMIT_AS` of 200 MB on a model that wants more | exit 6 after 0.5 s, JSON message `Out of memory` |
| More than 256 objects | exit 6, JSON message naming `--object-bits` |
| `--unwindset depth:5` | bounds recursion by function name; `depth.recursion:5` does not match |

A shortfall of the unwinding bound on correct code being reported as `counterexample` is a
false verdict, which `AGENTS.md` rule 2 forbids. The suite did not hide it: its `original` row
needs a confirmed witness, and its short-unwind row expects `incomplete` or `vacuous`, so a
case would fail its controls rather than publish the wrong word. A single `--variant` run said
`counterexample`, exit 1.

The names come from the CBMC source at tag `cbmc-6.11.0`: `src/goto-symex/symex_goto.cpp`
(`f.unwind.N`), `src/goto-symex/symex_function_call.cpp` (`f.recursion`, `f.no-body.g`). Those are
the only `vcc` sites in the goto-symex files read, other than the assertion instruction itself,
so an allow-list of property classes is not needed. Not every file of that directory was read.

## Changes

1. `native_check.interpret`: a failed `.no-body.` property gives `incomplete` and names the
   callee. A failed `.recursion` property counts as an unwinding shortfall, like `.unwind.`, in
   the verdict, in the loop count and in the witnesses. Coverage goals located in
   `<builtin-library-*>` are recorded apart and do not count as harness assumptions; the harness's
   own goals stay strict. Reachability of the end marker still decides vacuity.
2. A memory ceiling (`RLIMIT_AS`, `--memory-limit-mb`, default 4096) gives the named non-result
   `out_of_memory`. It replaces the `ps` watcher written twice in the working scripts.
3. A tool error carries CBMC's message in its reason.
4. `native_case`: `array` and `string` inputs. Each is a heap object of exactly the drawn size,
   filled from scalar draws, so witnesses and replay work unchanged. A `string` has one more
   byte for the terminator and `strlen(s) == s_len`; no string is lost by that, since a shorter
   one has a smaller length.
5. `#line` directives are refused, because a `#line` could relocate an assumption into a
   library file name and hide it from the coverage count.
6. `--find-bounds`: raises only the loops whose unwinding property fails, using `--unwindset`,
   then narrows. CBMC's documentation sets these bounds by hand and the search below found no
   tool that searches for them.
7. A harness assignment to a member, such as `object.size = 1`, no longer collides with an input
   named `size`. Optional checks: `--malloc-may-fail`, `--malloc-fail-null`,
   `--memory-leak-check`, `--pointer-primitive-check`, `--memory-cleanup-check`. Leak reports are
   read in the replay, and leak detection is off in the replay unless the leak check is asked for.

Searched for prior art on item 6: the CBMC manual (diffblue.github.io/cbmc/cprover-manual/md_cbmc-unwinding.html),
the CBMC training FAQ (model-checking.github.io/cbmc-training/faq/loop-unwinding.html), Kani's
notes (model-checking.github.io/kani/cbmc-hacks.html). Those give the syntax and the counting rule.

## Predictions, written before these were run

| # | prediction | falsified by |
|---|---|---|
| P1 | Correct recursive code at `--unwind 1` gives `incomplete`; at 5 `complete`; no witness is replayed for a bound | any `counterexample` |
| P2 | A callee with no body gives `incomplete`, naming it, also when another property fails | any `counterexample` or `complete` |
| P3 | A harness with `malloc`, and a function under test that allocates: sound gives `complete`, broken gives `counterexample` with a replay status of `memory_error` | another verdict or status |
| P4 | All 29 published suite rows of the 8 published cases, and the 3 rows of the PX4 case, keep their verdict, unit hash and property count | one changed row |
| P5 | No published case reaches the 4096 MB ceiling; a small ceiling on a synthetic model gives `out_of_memory` | a published case stopped; or any other verdict |
| P6 | The libuv case rewritten with an `array` input, a copy, not the fixture: same verdicts, confirmed witness, 9 or more harness lines removed, `fixed` time within 3 times the hand-written one | another verdict, or more than 3 times |
| P7 | The flac case rewritten with a `string` input, a copy: same verdicts and no new failing property, time within 3 times | another verdict, a new failure, or more than 3 times |
| P8 | `--find-bounds` on the 8 published cases reaches no unresolved bound and a bound no greater than the published one for every loop, and the resulting suite keeps its verdicts | a larger bound needed, or a changed verdict |
| P9 | `--find-bounds` gives a smaller model, in SAT variables, than the published global bound on at least 3 of the 8 | fewer than 3 |

P1 to P3 repeat what the probes showed, through the changed gate. P4 to P9 have not been run.

## Added after those were written: executions that vanish

Reading `symex_goto.cpp` for the names above turned up the line "no unwinding assertion will be
generated for self-loop", so this was probed as well. Each function below stops on input 0 and
returns 1 otherwise, and the harness asserts that it returns 1. The input 0 never returns, so
`complete` on that assertion is false.

| how the function stops on 0 | gate as published | gate with changes 1 to 7 |
|---|---|---|
| `abort()`, `exit(1)`, `_Exit(1)` | **`complete`** | **`complete`** |
| `__builtin_unreachable()` | **`complete`** | **`complete`** |
| `while (1) ;`, `while (a == 0) ;`, `here: goto here;` | **`complete`** | **`complete`** |
| `pthread_exit(0)` | `tool_error` | **`complete`**: a regression made by change 1 |
| `longjmp(env, 1)` | `tool_error` | `counterexample` |
| `quick_exit(1)`, `__builtin_trap()`, `__builtin_abort()`, `raise(SIGABRT)` | `counterexample` | `incomplete` |
| `assert(0)` | `counterexample` | `counterexample` |
| control: `return 1` | `complete` | `complete` |

Why, from the CBMC source at tag `cbmc-6.11.0`: `src/ansi-c/library/stdlib.c` models `abort`, `exit`
and `_Exit` as `__CPROVER_assume(0)`, and `pthread_lib.c` and `threads.c` do the same for
`pthread_exit` and `thrd_exit`; those assumptions end the execution without a property, and for
`abort`, `exit` and `_Exit` they give no coverage goal either. `builtin_functions.cpp` treats
`__builtin_unreachable` as nothing at all (`// says something like UNREACHABLE;`), so reaching it, which is
undefined behaviour, is not seen. `symex_goto.cpp` turns a self-loop into an assumption unless
`--no-self-loops-to-assumptions` is given, and the assumption is made during symbolic execution, so
assumption coverage cannot see it. A hang on one input therefore gave `complete`, while the same loop
with a statement in its body gave `incomplete`.

The ten models holding a constant false assumption were listed by a script over that directory. The
ones left out below: `ExitThread` (Windows only), and `__CPROVER_contracts_library` (contracts, not used here).

Change 8. All three stages pass `--no-self-loops-to-assumptions`. The inventory and checking stages also
link a second file, `stops.c`, with weak definitions of `abort`, `exit`, `_Exit`, `_exit`, `quick_exit`,
`pthread_exit` and `thrd_exit`, and map `__builtin_unreachable`, `__builtin_trap` and `__builtin_abort` to
stops of their own with `-D`. Each fails a property named `native.stop.NAME` and then ends the execution, so
the stop is seen and nothing after it gives a false alarm. The checked unit and its hash do not change, and a
project's own definition still wins. A case that means to stop can list the name in `allowed_stops`: that
stop then acts as before and the receipt says so. The replay reports `stopped_early` when the
native program ends after it started and before its last line. A `longjmp` is `incomplete`: the model refuses it.

| # | prediction, written before change 8 was made | falsified by |
|---|---|---|
| P10 | None of `abort`, `exit`, `_Exit`, `_exit`, `quick_exit`, `pthread_exit`, `thrd_exit`, `__builtin_unreachable`, `__builtin_trap`, `__builtin_abort` or the three self-loops gives `complete` on input 0 | one `complete` |
| P11 | The stops give `counterexample` with a confirmed native witness, `stopped_early` or `undefined_behavior`; the self-loops give `incomplete`; the control stays `complete` | another verdict or status |
| P12 | `allowed_stops: ["exit"]` gives `complete` and a receipt naming it; a project's own `abort` wins over the weak one | another verdict, or a link error |
| P13 | No published case moves, counting properties without those of `stops.c`. If one does, a stop was hidden in a published `complete`, and it is a finding to report, not to tune away | a moved row, which is then read |

P12 was falsified while this was being written, before any published case ran. The control for "a
project's own `abort` wins" failed: CBMC given two source files keeps the weak definition in both
orders; only `goto-cc` linking keeps the strong one. So `stops.c` is not weak: a stop whose definition
is in the unit is left out of it. The name of that test changed with it. The first half of P12 stands.

## Added: the solver

The slowest row of the first regression run was flac `fixed`, 270 s. On that unit, on one machine at once:

| `--sat-solver` | seconds | |
|---|---|---|
| `cadical` | 6.5 | |
| `minisat2`, the default | 351.1 | |
| `picosat`, `ipasir`, `zchaff`, `glucose`, `booleforce` | 350 to 358 | each answers "is not available" and runs the default |

Change 9. `--solver` chooses `minisat2` or `cadical`, the two in the pinned build. Any other name is refused,
because CBMC's own answer to one is a message and exit 0. The receipt records the solver.

| # | prediction, before the other cases were run on it | falsified by |
|---|---|---|
| P14 | CaDiCaL on all 8 published cases: the same verdicts, unit hashes and property counts as MiniSat; another witness may be found, but every `original` keeps at least one confirmed | a changed verdict or count, or an `original` with none confirmed |
| P15 | The total time of the 8 suites falls by at least half under CaDiCaL, and no single row takes more than 3 times as long | less than half, or a row 3 times slower |

If P14 and P15 hold, CaDiCaL becomes the default. A second solver is not an independent proof: both read the
one formula CBMC wrote, and neither result is checked by a proof checker here.

## Results

All on the final bytes of commit 8219841 and later, GCC 13.3.0, CBMC 6.11.0, run as an unprivileged user. Receipts are in
[`evidence/native-gate-2026-11-05/`](evidence/native-gate-2026-11-05/), from `native_fixture_check.py` and `native_rewrite_check.py`.
New tests: 31 of them fail against the published gate, for the reasons they name, and all pass here.

| # | outcome | measured |
|---|---|---|
| P1 | holds | recursion at `--unwind 1` is `incomplete` with no replay, and at 5 `complete` |
| P2 | holds | a callee with no body is `incomplete` and named, also beside another failure |
| P3 | holds | sound `complete`, broken `counterexample`, replay `memory_error`, `heap-buffer-overflow` |
| P4 | holds | 29 of 29 published rows the same; the 3 PX4 rows as expected. Before the stops, then again after them |
| P5 | holds | peak 524 MB under MiniSat and 882 MB under CaDiCaL, against 4096 MB; a synthetic model at 200 MB gives `out_of_memory` |
| P6 | holds, with one thing to say | same verdicts and witness, time 0.59. 9 lines removed and 2 aliases added, so a net of 7, short of 9 if the prediction meant net |
| P7 | holds | same verdicts, same failing properties, time 0.62. Faster, which was not predicted |
| P8 | holds | no loop needs more than its published bound; every suite keeps its verdicts |
| P9 | holds | a smaller model on 4 of 8 |
| P10 | holds | no stop and no self-loop gives `complete` |
| P11 | holds | stops `counterexample`, witness `stopped_early` or `undefined_behavior`; self-loops `incomplete`; the control `complete` |
| P12 | half falsified | `allowed_stops` holds. A weak stop does not lose to a project's definition, as written above |
| P13 | holds | 29 of 29 again, on both solvers. **No published `complete` was hiding a stop or a hang** |
| P14 | holds | same verdicts, hashes and counts; every `original` keeps a confirmed witness. Betaflight and INAV go from 2 to 1 |
| P15 | half falsified | total time 997 s to 302 s, a ratio of 0.30, but libcoap is 4.27 and 3.63 times slower, past the limit of 3 |

So **MiniSat stays the default**, as written before the run. `--solver cadical` is the documented option for a slow case. Worst and best:

| case, row | MiniSat s | CaDiCaL s | ratio |
|---|---:|---:|---:|
| flac `fixed` | 302.35 | 6.32 | 0.02 |
| open62541 `fixed` | 305.73 | 109.57 | 0.36 |
| open62541 `original` | 332.60 | 112.22 | 0.34 |
| libevent `fixed` | 19.68 | 10.25 | 0.52 |
| msgpack `fixed` | 9.34 | 13.67 | 1.46 |
| libcoap `original` | 3.74 | 13.57 | 3.63 |
| libcoap `fixed` | 2.79 | 11.91 | 4.27 |

Array and string inputs, in copies, with the published fixtures unchanged. The heap objects were faster, which nothing predicted:

| case | harness lines | assumptions by hand | `fixed` s by hand, rewritten | ratio | failing properties |
|---|---|---|---|---:|---|
| libuv-utf8-decode1 | 29 to 22 | 1 to 0 | 0.68, 0.40 | 0.59 | the same |
| flac-metaflac-parse-uint32 | 43 to 37 | 0 to 0 | 313.12, 193.37 | 0.62 | the same |
| libevent-servname-port-range | 62 to 43 | 12 to 0 | 23.10, 14.85 | 0.64 | the same |

Per-loop bounds found by search, under CaDiCaL. A model only shrinks where a loop was over-unwound. The others keep their size,
and the search then costs time for nothing but the loop count and a proposal that needs no guess:

| case | published `--unwind` | found, above a default of 2 | attempts | SAT variables, published to found | `fixed` s |
|---|---:|---|---:|---|---|
| betaflight-uvarint-encode | 6 | both loops 5 | 8 | 6,787 to 6,018 | under 1 |
| inav-uvarint-encode | 6 | both loops 5 | 8 | 6,787 to 6,018 | under 1 |
| msgpack-c-print-buffer-empty-bin | 10 | 9, 3, 3 | 8 | 601,159 to 208,532 | 13.67 to 6.39 |
| open62541-datetime-parse-year | 6 | one loop 6 | 6 | 208,935 to 167,613 | 109.57 to 93.35 |
| flac-metaflac-parse-uint32 | 12 | three loops 12 | 15 | the same | 6.32 to 6.39 |
| libevent-servname-port-range | 12 | four loops 12 | 16 | the same | 10.25 to 10.96 |
| libcoap-opt-parse-delta | 4 | none | 2 | the same | 11.91 to 12.96 |
| libuv-utf8-decode1 | 4 | none | 2 | the same | under 1 |

## What this bought

Three kinds of wrong answer are gone from the gate, and one of them was serious: it could read a hang as proved. Nothing published
rested on it, which the regression shows rather than assumes. One fix made another case worse, `pthread_exit`, and a probe
written to test that very worry caught it the same hour. The cost of a case fell on the measured rows, and the rules a person had to
learn by trial are now applied by the tool.

The stops list comes from reading CBMC's library at the pinned tag. A later CBMC could add another way to stop, and the gate refuses any
other version for that reason among others. The check in this file is not a proof that no other way exists.
