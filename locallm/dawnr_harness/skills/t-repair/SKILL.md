---
name: t-repair
description: Repair a t program after dawnr's checker reports a failing verdict (parses no, well formed no, an example that fails, is undefined or runs out of budget). Use when a t tool call or the stop check answered anything but a pass.
license: the repository's LICENSE
---

# Repairing a t program from the checker's verdict

The checker answers one line per stage and stops at the first failure. Read
the first line that is not a pass; it names the stage that failed.

1. `parses: no: <file>:<line>:<col>: expected X, found Y`: the text is not t.
   Go to that line and column. A program is `t 1`, optional `gate` lines,
   `task name(p: type, ...) returns (r: type)`, its `requires` and `ensures`
   lines, then a body in braces. Statements end in `;` except blocks
   (`if c { ... } else { ... }`, `while c invariant ... decreases ... { ... }`).
   Assignment is `:=`; declarations are `var i: int := 0;`.
2. `well formed: no: <why>`: the text is t but a name or a type is wrong. Check
   that every variable is declared before use, that `int`, `bool` and `seq`
   are not mixed, and that the return variable is assigned on every path.
3. `example k: fail: got G, expected E`: the program runs and computes the
   wrong value. Run it by hand on example k's inputs, line by line, until the
   first value that differs from what the `ensures` line demands. The fix is
   in the body.
4. `example k: undefined: <why>`: an operation left its domain (an index
   outside `[0, len(s))`, a division by zero) or no path assigned the return.
5. `example k: budget`: a loop does not finish. Check that its `decreases`
   expression really shrinks on every iteration.
6. `example k: requires-excluded`: the task's `requires` rules out this input.
   If the example came from the user, the `requires` is stronger than the task.

Never make a check pass by changing the specification: do not weaken an
`ensures`, drop an `invariant`, or edit the user's Example lines. A program
that meets a weaker specification is a different program. If the failure
cannot be found, say which line fails and stop; an honest "not repaired" is
better than a program that only looks repaired.

After the repair, call the t tool again on the whole program.
