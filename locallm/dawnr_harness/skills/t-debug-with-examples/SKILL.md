---
name: t-debug-with-examples
description: Trace a t program by hand on Example lines to find where it computes the wrong value, before trusting a proof or after an example fails or is undefined. Use for wrong values; see proof-failure-triage for a kernel table instead.
license: the repository's LICENSE
---

# Debugging a t program against concrete examples

`Example: name(arg1, arg2) == expected` lines (one call per line; arguments
and the expected result written as t values: ints, `true`/`false`,
`[1, 2, 3]` for a seq, `(1, 2)` for a pair) are what the `t` tool runs the
program on, before anything is proved. Read its answer one line at a time;
it stops at the first line that is not a pass:

    example 1: pass
    example 2: fail: got 5, expected 6
    example 3: undefined: <why>
    example 3: budget: <why>              (a loop did not finish)
    example 3: requires-excluded          (this input violates requires)
    example 3: arity: 2 arguments for 3 parameters

1. If nothing fails yet, add an Example anyway, on the smallest input the
   signature allows (the empty seq, zero, a one-element seq), before trusting
   the body. Never edit or remove an Example line the user gave; add new
   ones beside it.
2. On a `fail`, hand-simulate the body on that example's exact arguments:
   write down every variable's value after every statement, in order, the
   way the interpreter would. Inside a `while`, write one row per iteration.
   Stop at the first row whose value disagrees with what `ensures` (or plain
   arithmetic) demands; the statement just above that row is where the fix
   belongs.
3. On `undefined`, the diverging step is a partial operation outside its
   domain: `at`/`s[i]` with `i` outside `[0, len(s))`, `div`/`mod` by zero,
   or `slice` with `a > b` or `b > len(s)`. Find it in your hand trace, not
   by guessing.
4. On `budget`, the loop's `decreases` expression is not shrinking on this
   input; hand-trace it across iterations until it stops decreasing or goes
   negative.
5. On `requires-excluded`, the example itself violates the task's own
   `requires`; that is a fact about the example, not a bug in the body.

This finds *where* a body diverges from the value it should compute.
Deciding *which* checker stage to look at first is `t-repair`'s job; writing
the `ensures` these examples are checked against is `t-spec-writing`'s.
