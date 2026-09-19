# What the grammar bought, qwen3-coder-30b-apps-g1 against qwen3-coder-30b-apps-s1

Preregistered in [`t/PREREG-2026-09-18-constrained.md`](PREREG-2026-09-18-constrained.md),
with the sample and the primary outcome amended before anything was graded. Same model, prompt,
temperature and seed; the only difference is that the constrained arm's request carried
[`t/t.gbnf`](t.gbnf). Over the 334 problems the constrained arm attempted and the control
answered, of which it could not finish 121 inside half an hour each -- those
count here as attempts that passed nothing.

| | control | constrained |
|---|---|---|
| problems attempted by both | 334 (100%) | 334 (100%) |
| an answer came back | 334 (100%) | 213 (64%) |
| parses as t | 106 (32%) | 211 (63%) |
| well formed | 54 (16%) | 65 (19%) |
| passes the problem's own tests | 35 (10%) | 43 (13%) |
| clean: tests, seven proofs, refuted twin | 5 (1%) | 2 (1%) |

## The number the experiment exists for

| | control | constrained |
|---|---|---|
| tests pass, among answers that parse | 35/106 (33%) | 43/211 (20%) |

A constrained model writes t by construction. If its answers pass the problems' own tests at
the rate the control's parsing answers do, the notation was the only thing in the way. If they
pass at a lower rate, the constraint is buying syntax with sense, which is what locallm looks
like at 98 percent parsing and under 1 percent passing.

## The rule, applied

Test-passing problems: control 35, constrained 43 (x1.23).

**INCONCLUSIVE, the more informative outcome: the parse wall is real and the gates below it absorb what passes, so the limit is semantic.**

Cost: 3269 generation minutes for 43 test-passing answers, 4561 s each. The control's whole 1,133-problem run took about 19 minutes.

