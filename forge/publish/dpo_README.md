# A self-rewarding DPO pipeline with an executable reward

The model proposes solutions. **Unit tests decide.** Preferences are learned from the
verdict, never from another model's opinion.

This is the training half of a local-LLM loop: it generates candidate solutions to
coding tasks, runs them against hidden tests in an isolated subprocess, and emits
`(prompt, chosen, rejected)` preference pairs only where a real correctness gap
exists. The reward signal is an exit code, not a judgement.

## Why not use a bigger model as the judge

Because an LLM judge can be talked out of its verdict, and a model being trained
against one learns to talk it out of its verdict. A unit test has no opinion to
change. The trade is that the reward only covers what the tests cover — which is a
real limitation, stated here rather than hidden.

## The loop

```
forge.py                                  train_native.py
--------                                  ---------------
actor    -> K candidate solutions
verify   -> hidden unit tests = reward --> DPO+NLL on (prompt, chosen, rejected)
pair     -> chosen vs rejected         --> LoRA adapter
failures -> failures.jsonl                     |
    ^                                          v
    +---------- better actor <---- export_adapter.py -> Ollama ADAPTER
```

`failures.jsonl` is the interesting output: tasks *no* candidate could solve. Those
are the curriculum for the next round.

## What makes the data trustworthy

**Isolated execution.** Candidates run in a `python -I` subprocess under an 8-second
timeout with a coarse banned-operation filter (`forge.py`). This is defense in depth,
**not a sandbox** — for untrusted or large runs, use a container or a throwaway VM.

**Return types are checked, so `==` cannot be faked.** Every test compares with
`==`, and `==` is a method the solution controls: a class whose `__eq__` returns
`True` passed every assertion in a task before this was fixed. The harness now wraps
the entry point once and requires the return value to be built from plain builtins,
checked by exact type (`isinstance` is not enough — a `str` subclass with a custom
`__eq__` passes it). Both exploits are refused; honest solutions are unaffected, and
re-verifying all 1,279 existing pairs under the stricter rule produced 0 violations.

**A correctness gap, or no pair at all.** A pair is emitted only when `chosen` passes
every assertion and `rejected` demonstrably fails. Preferring the *shorter* of two
passing solutions is a length-bias reward hack, so that pair type is disabled
(`EMIT_CONCISENESS = False`).

**A gate training cannot skip.** `verify_dataset.py` re-executes both sides of every
pair — `chosen` must still pass, `rejected` must still fail — then writes a receipt
recording the sha256 of each verified file. Both trainers refuse to start unless a
receipt covers their exact input bytes with zero violations (`dataset_gate.py`). Edit
a dataset and the hash stops matching, so training halts until it is re-verified.
There is no bypass flag.

**The receipt pins the verifier, and the Python interpreter, not just the data.**
"0 violations" is a statement about specific code executed by a specific Python,
so the receipt records the sha256 of `forge.py` *and* the interpreter version, and
the gate refuses if either has changed since. This is not hypothetical: `verify()`
used to launch candidates with `sys.executable`, which meant ground truth depended
on which script happened to call it. Replaying 310 identical completions under two
interpreters scored 172/310 on 3.14 against 154/310 on 3.11 — 18 disagreements,
every one in the same direction. (Those counts come from a local replay whose
completions are not published, so treat them as illustration, not evidence.) **The
mechanism, unlike the counts, you can check in ten seconds**, and it is the part
that matters — [PEP 649](https://peps.python.org/pep-0649/) defers annotation
evaluation:

```bash
python -c "def f(x: List[int]) -> Tuple[int,int]: return (1,2)"
# Python <=3.13 -> NameError: name 'List' is not defined
# Python 3.14   -> exits 0
```

So `def f(x: List[int])` without `from typing import List` fails on 3.11 and runs
fine on 3.14, and any verifier that inherits its interpreter silently changes what
"correct" means. The interpreter is now
resolved in one place and recorded in every receipt. Re-verifying all 1,279 pairs
under the pinned interpreter still gives 0 violations, so the stricter reading cost
this dataset nothing.

Latest gate run: **1,279 unique pairs, 0 violations**, covering 2,200 rows across
`dpo_pairs.jsonl` (1,244), `dpo_pairs_capped.jsonl` (918 — the training file) and
`repair_pairs.jsonl` (38). Unique is below the row total because 3 pairs appear in
two files. All of it is in `data/`, so you can re-run the gate yourself.

## Honest status

**The pipeline runs end to end. It has not produced a result.**

Training has been executed once, on a small stand-in model
(`Qwen/Qwen2.5-0.5B-Instruct`, 10 optimizer steps), purely to prove the path works.
No run on a full-size base, no held-out evaluation, and **no claim that any of this
improves a model.**

What that smoke test did establish is narrow and real. TRL adds its NLL term only
when `rpo_alpha` is set, so "is this actually DPO+NLL or silently plain DPO?" is
answered by whether `nll_loss` appears in the metrics:

| `rpo_alpha` | `loss` | `nll_loss` |
|---|---|---|
| `1.0` | 1.0959 | **0.4036** |
| unset | 0.6914 | *absent* |

`0.6914 + 0.4036 = 1.0950` against an observed `1.0959` — the NLL term is added
exactly as documented. Recorded in `data/smoke_rpo_alpha_result.json`.

The export path is verified too (`data/export_acceptance_result.json`): conversion
tensor counts match, the adapted model and a null baseline both build, and — the
check that matters — scaling the LoRA `B` matrices by 50,000x collapses output into
gibberish. That is what proves Ollama is genuinely applying the adapter rather than
parsing the instruction and ignoring it. An adapter that is silently dropped passes
every other check.

## What an efficacy claim would require

None of this has been done, and the numbers below are why it is not a formality:

- a preregistration signed **before** the run;
- `eval.py`'s frozen held-out set scored before and after (it is disjoint from the
  training tasks by design — that is what makes it a ruler);
- a null baseline: the same Modelfile with the `ADAPTER` line removed, so "the
  adapter did something" is not confounded with "the export did something";
- k>=5 seeds, with test-retest variance reported separately from between-config
  variance.

> **The figures in the next two paragraphs are NOT reproducible from this repo.**
> They come from `data/eval_history.jsonl`, a local run log that is not published,
> so you cannot re-derive them the way you can re-run the gate. They are reported
> here because leaving them out would flatter the project, and you are being asked
> to take them on trust — which is exactly the thing every other number on this
> page does not ask of you. `python verify_claims.py` checks the claims that CAN
> be settled from the shipped artifacts and says plainly that these cannot.

**The ruler is currently saturated, and this is the binding constraint.** Across 57
logged runs of the identical configuration, 6 of the 10 held-out tasks scored a
perfect 1.000 every single time (`gcd`, `is_prime`, `reverse_words`, `flatten`,
`count_vowels`, `dedup`) and pass@3 took the value 0.90 in 55 of 57 runs. A task
that never varies contributes no information, so most of the instrument is inert.

The measured cross-run standard deviation of pass@1 is **0.0199** over those 57
runs — not the ~0.009 a 3-run sample suggested. That puts the honest 95% bar for a
single-run-vs-single-run comparison at **±0.055** (0.0199 x sqrt(2) x 1.96), and
total headroom to the ceiling is only 0.1221, most of which is one broken task
(`rotate` fails on the empty list). A pass@k moving from 0.42 to 0.44 would prove
nothing; so would most movements this instrument can currently produce.

`eval.py`'s docstring also concedes that its task shapes may overlap a base model's
pretraining, so absolute pass@k partly measures recall. It is a *relative*
instrument — iteration N against iteration 0 on a frozen set. It cannot support a
claim like "the model is 12% better at coding."

## Running it

```bash
python forge.py              # generate + verify pairs   (needs Ollama + a model)
python verify_dataset.py     # the gate; required before training
python build_training_set.py # the stratified, capped training file
python train_native.py       # QLoRA DPO+NLL            (needs a CUDA venv)
python export_adapter.py --adapter <dir> --base-tag <ollama tag> \
                         --name <new model> --verify
python eval.py               # score any Ollama model on the frozen set
```

Generation needs only `requests` plus a running Ollama. Training needs a separate
Python 3.10-3.12 environment with CUDA torch; see the header of `train_native.py`.
Export needs llama.cpp's `convert_lora_to_gguf.py` — set `SRLM_LLAMA_CPP` if it is
not at the default path.

Model choice is not hardcoded: `config.py` resolves an Ollama tag and a Hugging Face
base from `SRLM_MODEL` / `SRLM_HF_BASE`, with per-architecture LoRA targets.

## What runs from this checkout, what doesn't

This checkout is a **data + verification** artifact. `python verify_claims.py` and
the shipped datasets (`dpo_pairs.jsonl`, `dpo_pairs_capped.jsonl`,
`repair_pairs.jsonl`) work as published. The generation entry point
(`forge.py --tasks pool`) and the training gate's fingerprint (`verify_dataset.py`,
via `dataset_gate.py`) both require private task sources that are not published
here — regenerating them locally (screening your own candidate tasks) is required
first. This is a scoping fact about what ships, not a bug introduced by this
checkout's structure.

## Known limitations

- The banned-operation filter is a regex, not a sandbox, and it is **not
  exhaustive**: `from subprocess import run`, `import pathlib`, `import importlib`,
  `import pickle` and others pass it. `python -I` isolates from the user environment;
  it does **not** restrict the filesystem or network. Treat generated code as
  untrusted and run it in a container or throwaway VM at any real scale.
- `-I` is load-bearing for a second, non-obvious reason: it implies `-E`, which
  discards `PYTHONOPTIMIZE`. With `PYTHONOPTIMIZE=1` the interpreter strips every
  `assert` and a wrong answer would print `__PASS__` and exit 0. Do not remove it.
- The reward covers only what the hidden tests cover.
- Tasks are pure-function coding problems on purpose — objective reward, small blast
  radius. Keep new tasks that shape and the loop stays sound.
- 3 pairs appear in both `dpo_pairs.jsonl` and `repair_pairs.jsonl`, so they are seen
  twice per epoch under `--include-repair`. The default configuration is unaffected.
- The dataset receipt is unsigned. It defends against drift and accident, not against
  someone editing the receipt itself.

## License

Research use only, see [../LICENSE](../LICENSE). Copyright (c) 2026 Treston Malachi Cuzzort.
