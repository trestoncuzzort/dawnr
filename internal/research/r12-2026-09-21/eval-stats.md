# Deciding between locallm recipes when the score is 1-6 of 232

Every recommendation cites a source fetched and read this session (receipts at the end). Power numbers come from Card et al.'s simulation algorithm run on a model fitted to our spread: about 2 written-clean per seed, from six easy problems plus a thin tail. Two seed-effect settings bracket the data: σ=0 gives a variance-to-mean ratio of 0.78 and σ=0.75 gives 1.54; the observed {1,1,2,4} is 1.0. No r11 output was read.

## What sets the design
- **The unit is the training run.** McNemar compares two fixed models; Card et al. leave "comparing one training algorithm vs. another" uncovered. Sellam's target is θ = E_seed[L(S)].
- **r9 vs r10 was not a 1% change.** `/home/t/tup/locallm/data.py` `group_split` fills the holdout from a seeded shuffle of document *order*; its docstring's "by hash" does not match the code. So one seed on corpora of different length draws unrelated holdouts. Simulated, about 53 of ~270 training documents differ, which is closer to a seed draw than an ablation.
- **Single runs cannot decide.** Two runs of one recipe differ by 3 or more with probability 0.15-0.31. Single-run McNemar mid-p detects a true +3 only 25-35% of the time. One run against 10 seeds has a smallest possible p of 1/11; a soup against its 5 ingredients has 1/6.

## 1. Seeds per arm (80% power, one-sided α=.05)
| gain | permutation over seeds (these 232) | Multi-Bootstrap (problems too) |
|---|---|---|
| +3 | 5 (σ=0) / 10 (σ=.75) | 10-20 |
| +2 | 10 / 20 | 20 to more than 40 |
| +1 | 30 / more than 30 | not reached at 40 |

Miller's minimum detectable effect (MDE) is δ = (z_{α/2}+z_β)√((ω²+σ_A²/K+σ_B²/K)/n). With K seeds per arm it is 5.5-7.0 clean answers at K=1 and 1.9-3.9 at K=10. It has a floor of 2.0 as K→∞ when a gain sits on two problems. At 5 seeds, significant results exaggerate a true +1 by 2.1-3.0× (Card's Type-M).

## 2. The test
- **Decision test.** Exact one-sided permutation test of Δ̄ = mean_B − mean_A of per-seed written-clean counts.
  - A subset-sum DP covers all C(2n,n) relabelings; direct enumeration is too large (C(40,20) = 1.4e11).
  - Simulated size is 0.018-0.048. deep-significance measured the permutation test at 0.029/0.058 for 5/10 samples, against the bootstrap's 0.085/0.077.
  - Same corpus and same `--seed` list: use a paired sign-flip test.
- **Meaningfulness.** Bouthillier's P(B>A), ties counted ½, with a bootstrap CI and γ=0.75. That is roughly +1.2 to +1.8 clean answers here. His single-point comparison errs about 10% false positive and 75% false negative.
- **Not decision tests.** Pooled counts across seeds reach a size of 0.085. A GLMM in the style of Hagmann et al.'s LMEM/GLRT nearly separates at 99% zeros, so use it only for variance components.
- **Two fixed checkpoints** (a soup vs Phi): McNemar mid-p = two-sided p − f(n12|n), with no level violations in Fagerland's 9,595 scenarios. It needs at least 5 one-way discordant problems (0.5^5 = .031). r10's 5 against Phi's 3 gives 0.51.

## 3. Reporting
- A recipe is "mean [min-max] (n seeds)". No single-run numbers.
- A single checkpoint gets a Wilson 95% interval (Bowyer): 2 → [0.6, 7.2], 5 → [2.1, 11.5]. Wald goes negative because 2/232 < 1/(1+N/z²) = .016.
- A best seed appears only beside Dodge's E[V*_n] = Σ v(P̂(V≤v)^n − P̂(V<v)^n); best-of-10 is expected at 4.1-5.7 when the mean is about 2. Seed choice alone gave BERT +7 points (Dodge 2020).
- Every comparison carries:
  - the Multi-Bootstrap 95% CI, with one problem resample shared by both arms and nboot ≥ 10,000;
  - the per-problem table of seed solve rates (Miller's paired view);
  - the overdispersion ratio Var(count)/Σp̂(1−p̂).
- Say "generalizes" only if the Multi-Bootstrap lower bound is above 0.
- The 232 problems have no dev split beside them. Dwork: reuse "can easily lead to overfitting to the holdout set itself". Make each look a registered one-bit decision, and explore on pool-v6 problems kept out of training.

## 4. pass@k
- Chen's pass@k = E[1 − C(n−c,k)/C(n,k)] is c/n at k=1. It cuts one checkpoint's per-problem variance to p(1−p)/n.
- It does not remove seed variance, and it changes the estimand.
- Miller shows T=0 can triple variance (1/12 → 1/4), so greedy decoding may inflate our spread.
- Pilot it: 3 seeds × 10 samples at a pre-fixed T. Kernel-grade only the test-passing samples.

## Protocol for the next run (register before training)
1. **Arms.** Baseline is r11's 10 seeds plus seeds 10-19; treatment uses the same 20. A corpus change is tested unpaired.
2. **Power check.** First refit the simulation to r11's 10×232 matrix. If 20 seeds miss 0.8 at +2, register +3 as the target.
3. **Metric and looks.** Written-clean is primary. Take one look, or two looks at α=.025 each (Bonferroni). Card warns against sampling to a foregone conclusion.
4. **Verdict.** ADOPT if p ≤ .05 and the P(B>A) CI upper bound is above .75. NOT MEANINGFUL if that upper bound is at most .75. Otherwise INCONCLUSIVE, claimed as nothing.
5. **Reruns.** A same-seed GPU rerun is a numerical-noise row (Bouthillier), not a seed.

## Script design (repository untouched)
- **`/home/t/tup/t/score_heldout.py --per-problem OUT.json`** emits {tag: {problem_id: {clean, novel, spec}}} from its per-`tid` loop.
- **`t/compare_arms.py`**, standard library only:
  - Invocation: `--arm A=tags --arm B=tags [--paired] --prereg PATH`.
  - It refuses to run if the seed counts differ from the registration.
  - It prints: the arm summaries; Wilson intervals; the DP exact p and mid-p; P(B>A) with its CI; the Multi-Bootstrap CI and p; the per-problem table; E[max]; McNemar mid-p for checkpoints; and the verdict.
  - Self-tests: the DP matches brute force at n=5, and two halves of one arm reject at most 5% of the time.

## Sources (fetched URL · receipt)
- e89423ae63a6: ar5iv.labs.arxiv.org/html/2103.03098, /2002.06305, /1909.03004, /2010.06595
- 2805f36ed185: arxiv.org/html/2411.00640, bmcmedresmethodol.biomedcentral.com/articles/10.1186/1471-2288-13-91, arxiv.org/html/2503.01747
- ef7fc0d2a1a8: ar5iv.labs.arxiv.org/html/2106.16163, github google-research/language multiberts/multibootstrap.py (defaults nboot=500, p = mean(δ* ≤ 0))
- e5060fc9ac04: github Kaleidophon/deep-significance README, ar5iv.labs.arxiv.org/html/2204.06815
- 8b36b397409b: ar5iv.labs.arxiv.org/html/2107.03374, github openai/human-eval evaluation.py
- edcfa3a19841: ar5iv.labs.arxiv.org/html/1506.02629
- 9340eac11bcc: ar5iv.labs.arxiv.org/html/2302.04054

**What this buys:** a +3 recipe gain becomes a decision at 10 seeds per arm, and +2 at 20. A +1 is below what 232 problems can resolve. r9's 1 against r10's 4 is ordinary seed noise until r10's corpus has its own seeds.
