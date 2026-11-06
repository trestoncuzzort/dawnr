# Writing a native case

`t/native_case.py` checks a real C function with CBMC 6.11.0 under a stated machine model, and
replays any counterexample natively under UBSan and ASan. It is separate from the seven t
kernels and does not change their agreement counts. A `complete` verdict covers the stated
inputs, properties and machine model only. It says nothing about callers, other configurations or
the rest of the file. CBMC's translation of C to a formula is trusted, and the SAT solver is
too, unless the verdict is certified (below).

## What a case is

A directory holding `case.json`, the complete source files it names, and usually a `make_case.py`
that writes `case.json` from the files beside it. See `native_fixtures/` for examples.

| key | meaning |
|---|---|
| `format` | `dawnr-native-case-v1` |
| `id`, `repository`, `path` | what is being checked |
| `machine` | `ILP32` or `LP64`: the one the defect needs. A truncation of `long` needs `LP64`; firmware is `ILP32` |
| `sources` | `original` and optionally `fixed`, each with `file`, `sha256`, `revision` and `definitions` |
| `definitions` | whole items copied unchanged: `name`, `line`, `end_line`, optional `kind` (`function`, `macro`, `declaration`) and `starts_with` |
| `prelude` | optional C text placed first: includes, types, macros, stand-ins. Helpers copied from other files keep their licence notice |
| `inputs` | what is drawn nondeterministically; see below |
| `harness` | the body of `void harness(void)` |
| `assertions` | the names used in `__CPROVER_assert(condition, "name")` |
| `assumptions` | the number of `__CPROVER_assume(` in the harness text |
| `loops` | the fewest unwinding properties a complete run must show |
| `unwind`, `unwindset`, `under_unwind` | the global bound (default 4), per-loop bounds, and the bound of the short control (default 1) |
| `checks` | optional CBMC checks, from the list in `OPTIONAL_CHECKS` |
| `input_domain`, `limitations` | what is covered and what is not, in words. They go in every receipt |

### Inputs

```json
{"name": "value", "type": "uint32_t"}
{"name": "buf", "type": "unsigned char", "array": {"min": 1, "max": 5}}
{"name": "text", "type": "char", "string": {"max": 11}}
```

A scalar is one draw. An `array` is a heap object of exactly `buf_len` elements. A `string` is a
heap object of `text_len + 1` bytes, ending in its terminator, with `strlen(text) == text_len`; no
string is lost by that, since one with an earlier NUL has a smaller length. Both add a length
named `<name>_len` and one draw per element named `<name>_e0`, `<name>_e1`, and so on, and the
gate generates and counts their assumptions. Because each object has exactly the drawn size,
reading past its end leaves the object, in the model and under AddressSanitizer. A fixed buffer
cannot show that: a read past the terminator of a short string inside `char text[12]` looks fine.
The harness may read these names but not assign to them, or to any other input.

## Run it

```bash
python3 t/native_case.py CASE --variant fixed --cbmc CBMC --out NEW_DIR  # one variant
python3 t/native_case.py CASE --find-bounds --cbmc CBMC --out NEW_DIR    # per-loop bounds and the loop count
python3 t/native_case.py CASE --suite --cbmc CBMC --out NEW_DIR          # every control
python3 t/native_fixture_check.py --cbmc CBMC --out NEW_DIR              # have the published cases moved?
```

`--solver cadical` uses the build's other SAT solver. On the published cases it took 302 s in all against
MiniSat's 997 s, and one row went from 302 s to 6 s, but another went from 2.8 s to 11.9 s, and it found
fewer distinct witnesses on two cases. Try it when a case is slow. MiniSat stays the default.

`--find-bounds` starts every loop at 2, raises only the loops whose own unwinding property fails,
and narrows each one. Put its `unwind`, `unwindset` and `loops` in the case. It stops and says so
at `--max-bound`, or when a callee has no body. Its answer is a proposal: the gate still has to pass
with it. A large global bound multiplies the model by the longest loop, so per-loop bounds matter:
one case took over 3 GB with a global bound of 26, and 9 seconds with 10.

## The controls and the verdicts

`--suite` runs these in order. All have to give the expected verdict:

1. `original`: `counterexample`, with a witness confirmed by the native replay;
2. `fixed`: `complete`;
3. `vacuous`, which adds a contradictory assumption: `vacuous`;
4. when `loops` is above 0, `fixed` at `under_unwind`: `incomplete` or `vacuous`.

| verdict | meaning |
|---|---|
| `complete` | every inventoried property succeeded, every required unwinding check passed, and every assumption and the end of the harness can be reached. No execution in the domain stopped or hung on the way, unless the case allows that stop by name |
| `counterexample` | a property fails on a concrete trace. Read it with the replay: `assertion_failed`, `undefined_behavior`, `memory_error` and `stopped_early` confirm it, and `not_reproduced` means the model and the real code disagree. Find out why |
| `vacuous` | an assumption, or the end of the harness, cannot be reached |
| `incomplete` | a bound is too short for a loop or for recursion, or a callee has no body so nothing past the call is modelled. This is a limit of the model, not a defect |
| `uncertified` | asked for a certificate, and it could not be had or did not check. See below. `refuted` in the receipt means the tools disagree, and is a finding |
| `out_of_memory` | the model passed `--memory-limit-mb` (default 4096, enforced on Linux). Reduce the input domain or the bounds |
| `timeout`, `tool_error`, `absent`, `unsupported`, `input_error` | no result, with the reason beside it |

## Checking a `complete` verdict without trusting the solver

A counterexample has a check that does not trust the solver: it is replayed natively. A certificate
gives `complete` one too. The formula is exported, CaDiCaL writes an LRAT proof that it has no
solution, and `lrat-check`, a small separate program, checks that proof.

```bash
bash t/build_certify_tools.sh TOOLS   # pinned commits of both, verified after the checkout
python3 t/native_case.py CASE --suite --cbmc CBMC --cadical TOOLS/cadical --lrat-check TOOLS/lrat-check --out NEW_DIR
```

| `certificate.status` | meaning | verdict |
|---|---|---|
| `verified` | the checker printed exactly `c VERIFIED` and exited 0. The receipt holds the hashes of the formula and the proof, and the files are dropped unless `--keep-proof` is given | `complete` |
| `no_formula` | CBMC's simplification decided every property and wrote `p cnf 0 0`, so no solver was asked anything | `complete` |
| `refuted` | the exported formula has a solution, after CBMC said every property holds. The tools disagree | `uncertified` |
| `not_verified`, `solver_failed`, `export_failed`, `timeout`, `absent` | no certificate | `uncertified` |

What this does not do: it does not check CBMC's translation of C to the formula, where a wrong result is more
likely to come from, and it does not replace the coverage stage. A contradictory assumption gives a formula with no
solution and a proof that checks, so a certificate is only asked for after coverage has passed. It is not a
proof in any of the seven kernels. The checker reads text proofs, and a proof can run to gigabytes.

## Executions that stop or hang

Left alone, CBMC lets some executions vanish from the model with no property and no sign:
`abort`, `exit`, `_Exit`, `pthread_exit` and `thrd_exit` are modelled as `__CPROVER_assume(0)`,
`__builtin_unreachable` is ignored, and `while (c) ;` becomes an assumption. An assertion after them
then holds on the inputs that never reach it. So the gate passes `--no-self-loops-to-assumptions`, and
makes each of those a failing property named `native.stop.NAME`. A stop gives `counterexample`, with
the witness replayed natively, and a loop that never ends gives `incomplete`.

Where stopping is the function's contract, such as a command line tool's `exit(1)` on bad input, say so:

```json
{"allowed_stops": ["exit"]}
```

That stop then ends the execution as CBMC models it, with no property, and the receipt names it. Say in
`limitations` that nothing past it is examined. Or narrow the domain with an assumption, so that the
input does not reach the stop. A stop the checked code defines itself is the project's own function
and is modelled as written. These stops are in `STOP_FUNCTIONS` and `STOP_BUILTINS`; other library
models may still narrow what they return, and any assumptions they hold are listed in the receipt under
`library_assumption_goals`.

## What the default checks do not flag

Measured on CBMC 6.11.0 with the gate's check list, each as one statement in a harness.

| not flagged | flagged |
|---|---|
| reading an uninitialized variable or heap object: the model lets it hold any value, so what follows is checked for every value, but the read itself is not reported | use after free, double free, a pointer to a dead local |
| pointer arithmetic out of range, such as `b + a` or `NULL + 1`, until the pointer is used. `--pointer-overflow-check` is available in `checks` | overlapping `memcpy`, `memcpy` with a null pointer and a length of 0 |
| converting an out-of-range `double` to `int`, and a narrowing conversion. `--conversion-check` is available | signed overflow, a shift out of range or into the sign bit, `INT_MIN % -1`, division by zero |
| reading an object through a pointer of another type (strict aliasing) | out of bounds access, a null dereference |

## What costs time if you learn it by trial

- A definition is one whole item. A function range ends at its closing brace. Helpers from other
  files go in the prelude unchanged, naming the file and lines, and are listed in `limitations`.
- `__CPROVER_assume` stands on its own line, in the harness only, and is counted. None in the
  prelude. Line directives are refused, because one could hide an assumption from the count.
- `ILP32`: if the machine has no 32-bit C library headers, include nothing and write
  `typedef __UINT8_TYPE__ uint8_t; typedef __SIZE_TYPE__ size_t;` and so on.
- `malloc`, `free`, `memcpy`, `memset`, `strlen` and `memcmp` are modelled, and the assumptions
  inside CBMC's own models are recorded apart from yours (`library_assumption_goals`). CBMC has
  no usable model of `snprintf`, `sscanf`, the results of `strtol` and its family in general, or
  glibc's `<ctype.h>` macros. Reading `va_arg` in a stand-in also fails. If the code calls one of
  these, put a stand-in in the prelude inside `#ifdef __CPROVER__`, so the native replay uses the
  real C library, and make it refuse what it does not cover. State it in `limitations`, and add a
  `cross_check.py` that compares it with the C library over every argument it can get, and runs
  the harness natively over the input domain or a stated large sample of it.
- Write checks over an array as one statement per index rather than a loop, so that the harness
  adds no loop of its own to the model.
- Recursion and large switch statements: give each call a concrete selector, otherwise CBMC
  explores every branch at every depth.

## What makes a case worth anything

- The reference in the harness comes from something other than the code under check: the format
  specification, the project's own documentation, the C standard or a second implementation. Say
  which, with a URL. A harness that repeats the fixed code proves nothing.
- A property fails on the original because of the defect, and the witness is confirmed natively.
- Add properties that pin the neighbouring contract when they are cheap: no write past the given
  size, unchanged results for inputs the fix must not touch.
- Never weaken a check to get a verdict. If the gate cannot express the property, or the fixed code
  fails a property, stop and report it. A real remaining defect is a finding.

Run the tools as an unprivileged user. Test drivers that "save the old file" before writing to a
path they were given have replaced `/dev/null` with a regular file when run as root.
