# t cross-kernel agreement, 2026-10-10 12:50Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | framac | rocq |
|---|---|---|
| abs | verified / refuted | verified / refuted |
| gcd | verified / refuted | verified / refuted |
| reverse | tool_error / tool_error | verified / refuted |

Kernels present: 2 of 2 (framac, rocq)

Backends:
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- rocq: The Rocq Prover, version 9.2

Verdict basis: every source file hashed.

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all two |
|---|---|---|---|
| framac | 1 | 0 | reverse |
| rocq | 0 | 0 | (none) |

Of the 1 tasks in one, 1 is framac alone.

## Per kernel

| kernel | carried | real verified | twin refuted where the real is verified | abstains by name |
|---|---|---|---|---|
| framac | 3 | 2 | 2 of 2 (100%) | 0 |
| rocq | 3 | 3 | 3 of 3 (100%) | 0 |

Verified with the twin refuted in all two columns: 2 of 3 tasks.
