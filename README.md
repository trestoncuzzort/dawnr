# locallm

## A 92M model trained on one desk just drew level with a 3.8B Microsoft model

**locallm has 92 million parameters. Phi-4-mini has 3.8 billion, 41 times
more. On 232 held-out programming problems, both produced exactly 3 answers
that were correct and formally proved.**

An answer only counts when it passes the problem's own tests, is verified
against its specification by **seven independent proof systems** (Dafny, Verus,
SPARK, Frama-C, Lean 4, Rocq, F\*), and all seven catch a deliberately
sabotaged copy of it at a concrete input. That is a far harder bar than passing
unit tests.

| | locallm | Phi-4-mini |
|---|---:|---:|
| parameters | **92M** | 3.8B |
| trained | from random numbers, on one shared GPU | by Microsoft, on a cluster |
| **clean answers of 232** | **3** | **3** |
| of those, confirmed to specify the right problem | **3** | 2 |

Phi was regraded the same day, by the same evaluator, beside locallm, so the
two numbers are comparable rather than quoted from different weeks.

**The honest asterisks, because they belong next to the number.** 3 of 232 is
1.3%: both models fail the overwhelming majority of the time, and tying at a
low number is easier than tying at a high one. Phi has never seen t, the
specification language this project invented, so 220 of its 232 answers do not
parse at all; a Phi trained on t the way locallm is would likely look very
different. And three answers is thin, with no seeds behind it yet.

What is not asterisked: locallm was trained from random weights, on one
machine, on 46M tokens of source plus 50,142 tokens of specialization, in
minutes of GPU time, on a language that did not exist a month ago. The target
was never a tie, and [`ROADMAP.md`](ROADMAP.md) WS-22 is the plan to beat it
outright.

---

## What locallm has done

locallm is the thing this project builds. Everything else on this page is a
baseline it is measured against, or evidence about the pipeline that feeds it.

Written for people who write software and do not work on machine learning. Each
one links to the script that produced it; the version with the exact settings,
hashes and caveats is [`locallm/ACHIEVEMENTS.md`](locallm/ACHIEVEMENTS.md).

**1. It learned to write a formal language almost perfectly, from nothing.**
Starting from random numbers, with no downloaded model and no pretrained weights,
the 3.2M-parameter version produced a syntactically valid program in t for
**209 of 232** problems it had never seen. Microsoft's Phi-4-mini, which at
3.8B parameters is about 1,200 times larger and trained on a large part of the
public internet, managed **12**. Everyone assumes the hard part for a tiny model is
learning the notation. It isn't. It's nearly free.

**2. It now matches a Microsoft model 41 times its size.** On 232
problems it had never seen, locallm and Phi-4-mini each produced **3** answers
that passed the problem's tests, were proved correct by all seven systems, and
had their sabotaged twins caught. All three of locallm's also survived a check
that the specification it wrote describes the problem that was actually asked;
one of Phi's three could not be checked. It is a tie on three answers, which is
thin, and it is the first time anything trained here has drawn level.

**3. When it is right, it is provably right.** Software is normally tested;
here every answer is also *proved*, by seven independent proof systems, and
each one must also catch a deliberately broken copy of the same program. Every locallm answer that computed the right values
cleared all seven with the broken copy caught: **2 of 2**, and **1 of 1** in
the latest round. It has never written something correct that it couldn't
prove.

**4. You can stop it and start it again and get the identical model.**
Training can be interrupted by a crash, a shared machine or a power cut, then
resumed, and the result is the same weights bit for bit as if it had never
stopped. There's a test that fails the moment that stops being
true. It's the difference between a result you can reproduce and a result you
can only repeat.

**5. It is nowhere near the size this hardware can train.** The models on the
scoreboard have 3.2 million and 92 million parameters. We measured what the
machine actually supports by training at each size until it ran out of memory:
**875 million parameters trains**, on a single graphics card that another user
was sharing at the time. Nobody had ever checked. "Should we go bigger?"
was an argument for months; it's arithmetic now.

**6. It builds its own vocabulary instead of borrowing one.** Models read text
in chunks, and most projects download someone else's chunking rules. locallm
learns them from its own corpus, which cuts the same text into about **60%
as many chunks**, so more real content fits in the same amount of the model's
limited attention.

**7. It generates faster, and only because that was checked first.** Reusing
work between output tokens is a standard speed trick. We predicted how much it
would help, measured it, and the prediction failed, so the feature ships
turned **off by default**, with the evidence that it produces identical output
either way. Nothing here gets adopted just because everyone else does it.

**8. We tested our own architectural belief and it was wrong.** A "modern"
design looked about **25% better** than the older one after a short training
run, which is the point at which most projects would commit. Run four times
longer, the older design won at **every one of three random seeds**, while also
being 19% faster and using a third less memory. The belief was ours, we ran the experiment that could kill
it, and it did.

**And none of it is a win yet.** The gap, and what we're doing about it, is below.


**What this does not claim.** Nothing here is hallucination-free or 100 percent correct. A proof shows a program meets its specification, not that the specification says what the problem asked, which is why every table carries a **proven but wrong** column, why the tests are a separate gate, and why an accepted answer's specification is checked against the problem's own solution ([`t/spec_check.py`](t/spec_check.py)). **locallm has drawn level with Phi-4-mini, not beaten it**: its best round scores 3 clean answers of 232 and so does Phi, on a baseline regraded the same day by the same evaluator. Three answers is a thin result and this page says so next to it. Two models *run through* this pipeline beat Phi, and neither was built here, so neither is a result of this project's method. And the seven checkers do less of the work than the name suggests: a preregistered ablation ([`t/ABLATION-2026-09-17.md`](t/ABLATION-2026-09-17.md)) measured one prover admitting wrong answers 17.4 percent of the time against 12.9 percent for all seven with the twin refuted, at half the problem coverage; on held-out answers, where the model writes its own specification, every proof gate admits about 97 percent wrong and the tests catch what the proofs cannot. The honest claim is tests **and** proofs together, not seven provers rather than one.

## Why this project is unusual

Those came out of a setup that almost nobody runs:

- **Seven proof systems, not one.** Dafny, Verus, SPARK, Frama-C, Lean 4, Rocq
  and F\* each get their own translation of every program, and a training
  example survives only if **all seven** verify it. Projects that verify their
  training data usually use one prover. Writing seven translations of one
  language, and keeping them honest against each other, is the part nobody
  does.
- **Every program ships with a sabotaged twin.** For each verified program
  there is a near-identical broken one, plus the exact input where they
  disagree, and all seven provers must *catch* it. That is what stops a proof
  system from waving through something it never really checked.
  [`t/twins/`](t/twins/) is 426 such pairs over 90 programs, each with its
  separating input and seven independent refutations. We have not found another
  published set of that shape, though we have not searched exhaustively.
- **Predictions are written down before runs, including the wrong ones.** Every
  experiment here registers what would prove it wrong, then reports what
  happened. Several of this project's own beliefs died that way and the files
  that killed them are in the repo.
- **It corrects itself in public.** A scoring bug once credited answers as
  "specification checked" when nothing had checked them, which made one of our
  own published claims wrong. That is written up on this page, not quietly
  fixed. See [corrections](#corrections-this-project-made-against-itself).
- **Every number links to the script that produced it.** If a number here has
  no file behind it, it is a bug.

The industry bet is scale: more parameters, more tokens, more scraped code.
This one bets the other way: keep only what can be proved, then see how far a
small model gets on it.

## Start here

- **What is measured, and what is not:** the tables below, and the limits at the end of this page.
- **Run it yourself:** `python3 t/restore_run.py` puts the last run's data where the tools expect it; `python3 t/lab.py` opens a window that shows every step's state, progress and log. Setup is [`t/RUN-ON-LINUX.md`](t/RUN-ON-LINUX.md).
- **The day-by-day record, including every failure:** [`t/runs/`](t/runs/) and [`internal/ROADMAP-LOG.md`](internal/ROADMAP-LOG.md), which is the roadmap of record.
- **What comes next and why:** [`ROADMAP.md`](ROADMAP.md), WS-20 and WS-21.
- **Licence:** research and education only, see [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).

## The pipeline

```
problems in English, with tests (nl/; pool v5 is 3,003, 232 of them held out and never trained on)
  -> a generator model writes a specified program for each          spec_experiment.py generate
  -> keep only programs that pass their tests and copy nothing seen  spec_experiment.py tests, pool_pick.py
  -> prove each in Dafny, Verus, SPARK, Frama-C, Lean 4, Rocq, F*    run_par.py
     and require all seven to refute a deliberately broken twin
  -> check each accepted specification against the problem's own solution   spec_check.py
  -> the clean pool                                                  loop_dataset.py
  -> build a model from it: locallm from scratch, or a 1.5B student  loop_locallm.py, loop_train.py
  -> score every model on the 232 held-out problems                  score_heldout.py
```

A held-out answer is **clean** only when its tests pass and all seven proofs hold with the twin refuted. An answer all seven prove but whose tests fail is counted separately as **proven but wrong**. The split (`split-v3.json`'s 232 problems) has never changed, so every number on this page is comparable to every earlier one.

## Where locallm stands against Phi

The target is Phi-4-mini, and the target is not a tie.

| model | whose | well formed | tests pass | **clean** | converts | after the spec check |
|---|---|---:|---:|---:|---|---:|
| **locallm, round 4 (3.2M, from scratch)** | **ours** | **209** | 2 | **2** | 100% | 2 |
| **locallm, round 5 (3.2M)** | **ours** | 198 | 2 | **2** | 100% | 2 |
| **locallm, round 7 (92M, pretrained then specialized)** | **ours** | 136 | 1 | **1** | 1/1 | 1 |
| **locallm, round 7b (the same model, decoded greedily)** | **ours** | 149 | 2 | **2** | 2/2 | **2** |
| **locallm, round 8 (specification-checked pool)** | **ours** | 142 | 2 | **2** | 2/2 | **2** |
| **locallm, round 8 with signature-headed training (best)** | **ours** | 91 | 3 | **3** | 3/3 | **3** |
| Phi-4-mini, 3.8B | baseline | 12 | 6 | **3** | 50% | 2 |
| Phi-4-mini, regraded 2026-09-19 beside round 7 | baseline | 12 | 6 | **3** | 50% | 2 |
| Qwen2.5-Coder-1.5B, untrained | baseline | 39 | 13 | **3** | 23% | 2 |
| Qwen3.8-27B-FP8, prompted | reference, far larger | 116 | 81 | **12** | 15% | 11 |
| DeepSeek-Prover-V2-7B, prompted | reference | 39 | 10 | **6** | 60% | 6 |

**Where locallm stands: level with Phi at 3 clean of 232.** Giving every
training document the signature its own program declares cut the model's
signature failures from 40.8% to 12.1%, and that converted into the score. All
three of locallm's clean answers were checked against the problem's own
solution and agree with it; one of Phi's three cannot be checked at all, so on
that column it reads 3 against 2.

It is a tie, not a win, and it is three answers wide. The target is still to
beat Phi outright. It wins the
notation by a distance no baseline approaches, 209 well-formed answers to
Phi's 12 from the 3.2M model, about 1,200 times smaller, and loses the gate that
decides the score, which is passing the problem's own tests. Of 209 well-formed
answers, 2 computed the right values and 204 were proven correct against a
specification the model wrote for a function nobody asked for.

The gap is problem-solving, not formality, and that is the whole of what
remains. [`ROADMAP.md`](ROADMAP.md) names what is being done about it.

### Other models we ran through the pipeline, which are not the product

Kept because their numbers are evidence about the *pipeline*, and because this
project publishes what it measured rather than only what flattered it. None was
built here: the student is a fine-tune of someone else's base model and the
rest were prompted.

| model | well formed | tests pass | clean | converts |
|---|---:|---:|---:|---|
| student, round 4 (QLoRA + DPO on Qwen2.5-Coder-1.5B) | 37 | 12 | 3 | 25% |
| student, round 5 | 42 | 11 | 3 | 27% |
| student, round 6 | 36 | 9 | 3 | 33% |
| student, round 6, decoding against t's grammar | 58 | 14 | 4 | 29% |

Two facts from those rows that shaped the plan for locallm: the gate a borrowed
base loses at is the **proof**, not the notation, and a model pretrained to
write proofs converts better than anything else measured here: the prover
converted 6 of 10 where Phi converted 3 of 6. locallm has the opposite profile,
and that is why its work is on problem-solving rather than on formality.

## The owned core, trained here from random weights

`locallm/` trains a transformer from random weights on this machine's own
corpus. Two studies on 2026-09-19 measured it, both against predictions
registered first, and both came back negative.

**The architecture advantage did not survive a longer run.** Six arms, three
seeds, 4000 updates each on a frozen corpus and tokenizer
([PREREG](locallm/PREREG-source-longer-2026-09-19.md),
[FINDINGS](locallm/FINDINGS-source-longer-2026-09-19.md)).

| seed | modern val loss | GPT val loss | modern |
|---|---:|---:|---|
| 1337 | 1.3611 | 1.2676 | 7.4% worse |
| 7 | 1.3388 | 1.2641 | 5.9% worse |
| 42 | 1.3691 | 1.2824 | 6.8% worse |

At 1000 updates the modern core led by about a quarter; at 4000 it loses at
every seed, and it is also 18.8% slower and reserves 33% more memory. Two
registered predictions held (finite training, and each modern seed improving on
its own 1000-step endpoint by 44-46%) and the third was falsified in the
opposite direction. Completions from all six arms are still repetitive: a 45%
cut in token loss bought no usable completion, which is why the next experiment
was scored by executing programs instead of by nats per token.

**Execution and latent supervision: no synthesis gain, and a broken ruler.**
Four treatments (neither, latent only, execution only, both) from each
4000-step modern checkpoint, on a generated compositional curriculum whose
held-out patterns appear in training under no parameter assignment
([PREREG](locallm/PREREG-factorial-2026-09-19.md),
[FINDINGS](locallm/FINDINGS-factorial-2026-09-19.md)).

| seed | baseline | latent | execution | combined |
|---|---:|---:|---:|---:|
| 1337 | 2 | 1 | 3 | 4 |
| 7 | 2 | 3 | 7 | 1 |
| 42 | 2 | 9 | 2 | 2 |

All three registered predictions are falsified: combined never reaches the
5-point threshold, its paired difference is negative at one seed and zero at
another, and the interaction is negative at two of three. The seed moves the
score more than the treatment does.

Then the ruler itself failed a check. `t/audit_collapsible.py` asks whether a
proper sub-sequence of a task's own stages already passes all of its tests --
`cap 12` twice behaves like `cap 12` once. **Of the 38 correct answers produced
by all twelve arms together, 38 are on such tasks. No arm ever solved a task
that required composing its stages.** The generator now refuses those tasks and
the rebuilt dataset has none.

What did work is the part that says the intervention was real: on held-out
execution examples, the arms supervised on intermediate states predict about
half the trace correctly before derailing (line-prefix accuracy 0.48-0.63) and
the arms without that supervision score exactly zero. The supervision taught
what it was asked to teach, and that skill did not reach unaided synthesis.

## What has been ruled out, and what it cost to find out

| Idea | Measured | Record |
|---|---|---|
| More problems | the corpus is exhausted at about 3,000: APPS's test split yields 37 more, widening t's value kinds at most 353 | [`t/funnel.py`](t/funnel.py) |
| More answers per problem | rounds 4 and 5 grew the pool 60 to 87 rows and moved the clean count by 0 | [`t/out/score-r6.md`](t/out/score-r6.md) |
| Let the model repair its own unproven answers | 110 repaired answers, 2 clean (1.8 percent against 21 percent for fresh samples) | [`t/runs/2026-09-17/NOTES-home.md`](t/runs/2026-09-17/NOTES-home.md) |
| A more tolerant reader (comments, `&&`, `\|\|`) | rescues 119 of 6,603 refused replies, 2 percent | [`t/FUNNEL-2026-09-18.md`](t/FUNNEL-2026-09-18.md) |
| Growing t's syntax | the commonest refusal is a spec function written after the task, 18.5 percent of replies; moving them where t wants them rescues 1.6 percent | the same file |
| Decoding against t's grammar | parsing answers doubled and test-passing answers rose 1.23x, below the 1.5x the preregistration required | [`t/out/CONSTRAINED-2026-09-18.md`](t/out/CONSTRAINED-2026-09-18.md) |
| Preference pairs aimed at the proof gate | conversion 27 to 33 percent, clean count unchanged | [`t/PREDICT-2026-09-18-round6.md`](t/PREDICT-2026-09-18-round6.md) |

**Where the answers die.** Over 14,130 replies, a prompted stock model writes something t's parser accepts 38 percent of the time, so 62 percent never reach a proof system at all — more loss than every other gate together. locallm, trained on t from random weights, parses 98 percent and passes the problems' tests in 2 of 464 answers: it has the notation and not the problem. The fine-tuned student parses 32 percent, where the untrained 1.5B already sat.

## The proof side

- **Seven systems, one matrix.** 35 committed tasks, 31 of them verified with the twin refuted in all seven ([`t/AGREEMENT.md`](t/AGREEMENT.md)), regenerated on a second machine from a clean clone with no cell moved.
- **Nested loops, closed 2026-09-18.** A `while` inside a `while` was an abstain in Lean, Rocq and F\* and a timeout in Frama-C; all seven now verify it with its twin refuted. Two of those fixes were honesty defects rather than gaps: Lean could leave a goal unsolved that `sorryAx` then discharged, so a lowering that proved nothing could read as verified, and Frama-C was not slow at all — the lowering was emitting an invariant of its own that is false.
- **A grammar that is the notation.** [`t/t.gbnf`](t/t.gbnf) is t's syntax as a grammar a generator can decode against, with its identifier rules generated from the lexer's keyword set; [`t/grammar_check.py`](t/grammar_check.py) proves it accepts all 4,208 programs the parser accepts and refuses 590 of 590 replies the parser refuses.
- **The twins ship as an artifact.** [`t/twins/`](t/twins/) is 426 pairs over 90 programs: each one a verified
  program, a near-miss one deliberate edit away, the concrete input at which the near-miss breaks the
  specification the program keeps, and seven independent refutations of it at that input. A pair is written
  only when both halves are on the record. Verified programs are abundant; this pairing is the part with no
  substitute, and it is what lets a model be trained or graded on the difference between a proof that holds
  and one that does not.
- **The specifications are checked against the problems.** All 36 graded answer sets, 650 clean answers, 200
  random draws each against the problem's own solution: 13 disagree: answers whose tests passed, whose seven
  proofs held and whose twin was refuted, and whose specification still does not say what the problem asked.
  None is in the training pool ([`t/SPEC-CHECK-2026-09-18.md`](t/SPEC-CHECK-2026-09-18.md)). Re-run across
  every training answer set on 2026-09-19, because the training gate had been refusing answers nobody had
  checked: 321 tasks, **288 agree, 5 disagree, 28 could not be checked**
  ([`t/SPEC-CHECK-2026-09-19.md`](t/SPEC-CHECK-2026-09-19.md)). That check is what unblocked the pool, taking
  it from 87 preference pairs to 733.
- **Preflight.** [`t/preflight.py`](t/preflight.py) refuses to let a round start on a checker whose version cannot be read, a held-out problem in a training set, a clean answer resting on a flake or a timeout, or a specification that disagrees with its problem.

## Corrections this project made against itself

- **A column said "checked" when nothing had checked it.** `score_heldout.py` counted an answer as
  specification-checked whenever it was absent from the disagreement list, so an answer set nobody had run
  `spec_check.py` over scored full marks. Round 5's student was reported here and in conversation as 3 clean
  surviving the check against Phi's 2 — "one ahead". Checked properly it is **2 against 2**, a tie. The tool
  now records which tags it checked and prints `not checked` for the rest.

- The copy check kept each task's format version, so exact copies counted as new: the filtered-against-raw result was first recorded as 46 against 3 and is **29 against 1** recounted.
- Repair looked obvious and does not work: a 14B model handed seven verdicts writes worse proofs more often than better ones.
- A `--grammar` flag reached three `model.generate` call sites and missed the one every held-out run takes, so a "constrained" run was not constrained. It was caught by its own numbers: 158 parse failures against the unconstrained run's 159.
- DeepSeek-Prover-V2's tokenizer drops every space under transformers 5.17, turning sound answers into `t1tasksmall_nnum(...)`. The generator now round-trips a line of t through a tokenizer before trusting it.

## What is in the repository

| Path | What it is |
|---|---|
| [`locallm/`](locallm/) | the model builder: a transformer trained from random weights on your own hardware |
| [`t/`](t/) | the filter: a small specification language translated into seven proof systems, and every pipeline script above |
| [`t/twins/`](t/twins/) | 426 verified programs each paired with a near-miss and the input that separates them |
| [`nl/`](nl/) | natural-language programming problems with tests, from four public sources |
| [`forge/`](forge/) | the earlier training pipeline that grades a model by the twins it refutes |
| [`tup/`](tup/) | a Linux distribution built from source with a receipt per step |
| [`internal/`](internal/) | handoffs, the machine plan, the dated engineering log that is the roadmap of record |

## Limits, stated plainly

- No model trained here has beaten Phi-4-mini. Three rounds have tied it at 3 of 232.
- Pretraining the core did not help this pipeline. A 92M core pretrained on 46M tokens of real source and specialized on the filtered t data scored 1 clean of 232, wrote fewer well-formed answers than the 3.2M models, and produced 91 proven-but-wrong answers out of 136 well formed. The comparison moves size, tokenizer, corpus and recipe together, so it says the number did not improve and not which change is responsible.
- The owned core's architecture choice is not settled in its favour: at 4000 updates the older GPT core beats the modern one at every seed, on loss, time and memory.
- No auxiliary training objective tried here has improved program synthesis. Execution-state supervision improves execution-state prediction and does not transfer; latent prediction does neither at three seeds.
- Token loss on a validation window predicts nothing about behaviour at this scale. The 45% loss cut that bought no usable completion is the second time in two days that a loss result and a behaviour result disagreed here.
- The clean pool is small (87 examples) and the corpus that feeds it is exhausted, so the next move is a better generator or a better base model, not more rounds of the same shape.
- A proof covers the specification, not the intent. Hence the tests, the proven-but-wrong column and the specification check.
- t covers integers, booleans, sequences, pairs, strings as character sequences, loops with invariants and recursive specification functions. No heap, no floats, no concurrency.
- Phi's 3 of 232 is a low bar and it is low for a reason: Phi has never seen t, so most of its answers do not parse. Beating it at writing t is a weaker claim than beating it at Python, and this page says so next to the number.
- The 232 held-out problems are MBPP, which every base model here was almost certainly pretrained on. The split protects against *this project's* training leaking into its own evaluation — it cannot protect against a base model having seen MBPP before we met it. That applies to every row equally, ours and Phi's, so the comparison stands while the absolute numbers are softer than they look.
- The models are not the same size. DeepSeek-Prover-V2-7B is 7B against Phi-4-mini's 3.8B, so its 6 against 3 is not a per-parameter claim; what makes it interesting is the conversion rate, which is a property of what the model was trained on rather than how big it is.

## License

Research use only: the whole repository may be used, copied, modified and redistributed for research and education, and for nothing else without written permission ([`LICENSE`](LICENSE)). Third-party material keeps its own licenses; the problem corpora under `nl/` list theirs. `locallm/` was MIT until 2026-09-15.

Copyright (c) 2026 Treston Malachi Cuzzort.
