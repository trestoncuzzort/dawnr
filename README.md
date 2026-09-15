# tup

Two things live in this repository.

- **t** is a small specification language. A t program states what a function must do, and seven independent proof systems check that it does.
- **tup** is a Linux distribution built from source with a receipt for every step, so the machine that runs the proofs is itself accounted for.

Everything claimed below was measured by a script in this repository, and each number links to the file that records it.

## t in one minute

A t task is a function with a typed signature, preconditions, postconditions, and a body. The task is translated mechanically to seven verifiers, and each one checks it on its own: Dafny, Verus, SPARK, Frama-C, Lean 4, Rocq and F\*. t proves nothing itself; every verdict comes from a verifier with a long public record.

Every task also gets a deliberately broken copy, called its twin. A task counts only when the real program verifies and the twin is refuted, and a refutation means the verifier accepted a proof that the specification fails at a concrete input. A specification that cannot tell the real program from its twin is rejected as vacuous.

Seven verdicts on one program catch what one verifier cannot: a mistranslation, a specification with no content, or a verifier that quietly gave up.

## What is measured today

| Claim | Number | Record |
|---|---|---|
| Committed tasks that verify, with the twin refuted, in all seven verifiers | 30 of 34 | [`t/AGREEMENT.md`](t/AGREEMENT.md) |
| Conformance probes each verifier must pass | 457 of 462 | [`t/CONFORMANCE.md`](t/CONFORMANCE.md) |
| Dafny programs from DafnyBench translated into t by the lifter and graded | 326 tasks from 785 programs, 171 of 322 in all seven | [`t/COVERAGE-lifted-785.md`](t/COVERAGE-lifted-785.md) |
| The 164 LLM-written DafnyBench programs (MBPP-DFY) | 99 of 164 translate, 56 of 164 in all seven | [`t/COVERAGE-mbpp-dfy-lifter.md`](t/COVERAGE-mbpp-dfy-lifter.md) |
| DafnyBench programs within t's current language | 334 of 643 gradable | [`t/COVERAGE-dafnybench.md`](t/COVERAGE-dafnybench.md) |
| Natural-language programming problems with tests, the corpus t aims at | 24,748 problems, 772 of 4,239 function-shaped ones within t's language | [`nl/`](nl/), [`t/COVERAGE-nl.md`](t/COVERAGE-nl.md) |
| A 1.5B model trained on the twins it refuted | on 161 held-out problems, answers verified with a refuted twin went from 9 to 15 after two rounds (12 to 16 with three samples each); test passes did not move | [`t/LOOP-CURVE.md`](t/LOOP-CURVE.md) |
| tup 0.1 | boots from its own disk to a login prompt under QEMU in 20 to 45 seconds depending on the host, witnessed on macOS, Ubuntu and Windows by someone other than the author | [`tup/receipts/`](tup/receipts/) |

Numbers above are from 2026-09-15. When a number moves, the record moves with it.

## The verifiers

| Verifier | Version | Built on |
|---|---|---|
| Dafny | 4.11.0 | .NET, Z3 |
| Verus | 0.2026.08.30 | Rust, Z3 |
| SPARK (GNATprove) | FSF 16.1.0 | Ada, Why3, Z3 |
| Frama-C | 33.0 | C with ACSL, Alt-Ergo |
| Lean 4 | 4.33.1 | kernel-checked proof terms |
| Rocq | 9.2 | kernel-checked proof terms |
| F\* | 2026.08.30 | Z3 |

All seven run without root on Linux and macOS; five run natively on Windows and all seven under WSL2 ([`t/RUN-ON-LINUX.md`](t/RUN-ON-LINUX.md), [`t/RUN-ON-MACOS.md`](t/RUN-ON-MACOS.md), [`t/RUN-ON-WINDOWS.md`](t/RUN-ON-WINDOWS.md)).

## Try it

1. Install two or more of the verifiers; the install notes above list versions and paths.
2. Read [`t/TUTORIAL.md`](t/TUTORIAL.md) and the tasks in [`t/tasks/`](t/tasks/).
3. Run the matrix and the tests:

```
cd t
python3 run_par.py --jobs 8
bash reproduce.sh --tests
```

The first command regrades every committed task in every verifier it finds and rewrites `AGREEMENT.md`. The suite refuses to conclude from fewer than two verifiers.

## How the parts fit

| Path | What it is |
|---|---|
| [`t/`](t/) | the language, its seven translations, the verifier adapters, the lifter from Dafny, and the tables |
| [`tup/`](tup/) | the distribution's build driver, overrides and receipts |
| [`nl/`](nl/) | 24,748 natural-language programming problems with tests, from four public sources |
| [`forge/`](forge/) | the training pipeline that grades a model by the twins it refutes |
| [`locallm/`](locallm/) | a character-level model trained from scratch on your own machine (MIT) |
| [`ROADMAP.md`](ROADMAP.md) | what is done, what is next, and the bar for 1.0 |
| [`internal/ROADMAP-LOG.md`](internal/ROADMAP-LOG.md) | the dated engineering log behind the roadmap, kept for the record |

## Limits, stated plainly

- t is small on purpose: integers, booleans, sequences, pairs, strings as character sequences, loops with invariants, recursive specification functions, early return. No heap, no floats, no concurrency.
- Four adapters (Verus, SPARK, Frama-C, F\*) are not hardened against hostile input. The committed tasks do not exercise those holes, and the holes are listed rather than hidden.
- tup is witnessed, not verified. It records what was built from which bytes, in what order. It proves nothing about the kernel or libc. It is arm64 today; the x86_64 build is pending.

## License

[`locallm/`](locallm/) is MIT. The rest is a working research record. Third-party datasets keep their own licenses.

Copyright (c) 2026 Treston Malachi Cuzzort.
