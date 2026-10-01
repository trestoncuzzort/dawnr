# The plan of record from 2026-10-01: every goal, on borrowed ladders

The operator's direction, the evening of 2026-09-30: build from the ladders others have made; no
step may rest on a maybe; nothing the system says is relied on until it is proved, and that is the
whole point; other people's weights are fine if they are the best for this job and usable by
everyone; meet every goal in the project on those weights. This file maps each goal in
`AMBITION.md` to the published method it now stands on, the measurement that says it is met, and
where it stands. `internal/RESEARCH-2026-10-01-is-the-bet-supported.md` is why.

**What changed.** The product is the gate with a pretrained, permissively licensed model behind
it, fine-tuned here on what the gate admits. The from-scratch core is research; no run is spent
on it. The claim is the one the gate makes: an answer is shown with the proof that stands behind
it and how many independent provers gave it, or it is refused.

## The core loop

| rung | stands on | done when | state |
|---|---|---|---|
| R0 what pretrained models already do through the gate | our own answer sets, 2026-09-08 to 09-28 | pooled funnel on the clean 200 | **done**: 121 pass tests, 63 some prover, 23 all seven, 15 also specification-checked; from scratch 0 |
| R1 which weights | model cards for the licence; measurement for the rest (`t/PREDICT-2026-10-01-base-model-selection.md`) | the registered rule names the base | **named by the rule (2026-10-01 03:02Z): Qwen3.5-4B.** Fine-tuned on the same 527 rows the 1.5B, 2B and 4B answer 1, 1 and 3 of 100 dev problems at one prover with the specification checked, 0 at all seven; the rule picks the 4B, a paired test does not separate it from the 2B (p = 0.63); the 9B does not fit the card for training |
| R2 what "proved" means at each level | `t/kernel_disagreement.py`: 0 contradictions in 4,700 programs; one sound verifier is the published filter (SAFE, AlphaVerus) | coverage by level recorded | **done, and tightened 2026-10-01**: 50 (one prover) to 19 (seven) on the clean 200 after the instrument repairs; "specification-checked" now also asks that the specification reject at least 60% of the wrong outputs tried (SAFE's rule), which reads 48 to 19; with draws from every example and other inputs' answers as mutants (the check drew only from the first example until then), 47 to 19 |
| R3 proof repair with the verifier's message | SAFE's self-debugging (arXiv:2410.15756): incorrect proof plus error to a fixed proof, trained, not only prompted | conversion from tests-pass to proved measured before and after on dev | measured once and it does not work yet: a second try trained on 788 debugging rows with one generic line a kernel repaired 1 answer of 91 (`t/PREDICT-2026-10-01-several-answers.md`, prediction 22). The next student's proof-repair rows carry Dafny's own diagnostics, the clause that failed (`t/dafny_feedback.py`); its repair measurement is to be registered before it runs |
| R4 several answers and the gate as the filter | SAFE's Accuracy@10; the gate makes sampling safe | coverage at k samples on dev | **measured (2026-10-01):** the 4B on v4 proves 4 dev problems of 100 with one answer, 7 with ten, 8 with ten and the specification first (3 by all seven); retrieved examples and a second try add nothing. **Corrected the same night: five of the eight rest on a weak specification; on complete ones the counts are 2, 3 and 4 (1 by all seven)**, and the held-out rule now uses that count |
| R5 the student | SAFE's loop with QLoRA's recipe (arXiv:2305.14314 B.2); `t/graded_pool.py`, `t/student_sft.py` | the student's dev table, then the clean 200 once | **given the specification it works: the 4B proves 28 of 33 unseen specifications, 26 by all seven kernels** (`t/PREDICT-2026-10-01-spec-given.md`). From English it proves 2 of 100 dev problems with one answer on a specification that says what was asked (4 with ten answers and the specification first): the specification is the failing step for every model measured (across every answer set on record only 28 of the 100 dev problems have ever received a specification their own tests support). The clean 200 is run once, with the route the rule picks |
| R6 more proved data each round | SAFE's rounds: the teacher and the student write, the gate filters, retrain | pool size and student coverage per round | **first round on own hardware done (2026-10-01).** The pool went from 527 rows over 262 problems to **693 over 323**: 661 training answers that had never been graded went through the kernels (323 proved), the answers three instrument faults had refused were re-read, and a proof round gave the 4B student 352 right specifications for 273 unsolved training problems (187 answered with a test-passing program, 34 proved, 31 admitted; `t/PREDICT-2026-10-01-proof-round.md`). The 4B is training on the rows built from it. The rented teacher round was stopped unfinished at the operator's instruction (own machines only; outside compute only on Google or AWS) |
| R2b the gate with no reference | Clover's consistency check between independently written artifacts (arXiv:2310.17807); SAFE's completeness floor; our own exploit and mutation instruments of 2026-09-20 | of what the gate shows without a reference, the share that is right by the reference | **built and measured (2026-10-01)**: `t/spec_gate.py`, the base model's tested Python as the second artifact. Dev (the 4B on v4): 10 shown and 4 right before, 3 and 3 with the stage. 1,038 proved training answers: 79.3% right before, 94.0% with it (registered bar 95%: missed), keeping 80% of right answers. Still to run: the 4B on v5's dev answers, and the held-out run for the student and the reference |
| R7 usable by everyone | Apache-2.0 base; merged weights and a 4-bit GGUF (llama.cpp's convert and quantize); the gate as a tool | a fresh machine runs the student and the gate offline | **one command exists and ran (2026-10-01)**: `t/answer.py` took three fresh questions through the student at 4 bits on a CPU, the base model's Python, the stage and the seven provers on one machine: one shown at seven provers, one at four, one refused (no valid `t`). The 4-bit student (Q4_K_M, 2.71 GB) on 12 CPU threads: 15.5 tokens a second; dev unchanged (the same 2 problems on complete specifications); the specification-given questions 23 of 33 proved (bf16 28), 22 by all seven (bf16 26) (`t/PREDICT-2026-10-01-small-hardware.md`). Q8_0 (4.48 GB) keeps every proof of full precision (28, 26 by seven); an importance matrix does not rescue 4 bits (25). Not done: published files, a clean-machine install |

## Every goal in AMBITION.md

| goal | ladder | measured by | state |
|---|---|---|---|
| 1. beat the 3.8B reference | the student against the same prompted model on the clean 200, same scorer | proved, specification-checked answers, per trust level | reference reads 1 of 200 at seven; student pending R5 |
| 2. the product | the gate plus the student (this file) | R7 | restated here; README and AMBITION follow when R1 names the base |
| 3. size as a curve | the same table across sizes: fine-tuned small against prompted large | coverage against parameters | prompted points exist (1.5B to 235B) |
| 4. scale the engine | R6 | rows the gate admits per round | 693 rows over 323 problems at one prover (333 at seven) after the first round on our own machines (2026-10-01); 527 over 262 before it |
| 5. own the whole loop | local generator, local gate, our own machines (the operator, 2026-10-01: nothing outside them except Google or AWS) | no outside call in a round | holds from 2026-10-01 02:22Z; the teacher is whatever model our own cards can run |
| 6. matter to others | R7 and the twins | release artifacts | twins graded 2026-09-30 (233 usable negatives) |
| a brain | the chosen pretrained base | R1 | running |
| learn, not memorise | the clean 200 with the specification check, by trust level | R5 on the clean 200 | pending |
| know when it is right | the gate; then P(True) against the gate's verdict (arXiv:2207.05221) | calibration error of the student's own confidence against proof outcomes | gate done; calibration open |
| better reasoning | SAFE's rounds (expert iteration); RL only where a published result supports it at this scale | coverage per round | R6 |
| know what it was not trained on | retrieval of proved examples into the prompt (the dynamic few-shot of arXiv:2402.00247); `DAWNR-RETRIEVAL.md`'s index | dev coverage with and without retrieval | open |
| remember the person | per-person adapters on the base (the harness already keeps them) | the four simulated-person measurements re-run on the base | open |
| act through tools | the base's native tool calls through the existing harness (permissions, hooks, MCP) | the 1,007-conversation tool evaluation re-run on the base | harness built; re-measure |
| hear and speak | pretrained recognisers and voices with permissive licences | word error rate on a public test set; offline | **hearing done (2026-10-01)**: Whisper base.en under whisper.cpp, 4.14% on LibriSpeech test-clean (paper 4.2), 16x real time on 8 CPU threads; speaking (Piper, MIT) measured next |
| see | the base's own vision input if it has one, else a permissive pretrained encoder | a small image check through the harness | open |
| small hardware | 4-bit GGUF of the student | tokens per second on an 8 GB card and on a CPU | R7 |
| understood from inside | published sparse autoencoders for the base family where they exist | a feature that tracks specifications, registered before looking | open |
| improve itself safely | the data engine (built) driving R6 | R6 | built |

Order of work: R1 and R5 (they are one measurement), then R4 and R3 on the chosen student, the
clean 200 once, R6, R7, then the table's remaining rows top to bottom. Every rung registers its
prediction before it runs and records its outcome in the same file.
