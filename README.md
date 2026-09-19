# locallm

Small language models built from scratch on your own machine, trained only on code that seven independent proof systems agree is correct.

The industry bet is scale: more parameters, more tokens, more scraped code. locallm bets the other way. Keep a training example only when it passes its tests, is proven against its specification by seven proof systems, and has a deliberately broken copy of itself caught by all seven. Then ask whether a small model built from that data does more per parameter than a model built from raw data, and than small open models such as Microsoft's Phi-4-mini.

Every number below was measured by a script in this repository and links to the file that records it. Where a number of this project's own turned out wrong, the correction is on this page rather than in its history.

**The model of record is locallm.** The comparison this project exists to settle is **locallm against Phi-4-mini**: a model trained here from random weights, on filtered data, against a small open model trained the usual way. The fine-tuned 1.5B student rows below are a second, borrowed-base experiment and not the claim. locallm is not fixed at the 3.2M of its round-4 and round-5 rows either: the core now trains at **91M parameters** on this hardware and its optimizer step is checked through **312M** ([locallm/CORE-2026-09-19.md](locallm/CORE-2026-09-19.md)). What has not yet happened is the run that puts a locallm of that size through this pipeline's data and scores it on the 232 held-out problems; until that exists, locallm's row on this page is a 3.2M model's row and is read that way.

**Status, 2026-09-19.** Two negative results landed the same day, both measured against predictions written before the runs. The modern core's architecture advantage **reversed** at four times the training budget, and a preregistered four-cell experiment in execution and latent supervision produced **no synthesis gain at any seed**, while revealing that its own held-out tasks were passable without composing anything. Both are below, under [the owned core](#the-owned-core-trained-here-from-random-weights).

**What this does not claim.** Nothing here is hallucination-free or 100 percent correct. A proof shows a program meets its specification, not that the specification says what the problem asked, which is why every table carries a **proven but wrong** column, why the tests are a separate gate, and why an accepted answer's specification is checked against the problem's own solution ([`t/spec_check.py`](t/spec_check.py)). **No model trained here has beaten Phi-4-mini**: three rounds of the loop have produced 3 clean answers out of 232 each time, which is exactly Phi's score. Two models *run through* this pipeline do beat it, and neither was trained by us. And the seven checkers do less of the work than the name suggests: a preregistered ablation ([`t/ABLATION-2026-09-17.md`](t/ABLATION-2026-09-17.md)) measured one prover admitting wrong answers 17.4 percent of the time against 12.9 percent for all seven with the twin refuted, at half the problem coverage; on held-out answers, where the model writes its own specification, every proof gate admits about 97 percent wrong and the tests catch what the proofs cannot. The honest claim is tests **and** proofs together, not seven provers rather than one.

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

## Held-out results, 232 problems

Measured by [`t/score_heldout.py`](t/score_heldout.py); the full table is [`t/out/score-r6.md`](t/out/score-r6.md).

| model | who trained it | well formed | tests pass | **clean** | converts | after the spec check |
|---|---|---|---|---|---|---|
| Qwen3.8-27B-FP8, prompted | not us | 116 | 81 | **12** | 15% | 11 |
| DeepSeek-Prover-V2-7B, prompted | not us | 39 | 10 | **6** | **60%** | 6 |
| Phi-4-mini, 3.8B | not us | 12 | 6 | **3** | 50% | 2 |
| Qwen2.5-Coder-1.5B, untrained | not us | 39 | 13 | **3** | 23% | 2 |
| student, round 4 | us, QLoRA + DPO | 37 | 12 | **3** | 25% | 2 |
| student, round 5 | us | 42 | 11 | **3** | 27% | 2 |
| student, round 6 | us | 36 | 9 | **3** | 33% | 2 |
| student, round 6, decoding against t's grammar | us | 58 | 14 | **4** | 29% | 3 |
| **locallm, round 4 (3.2M, from scratch)** | us | 209 | 2 | **2** | 100% | 2 |
| **locallm, round 5 (3.2M)** | us | 198 | 2 | **2** | 100% | 2 |

**converts** is the share of test-passing answers the seven can prove, and it is where this project is stuck.
The two locallm rows are the ones that count, and they are 3.2M-parameter models: they write well-formed t
almost every time (209 and 198 of 232) and pass the problems' tests twice, which is the notation without the
problem. The 1.5B student rows sit beside them as a borrowed-base comparison; the student writes three times
Phi's well-formed answers and converts a third of them where Phi converts half.

Three rounds, three different data recipes — more problems, more answers, then preference pairs aimed at the exact gate the student loses at — and the clean count did not move. Round 6's predictions were written before it ran ([`t/PREDICT-2026-09-18-round6.md`](t/PREDICT-2026-09-18-round6.md)) and the one that mattered was wrong.

**The gate we lose at is the proof, not the notation.** Round 6's student wrote three times as many well-formed answers as Phi and one and a half times as many test-passing ones, then converted 3 of 9 into clean answers where Phi converted 3 of 6. A model pretrained to write proofs converts better than either: DeepSeek-Prover-V2-7B, prompted and never fine-tuned by us, converted 6 of 10 and none of its six specifications disagreed with its problem. That result is three answers wide and needs seeds before it is a claim, but it is the first thing measured here that points at a fix rather than closing a door.

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
Four treatments -- neither, latent only, execution only, both -- from each
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
  random draws each against the problem's own solution: 13 disagree -- answers whose tests passed, whose seven
  proofs held and whose twin was refuted, and whose specification still does not say what the problem asked.
  None is in the training pool ([`t/SPEC-CHECK-2026-09-18.md`](t/SPEC-CHECK-2026-09-18.md)).
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
