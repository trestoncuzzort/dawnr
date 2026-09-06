# Why no number about this corpus counts yet

The standing rule, in Treston's words on 2026-09-06:

> If the t lifter isn't flawlessly preserving meaning on the simplest functional tasks,
> any success metric on the larger 24,000-problem corpus is mathematically meaningless.

This file states what that rule costs, what is measured today, and what has to hold
before a coverage number over `nl/`'s 24,748 problems is worth printing. It is a gate,
not an aspiration: the numbers below come from `t/fidelity_domain.py`, which anyone can
re-run.

## The argument

A coverage claim over a corpus has the shape "N of 24,748 problems are in t's fragment".
Every such claim is a composition of two steps: the lifter turns a source program into a
t task, and t's kernels grade the task. The kernels are the part with a proof story. The
lifter is not, and it sits underneath every row.

So a corpus number inherits the lifter's error rate whether or not anyone measures it.
If the lifter silently changes meaning on p of the programs it accepts, then a reported
coverage of N is really a statement about N programs of which about pN are not the
programs anyone asked about. The number does not become approximately right; it becomes
a measurement of a corpus nobody has seen. That is the sense in which it is meaningless
rather than merely noisy: there is no error bar to attach, because the quantity being
estimated is not defined until the lift is known to be faithful.

The order therefore matters. Fidelity on the simplest tasks is not a nice-to-have that
can be established in parallel with a corpus run; it is the precondition that gives the
corpus run a referent. And the simplest tasks are the right place to establish it,
because a lifter that cannot be shown faithful on `abs` and `factorial` will not be shown
faithful on a Codeforces problem, and because a failure there is diagnosable rather than
merely observable.

## What the lifter actually checks today

`LIFTER-DESIGN.md` is honest about this and should be read directly; sections 9, 10 and
11 are the relevant ones. In summary, three instruments run:

1. **Spec equivalence, proved.** Section 9 emits Dafny lemmas (`L_fun_F`, `L_req`,
   `L_ens`, `L_inv_k`) asserting that each lifted clause is equivalent to its source
   clause on the source's domain, and Dafny verifies them. This is a real proof, and it
   has negative controls: five deliberately wrong lifts of `fatorial2` each fail exactly
   the lemma they should. Spec fidelity is in good shape.

2. **Body agreement, sampled.** Section 10(a) runs the source method and the lifted body
   on every point of `interp.domain(task)` and reports `points=N bad=M`. The design says
   plainly that "agreement on the domain is not a proof of identity".

3. **Parser fidelity, measured.** Section 10(b)'s print-and-compare fixpoint over all 785
   programs checks the parser, and it is a genuine measurement of that.

The gap is instrument 2, and section 11 names it: what remains unverified is "identity of
the body's statement skeleton beyond the interp domain". The body is the part a spec lemma
cannot see, and it is checked only by sampling.

## How much sampling, exactly

The caveat above is qualitative. Here is the quantity, from
`python3 t/fidelity_domain.py` on the eleven hand-written tasks in `t/tasks/`, which are
the simplest functional tasks t has:

```
MAX_POINTS cap: 2048

task             params            full cross   visited  coverage
------------------------------------------------------------------
abs              int                       86        86    100.0%
all_nonneg       seq                       82        82    100.0%
contains         seq,int                7,052     2,048     29.0%
count_matches    seq,int                7,052     2,048     29.0%
factorial        int                       86        86    100.0%
fib              int                       86        86    100.0%
gcd              int,int                7,396     2,048     27.7%
linear_search    seq,int                7,052     2,048     29.0%
max              int,int                7,396     2,048     27.7%
seq_max          seq                       82        82    100.0%
sum_upto         int                       86        86    100.0%
------------------------------------------------------------------
5 of 11 tasks are truncated by the cap
  lowest coverage: gcd at 27.7% (2,048 of 7,396 points)
  widest untried integer interval: (-2,147,483,649, -1,000,000), 2,146,483,649 wide
```

Three facts follow, and each is a distinct weakness:

**The single-parameter tasks are exhaustive over a ladder of 86 values.** For `abs`,
`factorial`, `fib` and `sum_upto` the check tries every point the ladder offers, so within
the ladder there is nothing left to find. The ladder is
`0, 1, -1, 2, -2, 1000000, -1000000, 2147483648, -2147483649, 2147483647, 3..40` and their
negations. It is a well-chosen ladder: it has zero, the small integers, and the int32
boundaries. It is still 86 points.

**The ladder is essentially task-independent.** `interp.ladders` builds it from
`[0, 1, -1] + _around(literals) + INTS`, and for `factorial`, `abs` and `gcd` the literals
are all 0 and 1, which the fixed `INTS` tuple already contains. All three get the identical
86-value ladder. The domain does not adapt to the program, so a program whose interesting
behaviour lives at 97, or at 12345, is sampled nowhere near it.

**The two-parameter tasks are truncated, not exhaustive.** `gcd` and `max` are checked on
2,048 of 7,396 points, 27.7%. The three `seq,int` tasks are checked on 29.0%. The cap is
`MAX_POINTS = 2048` and the traversal is shell order, so what gets visited is a ball
around low ladder indices; the far corner of the cross product is never reached. This is
the weakness that grows: three parameters would be 86^3 = 636,056 points, of which 2,048
is 0.3%.

The widest untried interval is a blunt way to say the same thing. No input between
-2,147,483,649 and -1,000,000 is ever tried by any check the lifter runs, so a lifted body
that agrees with its source everywhere except there passes every instrument and is
reported as faithful.

## What this does not say

It does not say the lifter is wrong. Instrument 1 proves spec equivalence, and it is the
spec that the flip rule and the twin ladder actually rest on; a body that meets a proven
equivalent contract is already constrained. Nor is 86 points nothing: for `abs` it is
plainly enough, because the program is small enough to reason about directly.

It says the evidence for body fidelity is weaker than the evidence for spec fidelity, by a
lot, and that the gap is currently unquantified in the tables. A row that reads "agrees on
2,048 points" and a row that reads "agrees on 100% of its domain" are different claims and
today print the same way.

## The gate

Before any coverage number over `nl/`'s 24,748 problems is reported, these must hold, in
this order. None of them is satisfied today.

1. **Every task in `t/tasks/` reports its domain coverage alongside its verdict.** A
   sampled agreement is labelled as sampled, with the fraction. `t/fidelity_domain.py`
   produces the fraction; nothing consumes it yet.

2. **The simplest tier is checked exhaustively, not to a cap.** For the eleven tasks the
   full cross product is at most 7,396 points, which is affordable; the 2,048 cap buys
   nothing here and costs 72.3% of `gcd`'s domain. The cap exists for witness search, where it
   is load-bearing, so this needs a separate limit for the fidelity run rather than a
   change to `MAX_POINTS`.

3. **The ladder is widened past its own literals for the fidelity run.** A domain derived
   from the program's constants cannot find a divergence away from those constants. Random
   sampling under a fixed seed, plus the existing boundaries, would cover the untried
   intervals and stay reproducible.

4. **`bad=0` on every task in the tier, at that widened domain, with the count recorded.**
   This is the condition the rule actually names. It is a measurement, so it can fail, and
   if it fails the corpus run does not start.

5. **Only then, the corpus number, carrying the tier result with it.** The claim is
   "N of 24,748, under a lifter measured faithful on the simplest tier at D points per
   task", and it is never quoted without the second clause.

## Where nl/ comes in

`nl/` is the corpus the rule is about, and it also happens to hold the antidote to
weakness 2. HumanEval's 164 problems and MBPP's 974 are the simplest functional tasks in
the corpus, and unlike DafnyBench they ship **executable tests written by people who were
not looking at the lifter**: `test_list` for MBPP, a `check(candidate)` harness for
HumanEval. Those inputs are independent of the program's literals by construction, which
is exactly the property `interp.ladders` cannot have.

They are Python, and the lifter reads Dafny, so this is not a drop-in domain today. It is
the reason to keep the tier definition and the corpus in one repo: when a Python path
exists, the fidelity domain for the simplest tier should come from those human-written
tests rather than from a ladder the lifter generated for itself.

## Re-running the numbers

```bash
cd t && python3 fidelity_domain.py           # the table above
cd t && python3 fidelity_domain.py --json    # same, machine-readable
```

The tool reads task JSON and counts what `interp.domain` yields. It needs no dafny, no
network and no corpus, so it is cheap enough to run in a gate.
