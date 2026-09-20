# Seven provers as each other's reference

3,321 graded programs over 51 answer sets, each lowered to seven independent proof systems.

A **contradiction** is one kernel reading `verified` and another reading `refuted` about the same program: they cannot both be right. A **gap** is one kernel deciding where another could not, which measures capability rather than soundness and is counted apart.

| finding | count |
|---|---:|
| real-side contradictions (`verified` vs `refuted`) | **0** |
| twin-side unsound (a twin that verifies where others refute) | **0** |

**No contradictions anywhere.** Across every graded answer set, no two kernels ever reached opposite decided verdicts on the same program, and no twin verified in one kernel while being refuted in another.

That is the strongest integrity statement this project can make about its own evaluator, and it is worth saying what it does *not* mean: seven kernels agreeing does not make a specification right (see `locallm/FINDINGS-completeness-2026-09-20.md`, where they agree on specifications that are flatly false at the problem's own solution). It means the instrument is self-consistent, not that the measurement is meaningful.

It is also a property of a search: these programs come from one lowering pipeline and one problem corpus. A zero found by a search is a property of the search.

## Gaps, which are not disagreements

How often each kernel could not decide while at least one other did. This is a capability ranking, not a soundness one; `t/BUDGETS-2026-09-19.md` is the matching cost side.

| kernel | undecided while another decided |
|---|---:|
| dafny | 222 |
| verus | 262 |
| spark | 346 |
| framac | 384 |
| lean | 491 |
| rocq | 410 |
| fstar | 366 |

