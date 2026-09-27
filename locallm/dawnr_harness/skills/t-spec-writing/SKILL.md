---
name: t-spec-writing
description: Write a new t task from a plain-language problem: signature and types, then requires and ensures, then a body that satisfies them. Use when starting from nothing, not when repairing or debugging a program that already exists.
license: the repository's LICENSE
---

# Writing a t task from a problem statement

Write the parts in this order; each one constrains the next.

1. **Signature.** `task name(p1: type, ...) returns (r: type)`. Types are
   `int` (unbounded, no overflow), `bool`, `seq` (of `int`; a string is a seq
   of code points), `(T1, T2)` a pair, `seq<seq>` one level of nesting.
   Exactly one return.
2. **requires.** What the caller must guarantee, as a list of expressions
   (conjoined; `[]` means true). State only what the body genuinely needs;
   a `requires` that is itself undefined at some type-correct input (reading
   `s[0]` with nothing establishing `len(s) > 0`) is a defect, not a
   restriction.
3. **ensures.** Write this from the problem statement, not from the body you
   are about to write. It is the fixed instrument the twin gets checked
   against: an `ensures` a wrong body could also satisfy (`ensures true`, or
   `ensures r == <the body's own expression>`) is vacuous, and a vacuous task
   is refused even if seven kernels verify it (t/README.md, "The twin rule").
4. **body.** A sequence of `var`, `assign`, `if`, `while`, `return`
   statements that make `ensures` true. Every path must assign the return
   variable (or `return` it). `while` needs `invariant` lines and a
   `decreases` that is `>= 0` and strictly shrinks every iteration; only the
   variables the loop body assigns need an invariant describing them, because
   a `while` only havocs what it assigns (SPEC.md, "The frame rule
   (normative)"). Do not write an invariant restating a variable the loop
   never touches.
5. Guard every partial operation: `at`/`s[i]` needs `0 <= i < len(s)`,
   `div`/`mod` need a nonzero divisor, `slice`/`s[a..b]` needs
   `0 <= a <= b <= len(s)`. Put the guard in `requires` when the caller owns
   it, in the loop invariant or an `if` when the body must establish it.
6. Order matters inside a list: each `requires`/`ensures`/`invariant` may
   assume only the ones written before it in the same list (SPEC.md,
   "Definedness"), so a length bound must come before an element read that
   needs it.

Call the `t` tool on the finished task. A `parses`/`well formed` failure or a
failing example is `t-repair`'s job, not this one; a body that runs but you
are not sure computes the right value is `t-debug-with-examples`'s job.
Never loosen `ensures` to make the task easier to satisfy: a proof of a
weaker promise is a different, smaller task, not the one that was asked.
