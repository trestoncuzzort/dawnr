# Next semantic evaluation: proposed bounded pilot

The source-pretraining loss report is a pipeline measurement. Its next test
should be **96 newly authored tasks across 12 held-out families**, with eight
variants per family and a locked executable oracle and t contract. This is a
proposed pilot, not a preregistered Phi-win study. The enterprise plan's larger
private evaluation remains necessary for a commercial quality claim.

Before generating model answers:

1. Choose the families independently of model outputs, from concrete deterministic
   transformation needs: record validation, bounded routing rules, guarded sequence
   selection, interval clipping, tuple decomposition and recomposition, sequence
   window transformations, and related combinations. Include composition of at
   least two operations and boundary behavior; avoid merely changing constants in
   a familiar benchmark. Freeze all 12 family definitions and all 96 task IDs.
2. Keep entire families, templates, reference programs, tests and near-duplicate
   variants out of every instruction/SFT dataset and retrieval/few-shot context.
   Author these tasks after the source corpus is frozen. Do not derive them from
   MBPP, HumanEval, existing `nl/`, `t/tasks`, `t/twins`, or previous generated-answer
   pools. Check exact and normalized hashes plus structural/semantic similarity
   against all task-training pools; retain the exclusion audit. Public pretraining
   can contain the same general algorithms, so a zero-semantic-contamination claim
   would be unjustified even after this audit. The held-out claim concerns the
   complete task families and their artifacts, not unseen arithmetic concepts.
3. Write independent executable oracles and input tests before any model run,
   including empty/singleton sequences, negative values, zero divisors where
   admissible, boundary transitions, and larger inputs. Use metamorphic properties
   where an independent oracle is difficult. Verify each reference against its
   frozen contract with the seven kernels and a meaningful refuted twin. Exclude
   unsupported reference shapes before model evaluation and report that exclusion
   denominator; retain a separate capability inventory rather than silently
   presenting the common supported fragment as all enterprise tasks.
4. Seal the full manifest and content hashes in ignored evaluation output. Training
   recipes accept an explicit allowlist and must fail if any sealed family or task
   hash appears in a source. Keep only aggregate results and the recipe public
   until the evaluation is retired. Once answers influence training, retire that
   evaluation and create a new family holdout; do not keep calling it unseen.

Give each model the same task statement, typed signature and immutable contract.
Have it complete only the helper declarations and body following the frozen
prefix. Definitions may use the new typed inline syntax, but cannot replace the
supplied contract or inject new task declarations. Reference oracles and private
tests remain outside the prompt. The task checks its requirement, not a weaker
specification supplied by the model itself.

Evaluate every completed owned checkpoint from seeds 1337, 7 and 42, the matched
GPT controls, the untrained core as a sanity baseline, and a separately pinned
Phi checkpoint/tokenizer revision. Use a fixed prompt and one greedy attempt
per task, no model-specific repair or teacher intervention. Freeze a common
output byte cap and wall-time cap after an infrastructure-only dry run, and
record native token counts, time and peak memory; tokenizer-specific tokens
are not equal units of work. Keep identical solver budgets and three real/twin
repetitions per kernel. If an arm cannot fit or complete a task, retain it in
the denominator as a failure with its reason.

Report, for every family and every arm: parsed and well-formed, executable tests
passed, seven-kernel real/twin clean, wrong-but-proven, timeout/abstention, and
cost per accepted answer. The primary score is **all private tests plus all
seven real verifications and all seven meaningful twin refutations**, out of
all 96 locked tasks. Show the paired task disagreements and all training seeds;
do not select the seed with the highest score. Inspect failures only after the
first sealed result. This pilot identifies the next bottleneck; it is too small
and too restricted to establish the enterprise plan's general Phi-win claim.

Implementation order: a family manifest and contamination audit, frozen-prefix
generation adapter, independent oracle runner, then existing t real/twin grading
and the paired report. Each artifact must be reviewable before the first scored
generation. No external benchmark download or third-party outreach is needed.
