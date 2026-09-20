# Round 7b: three arms, and the one that helped cost nothing

Three excuses for round 7's score, each turned into an arm and registered with
its falsifier in [`t/PREDICT-2026-09-19-round7b.md`](../t/PREDICT-2026-09-19-round7b.md)
before any arm generated an answer. `t/out/score-r7b.md` has the full table,
graded with `evaluator_stable: true` and no file hash moving on either machine.

## The table

| arm | well formed | signature failures | tests pass | **clean** | spec checked | proven but wrong |
|---|---:|---:|---:|---:|---:|---:|
| round 7 (temperature 0.5) | 136 | 55 (40.4%) | 1 | **1** | 1 | 91 |
| `step150` (shorter schedule) | 92 | 49 (53.3%) | 2 | **0** | 0 | 46 |
| `headed` (every document has a head) | 16 | 3 (18.8%) | 0 | **0** | 0 | 10 |
| **`greedy` (round 7's model, temperature 0)** | **149** | 48 (32.2%) | 2 | **2** | **2** | 117 |
| Phi-4-mini, regraded today | 12 | — | 6 | **3** | 2 | 1 |

## The predictions

1. **`headed` cuts signature failures below 20%: held at 18.8%, and the number
   is hollow.** It is 3 of 16, because the arm produced 16 well-formed answers
   instead of 136. A rate computed on a collapsed denominator is not evidence
   that the mechanism worked, and this one is reported as held only because
   that is what was registered. See below for what actually happened.
2. **No arm reaches 3 clean: held.** The best is 2.
3. **`step150` lands within one clean answer of round 7 and within 10 points on
   signature failures: falsified.** The clean count is within one (0 against
   1), but signature failures went 40.4% to 53.3%, 12.9 points, past the
   registered bound. A shorter schedule is worse on both counts.
4. **`greedy` writes more well-formed answers than 136: held**, at 149.
5. **Tests passing stays single digits in every arm: held**, at 2, 0 and 2.

Three held, one falsified, one held on a denominator that makes it meaningless.

## What actually happened to the headed arm

Not a verdict on head conditioning. An interface bug, and the raw replies name
it exactly: the model writes one program, then a blank line, then
`Signature: dafny_synthesis_task_id_441__medianOfThree(int, int) -> int`, then
a second program. Training documents began with a head, so the model learned
that a head is how a document *starts*, and emits one when it thinks the
previous document ended.

`t/loop_locallm.py` cuts an answer at the next document with
`re.split(r"\n\s*\n(?=Problem: |t \d)", ...)`, a boundary that knows about
`Problem:` heads and bare programs and nothing else. So both programs stayed in
one reply and 216 of 232 answers failed to parse.

The splitter now knows about `Signature:` heads, and the arm is regenerating
under the fix. Until that lands, **this arm measured a corpus format against a
splitter that did not know about it**, which is worth exactly one lesson:
changing the shape of training documents changes the shape of the output, and
every boundary in the pipeline that reads that output has to be changed with
it.

## The result worth keeping

**Greedy decoding is the best locallm row measured, and it cost nothing.** Same
checkpoint as round 7, temperature 0 instead of 0.5: well-formed 136 to 149,
signature failures 40.4% to 32.2%, clean 1 to **2**, and both of those clean
answers survived the specification check against the problem's own solution --
`clean, spec checked: 2, spec unchecked: 0`.

That matters beyond the count. The 3.2M rows also score 2 clean, but neither
had ever been specification-checked. **This is the first locallm result whose
every clean answer is verified by all seven, with its twin refuted, and checked
to be a specification of the problem that was actually asked.**

It is still 2 against Phi's 3.

## What it says about where the gap is

Sampling noise was costing real answers, and removing it was free. What it did
not touch is the number that decides the score: tests passing went 1 to 2,
while `proven but wrong` went 91 to 117. The model is now *more* productive at
writing internally consistent specifications of functions nobody asked for.

That is WS-22's diagnosis holding up under another round: locallm's bottleneck
is solving the problem, and the levers that remain are the training data
(step 22.2, growing the clean pool with the best converter measured) and size
(22.3). Decoding and schedule are done; they bought 1 clean answer between them
and will not buy another.
