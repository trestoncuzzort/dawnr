# The bottleneck has a name, and it is not the one this project has been fixing

Written 2026-09-19, from the day's numbers, for whoever runs the next round.

## What the numbers actually say

locallm's failure is not proof and it is not notation. Both of those are solved
to a first approximation:

- **Notation:** 209 of 232 well formed at 3.2M parameters, 149 at 92M, against
  Phi's 12. Writing t is nearly free.
- **Proof:** conversion is 2 of 2, 1 of 1, 3 of 3. Every locallm answer that
  computed the right values was verified by all seven with its twin refuted.
  The provers are not the gate for this model.

The gate is a single population, and it is enormous:

| arm | well formed | **proven but wrong** | tests pass |
|---|---:|---:|---:|
| locallm r4 (3.2M) | 209 | **204** | 2 |
| locallm r7 (92M) | 136 | **91** | 1 |
| locallm r7b greedy | 149 | **117** | 2 |
| locallm r8 headed | 91 | **59** | 3 |

**Proven but wrong means all seven proof systems agreed the program satisfies
the specification the model wrote, the sabotaged twin was caught, and the
problem's own tests still failed.** The model writes a correct implementation
of the wrong function, and then proves it.

That is not a verification problem. It is **specification–intent misalignment**:
the step from an English problem to a formal postcondition. The project's own
instrument already measures it (`t/spec_check.py` evaluates a task's `ensures`
against the problem's reference solution on random inputs) and it is used as a
*gate*, never as a *training signal*.

## The cheapest experiment that attacks it, and it has not been run

**Put the problem's own examples in the prompt.** MBPP problems ship with test
cases. The prompt today is `Problem:` plus `Signature:`, and the round 8 result
showed that adding the signature line to every training document took signature
failures from 40.8% to 12.1% and turned 2 clean into 3. The example is the same
kind of anchor, one level deeper: it pins the *semantics* the way the signature
pinned the *types*.

Concretely: `problem_head` in `t/loop_locallm.py` builds the head. Add one or
two of the problem's assertions to it, rebuild the corpus with
`t/head_align_corpus.py`, train with `continue_from_checkpoint.py`, decode
greedily. Thirty seconds of training and one generation run. If the
proven-but-wrong population falls, that is the answer to the whole project's
bottleneck, and it costs an evening.

The obvious objection, which must be checked and not waved away: an example in
the prompt is a hint the held-out evaluation would also give, so it changes the
task for every model. **Phi must be regraded with the same prompt** or the
comparison is dishonest. That is cheap too.

## Four more, ranked by cost over expected value

1. **Turn `spec_check.py` into a training signal.** Generate k specifications
   per training problem, keep the ones that agree with the reference solution on
   random inputs, and train on those. The checker already exists and already
   produces exactly this label. It turns a gate into a data source, and the
   project's whole thesis is that verified filters make better data.
2. **Train the specification, not the program.** The corpus teaches whole tasks,
   where the `ensures` is a couple of lines buried in a body the model also has
   to write. A `problem -> ensures` objective isolates the step that fails.
3. **Mine negatives from what is already on disk.** 13 clean answers disagree
   with their problem under the specification check, and 28 more were found on
   2026-09-19. Those are gold-standard "plausible but wrong specification"
   examples, the exact failure being made 59 to 204 times per round. Contrastive
   training on them is free data nobody has used.
4. **The twin generator idea from `forge/dafny_pairs.py`.** "Any file that
   verifies is a pair generator": strip one hint at a time instead of all at
   once, so a program with N invariants yields N minimally-broken twins instead
   of 1. `t/twins/` is 426 pairs over 90 programs, one family each. The seven
   verifiers are the oracle for both halves, so this scales without a teacher.

## Literature worth reading against this specific gap

The archive in `tup-reports/` and `internal/RESEARCH-ANGLES-2026-09-19.md` are
weighted toward proof search and execution supervision, which is the half of
the problem this project does not have. The gap is autoformalization: natural
language to formal specification, and how to tell a right specification from a
plausible one. Search terms that match the failure, rather than the tooling:
specification inference from natural language; autoformalization evaluation and
its failure modes; property-based testing as a specification oracle; intent
alignment for program synthesis; "specification is the bottleneck" results in
verified synthesis. The papers already audited (ExeDec, FoVer, AlphaVerus,
DeepSeek-Prover) all assume the specification is given, which is exactly why
none of them moved this number.

## What not to spend time on, with the evidence

- **More proof-side work.** Conversion is already 100% for this model.
- **More notation work.** 90% well formed at 3.2M parameters.
- **The synthetic composition curriculum.** Three seeds, 0, 2 and 0 of 323.
- **A cleaner pool alone.** Round 8 replaced 28 disagreeing answers with checked
  ones and scored exactly what the previous recipe scored.
- **A bigger model alone.** 92M wrote *fewer* well-formed answers than 3.2M. The
  capacity is there, measured to 875M; the data to justify it is not.

## Implemented 2026-09-19, ready to run

`t/loop_locallm.py` now takes `--examples` on both `corpus` and `generate`,
putting up to two of the problem's own assertions in the head as
`Example: fn(args) == value`. Verified on pool v5:

    Problem: Write a python function to identify non-prime numbers.
    Signature: is_not_prime(int) -> bool
    Example: is_not_prime(2) == false
    Example: is_not_prime(10) == true

The whole experiment, once the pool is rebuilt:

    python3 t/loop_locallm.py corpus --pool v5 --lifted --examples \
        --sft t/out/loop/sft-r8.jsonl --out t/out/loop/corpus-ex.txt
    python3 t/head_align_corpus.py --corpus t/out/loop/corpus-ex.txt \
        --out t/out/loop/corpus-ex-headed.txt
    ~/.venv-vllm/bin/python locallm/continue_from_checkpoint.py \
        --init t/out/source-pretraining-longer-2026-09-19/gpt-seed1337 \
        --data t/out/loop/corpus-ex-headed.txt --out t/out/locallm-ex --steps 300 --lr 3e-5
    python3 t/loop_locallm.py generate --model t/out/locallm-ex --tag locallm-ex \
        --split t/out/loop/split-v5.json --tokens 1200 --temperature 0 --examples
    bash t/grade_lab.sh heldout locallm-ex
    python3 t/spec_check.py locallm-ex --pool v5 --n 100 --only clean --out t/SPEC-CHECK-ex.md
    python3 t/score_heldout.py phi4-mini-eval2-2026-09-19 locallm-r7b-headed2 locallm-ex

**Register the prediction before running it.** Mine, on the evidence above:
proven-but-wrong falls below 40 of its well-formed answers, from 59; clean
reaches 3 or more; and well-formedness does not collapse the way the first
headed arm's did. The number that decides it is proven-but-wrong, not clean.

**And the fairness rule, which is not optional.** A model asked with examples
is being given information every baseline must also get. Before any comparison
is quoted, Phi has to be regenerated with `--examples` and regraded. Round 7's
discipline applies: regrade the baseline the same day, with the same evaluator,
and record `t/out/evaluator-state-*.json` around it.
