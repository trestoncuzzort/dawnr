# Is the project resting on a result nobody has shown? (2026-10-01 00:17Z)

The operator's question, 2026-09-30 evening: are we doing something for no reason, holding out
for math that does not exist; if the project rests on a maybe, we are doing it wrong. This file
answers from our own record first, then from fetched work. Receipt 015765a357ab.

## The bet, in the project's own words

`AMBITION.md` section 2: "a model trained here, from random numbers, on one machine, on data seven
proof systems agreed was correct", and section 3: "proof that verified data buys parameter
efficiency". Concretely: a 93M-parameter model, from random weights, reads an English problem and
writes a correct specification and program in `t`, having seen 531 proved documents (about 312 KB,
on the order of 100,000 tokens of `t`).

## What our own record says

| measurement | result | where |
|---|---|---|
| ten r11 seeds, r12 head-prompt seeds, chat pipeline seeds, specification check applied | 0 correct on the held-out 200, every arm | `AMBITION.md` section 1 |
| three cores (sweep, English pilot B/C, the r12 core with 12x the English) | 0 on dev, every core | `t/PREDICT-2026-09-30-dawnr-r12-core.md` |
| 6,400 sampled answers from the r12 core | 0 correct by hand | `t/PREDICT-2026-09-30-dawnr-base-rate.md` |
| RL gate on the fine-tuned policy, 372 prompts x 16 | 0 of 271 prompts outside its corpus | `t/RL-DESIGN-2026-09-26.md` section 8 |
| the round on the new core, seeds 1 to 3 | 0 tests passed of 232 each | `t/out/r12-run/` |
| a prompted 3.8B pretrained model on the same held-out set | 2 of 232 with the specification check | `AMBITION.md` section 1 |

More English, a lower code loss, more seeds and sampling instead of greedy decoding each moved
form (well-formed output) and none moved correctness. The shelf named the wall on 2026-09-20
(`internal/RESEARCH-NEXT-2026-09-20.md`: the failing step is English to specification) and the
stage sweep measured the gap on 2026-09-30 (the proved corpus is one to two orders short of the
smallest published synthesis sets).

## What fetched work says

| source | setting | size and data | result |
|---|---|---|---|
| PolyCoder evaluation, arXiv:2202.13169, table 4 | from scratch, ordinary Python, unit tests (HumanEval) | 160M on 39B code tokens; CodeParrot 110M on 26B Python tokens; GPT-Neo 125M on 300B tokens | pass@1 2.13%, 3.80%, 0.75% |
| phi-1, arXiv:2306.11644 | from scratch on curated and synthetic "textbook" data | 1.3B and 350M parameters; 6B filtered + 1B tokens written by a large model | 50.6% and 45% HumanEval |
| SAFE, arXiv:2410.15756, table 8 | verified Rust proofs, **specification given**, pretrained code model, verifier-filtered self-evolution bootstrapped by a frontier model | smallest backbone 1.3B pretrained; tens of thousands of synthesized proofs | 1.44% raw to 21.58% after three rounds (33B backbone: 43 to 52%) |
| Vericoding benchmark, arXiv:2509.22908 | frontier models, **specification given**, write verified code | off the shelf | 82% Dafny, 44% Verus, 27% Lean |

Read together:

1. **Size.** From scratch at 110 to 160M parameters, tens of billions of code tokens buy 2 to 4%
   on ordinary Python with unit tests. Our core is smaller, saw roughly a thousandth of that code,
   and is asked for something harder (a program and a specification that seven provers accept and
   that matches the reference on drawn inputs).
2. **Clean data does buy efficiency, at volume.** phi-1 is the evidence for the project's thesis,
   and it used seven billion tokens of targeted data, a billion of them written by a large model.
   We have about a hundred thousand tokens of `t`. The proof gate cannot produce volume by itself;
   it only filters what something else writes.
3. **Every positive verified-code result starts from a pretrained model.** The smallest found is
   1.3B, pretrained on code, taught by a frontier model, with the specification supplied. No
   fetched work trains a verified-code model from random weights at any size.
4. **Writing the specification from English is the open part even for frontier models.** The
   published successes are given the specification. Our model is asked to write it.

## Verdict

Zero is the expected result of the from-scratch bet at this scale, not a surprise and not a bug:
the gap is one order in parameters and three to five in targeted data, on a task no published
system does from random weights. Holding the project's progress on that model is holding it on a
maybe. The teacher round registered for 2026-10-01 is the right kind of step (it is SAFE's loop)
and the wrong size to change this alone: it predicts at least 50 new clean documents against a
need of tens of thousands.

What is **not** resting on a maybe: the gate. Proof against a specification, twins, the
specification check, the decontamination and the grading stack are model-agnostic, they work,
and they are the idea the project started from (a verdict the candidate cannot forge).

## What doing it right looks like, by the evidence

1. **Keep the gate exactly as it is.** It is the product.
2. **Put a pretrained small code model behind it as the student** (the 1 to 2B class SAFE used
   fits the desktop card with low-rank adapters and runs offline), and run SAFE's loop: the
   teacher writes, the provers and the specification check filter, the student trains on what
   survives, repeat. The lab worktree with the adapter track is the parts bin.
3. **Split the task the way the published successes do.** Specification given, write the program
   and its proof hints: measurable today and known to work. English to specification second, with
   the specification check as its gate and the teacher as its source.
4. **Keep the from-scratch core as research with its scale stated**: it needs on the order of
   10^4 proved documents before a result is plausible, and step 2 is what manufactures them.
5. **Stop spending rounds on the same corpus.** Another ten seeds on 531 documents answers a
   question already answered seven ways.

The trust claim changes from "trained here from random weights" to "nothing it says is relied on
until it is proved", which is the stronger claim and the one that does not depend on a maybe.
The decision is the operator's.
