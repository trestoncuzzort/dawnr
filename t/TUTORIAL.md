# Learning t from zero

This is the beginner's walk through t: every piece of the language, explained
as if this were your first programming class. No prior language assumed. The
one-page grammar lives in [`SYNTAX.md`](SYNTAX.md) and the precise rules in
[`SPEC.md`](SPEC.md); come back to those once this page has done its job.

Throughout, examples appear in a readable notation like `r := x + 1`. That
notation is for humans. A real t task is stored as JSON (you'll see one at
the end of lesson 1), and nothing parses the pretty form. Think of it the way
your teacher writes on a whiteboard versus what actually goes in the file.

---

## Lesson 0: what t is

Most programs are just instructions: *do this, then this*. A t program is two
things: instructions, **and a promise about the result**. The instructions are
called the *body*. The promise is called the *contract*.

What makes t different from every language you'd meet in a first course:
**the promise is checked by a machine, before the program ever runs.** Not
tested on a few examples but *proved*, for every possible input, by an outside
program called a proof kernel. t hands your task to six different kernels,
and they must all agree.

So writing t is a conversation: you state what your program promises, you
write the steps, and the kernel either says "I can see why that promise
always holds" (VERIFIED) or "I cannot" (REFUTED). Your job is to make the
promise and the steps line up so perfectly that a machine can follow the
reasoning.

---

## Lesson 1: your first task

Here is the complete t task `abs`, which computes the absolute value of a
number (the distance from zero: `abs(5)` is 5, `abs(-5)` is also 5).

```
task abs
  takes    x : int
  returns  r : int
  ensures  r >= 0
  ensures  r == x  or  r == -x
body
  if x >= 0 { r := x } else { r := -x }
```

Read it top to bottom:

- **`task abs`**: every task has a name, like a function in any language.
- **`takes x : int`**: the *input*. `x` is its name, `int` is its type
  (lesson 2). Inputs are called **params**.
- **`returns r : int`**: the *output*, and it has a name too. In t you don't
  "return a value" with a statement; you **assign into `r`**, and whatever
  `r` holds at the end is the answer. Every path through the body must give
  `r` a value.
- **`ensures r >= 0`**: the promise, part one: whatever happens, the answer
  is never negative.
- **`ensures r == x or r == -x`**: the promise, part two: the answer is the
  input or its negation (this is what stops you from just writing `r := 0`
  and calling it done: 0 is `>= 0`, but it isn't `x` or `-x` unless x was 0).
- **the body**: one decision: if `x` is already zero-or-more, the answer is
  `x` itself; otherwise flip its sign.

Multiple `ensures` lines are all promised at once, joined by an invisible
"and".

And here is what that task really looks like in the file: the same thing,
as JSON. Every construct on this page has a JSON form like this; the full
mapping is in `SYNTAX.md`, and after this lesson we'll stay on the
whiteboard:

```json
{"t": 0, "name": "abs",
 "params":  [{"name": "x", "type": "int"}],
 "returns": [{"name": "r", "type": "int"}],
 "requires": [],
 "ensures": [
   {"op": ">=", "args": [{"var": "r"}, {"int": 0}]},
   {"op": "or", "args": [
     {"op": "==", "args": [{"var": "r"}, {"var": "x"}]},
     {"op": "==", "args": [{"var": "r"}, {"op": "neg", "args": [{"var": "x"}]}]}]}],
 "body": [
   {"if": {"cond": {"op": ">=", "args": [{"var": "x"}, {"int": 0}]},
           "then": [{"assign": ["r", {"var": "x"}]}],
           "else": [{"assign": ["r", {"op": "neg", "args": [{"var": "x"}]}]}]}}]}
```

---

## Lesson 2: values and types

A **value** is a piece of data. A **type** says what kind of data. t has
three types, and the small number is on purpose:

- **`int`**: a whole number: … -2, -1, 0, 1, 2 … Here is the surprise if
  you've programmed before: t's integers are *mathematical* integers. They
  never run out. There is no biggest int, no wrap-around, no overflow. When
  you prove something about `x + 1`, it is true for every integer, full stop.
- **`bool`**: exactly two values, `true` and `false`. The answers to
  yes/no questions live here.
- **`seq`**: a finite list of integers, like `[3, 1, 4]`, that **cannot be
  changed**. You can look at it; you cannot edit it. (Why: things that never
  change are enormously easier to reason about. Most of the pain in proving
  programs correct comes from things changing behind your back.) A `seq` can
  only arrive as an input.

There is no text type, no decimal-point type. Not yet, on purpose: every
piece of t exists only once six independent proof kernels agree on exactly
what it means.

---

## Lesson 3: expressions

An **expression** is anything that has a value: `5`, `x`, `x + 1`,
`x + 1 > y`. Expressions are how you compute and how you state promises.

**Arithmetic**: `+`, `-`, `*`, `-x` (negation), and in `t 1` tasks `/`
(integer division) and `%` (remainder).

Division needs a word about a disagreement. The kernels t answers to did
not all agree about what `-7 / 2` should be (some say -3, some say -4, and
both conventions are respectable), and for a while t had no division at
all rather than quietly pick a side. It now picks a side out loud: `/` and
`%` are *Euclidean*, which means the remainder is never negative. So `-7 / 2`
is `-4` and `-7 % 2` is `1`, because `-7 == -4 * 2 + 1`. Dividing by zero is
not an error message, it is *undefined*: a task that could divide by zero
has to prove it never does, the same way it has to prove a sequence index is
in range. Kernels whose own division rounds differently are told exactly
what t means, and are checked on it. You will see that rule again: when
kernels disagree, state one meaning and measure every kernel against it.

**Comparisons**: `==` (equal; two symbols, because a single `=` is not an
expression in t at all), `!=`, `<`, `<=`, `>`, `>=`. A comparison's value is
a bool.

**Logic**: how you combine yes/no answers:

- `p and q`: true when both are.
- `p or q`: true when at least one is.
- `not p`: flips it.
- `p implies q`: the one that's new to most beginners. Read it as
  "whenever p holds, q holds." It only makes a claim *when p is true*; if p
  is false, the whole thing is true by default, having promised nothing about
  that case. `x < 0 implies r == -x` says: *in the case* that x is
  negative, r must be its flip. It says nothing at all about positive x.
  You'll use `implies` constantly in promises.

`and` and `or` check left to right and stop as soon as the answer is known.
That matters in lesson 6.

**Choosing inside an expression**: `if c then a else b` as a *value*:
written `ite(c, a, b)`. Like `if`, but it picks between two values instead
of two lists of actions.

---

## Lesson 4: statements

A **statement** does something (contrast: an expression *is* something).
Statements run in order, top to bottom. t has exactly four, and you know two
already:

**Assignment**: `r := x + 1` means "compute the right side, store it in the
name on the left." The `:=` symbol is deliberate: assignment is an *action*,
not a claim. (`r == x + 1` is a claim, true or false. `r := x + 1` is an
order: *make* r be that.)

**If/else**:

```
if x >= 0 { r := x } else { r := -x }
```

Evaluate the condition; run one block or the other. The `else` can be empty,
but it's always written: there is no dangling half-if in t.

The other two statements (`var` and `while`) get their own lessons.

---

## Lesson 5: contracts: requires and ensures

This is the heart of the language. A contract has two sides:

**`requires`**: what the task assumes about its inputs. It is a promise the
*caller* makes to you. Example: a task that finds the largest element of a
list cannot answer for an empty list, so it states
`requires len(s) > 0`, which reads "don't call me with an empty list." Inside the
body, you may take every `requires` for granted; the kernel checks that
anyone who calls the task proves it first. No `requires` lines means "I
accept anything."

**`ensures`**: what the task guarantees about its output. It is your
promise to the caller, and the kernel holds you to it: it must be able to
prove every `ensures` line true at the end of the body, **for every input
allowed by `requires`**. Not for the inputs you thought of. All of them.

Two habits that will save you:

1. **A weak promise is easy to keep and worthless.** `ensures r == r` is
   always true and says nothing. t has machinery (lesson 12) that catches
   contracts too weak to mean anything.
2. **Think of `ensures` as the definition of correct.** The body is just one
   way of achieving it. Someone should be able to read only your contract
   and know exactly what the task does, never needing to read the body.

---

## Lesson 6: sequences: len and s[i]

Two tools for a list `s`:

- **`len(s)`**: how many elements. Always `>= 0`.
- **`s[i]`**: the element at position `i`. Positions start at **0**: the
  first element is `s[0]`, the last is `s[len(s) - 1]`.

Now the important rule. Ask for `s[7]` when the list has three elements and
in most languages you get a crash, garbage, or a lurking bug. In t, an
out-of-range `s[i]` is **undefined, and the kernel refuses the whole task
unless it can prove, in advance, that every `s[i]` you ever write stays in
range.** Index errors aren't caught at run time; they're made impossible
before run time.

That's why order matters in logic. This is safe:

```
i < len(s)  and  s[i] > 0
```

because `and` checks left to right and stops early: by the time `s[i]` is
looked at, `i < len(s)` is already known. Flip the order and the kernel will
reject it: you looked before you proved it safe to look.

**Building and changing a list.** A list is a value, so you never change
one in place; you make a new one. `s[i := v]` is the list equal to `s`
except that position `i` now holds `v` (same range rule as `s[i]`), and
`seq(n, v)` is the list of `n` copies of `v` (`n` must be `>= 0`). A task
can return a list (`returns r : seq`) and keep one in a local. Two lists
are `==` when they have the same length and the same element at every
position. Swapping two positions is two updates:

```
var tmp: int := s[i];
r := s[i := s[j]];
r := r[j := tmp];
```

and reversing a list is a loop that fills a fresh one, `r := seq(len(s), 0)`,
then writes `r := r[i := s[len(s) - 1 - i]]` for each `i`. In both the
invariant says what the elements written so far are; nothing says which
elements did not change, because nothing can change: `r` is a new value
every time.

**Writing a list down, joining two, taking a piece.** `[3, 5, 7]` is a
list of three; `[]` is the empty list. `s + t` is `s` followed by `t` (the
same `+` you use on numbers; t knows which one you mean from what is on
either side). `s[a..b]` is the piece of `s` from position `a` up to but not
including `b`, so it has `b - a` elements, and it is defined only when
`0 <= a <= b <= len(s)`; `s[1..]` means "from 1 to the end" and `s[..b]`
"from the start up to b". The common shape is a loop that grows a list one
element at a time:

```
r := [];
var i: int := 0;
while i < len(s)
  invariant 0 <= i
  invariant i <= len(s)
  invariant len(r) <= i
  invariant forall k in [0, len(r)) . r[k] > 0
  decreases len(s) - i
{
  if s[i] > 0 { r := r + [s[i]]; } else { }
  i := i + 1;
}
```

which keeps the positive elements of `s` (`tasks/filter_pos.json`). Note
the invariant order: the one that bounds `len(r)` comes before the one
that reads `r[k]`, because each invariant is checked with only the earlier
ones known.

**Strings, briefly.** A string is a list of code points: write `"abc"` or
`'a'` and t sees numbers, `[97, 98, 99]` or `97`. Nothing new to learn,
because everything above, `len`, `s[i]`, `+`, a slice, `==`, already works
on it; t adds no string type and no string operator, just the two literal
forms. Escapes `\n`, `\t`, `\r`, `\0`, `\'`, `\\`, and, inside `"..."`,
`\"`, spell the usual control characters and the quote marks.

---

## Lesson 7: forall and exists: claims about many things at once

How do you promise "`r` is at least as big as *every* element"? You can't
write a separate line per element, because you don't know how many there are. You
quantify:

```
forall i in [0, len(s)) . r >= s[i]
```

Read: "for every position `i` from 0 up to (but not including) `len(s)`, r
is at least `s[i]`." Its partner:

```
exists i in [0, len(s)) . r == s[i]
```

"there is at least one position holding exactly r." The task `seq_max`
(find the largest element) promises both: the first says *nothing is
bigger*, the second says *it's actually in the list*. Either alone is a
weak promise: without `exists`, a trillion would satisfy "nothing is
bigger."

Details that bite beginners:

- The range `[lo, hi)` is **half-open**: `lo` included, `hi` excluded.
  That's why `[0, len(s))` fits arrays perfectly.
- If `hi <= lo` the range is empty. A `forall` over nothing is **true**
  ("every element of nothing passes"; there's nothing to fail). An
  `exists` over nothing is **false**.
- The `i` is a brand-new name that exists only inside the claim. It may not
  reuse a name you already have.
- A quantifier is an expression, a claim with a true/false value, not a
  loop. Nothing "runs"; it *states*.

---

## Lesson 8: locals and while loops

**Local variables.** The inputs and the output aren't always enough working
space. Declare your own:

```
var i : int := 1
```

New name, its type, and, required, its starting value. No uninitialized
variables exist in t.

**While loops.** "Keep doing this while the condition holds":

```
while i < len(s) { ... ; i := i + 1 }
```

Check the condition; if true, run the body and check again; if false, move
on. But in t a bare loop like that is **not accepted**. A loop must carry
two extra pieces, an *invariant* and a *decreases*, and they're the next
two lessons. This is the part of t with no counterpart in a normal first
course, and it's the part that makes proving loops possible at all.

---

## Lesson 9: invariants: what stays true while things change

The kernel can follow straight-line code step by step. A loop is a problem:
it might run a thousand times, or a billion. The kernel cannot walk every
lap. The solution is one of the great ideas of computer science:

An **invariant** is a statement that is true every time the loop is *at the
top*, checking its condition. Before the first lap and after each lap, the
same statement, every time. You write it; the kernel checks it holds at
entry, and that *if* it holds at the start of any one lap it still holds at
the end of that lap. Just one lap: that's the trick. One lap, plus "it held
at the start," covers all billion by dominoes.

Then, when the loop ends, the kernel knows two things: the invariant (still
true) and the condition (now false), and from those two it must reach your
`ensures`.

Example: summing `1..n` with a running total.

```
var i : int := 0
var total : int := 0
while i < n
  invariant 0 <= i and i <= n
  invariant total == sum of the first i numbers      (stated via a spec function)
{ i := i + 1 ; total := total + i }
```

The second invariant is the real one: *the total is always correct for how
far we've gotten*. When the loop ends, `i == n`, so "correct for how far
we've gotten" becomes "correct for n", which is exactly the promise.

Finding the invariant is the skill. Ask: **"what is true at every lap that,
combined with the loop being over, gives me my promise?"**, then check the
body actually preserves it. Expect this to be the hardest and most
satisfying part of writing t.

---

## Lesson 10: decreases: proving the loop actually ends

An invariant proves the loop does the right thing *if it finishes*. Nothing
so far says it finishes. `while true { }` would sail past lesson 9.

So every t loop must also state a **`decreases` expression**: a number that
(the kernel checks) is never negative while the loop runs and gets
**strictly smaller on every single lap**. A non-negative number can't shrink
forever, so the loop must stop. For a loop counting `i` up to `len(s)`,
the measure is:

```
decreases len(s) - i
```

The gap that's left. Each lap `i` grows, the gap shrinks, and at zero the
condition has failed. In t the `decreases` is **required on every loop**:
you are never allowed to write a loop you can't show terminates.

---

## Lesson 11: spec functions and recursion

One more situation: how do you *promise* "`r` is n factorial"
(n × (n-1) × … × 1)? You need the concept "factorial" available inside the
contract. You define it as a **spec function**, a small, pure,
mathematical definition that exists for the contract's sake:

```
specfun fact(n : int) : int
  decreases n
  = ite(n <= 0, 1, n * fact(n - 1))
```

Notice `fact` calls itself. That's **recursion**, defining a thing in terms
of a smaller case of itself, plus a base case (`n <= 0` gives 1) so it
bottoms out. And notice the required `decreases n`: same idea as loops:
every self-call must be on a strictly smaller measure, so the definition
can't chase itself forever.

Now the task can promise `ensures r == fact(n)`, and its body can compute
factorial any way it likes, by a loop or by calling *itself* recursively (a
task body may self-call, carrying its own task-level `decreases`).

One rule that looks pedantic and is actually deep: a recursive task's
promise must be anchored to a *spec function*, never to the task's own name.
`ensures r == fact(n)` is good. "ensures r == whatever this task returns" is
circular, and worthless as a promise.

---

## Lesson 12: the twin: how t grades your contract

Everything so far checks the body against the promise. One failure mode
remains: **a promise so weak that even a wrong body keeps it.** Nothing in
lessons 1–11 catches `ensures r >= 0` standing alone on `abs`, and plenty of
wrong programs stay non-negative.

t's answer is the **twin**. For every task, t mechanically builds a
deliberately broken copy of your body, by one fixed ladder of mutations and no
human choice. It tries, in order:

- **delete one invariant** of one loop (is your stated reasoning actually
  load-bearing?);
- **collapse one if** to its then-branch, erasing the decision (does your
  promise even notice the behavior changing?);
- then swap an `if`'s branches, flip a `<` to `<=`, exchange a comparison's
  operands, move a literal or an index by one, substitute another variable of
  the same type, or drop a conjunct from a guard.

It takes the **first mutation it can prove is really broken**: t interprets
both bodies over a bounded set of inputs and keeps a mutation only once it
has a *witness*, an input where your body and the twin return different
answers (or, for the deleted invariant, a loop state your remaining
invariants no longer cover). A mutation nothing can tell apart from your real
body would make the whole exercise theatre, so it is discarded, and a task
where no mutation has a witness is refused with that reason named.

Then both versions face the kernels, and a task **counts** only on the
double result: real body **VERIFIED, and twin REFUTED**. If the broken twin
still verifies, your contract failed to notice sabotage. It is too weak to
mean anything, and the task is refused. Both halves are measured by the
actual kernels, never assumed.

That is t's culture in one mechanism: a claim doesn't count until something
tried to break it and failed.

---

## The mistakes everyone makes first

| You wrote | What happens | The fix |
|---|---|---|
| `s[i]` before establishing `i` is in range | task refused, unprovable definedness | guard it: `i < len(s) and s[i] …`, in that order |
| a loop with no `decreases` | not valid t | state the shrinking measure, usually `end - i` |
| an invariant that's true but unused | t finds no loop state it covers, and moves down the ladder to a different mutation | state the invariant your `ensures` actually needs |
| a body whose branches assign the same thing | no mutation changes what it computes → refused, `no-witness` | make the decision matter, or drop the `if` |
| `ensures` that only bounds the answer (`r >= 0`) | a constant body might satisfy it | add the connecting clause (`r == x or r == -x`, or an `exists`) |
| reusing a name as a quantifier variable | task refused, shadowing is banned | pick a fresh name (`j` when `i` is taken) |
| expecting `s[i]` to crash "at run time" | nothing in t happens at run time; the proof already covered it | internalize: errors are ruled out before running, or the task is refused |
| divide, remainder, strings, floats | not in the language | see SPEC.md; features arrive only when six kernels agree on their meaning |

Where to go next: read [`tasks/`](tasks/) in this order: `abs`, `max`,
`all_nonneg`, `seq_max`, `sum_upto`, `factorial`, `gcd`. Each one uses
exactly one more idea than the one before. Then `AGREEMENT.md` shows every
task × every kernel, measured.
