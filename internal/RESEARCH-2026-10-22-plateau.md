# Why dawnr is still on v5: the plateau, read from our own instruments and the literature (2026-10-22)

Written 2026-10-22 10:05Z, the hour the user asked why we are at a standstill. The four scouts on this question are
running (`internal/research-2026-10-22/plateau-papers-A.md`, `plateau-papers-B.md`, `plateau-repos-A.md`,
`plateau-repos-B.md`, 250 entries each); this note holds what our own records and the local paper library already
say, so the scouts' lists land on a question that is already framed. Sections marked "pending" are filled when
the lists are verified.

## What our instruments say

| instrument | reading | record |
|---|---|---|
| development panel, frozen route | v5 ends fully clean on 6 of 95; v6 corrective 6, v7 4, v8 4 | the week's PREDICT files |
| the same v5, decoded three times | 6, 4, 6 clean (mean 5.3); the sampling seed alone moves the count by two | `t/PREDICT-2026-10-22-seed-variance.md` |
| ceiling (20 specification candidates per problem) | a reference-correct specification exists within 20 samples for 29 of the 63 problems the student solves in Python; within 5 for 18 | `t/PREDICT-2026-10-21-spec-ceiling.md` |
| the three-test gate's precision on those candidates | 0.785 for v5, 0.515 for v8: v8's candidates pass the small gate more often while being wrong against the reference more often | same, and `t/PREDICT-2026-10-21-v8-spec-rows.md` |
| repair turns (specification, proof, Python stages) | 1 of 32 and 5 of 52 repair asks accepted; the model rewrites, it does not fix | `t/PREDICT-2026-10-21-repair-turn.md`, `-proof-repair.md`, `-python-repair.md` |
| a primed 9B teacher (grammar card plus six worked examples) | 15 reference-correct specifications, 6 on problems the student never solves | `t/PREDICT-2026-10-21-v8-spec-rows.md` |

Read together: the student can solve the Python for two thirds of the panel, can produce a correct specification for
fewer than half of those only when sampled many times, cannot use a verifier's finding to fix its own output, and
one more round of supervised rows (even reference-checked ones) did not move the count past the instrument's noise.
The count of six is not a measurement of the data rows; it is the sum of a selection problem (the right specification
is in the sample set but the gate picks a wrong one), a coverage problem (for 34 of 63 problems no correct
specification appears in 20 samples), and a noise problem (a single decode cannot resolve the differences we chase).

## What the literature says moved small models past the same wall (local library, read 2026-10-22)

- **Expert iteration with a strong verifier, many problems, many rounds.** Goedel-Prover (7B, arXiv:2502.07640):
  1.64 million formal statements, eight iterations of sample, verify in Lean, add the newly proved statements to the
  training set, retrain; "consistent improvement starting from the first iteration"; 57.6% Pass@32 on miniF2F, 7.6
  points over the previous open model, by supervised fine-tuning alone on the verified set. DeepSeek-Prover-V1.5 (7B,
  arXiv:2408.08152): reinforcement learning from the proof assistant's verdict adds 10.2 points on miniF2F (50.0 to
  60.2), and tree search at test time takes it to 63.5. The verifier in both is the ground truth, not a proxy, and
  the statement pool is hundreds of thousands wide. Our v8 was one round, 346 problems, filtered by a three-test proxy
  and then the reference check; the literature's gains come from the opposite settings on all three axes.
- **An ultra-low-resource language is bootstrapped with the grammar in context, then a difficulty curriculum.**
  CodeRise (ACL 2026 Findings, aclanthology.org/2026.findings-acl.1840): for languages with near-zero pretraining
  data (Tengo, Janet) a stage one generates data with a long syntax prompt in context, a stage two drops the prompt
  and self-refines along a curriculum tiered by Pass@10; the fine-tuned 7B and 8B students "consistently
  outperform" training-free and training-based baselines (the exact before and after numbers are in its tables, to
  be copied when the scouts' lists are verified). Our t language is in that class, and our spec primer (the grammar
  card) is their stage one applied only at inference, never in the training data.
- **Small models do not repair their own code unless trained to.** CYCLE (arXiv:2403.18746): untrained 350M to 3B
  models copy their own faulty program in 64.8% of self-refinement attempts; trained for refinement, the same sizes
  gain up to 63.5% relative on three benchmarks, and a 350M refiner beats an untrained 1B. This is our repair-turn
  finding by another route, and it says the repair turn is a training target, not a prompt.

## Working hypothesis (to be tested, not assumed)

The plateau is what one supervised round on a fixed, narrow set produces for a 4B student in a near-zero-data
language. The moves that the literature shows working at this size are (1) expert iteration: sample wide (20 or
more per problem) across every problem we have specifications for (the 3,000-problem pools, not the 95), keep only
what the kernels and the reference check accept, retrain, repeat for several rounds, with the primer in context
during sampling; (2) a repair-trained student: rows of (wrong specification, the verifier's finding, the corrected
specification) so the repair turn becomes a skill; (3) verifier-reward reinforcement learning after the supervised
rounds, which fits a 16 GB card with GRPO at 4B in 4-bit (the repo scout settles which stack). Each is measured
under the three-decode protocol; none is called a gain on one decode.

## Pending from the scouts

- papers A: which mechanism moved which model size, with numbers (pending)
- papers B: why supervised fine-tuning saturates and why self-generated rows collapse into test-fitting (pending)
- repos A: what we can take, with licences (pending)
- repos B: what runs this week on an 8 GB and a 16 GB card (pending)
