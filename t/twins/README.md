# t twins: verified programs paired with the near-miss that breaks them

426 pairs. Written by `t/twins_artifact.py`; regenerate with `python3 t/twins_artifact.py`
and check an unchanged tree with `--check`.

Each file under `pairs/` holds one pair:

- `program`: a task in t -- a program with its own specification -- that passed the problem's own
  tests and was **verified by all seven** proof systems (Dafny, Verus, SPARK, Frama-C, Lean 4, Rocq,
  F\*).
- `twin`: the same program with one deliberate edit, named in `operator`.
- `witness`: the concrete input at which the twin breaks the specification the program keeps, with
  what each one answers there. `witness_reads` says it in a sentence.
- `twin_refuted_by`: the seven systems that refuted the twin. A pair is written only when both halves
  are on the record -- verified in all seven and refuted in all seven -- so there is no pair here
  resting on a partial column.

## Why this and not a corpus of verified programs

Verified programs are abundant. A verified program *and* a near-miss *and* the input that separates
them *and* seven independent refutations of the near-miss at that input is the part with no
substitute: it is what lets a model be trained, or graded, on the difference between a proof that
holds and one that does not, rather than on proofs alone.

## The operators that made the twins

| operator | pairs |
|---|---|
| `off-by-one` | 99 |
| `off-by-one#1` | 99 |
| `collapse-if` | 62 |
| `negate-cond` | 39 |
| `compare-flip` | 24 |
| `boundary-swap` | 23 |
| `wrong-var` | 21 |
| `wrong-var#1` | 21 |
| `collapse-if#1` | 20 |
| `wrong-constant` | 8 |
| `wrong-constant#1` | 8 |
| `collapse-if#2` | 1 |
| `off-by-one#2` | 1 |

## Provenance

Every pair came from a model's answer to a problem in `nl/`, filtered by the problem's own tests and
by the seven, and recorded by `t/loop_dataset.py`. `written_by` names the answer set. The verdicts
are the same runs `t/AGREEMENT.md` and each set's `kernels.md` record.

## Licence

Research and education only, as the repository's [`LICENSE`](../../LICENSE) states; commercial use,
and training a model on this artifact outside research, need written permission.
