# dawnr

dawnr combines local language models, program verification, and an assistant that works with code and documents.
It generates candidate programs, tests their behavior and specifications, checks them with proof tools, and uses
accepted results to build training data. The trained models can then propose new programs through the same checks.

The repository contains both the system and its working record: programs, contracts, deliberately broken variants,
counterexamples, datasets, model-training code, evaluation scripts, and measured results. Its applications include
checking selected PX4 flight-software routines against compiled C++ and recording proposed fixes alongside the
inputs that expose the original failures.

## What is implemented

| Part | What it does | Implementation |
|---|---|---|
| Program verification | Parses and checks `t` programs, translates them into proof-system inputs, and tests each verifier against a deliberately broken variant. | [`t/`](t/README.md), [`t/run_par.py`](t/run_par.py) |
| Specification checks | Checks contracts against examples and reference behavior; mutates programs and outputs to find wrong results a contract still allows. | [`t/spec_gate.py`](t/spec_gate.py), [`t/spec_check.py`](t/spec_check.py), [`t/audit.py`](t/audit.py) |
| Executable comparisons | Compiles generated C or Dafny/Python and compares it with the interpreter. Separately checks C contracts and overflow obligations at machine width. | [`t/build.py`](t/build.py), [`t/ship.py`](t/ship.py) |
| PX4 checks | Models selected routines, records failing inputs and fixes, and compares the models with PX4's compiled functions or extracted statements. | [`t/flight/`](t/flight/README.md) |
| Training and evaluation | Filters generated answers, assembles corpora, trains or fine-tunes models, and evaluates them with recorded splits, input hashes, and per-stage results. | [`t/student_rows.py`](t/student_rows.py), [`locallm/dawnr_pipeline.py`](locallm/dawnr_pipeline.py), [`locallm/dawnr_report.py`](locallm/dawnr_report.py) |
| Local assistant | Reads files, proposes edits, journals changes, runs sandboxed commands, and uses retrieval, memory, and external tools. | [`locallm/dawnr_cli.py`](locallm/dawnr_cli.py), [`locallm/dawnr_agent/`](locallm/dawnr_agent/), [`locallm/dawnr_harness/`](locallm/dawnr_harness/) |
| Documents and arithmetic | Answers with quotations from supplied files, extracts fields from source text, and compares a model's numerical answer with separately generated workings evaluated exactly. | [`locallm/cite_docs.py`](locallm/cite_docs.py), [`locallm/extract_docs.py`](locallm/extract_docs.py), [`locallm/calc.py`](locallm/calc.py) |

The [`dawnr` command](bin/dawnr) exposes the assistant and its checks in a terminal. A local browser interface,
HTTP job API, and MCP server expose them to other clients. The [command reference](docs/COMMANDS.md) describes
the individual entry points.

## How code is checked

The verification language is **`t`**. A task states its inputs, preconditions (`requires`), postconditions
(`ensures`), implementation, and any loop invariants. Its engine supports **Dafny, Verus, SPARK, Frama-C,
Lean 4, Rocq, and F\***. Several front ends share underlying solvers; the reports identify the tools and versions
that actually ran.

For a question with examples, [`dawnr ask`](t/answer.py) runs this sequence:

1. Generate candidate `t` programs and reject ones that fail parsing, well-formedness checks, or the supplied tests.
2. Generate a separate Python solution and test it in a sandbox.
3. Check whether the candidate's specification agrees with that solution on sampled inputs and rejects mutated outputs.
4. Run available provers on the surviving program and a deliberately broken variant, with a concrete input that
   distinguishes the two. Report refutations, missing tools, unsupported constructs, and timeouts.
5. Translate an accepted program to Python and compare the translation with the `t` interpreter before returning it.

Other entry points reuse these components. [`dawnr prove`](t/prove.py) starts from a supplied specification;
[`dawnr verify`](t/verify_py.py) uses an existing Python function as the behavioral reference.
[`dawnr check`](t/certificate.py) replays a saved certificate's hashes, tests, prover checks, and executable
comparisons without asking a model to regenerate the answer.

A proof establishes a property of the `t` program under its stated assumptions. The Python translation and PX4
correspondence are checked on bounded inputs. Specification checks can expose a mismatch with the intended
behavior, but they cannot establish that the specification captures everything the user meant. These distinctions
are part of the reported result.

The installed `dawnr` proof commands default to a minimum of **one** prover. An all-seven result must show seven
successful program checks and seven refuted variants. The current engine pin is in [`t/ENGINE.md`](t/ENGINE.md);
engine development lives in [t-proof-engine](https://github.com/trestoncuzzort/t-proof-engine).

## PX4 work in this repository

[`t/flight/`](t/flight/README.md) contains models of math helpers, filters, hysteresis, ring-buffer operations,
collision-prevention indexing, and message-handler behavior. Findings include the failing contract and a concrete
input; proposed fixes have separate tasks so the original and corrected behavior can be checked side by side.

Examples from the recorded, pinned PX4 revisions:

| Case | Original behavior at the recorded input | Evidence |
|---|---|---|
| Obstacle-bin wrapping | Bin `-73` with 72 bins returns `-1`, outside the valid index range. | [Compiled-function comparison](t/PX4-DIFF.md) |
| SUMD channel decoding | A valid 32-channel frame reaches index 64 of a 64-byte buffer. | [Finding and concrete input](t/FLIGHT-FINDINGS-REAL.md) |
| Arming parameter conversion | Parameter `257` narrows to the arm action. The proposed fix rejects it. | [Original and fixed statements](t/PX4-STMT.md) |
| MAVLink serial control | A count of 71 exceeds the message's 70-byte data field. The proposed fix rejects that count. | [Original and fixed statements](t/PX4-STMT.md) |

[`px4_diff.py`](t/flight/px4_diff.py) compiles PX4's own routines and compares their outputs with the `t` models.
[`px4_stmt.py`](t/flight/px4_stmt.py) compiles selected handler statements from original and proposed-fix revisions,
with stand-ins for surrounding types and services. Each record names its revision, inputs, and comparison scope.

These checks cover the modeled routines and extracted statements. They do not establish correctness of the
complete autopilot or behavior in flight. The numeric model also matters: many floating-point comparisons use
binary64, while PX4 commonly uses binary32. The [flight notes](t/flight/README.md) document those boundaries.

## The data and model pipeline

Programs that pass checks feed corpus builders and training runs. Rejected programs, counterexamples, and verifier
feedback are also used to construct and evaluate repair tasks. Held-out problems,
contamination checks, and specification checks determine what a reported model result counts.

The resumable [`dawnr_pipeline.py`](locallm/dawnr_pipeline.py) driver covers tokenization, base training or an
existing checkpoint, conversation construction, mid-training, optional supervised fine-tuning, evaluation, and
reporting. Stage records contain input hashes and parameters; changed inputs invalidate downstream work. Its
chat reinforcement-learning stage currently records a skip. Other experiments have their own drivers and records.

The installer supplies the **student-v5** fine-tuned Qwen3.5-4B for program generation and a quantized base
Qwen3.5-4B for the assistant and reference answers, served locally through llama.cpp. The repository also contains
training code for models initialized from random weights. These are separate experimental paths; the installed
model is described in the [model card](release/MODEL-CARD-student-v5.md).

Results and corrections are kept in [SCOREBOARD.md](SCOREBOARD.md), [docs/MEASURED.md](docs/MEASURED.md),
[CORRECTIONS.md](CORRECTIONS.md), and the linked experiment records. They describe particular runs and populations.
Large weights and many generated run artifacts are downloaded or produced separately from a source checkout.

## Install and use

The application supports Linux, macOS, and Windows through WSL2, with Python 3.10 or newer. CPU inference is
supported. The installer downloads the model server and models, checks their published checksums, installs Dafny
where supported, and adds `dawnr` to `~/.local/bin`. Other proof backends have separate setup instructions in
[`t/README.md`](t/README.md).

```bash
git clone https://github.com/trestoncuzzort/dawnr
cd dawnr
./install.sh
dawnr doctor
```

On a fresh Ubuntu installation, the installer may require `libgomp1`, `unzip`, and `bubblewrap`. Commands that
execute generated Python require a working sandbox. See the [installation guide](docs/USER-GUIDE.md) for setup,
model storage, and platform-specific requirements.

```bash
# Generate a checked function and save its replayable record.
dawnr ask "Write a function that returns the larger of two integers." \
  --test "assert larger(3, 5) == 5" --test "assert larger(9, 2) == 9" \
  --save-python larger.py --certificate larger.cert.json
dawnr check larger.cert.json

# Work with a folder or ask a question about a document.
dawnr do "Describe the modules in this repository." --read-only
dawnr cite "What assumptions does this check make?" t/flight/README.md
dawnr calc "A logger records 12 samples per second for 15 seconds. How many samples is that?"
```

The assistant defaults to local models and offline operation. Its file tools support reviewed edit plans and a
change journal; `/undo` restores recorded changes. Shell commands run in a sandbox over a copy of the workspace. `--online`
enables the assistant's network tools, and `DAWNR_WRITER_URL` can select an external model for program generation.
Those options change what stays local. See [PRIVACY.md](PRIVACY.md) and [DAWNR-AGENT.md](DAWNR-AGENT.md).

## Run existing verification tasks without a model

The parser, interpreter, and mutation audit can run directly from the source checkout. Formal checks need the
selected prover installed and on `PATH`; compiled comparisons also need the relevant compiler.

```bash
python3 t/cli.py check t/flight/fixes/px4_wrap_bin_fixed_72.t
python3 t/cli.py audit t/flight/fixes/px4_wrap_bin_fixed_72.t --json

# A proof and its deliberately broken variant, using Dafny.
T_MIN_KERNELS=1 python3 t/cli.py verify \
  t/flight/fixes/px4_wrap_bin_fixed_72.t --kernels dafny --json

# Refute the original contract at a recorded failing input.
python3 t/refute_at.py t/flight/findings/px4_wrap_bin_any.t \
  --at '{"bin": -73, "bin_count": 72}' --kernels dafny --json

# Compile and compare the pinned PX4 routines; fetches source when absent.
python3 t/flight/px4_diff.py --table /tmp/dawnr-px4-diff.md
```

The engine CLI also exposes lowering, contract repair, compiled-output comparisons, and machine-width checks:
`python3 t/cli.py --help`. Reports and certificates retain the scope of the checks that ran; an unavailable or
unfinished check does not count as a pass.

## Repository map

| Path | Contents |
|---|---|
| [`bin/dawnr`](bin/dawnr), [`install.sh`](install.sh) | Application launcher, local model serving, and installation. |
| [`t/`](t/README.md) | Pinned proof engine plus dawnr's generation, data-filtering, and evaluation scripts. |
| [`t/flight/`](t/flight/README.md) | PX4 models, findings, proposed fixes, and source-comparison harnesses. |
| [`locallm/`](locallm/) | Model and training code, the assistant, document tools, retrieval, memory, and evaluations. |
| [`nl/`](nl/README.md) | Programming-problem datasets and their preparation records. |
| [`release/`](release/) | Model cards and release documentation. |
| [`docs/`](docs/) | Command reference, user guide, and measurements. |
| [`internal/`](internal/) | Research notes, design records, and historical handoffs. |

For development, see [CONTRIBUTING.md](CONTRIBUTING.md). For recorded limitations and reporting defects, see
[LIMITS.md](LIMITS.md), [DISCLAIMERS.md](DISCLAIMERS.md), and [SECURITY.md](SECURITY.md).

## License

Research and education use only; see [LICENSE](LICENSE) and [DISCLAIMERS.md](DISCLAIMERS.md).

Copyright (c) 2026 Treston Malachi Cuzzort.
