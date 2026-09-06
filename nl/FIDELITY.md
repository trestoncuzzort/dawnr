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

task             params         full cross   visited   checked  checked%
--------------------------------------------------------------------------
abs              int                    86        86        86    100.0%
all_nonneg       seq                    82        82        82    100.0%
contains         seq,int             7,052     2,048     2,048     29.0%
count_matches    seq,int             7,052     2,048     2,048     29.0%
factorial        int                    86        86        41     47.7%
fib              int                    86        86        17     19.8%
gcd              int,int             7,396     2,048       450      6.1%
linear_search    seq,int             7,052     2,048     2,048     29.0%
max              int,int             7,396     2,048     2,048     27.7%
seq_max          seq                    82        82        81     98.8%
sum_upto         int                    86        86        41     47.7%
--------------------------------------------------------------------------
5 of 11 tasks are truncated by the MAX_POINTS cap
5 of 11 lose further points to their `requires`
  least-checked task: gcd, 450 of 7,396 points (6.1% of its input space)
  fewest points outright: fib at 17
  widest untried integer interval: (-2,147,483,649, -1,000,000), 2,146,483,649 wide
```

VISITED and CHECKED are different numbers and only CHECKED matters.
`build_differential` runs `interp.Reference(task).points`, which is the domain
after the `requires` filter, so a task with a precondition is checked on fewer
points than it visits.

**The first version of this file, committed earlier the same day, printed VISITED
and called it coverage.** That was wrong in the flattering direction: it reported
`fib` at 100% and `gcd` at 27.7%, when the harness actually runs 17 points for
`fib` and 450 for `gcd`. The tool has been fixed to print both.

Four facts follow, and each is a distinct weakness:

**Only `abs` and `all_nonneg` are checked on their whole input space.** Their ladders are
86 and 82 values and they have no precondition to shed, so within the ladder there is
nothing left to find. The ladder is
`0, 1, -1, 2, -2, 1000000, -1000000, 2147483648, -2147483649, 2147483647, 3..40` and their
negations. It is a well-chosen ladder: it has zero, the small integers, and the int32
boundaries. It is still 86 points.

**A precondition can take most of them away.** `fib` and `sum_upto` and `factorial` all
require a non-negative argument, so the negative half of the ladder is discarded before
anything runs: `fib` is checked on **17 points**, `factorial` and `sum_upto` on 41. `gcd`
requires both arguments positive and lands on 450 of its 7,396, **6.1%**. The narrowest
body-fidelity evidence in the tier is seventeen integers.

**The ladder is essentially task-independent.** `interp.ladders` builds it from
`[0, 1, -1] + _around(literals) + INTS`, and for `factorial`, `abs` and `gcd` the literals
are all 0 and 1, which the fixed `INTS` tuple already contains. All three get the identical
86-value ladder. The domain does not adapt to the program, so a program whose interesting
behaviour lives at 97, or at 12345, is sampled nowhere near it.

**The two-parameter tasks are truncated, not exhaustive.** `max` is checked on
2,048 of 7,396 points, 27.7%, and the three `seq,int` tasks on 29.0%. The cap is
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
this order. Condition 0 is settled below and needs no further work; conditions 1 through 5
are open, and none of them is satisfied today.

0. **The tier is the 164 MBPP-DFY programs, not the eleven hand-written tasks.** This is
   a correction to the first draft of this file. `lift_check.build_differential(task,
   source, closure)` needs a real `MethodDecl` and call-graph closure, which only
   `lift_resolve.resolve` on an actual `.dfy` file produces. The tasks in `t/tasks/` have
   no Dafny source, and lowering a task to serve as its own `source` compares a thing to
   itself. The eleven remain the right place to measure the DOMAIN, which is what
   `fidelity_domain.py` does; they are not a place the differential arm can run.

1. **Every row reports CHECKED points, not visited ones, beside its verdict.** A sampled
   agreement is labelled as sampled, with the count that actually ran.
   `lift_check` already words it correctly ("agrees on N of M points"); what is missing is
   that nothing refuses to print a coverage number when N is small.

2. **The tier is checked on the human-written inputs as a second arm.** The 492 MBPP
   assertions, parsed to concrete points, run through
   `lift_check._build_differential_with_points`, which already accepts an explicit point
   list. Not merged with the ladder arm: two arms, two numbers, reported separately,
   because they answer different questions and only one of them is independent.

3. **Points outside t's `int`/`bool`/`seq<int>` types are refused with a named reason,**
   the same discipline the lifter applies to constructs. An MBPP assertion over strings,
   dicts or tuples is not silently dropped; it is counted and named, so the surviving
   count is a measurement and not a filter nobody audited.

4. **`bad=0` on both arms across the tier, with both counts recorded.** This is the
   condition the rule actually names. It is a measurement, so it can fail, and if it fails
   the corpus run does not start.

5. **Only then, the corpus number, carrying the tier result with it.** The claim is
   "N of 24,748, under a lifter measured faithful on the MBPP-DFY tier at L ladder points
   and H human-written points per program", and it is never quoted without the second
   clause.

## Where nl/ comes in

`nl/` is the corpus the rule is about, and it also happens to hold the antidote to
weakness 2. HumanEval's 164 problems and MBPP's 974 are the simplest functional tasks in
the corpus, and unlike DafnyBench they ship **executable tests written by people who were
not looking at the lifter**: `test_list` for MBPP, a `check(candidate)` harness for
HumanEval. Those inputs are independent of the program's literals by construction, which
is exactly the property `interp.ladders` cannot have.

They are Python and the lifter reads Dafny, but that gap is already bridged, and the bridge
was found on 2026-09-06 rather than built. **DafnyBench's 785 ground-truth programs include
164 named `dafny-synthesis_task_id_NNN.dfy`**: Dafny versions of MBPP problems, the same
164 that ROADMAP WS-13.1 and WS-16.2 call "the MBPP-DFY programs". They join to `nl/`'s
MBPP records by `task_id`, and the join was measured, not assumed:

```
MBPP-DFY Dafny programs in DafnyBench:            164
matched to an MBPP record in nl/:                 164 (100.0%)
human-written assert statements they carry:       492 (3.0 per program)
```

So for exactly the tier the rule is about, there is a Dafny source the lifter can read AND
an independent set of inputs somebody wrote without reference to the lifter. MBPP task 605
tests `prime_num(-1010)==False`; -1010 lies inside the untried interval between 40 and
10^6, so that one human-written line already reaches where the ladder never looks.

This also settles how to widen the domain, because two constraints rule out the obvious
answer. `interp.py` states that "the domain is enumerated, never sampled" and treats the
determinism as load-bearing for reproducible witness selection, so seeded random sampling
is a departure, not a free upgrade. And `DIFF_MAX_POINTS = 512` exists because the Dafny
differential run is superlinear: 512 points take 7.5 s, 2,048 take 87 s. More points is
therefore the wrong lever. **492 human-chosen points is the right one:** deterministic,
independent of the program's own literals, and nearly free against the Dafny budget.

## What the gate says today

`t/lift_gate.py` runs both arms over the tier and exits nonzero while anything is
unproven. First full run, 2026-09-06, on the MacBook:

```
MBPP-DFY gate tier: 24 programs (in fragment, with human points)
  both arms bad=0:      24 of 24
  a disagreement:       0
  an arm unavailable:   0
  points run:           5697 ladder, 71 human
GATE PASSED on 24 programs: both arms bad=0.
```

Read that narrowly, because it is a narrow claim. **24, not 164.** The gate can only
speak about a program that the census calls in fragment AND that carries a human-written
point inside t's `int`/`bool`/`seq<int>` types: 25 of the 164 are in fragment, 96 carry a
usable point, and 24 satisfy both. The other 140 are not passing, they are unmeasured, and
the reason they are unmeasured is that t's fragment does not reach them yet.

The per-program point counts are worth reading too. The ladder arm ranges from 12 points
(`task_762`, IsMonthWith30Days) to 512, the `DIFF_MAX_POINTS` ceiling, which 9 of the 24
hit; those nine are checked on a quarter of their own interp domain. The human arm is 3
points per program, 71 in total. Three independent points is not many. It is more than
zero, which is what the tier had this morning.

So conditions 1, 2 and 3 are met for these 24, condition 4 passes for these 24, and
condition 5 still forbids a corpus number, because 24 in-fragment arithmetic problems are
not evidence about 24,748.

## Re-running the numbers

```bash
cd t && python3 fidelity_domain.py           # the domain table above
cd t && python3 mbpp_dfy.py                  # the tier and its human points
cd t && python3 lift_gate.py                 # both arms; exit 1 if unproven
cd nl && python3 scripts/corpus_audit.py     # overlap and leakage
```

The tool reads task JSON and counts what `interp.domain` yields. It needs no dafny, no
network and no corpus, so it is cheap enough to run in a gate.
