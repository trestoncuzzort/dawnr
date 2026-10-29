# Select one qualified training seed before the final panel

The current candidate uses the registered two-seed, three-decode protocol on the
clean 206 development problems. The earlier `v6_candidate.py` guard applies to a
different 95-problem, fixed-checkpoint experiment and is not this candidate's gate.

Before candidate grades are available, freeze the current registration at private
SHA-256 `01561ed8d8f37d42ad6d3f078864b0a2aa3069f72f78aa837fdeb5e675c9dcea`.
It binds the two seeds, final training length, dataset, development and held-out
panel digests, baseline tags, and exact precision/specification grader manifests.
The 558 precision source/data hashes and 562 given-specification source hashes
were independently matched to their frozen Git revisions.

`release_seed_selection.py` consumes independently audited artifact evidence. It
does not replace archive verification, full-panel receipt checks or source audits.
Before calling it on a real candidate, recover every required artifact, verify its
digest and input correspondence, and read each original 95/145-panel grade through
the existing reader before joining the clean 206. Preserve that reader's removal
of unconfirmed specifications; do not reinterpret its results or omit failed arms.

The decision logic must:

1. Require all three baseline and all six candidate decodes, with no repeated or
   foreign tags/problems. Recompute means, fractions and both paired statistics
   using the existing `three_decode_report.py` functions. An altered summary or
   displayed p-value is an error.
2. Require the registered paired clean improvement: more problems up than down
   and permutation p at or below 0.05. The mean predictions of 21 clean and 10
   all-seven remain predictions, not substitute selection conditions.
3. Bind each seed's six original generation parts and precision measurement to
   the exact final Q8_0 export from that registered seed and dataset. Bind both
   private instruments to their audited inputs and frozen grader sources.
4. Select only among seeds with precision at least 0.70 and at least 27/33 proved
   by all seven. Rank by mean clean count, then mean all-seven count, then lower
   seed number. If the combined paired gate fails or neither seed qualifies,
   select no seed.
5. Recompute the decision before writing an exclusive frozen-choice file. Identical
   inputs may recover that same choice; changed evidence or a different seed may
   not replace it. This permits resuming the original evaluation, not another
   decode. The held-out launcher must separately bind its one cache and job record.

Tests exercise the exact precision boundary, ties, missing and altered evidence,
different model/panel identities, partial checkpoints, NaN ratios, a better mean
without paired evidence, and attempts to switch a frozen choice. They also pass
in an isolated tree without downloaded data. A negative software control reread
the six saved baseline parts, reproduced clean counts 20/19/19 and all-seven
9/8/9, then used those same sets on both sides. The paired gate correctly failed
with p = 1. This is an implementation control, not a candidate result.

No candidate decision has been frozen and no held-out answer has been generated.
A qualifying decision still needs one private held-out reading, the final laptop
conditions, packaging and publication. The goal is not complete at this step.

Sources: `t/recipes/three_decode_report.py`, `t/recipes/v7_local_pair.py`,
`t/recipes/v6_candidate.py`, `t/recipes/spec_ceiling.py`,
`t/PREDICT-2026-10-29-cohere-curated-candidate.md`, and
`internal/RELEASE-6.0-PLAN.md`, section 3.
