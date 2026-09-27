# dawnr_interp: a sparse-autoencoder feature browser for locallm's core

AMBITION.md's harness table lists interpretability as "planned"; this is the first
piece: a dictionary over one residual-stream layer's activations, a feature browser
so a person can look at what fires, and a first, narrow question -- do any features
separate `t`'s own specifications (`requires`, `ensures`, `invariant`, `decreases`,
`spec`) from repeated boilerplate lines? "What has been measured so far" below has
the first answer, and it is a narrower one than that question: mostly, so far, that
the pipeline runs end to end on a real checkpoint.

## The recipe, and what is not from it

Cunningham, Ewart, Riggs, Huben, Sharkey, "Sparse Autoencoders Find Highly
Interpretable Features in Language Models" (arXiv:2309.08600). One hidden layer,
`code = ReLU(Mx + b)`, tied decoder `x_hat = M^T code`, decoder rows (dictionary
features) held to unit norm, `loss = ||x - x_hat||^2 + alpha * ||code||_1` (their
eq. 1-4). See `sae.py`'s module docstring for the exact correspondence and
`activations.py`'s for the one addition this project needs that the paper does
not: activations are cached only from a corpus's *training* split
(`data.group_split`, the same split a real training run would draw its own
holdout from), never validation text.

Not implemented: their dead-feature resampling procedure. The section of the paper
covering it was not fetched for this module's research-first receipt, so
`sae.dead_features` only counts dead features; it does not resurrect them. Treat
retuning `--l1` and adding resampling as the two open follow-ups, not settled
design choices -- the default is deliberately left low (`1e-3`) rather than copied
from the paper's own alpha, which was tuned for a different model's activation
scale and does not transfer (their footnote around eq. 4; "What has been measured
so far" below is also this module's own confirmation of that).

## Pieces

| file | what |
|---|---|
| `sae.py` | `SparseAutoencoder`, `SAEConfig`, `train_sae`, `dead_features` |
| `activations.py` | `cache_residual_stream` (the hook), `training_split_documents` (the held-out-respecting split) |
| `browser.py` | `feature_browser_markdown`, `top_contexts`, `feature_stats` |
| `spec_probe.py` | the specification-vs-boilerplate question: `label_lines`, `boilerplate_lines`, `feature_label_contrast`, `render_report` |
| `run_sae.py` | the command line that runs all four in sequence |

Tests are flat in `locallm/` (this project's convention for every subpackage, see
`dawnr_harness`'s own tests): `test_dawnr_interp_sae.py`,
`test_dawnr_interp_activations.py`, `test_dawnr_interp_spec_probe.py`,
`test_dawnr_interp_browser.py` test the four pieces each on their own, and
`test_dawnr_interp_run_sae.py` runs the command line itself end to end against a
tiny synthetic checkpoint. All CPU, all seconds; `test_dawnr_interp_sae.py` also
checks the one property this whole recipe exists for -- that training recovers a
small planted dictionary from data generated to need one.

## What has been measured so far (2026-09-27)

A dictionary trained on layer 2 of `t/runs/2026-09-16/filter-loop/clean/r2/model`
(4 layers, 256-wide, the char tokenizer -- the smallest, earliest checkpoint in
`t/runs/`, not the r12 core) over 24,161 cached token positions from 120
training-split documents of the 2026-09-27 proved corpus:

| `--l1` | steps | reconstruction | L0 (of 1024) | dead |
|---|---|---|---|---|
| 0.001 (the default above) | 300 | 109.2 | 318.3 | 0 |
| 0.05 | 300 | 110.2 | 310.9 | 0 |
| 1.0 | 300 | 153.9 | 173.8 | 0 |
| 1.0 | 2000 | 63.2 | 69.0 | 43 |

The jump is between 0.05 and 1.0, not 0.001 and 0.05: this checkpoint's layer-2
activations needed alpha of order 1, not order 1e-3, before the sparsity term
competed with reconstruction at all. On the specification-vs-boilerplate question,
at the last (sparsest) setting: zero features have activation on spec lines
exceeding one standard deviation over their activation on boilerplate lines, one
has it the other way. One feature (dictionary index 800) is qualitatively
suggestive without clearing that quantitative bar -- its five strongest activating
contexts, unedited:

```
34.277    requires index < len(l)
  en<<s>>ures element == l[(index - n
34.238    requires index < len(l)
  en<<s>>ures element == l[(index - n
34.174  (n: int) returns (d: int)
  re<<q>>uires n >= 0
  ensures 0 <= d
34.162  (x: int) returns (y: int)
  re<<q>>uires 10 <= x
  ensures 25 <=
34.147  (n: int) returns (k: int)
  re<<q>>uires n >= 0
  requires n >=
```

Every one lands on a character inside the literal spelling of `requires` or
`ensures`. It still does not cross the 1.0 bar because it also fires on plenty of
ordinary `r`/`s`/`q` characters elsewhere (spec fire rate 62.9%, boilerplate fire
rate 53.8%) -- whether that is "a keyword-spelling feature that also catches other
things" or something less specific is exactly what more data should settle, not
this first pass.

**Read this as exploratory, not a confirmed result, for one specific, named
reason.** This project's own rule (AGENTS.md rule 3; this track's instructions)
is to write a prediction into a dated, committed note before a run gets reported.
That did not happen here: the three smaller `--l1` values above were tried, in
that order, because each one had already been measured not to sparsify the
dictionary, which is a hyperparameter search, not a pre-registered measurement. It
is reported in full instead of only showing the last row, because a repository
that only shows the run it liked is worse than one that shows the search. Before
this means more than "the pipeline runs end to end on a real checkpoint," it
needs: a prediction committed before the run, not folded into the README after
it; more than one checkpoint (and the r12 core specifically, once one exists);
more than 120 of the corpus's 431 documents; and more steps at a fixed alpha,
since L0 and reconstruction were both still moving at step 1999.

Reproduce with this file's own command below, `--max-documents 120 --l1 1.0
--steps 2000`, and the corpus text described above; `run.json` in `--out` records
the exact settings and final metrics of whichever run produced it. The full
feature browser for this run was not committed (5,742 lines); it lives at
`~/scratch/interp/` on the machine that ran it.

## Running it

```sh
python3 locallm/dawnr_interp/run_sae.py \
  --checkpoint t/runs/2026-09-16/filter-loop/clean/r2/model \
  --corpus path/to/a-corpus.txt \
  --out ~/scratch/interp/some-run \
  --l1 1.0 --steps 2000
```

Writes `spec-probe.md`, `feature-browser.md`, `sae.pt` (the trained dictionary and
its config) and `run.json` (the exact settings and final metrics, for reproducing
or citing the run) to `--out`. CPU by default -- the corpora this reads are a few
hundred KB to a few MB of source text, not a pretraining run, and CPU finishes well
inside this project's time budget. A `--device cuda` run must go through the GPU
lock (`run_sae.py`'s own module docstring has the exact command).

`--layer` defaults to the middle of the model; `--l1` (the paper's alpha) and
`--steps` need retuning per checkpoint -- watch the printed `l0` (mean features
active per position) and `dead` (fraction that never fire) columns while it trains.
