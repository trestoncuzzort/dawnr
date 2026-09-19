# The longer source-pretraining study: the architecture advantage reversed

Six arms, three seeds, 4000 updates each, 65,536 tokens per update
(262,144,000 tokens per arm), identical frozen corpus
(`source-corpus-2026-09-19-v2`) and tokenizer
(`source-tokenizer-2026-09-19-v2`), modern then GPT within each seed.
Output `t/out/source-pretraining-longer-2026-09-19`; the machine-checked tables
are `summary-4000.json` and `summary-4000.md` beside it, written by
`locallm/summarize_pretraining.py --steps 4000`. Predictions were registered in
[PREREG-source-longer-2026-09-19.md](PREREG-source-longer-2026-09-19.md) before
the run. The live integrity probe reported no issues at any check, and the
final probe reports six of six arms complete at step 4000.

## What was measured

| seed | core | initial val | final val | drop | wall s | peak GiB |
|---|---|---:|---:|---:|---:|---:|
| 1337 | modern | 9.1584 | 1.3611 | 85.14% | 1141.9 | 11.02 |
| 1337 | gpt | 9.1768 | 1.2676 | 86.19% | 961.4 | 8.27 |
| 7 | modern | 9.1554 | 1.3388 | 85.38% | 1140.4 | 11.02 |
| 7 | gpt | 9.1648 | 1.2641 | 86.21% | 961.5 | 8.27 |
| 42 | modern | 9.1737 | 1.3691 | 85.08% | 1141.5 | 11.02 |
| 42 | gpt | 9.1399 | 1.2824 | 85.97% | 961.7 | 8.27 |

Parameters: modern 91,245,312; GPT 92,920,320.

## The three registered predictions

1. **All updates remain finite.** Held. Six arms of 4000 updates completed with
   no non-finite loss and no integrity issue.
2. **Each modern endpoint improves on its own 1000-step seed by at least 10%
   relative.** Held, with room: 2.5105 to 1.3611 (-45.8%), 2.4570 to 1.3388
   (-45.5%), 2.4315 to 1.3691 (-43.7%).
3. **Modern keeps at least a 3% relative advantage over the matched GPT control
   at every seed.** **Falsified, and in the opposite direction.** Modern is
   7.38%, 5.91% and 6.76% *worse* than its paired GPT control at seeds 1337, 7
   and 42. The prediction fails at every seed, not at one.

## What reversed, and by how much

At 1000 updates the modern core led by roughly a quarter: 2.5105 against
3.3274, 2.4570 against 3.3477, 2.4315 against 3.4103, a 24.6%, 26.6% and 28.7%
relative advantage. Over the same corpus at four times the budget the GPT
control fell 61.9%, 62.2% and 62.4% while the modern core fell only 45.8%,
45.5% and 43.7%, and the ordering flipped at every seed. The advantage this
project measured at 1000 updates was an advantage at 1000 updates, not an
advantage of the architecture.

The cost runs the same way. The modern arm takes 1141 s against 961 s for the
same number of updates and the same tokens, 18.8% more wall time, and reserves
11.02 GiB against 8.27 GiB. At this budget the modern core is behind on loss,
behind on time and behind on memory.

## What the models actually write

`locallm/sample_source_study.py` wrote `completions-4000.json`: four fixed
post-hoc category prompts, greedy, 96 new tokens, all six arms. They remain
repetitive at 4000 updates. The modern seed-1337 Python completion restates
`if len(values) > 0: return 0` six times; its GPT counterpart restates a
`_count_positive` stub that returns its argument four times; the Rust arms
repeat `#[cfg_attr(f128_enabled)]` and a counter loop that counts nothing. A
45% cut in token loss did not buy a usable completion, from either core.

This is the second time in two days that a loss result and a behaviour result
have disagreed here, and it is the reason the next experiment is scored by
executing programs rather than by nats per token.

## What this buys

- The architecture question is decided *at this scale and budget* and it is
  decided against the modern core: do not spend the next run on it, and do not
  quote the 1000-step advantage again without the 4000-step reversal beside it.
- Both cores are trained far enough to be reasonable initializations; the six
  checkpoints are retained, and the factorial described in
  [DESIGN-latent-execution-2026-09-19.md](DESIGN-latent-execution-2026-09-19.md)
  initializes from the three modern 4000-step seeds as its design specifies.
  That design was fixed before this result. The initialization it names is now
  known to be the weaker of the two cores at this budget, which matters for any
  absolute number taken from the factorial and not for its paired contrasts;
  repeating the factorial from the GPT checkpoints is a separate follow-up.
- Nothing here is an executable-correctness, proof or Phi result. Token loss on
  a fixed validation window is all that was measured.
