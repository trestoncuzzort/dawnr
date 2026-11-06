# Native CBMC gate over case descriptions, 2026-11-05

`t/native_check.py` checks one function: the pinned PX4 `wrap_bin`. This adds
`t/native_case.py`, which runs the same gate over any function a case directory
describes, so the check can be pointed at other code without editing the adapter.
Read first: `t/PREDICT-2026-10-10-native-cbmc.md` and section 3 of
`internal/RESEARCH-2026-10-10-verification-next.md`, which set the controls.

This is not a preregistration. The controls below were first run before this file
was written, so the expected values were stated after seeing the results. They are
recorded as measurements.

## What a case is

A directory holding `case.json` and the full source files it names. The description
gives, for the original source and optionally a fixed one: the file, its SHA-256,
its revision and the line ranges to extract. Each range must be exactly one function
definition, one preprocessor definition or one declaration, and is copied unchanged.
It also gives a prelude, the scalar inputs, the harness body, the assertion names,
and the counts of assumptions and loops. Stating a task as a program plus a
specification under a named ILP32 or LP64 architecture follows the
[SV-COMP rules](https://sv-comp.sosy-lab.org/2025/rules.php). Pinning the files by
hash and expecting a verdict per control come from the pilot.

The adapter generates the rest: one nondeterministic draw per input, a machine
assertion for ILP32 or LP64, and an end marker, `__CPROVER_assume(1 == 1)`, as the
last statement of the harness. The gate in `native_check.interpret` is used
unchanged. Its assumption coverage then also decides whether the end of the harness
is reachable, so a harness that returns early or never terminates cannot be
`complete`, and a case with no assumptions of its own still passes through the
coverage stage. `--conversion-check` is off unless a case asks for it, because a
defined conversion is not undefined behavior.

A counterexample is replayed by compiling the same prelude, definitions and harness
natively with GCC under UBSan and ASan. Inputs are passed as the bit patterns of the
values the harness drew in the trace. The replay is valid only where the native
widths equal the model's, which the program checks per input.

## Controls and measurements

Tool: official CBMC 6.11.0 Ubuntu 24.04 release asset, SHA-256
`b3721aa541038384d7801ea3aeabbcddc3e8845ac8f1cbff637cf8dec7481ac8`, extracted
under a user-owned directory. Compiler: GCC 13.3.0, x86-64.

| control | expected | measured |
|---|---|---|
| pilot tests, `CBMC=... pytest -q test_native_check.py` | 36 passed | 36 passed |
| PX4 case, original source | counterexample, replayed | counterexample; 15 properties, 5 failed; 2 distinct witnesses, both replayed |
| PX4 case, published fix | complete | complete; 15 properties |
| PX4 case, fix with `assume(0 != 0)` | vacuous | vacuous; 5 of 6 coverage goals unreachable |
| synthetic case with no assumptions, original and fix | counterexample, complete | as expected |
| harness that returns before its assertion | not complete | vacuous |
| call to a function with no body | not complete | not complete, no replayed witness |
| loop with `--unwind 1`, then 4 | incomplete, complete | as expected |
| new tests, `pytest -q test_native_case.py` | pass | 32 passed, 5 skipped without CBMC; 37 passed with it, 1.15 seconds |

The two PX4 witnesses are the pilot's: `bin = -2147483584` gives `-64`, which fails
the range assertion and then indexes the 72-element array out of bounds, and
`bin = 2147483632` is a signed overflow in `bin + bin_count`. The property count is
15, not the pilot's 14: the machine assertion also compares the pointer width, and
that comparison adds one conversion check. The other 14 are the pilot's.

## Limits

Inputs are scalars of at most 64 bits. Arrays and pointers have to be built in the
harness from scalar draws. The extracted text is parsed as C. A case states its own
harness, so `complete` covers the stated inputs, properties and machine model only,
and says nothing about callers, other configurations or the rest of the file. The
SAT solver is trusted. None of the seven t kernels checks these results and their
agreement counts are unchanged. This file belongs with the engine copy of the native
pilot and has to land in t-proof-engine before dawnr treats it as synchronized.
