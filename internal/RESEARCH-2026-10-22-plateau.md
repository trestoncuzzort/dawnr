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

## Working hypothesis, revised after papers A (10:55Z)

Two of the three moves in the first hypothesis are now contradicted by the literature at our model size: wider
sampling (the trained prover saturates at k=32) and repair as a prompt (no gain over resampling at 7B). What is
supported at 4B to 8B is the quality of the kept rows: curation (arXiv:2603.15510) and the removal of weak,
hackable specifications (arXiv:2605.30914). The self-distilled rows of v8 were reference-correct but not filtered for
strength; the ranked-weakest-first instrument for that exists (`t/spec_strength.py`). The next data row is therefore
v5's rows plus only the strong, reference-correct self-distilled and teacher specifications, trained from v5's own
base, read under the three-decode protocol; expert iteration continues from there only if that row moves the count.

## The plan from the four lists (11:25Z), each step read under the three-decode protocol

1. **v9, strict rows (running now).** v5's own 4,189 rows plus only the self-distilled specifications that pass the
   reference check at 1000 draws with both mutant families rejected at 90% or more (`t/recipes/v9_strict_specs.py`,
   the floor raised from SAFE's 60%); the synthetic share stays under 20%. Trained from v5's base with the exact recipe
   on the desktop after the seed-2 run; three decodes; the ceiling instrument's gate precision beside the count.
2. **v10, repair as a trained skill.** Rows of (a failed specification, the verifier's witness, the kept specification)
   built from our own scored candidates (the failed and the kept candidates of one problem are natural pairs, the
   witness from `spec_quality.witnesses`), on the pattern of the 5,306 correction traces of arXiv:2507.02778 and CYCLE;
   then the falsified `--repair` turn is re-run on the model that was taught it.
3. **Expert iteration, round two, with the strict filter and the primer in context during sampling**, over the
   3,003-problem pool rather than 346 problems, keeping the synthetic share at the edge the literature allows.
4. **Reinforcement learning with the verifier reward** (TRL GRPO on the desktop's card, the strict strength filter as
   the guard against specification hacking) only after a supervised step has moved the count.

Not pursued, on the evidence: wider sampling of the same model, repair as a prompt, and another round of weakly
filtered self-distillation.

## The first hypothesis (10:05Z, kept for the record)

The plateau is what one supervised round on a fixed, narrow set produces for a 4B student in a near-zero-data
language. The moves that the literature shows working at this size are (1) expert iteration: sample wide (20 or
more per problem) across every problem we have specifications for (the 3,000-problem pools, not the 95), keep only
what the kernels and the reference check accept, retrain, repeat for several rounds, with the primer in context
during sampling; (2) a repair-trained student: rows of (wrong specification, the verifier's finding, the corrected
specification) so the repair turn becomes a skill; (3) verifier-reward reinforcement learning after the supervised
rounds, which fits a 16 GB card with GRPO at 4B in 4-bit (the repo scout settles which stack). Each is measured
under the three-decode protocol; none is called a gain on one decode.

## Pending from the scouts

- papers A (landed 10:45Z, verified, `plateau-papers-A.md`, 250 papers): four findings bear directly on our instruments,
  all checked against their abstracts. (1) Sampling saturates for a trained prover: DeepSeek-Prover-V1.5-RL solves 42 of
  244 miniF2F theorems at k=32 and the same 42 at k=64; a fixed schedule of 15 tactic skeletons breaks that plateau,
  +12.3 theorems over three seeds (arXiv:2601.16172). Our ceiling instrument's "a correct specification within 20 samples
  for 29 of 63" is likely a ceiling of the model, not a selection problem that more samples fix. (2) Repair with the
  verifier's diagnostics does not beat plain resampling at equal budget for a 7B prover; DeepSeek-Prover-V2-7B shows no
  recovery over 64 attempts (arXiv:2610.22698). Our three falsified repair rows are the same finding. (3) Curated training
  data for invariant synthesis nearly doubles invariant correctness for Qwen3 4B and 8B, and the 4B model then beats an
  off-the-shelf model twenty times its size on InvBench (arXiv:2603.15510): data quality moves a 4B model where rows did
  not. (4) Reinforcement learning with a verified reward on Dafny lifts the verified reward from 2.2% to 58.1%, but by
  specification hacking; after filtering underspecified tasks, multi-turn RLVR takes the verified pass rate from 9.7% to
  31.1% (arXiv:2605.30914). Our v8 test-fitting (gate precision 0.785 to 0.515) is specification hacking by another name,
  and the remedy that worked was filtering the weak specifications out of the task set. Also: specialization on a verifier
  signal adds 33 to 38 points of solve rate where no augmentation mode adds more than 3 (arXiv:2609.34460); self-play for
  200 rounds lets a 7B prover pass a 671B model at pass@4 (arXiv:2604.20209); Goedel-Prover-V2-8B reaches 84.6% pass@32
  with scaffolded data and self-correction (arXiv:2508.03613).
- papers B (landed 11:10Z, verified, `plateau-papers-B.md`, 250 papers): (1) the share of self-generated rows has a
  known edge: Pythia models from 410M to 12B hold up to 20% synthetic data and degrade faster beyond 30%, smaller models
  first (arXiv:2510.05133); v8 added 980 self-distilled rows to 4,089, a 19% share, right at that edge. (2) The repair
  failure is a blind spot of supervised data, not of size alone: 14 open models show a 64.5% self-correction blind spot
  traced to training data without error-correction sequences, and fine-tuning on 5,306 correction traces cuts it by
  76.0% (arXiv:2507.02778). (3) On Dafny at 8B, fine-tuning LLaMA 3.1 on DafnyBench plus DafnySynth, a synthetic set
  validated by Dafny itself, takes annotation success from 15.7% to 50.6% of methods, more than either set alone
  (arXiv:2411.15143). (4) Repetition over scaling: Olmo3-7B at 128 epochs on 400 samples beats one epoch on 51,200 by 12
  to 26 points (arXiv:2602.11149), so which rows repeat matters more than how many exist. (5) Rejection-sampling
  fine-tuning with a real checker lifted LLaMA-7B from 35.9% to 49.3% on GSM8K (arXiv:2308.01825), and ReST-EM's filtered
  self-training beat human data alone (arXiv:2312.06585); both are the expert-iteration shape with a strict filter.
- repos A (landed 10:10Z, verified, `plateau-repos-A.md`, 250 repositories, 174 permissive): the specification corner
  has six permissively licensed pieces to take: dafny-annotator (MIT; an LLM adds assertions and invariants until Dafny
  accepts, the verifier-error loop), Microsoft's loop-invariant experiments and NeuralInvariantRanker (MIT; candidate
  invariants checked by Frama-C, and a ranker that cuts verifier calls), SpecGen (MIT; generate, check with OpenJML,
  repair), CLEVER (MIT; specification quality scored against held-out reference specifications, which is our reference
  check as a benchmark), Verina (Apache-2.0; Lean tasks with specification, code and proof), STP (MIT; self-play that
  proposes and proves statements, a source of verifier-checked rows). The MCTS-with-verifier search
  (llm-verified-with-monte-carlo-tree-search, MIT) is the step-wise search option. No repository for Clover, Laurel,
  SAFE, Baldur or nl2postcond was found; Huosj/AutoSpec is excluded (its contents are a leaked commercial tool).
  Nothing here has been run on our data; READMEs were read, not code.
- repos B (landed 10:30Z, verified, `plateau-repos-B.md`, 250 repositories, 209 permissive): the infrastructure for every
  move in the hypothesis exists under Apache-2.0 or MIT and runs without cloud: TRL (GRPO, online DPO, GKD with custom
  reward functions), unsloth (QLoRA and GRPO with less memory), ms-swift (SFT, DPO, GRPO with quantized base weights;
  its README states 9 GB for a 7B model), LMFlow (RAFT, a reward-ranked rejection-sampling loop, the expert-iteration
  shape; its QLoRA table gives 6 GB at 7B), EasyR1 (GRPO on veRL; 12 GB at 1.5B with LoRA, so the 4080 covers small
  models only), search-and-learn (best-of-n and beam search with a reward model, where our verifier is the reward),
  llama.cpp GBNF grammars (constrained decoding of the t syntax on the pinned server, to be tried against a t program
  first), Liger-Kernel (fused training kernels, relative memory savings only), DistillKit (logit distillation from a
  local teacher). Only LMFlow's table reaches an 8 GB card with a stated number; fitting the 4B student is our own
  estimate. Nothing here has been run on our data.
