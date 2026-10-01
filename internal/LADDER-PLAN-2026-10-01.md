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
| R1 which weights | model cards for the licence; measurement for the rest (`t/PREDICT-2026-10-01-base-model-selection.md`) | the registered rule names the base | prompted half measured (floor for small models); fine-tuned half running |
| R2 what "proved" means at each level | `t/kernel_disagreement.py`: 0 contradictions in 4,700 programs; one sound verifier is the published filter (SAFE, AlphaVerus) | coverage by level recorded | **done**: 45 (one prover) to 16 (seven), specification-checked |
| R3 proof repair with the verifier's message | SAFE's self-debugging (arXiv:2410.15756): incorrect proof plus error to a fixed proof, trained, not only prompted | conversion from tests-pass to proved measured before and after on dev | open; our prompted single round moved 3 cells of 182 (`t/FINDINGS-repair-2026-09-20.md`) |
| R4 several answers and the gate as the filter | SAFE's Accuracy@10; the gate makes sampling safe | coverage at k samples on dev | open |
| R5 the student | SAFE's loop with QLoRA's recipe (arXiv:2305.14314 B.2); `t/graded_pool.py`, `t/student_sft.py` | the student's dev table, then the clean 200 once | first students training |
| R6 more proved data each round | SAFE's rounds: the teacher and the student write, the gate filters, retrain | pool size and student coverage per round | teacher round registered (`t/PREDICT-2026-10-01-dawnr-teacher-round.md`), free credit only |
| R7 usable by everyone | Apache-2.0 base; merged weights and a 4-bit GGUF; the gate as a tool | a fresh machine runs the student and the gate offline | open |

## Every goal in AMBITION.md

| goal | ladder | measured by | state |
|---|---|---|---|
| 1. beat the 3.8B reference | the student against the same prompted model on the clean 200, same scorer | proved, specification-checked answers, per trust level | reference reads 1 of 200 at seven; student pending R5 |
| 2. the product | the gate plus the student (this file) | R7 | restated here; README and AMBITION follow when R1 names the base |
| 3. size as a curve | the same table across sizes: fine-tuned small against prompted large | coverage against parameters | prompted points exist (1.5B to 235B) |
| 4. scale the engine | R6 | rows the gate admits per round | 527 rows over 262 problems at one prover (271 at seven) |
| 5. own the whole loop | local generator, local gate, free compute only | no paid call in a round | holds; the teacher runs on free credit or locally at 9 to 14B |
| 6. matter to others | R7 and the twins | release artifacts | twins graded 2026-09-30 (233 usable negatives) |
| a brain | the chosen pretrained base | R1 | running |
| learn, not memorise | the clean 200 with the specification check, by trust level | R5 on the clean 200 | pending |
| know when it is right | the gate; then P(True) against the gate's verdict (arXiv:2207.05221) | calibration error of the student's own confidence against proof outcomes | gate done; calibration open |
| better reasoning | SAFE's rounds (expert iteration); RL only where a published result supports it at this scale | coverage per round | R6 |
| know what it was not trained on | retrieval of proved examples into the prompt (the dynamic few-shot of arXiv:2402.00247); `DAWNR-RETRIEVAL.md`'s index | dev coverage with and without retrieval | open |
| remember the person | per-person adapters on the base (the harness already keeps them) | the four simulated-person measurements re-run on the base | open |
| act through tools | the base's native tool calls through the existing harness (permissions, hooks, MCP) | the 1,007-conversation tool evaluation re-run on the base | harness built; re-measure |
| hear and speak | pretrained recognisers and voices with permissive licences | word error rate on a public test set; offline | open |
| see | the base's own vision input if it has one, else a permissive pretrained encoder | a small image check through the harness | open |
| small hardware | 4-bit GGUF of the student | tokens per second on an 8 GB card and on a CPU | R7 |
| understood from inside | published sparse autoencoders for the base family where they exist | a feature that tracks specifications, registered before looking | open |
| improve itself safely | the data engine (built) driving R6 | R6 | built |

Order of work: R1 and R5 (they are one measurement), then R4 and R3 on the chosen student, the
clean 200 once, R6, R7, then the table's remaining rows top to bottom. Every rung registers its
prediction before it runs and records its outcome in the same file.
