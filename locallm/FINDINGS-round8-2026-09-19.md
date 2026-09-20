# Round 8: locallm matches Phi, and the thing that did it was a header

Predictions were registered in
[`t/PREDICT-2026-09-19-round8.md`](../t/PREDICT-2026-09-19-round8.md) before the
corpus was built. `t/out/score-r8.md` is the table, graded with
`evaluator_stable: true` on a Phi baseline regraded the same day.

## The table

| model | well formed | signature failures | tests pass | **clean** | clean, spec checked | spec unchecked |
|---|---:|---:|---:|---:|---:|---:|
| Phi-4-mini, regraded today | 12 | — | 6 | **3** | 2 | 1 |
| locallm r4 (3.2M) | 209 | — | 2 | **2** | 0 | 2 |
| locallm r5 (3.2M) | 198 | — | 2 | **2** | 0 | 2 |
| locallm r7 (92M, temperature 0.5) | 136 | 40.4% | 1 | **1** | 1 | 0 |
| locallm r7b greedy | 149 | 32.2% | 2 | **2** | 2 | 0 |
| locallm r8 (checked pool, no heads) | 142 | 40.8% | 2 | **2** | 2 | 0 |
| **locallm r7b headed2 (heads, greedy)** | 91 | **12.1%** | **3** | **3** | **3** | **0** |

**locallm now ties Phi-4-mini at 3 clean answers of 232, and all three of
locallm's agree with the problem's own solution while one of Phi's three cannot
be checked at all.** On the column that survives the specification check it
reads 3 against 2. That is a tie on the headline number, not a win, and the tie
is three answers wide.

## The predictions

1. **`locallm-r8` scores at least 2 clean: held**, at 2.
2. **`locallm-r8` does not reach 4 clean: held**, at 2.
3. **`headed2` writes at least 100 well-formed answers: falsified**, at 91. It
   is five and a half times its broken-splitter predecessor's 16 and still
   under the bound I set.
4. **`headed2` keeps signature failures below 25%: held**, at 12.1%, against
   32.2% for the same decoding on an unheaded corpus.
5. **Neither arm passes more than 4 tests: held**, at 2 and 3.

Four held, one falsified.

## What moved the number, and what did not

**Head conditioning moved it.** Every training document carrying the signature
its own program declares took signature failures from 40.8% to **12.1%**, and
that converted: 3 answers passed their tests against 2, and all three came out
clean. The mechanism named in round 7's findings was the right one, and round
7b failed to see it only because the answer splitter did not know about the
heads the corpus taught the model to write.

**The specification-checked pool did not move it.** `locallm-r8` trained on a
pool where every example is verified, twin-refuted *and* confirmed to specify
the problem asked, replacing a pool that contained 28 answers which disagree
with theirs. It scored 2 clean, exactly what the same recipe scored before. A
cleaner pool is better practice and it is not, at this size, better data.

**There is a cost to the header.** `headed2` writes 91 well-formed answers
where the unheaded arms write 142 and 149. It throws away far fewer answers on
the signature and produces fewer parseable answers overall, so its gain is
precision, not volume: 3 of 91 pass their tests, 3.3%, against 2 of 149, 1.3%.

## What has not changed

The gap is still problem-solving. `headed2` produced **59 proven-but-wrong**
answers, where all seven verifiers agreed the program meets the specification
the model wrote and the problem's own tests still failed. That is the
population every locallm round is largest in, and no change so far has shrunk
it for the right reason.

## What is next, and it is already running

The obvious arm was not run here: `headed2` used round 7's corpus with heads
added, and `locallm-r8` used the checked pool without heads. **Heads on the
checked pool is the combination neither arm tested.** It is thirty seconds of
training away.

Behind that, the prover is answering the 2,354 training problems nobody had
ever asked it, at about 19 s each. Its predecessor converted 31 of 88 graded
cells into clean answers. If that rate holds anywhere near, the pool this round
argued about stops being the constraint.
