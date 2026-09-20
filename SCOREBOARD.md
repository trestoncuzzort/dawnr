# Scoreboard

Every model measured on the same 232 held-out problems, by the same pipeline.
The headline is in [`README.md`](README.md); the caveats are in
[`LIMITS.md`](LIMITS.md).

A held-out answer is **clean** only when its tests pass and all seven proofs
hold with the twin refuted. An answer all seven prove but whose tests fail is
counted separately as **proven but wrong**. The split has never changed, so
every number here is comparable to every earlier one.

## Where locallm stands against Phi

| model | whose | well formed | tests pass | **clean** | converts | after the spec check |
|---|---|---:|---:|---:|---|---:|
| **locallm, round 4 (3.2M, from scratch)** | **ours** | **209** | 2 | **2** | 100% | 2 |
| **locallm, round 5 (3.2M)** | **ours** | 198 | 2 | **2** | 100% | 2 |
| **locallm, round 7 (92M, pretrained then specialized)** | **ours** | 136 | 1 | **1** | 1/1 | 1 |
| **locallm, round 7b (the same model, decoded greedily)** | **ours** | 149 | 2 | **2** | 2/2 | **2** |
| **locallm, round 8 (specification-checked pool)** | **ours** | 142 | 2 | **2** | 2/2 | **2** |
| **locallm, round 8 with signature-headed training (best)** | **ours** | 91 | 3 | **3** | 3/3 | **3** |
| Phi-4-mini, 3.8B | baseline | 12 | 6 | **3** | 50% | 2 |
| Qwen2.5-Coder-1.5B, untrained | baseline | 39 | 13 | **3** | 23% | 2 |
| Qwen3.8-27B-FP8, prompted | reference, far larger | 116 | 81 | **12** | 15% | 11 |
| DeepSeek-Prover-V2-7B, prompted | reference | 39 | 10 | **6** | 60% | 6 |

Phi's row was regraded on 2026-09-19 beside round 7 and reproduced exactly,
cell for cell, so the comparison is one evaluator and not two.

**What moved the score.** Giving every training document the signature its own
program declares cut the model's signature failures from 40.8% to 12.1%, and
that converted into the number. All three of locallm's clean answers were
checked against the problem's own solution and agree with it; one of Phi's
three cannot be checked at all, so on that column it reads 3 against 2.

**Where the gap is.** locallm wins the notation by a distance no baseline
approaches, 209 well-formed answers to Phi's 12 from a model about 1,200 times
smaller, and loses the gate that decides the score, which is passing the
problem's own tests. Of 209 well-formed answers, 2 computed the right values
and 204 were proven correct against a specification the model wrote for a
function nobody asked for. The remaining 3 were neither: well formed, but not
proven and not passing. The gap is problem-solving, not formality.

## Other models run through the pipeline, which are not the product

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

Two facts from those rows shaped the plan for locallm: the gate a borrowed base
loses at is the **proof**, not the notation, and a model pretrained to write
proofs converts better than anything else measured here, the prover converting
6 of 10 where Phi converted 3 of 6. locallm has the opposite profile, and that
is why its work is on problem-solving rather than on formality.

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
proper sub-sequence of a task's own stages already passes all of its tests, so
that `cap 12` twice behaves like `cap 12` once. **Of the 38 correct answers
produced by all twelve arms together, 38 are on such tasks. No arm ever solved
a task that required composing its stages.** The generator now refuses those
tasks and the rebuilt dataset has none.

What did work is the part that says the intervention was real: on held-out
execution examples, the arms supervised on intermediate states predict about
half the trace correctly before derailing (line-prefix accuracy 0.48-0.63) and
the arms without that supervision score exactly zero. The supervision taught
what it was asked to teach, and that skill did not reach unaided synthesis.

## What has been ruled out, and what it cost to find out

| Idea | Measured | Record |
|---|---|---|
| More problems | **superseded 2026-09-20.** Read as "exhausted at about 3,000" until the stdin-shaped problems `t/nl_stdin.py` had already measured were wired in: pool v6 is 4,035, **+1,032 (+34.4%)**, APPS 474 and CodeContests 558. APPS's test split still yields 37 more on top | [`t/nl_stdin_pool.py`](t/nl_stdin_pool.py), [`t/funnel.py`](t/funnel.py) |
| More answers per problem | rounds 4 and 5 grew the pool 60 to 87 rows and moved the clean count by 0 | [`t/out/score-r6.md`](t/out/score-r6.md) |
| Let the model repair its own unproven answers | 110 repaired answers, 2 clean (1.8 percent against 21 percent for fresh samples) | [`t/runs/2026-09-17/NOTES-home.md`](t/runs/2026-09-17/NOTES-home.md) |
| A more tolerant reader (comments, `&&`, `\|\|`) | rescues 119 of 6,603 refused replies, 2 percent | [`t/FUNNEL-2026-09-18.md`](t/FUNNEL-2026-09-18.md) |
| Growing t's syntax | the commonest refusal is a spec function written after the task, 18.5 percent of replies; moving them where t wants them rescues 1.6 percent | the same file |
| Decoding against t's grammar | parsing answers doubled and test-passing answers rose 1.23x, below the 1.5x the preregistration required | [`t/out/CONSTRAINED-2026-09-18.md`](t/out/CONSTRAINED-2026-09-18.md) |
| Preference pairs aimed at the proof gate | conversion 27 to 33 percent, clean count unchanged | [`t/PREDICT-2026-09-18-round6.md`](t/PREDICT-2026-09-18-round6.md) |

**Where the answers die.** Over 14,130 replies, a prompted stock model writes
something t's parser accepts 38 percent of the time, so 62 percent never reach
a proof system at all, more loss than every other gate together. locallm,
trained on t from random weights, parses 98 percent and passes the problems'
tests in 2 of 464 answers: it has the notation and not the problem. The
fine-tuned student parses 32 percent, where the untrained 1.5B already sat.
