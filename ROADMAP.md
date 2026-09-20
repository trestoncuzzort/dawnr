# t and tup: roadmap and engineering log

This is the public record for t and tup: what is planned, what has been measured, what is currently blocking the project, and what is required for the 1.0 release. It merges the overview in `ROADMAP.md` with the dated engineering notes behind it, while omitting personal and machine-specific details.

This is not a diary of individuals or hosts. It records the work itself: the measurements, the bottlenecks, the rules, and the checks a third party can rerun.

## The project in one paragraph

`t` is a small specification language. A program written in it is lowered into seven independent proof systems — Dafny, Verus, SPARK, Frama-C, Lean 4, Rocq, and F* — and every program is paired with a deliberately broken twin that all seven must refute at a concrete input. On top of that sits a data pipeline: a model answers a natural-language problem in `t`, the answer is kept only if it passes the problem's own tests and all seven verify it with the twin refuted, and the surviving answers train a small model. The question is whether a model built from that filtered data does more per parameter than one trained on raw code.

## Rules that matter

1. Measure before you claim. Every number in this repository links to the script that produced it.
2. An honest refusal beats a false verdict. If a lowering cannot express something, it must abstain by name.
3. Write predictions before runs, with the number that would falsify them.
4. Report the failure plainly, then what it bought.
5. No assistant attribution or personal identifiers appear in this record. Commit messages explain what was measured and why.
6. The project is public, and the record avoids personal, institutional, and host-specific identifiers.

## The bar for 1.0

Two halves. Both must hold before the tag.

1. Coverage. At least 82 of the 164 MBPP-DFY programs lift into `t` and read all seven, and a second person reproduces the table from a clean checkout.
2. Usability. A fresh checkout opens a `.t` file in VS Code on Linux and Windows, and in Visual Studio on Windows, with syntax highlighting, errors at the token, hover, go to definition, formatting, and project-wide coverage.

## What is done and what is next

| Workstream | State |
|---|---|
| WS-13 the language | 13.2 and 13.3 done; 13.4 nearly complete; 13.1 open |
| WS-14 the notation | done |
| WS-15 the editors | library, cache and language server done; VS Code built; Visual Studio open |
| WS-16 the claims | 16.1 done; 16.2 partial; 16.3 open |
| WS-17 the release | install pages written for three operating systems; public release path open |
| WS-18 the training loop | measured; the student tied the baseline in some rounds, but the clean count remains below target |
| WS-19 the frontier moves | several moves complete; a model that reads a verifier error remains a candidate |
| WS-20 what caps the corpus | ordered by measured evidence: nested loops, more sources, stronger tests, and the twin artifact |
| WS-21 the parse wall | syntax gate measured as the dominant bottleneck |
| WS-22 beating the baseline | the project target remains a clean win over the fixed Phi-4-mini baseline |

## WS-13: the language

### 13.1 Constructs to the coverage bar

Open. Each construct needed by the corpus is added to the language, given a meaning in every verifier, and checked in the matrix by adversarial reading.

### 13.2 Names in all seven columns

Done. A single renaming pass makes every identifier legal in every verifier.

### 13.3 What a verified twin means

Done. A twin that verifies is refused as decorative. A twin the interpreter refutes but a verifier proves is unsound. A clean result requires both a verified real program and a refuted twin.

### 13.4 The spec freeze and conformance probes

Nearly done. The specification is frozen at a release candidate, and the conformance suite checks the declared verdict per verifier across probe tasks.

## WS-14: from a JSON tree to a language you type

Done. `.t` files are the input; parse and well-formedness errors carry a file, line, column, and rule; the checker is a module; and the language is exposed as user-facing syntax instead of only a JSON tree.

## WS-15: the editors

### 15.1 The harness as a library, with a cache

Done. An unchanged task costs no verifier run.

### 15.2 The language server

Done. Diagnostics, hover, go-to-definition, formatting, and verdict notifications are exposed as a language server.

### 15.3 VS Code

Built, not yet witnessed by a second person from a fresh checkout.

### 15.4 Visual Studio

Open. It reuses the language server and targets Visual Studio 2022.

### 15.5 Verdicts in the editor

Built but not yet fully witnessed: each verifier's real and twin verdict, the twin's operator, and the witness input are shown in-editor.

## WS-16: the claims

### 16.1 The lifter, the sweep, and the spec experiment

Done. The lifter translates programs into `t` and checks each translation by lemma and by a differential run.

### 16.2 MBPP-DFY to half

Open, and the measured count reflects how much of the corpus is now in the fragment rather than how much is left to do.

### 16.3 The next corpora

Open. HumanEval and MBPP bodies from other sources are routed through the same pipeline.

## WS-17: the release

### 17.1 Install stories per operating system

Pages exist for Linux, macOS, and Windows.

### 17.2 The tag

Open. A 1.0 tag must contain the frozen specification, conformance suite, matrix, coverage table, and install pages, all regenerated by a fresh checkout and checked by a second reader.

### 17.3 Going public

The repository is public. It was private while claims were in motion, and this line said so until 2026-09-20; `AGENTS.md` has said "this repository is public" for longer, and the two disagreed in public.

## WS-18: the training loop

A model writes a `t` task from a problem statement; the verifiers grade it; the refuted twin is the bug it trains on. The loop has been built and measured multiple times. The central question remains whether a model trained on this filtered data beats the baseline at equal or lower size.

## WS-19: the frontier moves

Seven moves were chosen from a survey of the field, in the order decided earlier.

1. The grader as the artifact. Done.
2. A model that reads an error through the grader. Blocked on access to a suitable large model.
3. The data multiplier over the verified corpus. Waits on move 2.
4. The bottleneck column on the sweep. Done.
5. The construct line. This is the order of the language expansion.
6. The twin ladder as a completeness measurement. Done.
7. The preregistered reward ablation. Done; it went against the project's own framing and was recorded as a result.

## WS-20: what caps the corpus

Measured on a strong recent run: a substantial fraction of answers pass their tests, but a smaller population is clean in all seven. The abstains point to specific structural limits, and the measurements say the order of the next work.

1. Nested-loop lowering for Lean, Rocq, and F*. Until it exists, the corpus cannot hold a real algorithm: any program with a loop inside a loop, or two loops in a body, abstains in several proof systems and can never be clean.
2. More problem sources. Quicker to improve the ceiling than to augment the fragment. The gate is test reading per source, not a new language feature.
3. Test quality. Differential testing measured where a clean answer still does not say what the original problem asked.
4. The twins and witnesses as a first-class artifact. The project now ships verified programs together with their near-miss twin, witness input, and the seven verdicts.

The key engineering lesson is that a proof result is only useful if it is paired with both a concrete witness and a measured reason it failed.

## WS-21: the parse wall

The syntax gate loses more answers than every other gate together. The measured evidence is clear: the dominant failure mode is not proof difficulty but a model producing replies that are not valid `t`.

The cheap fixes were measured and rejected. A tolerant reader that drops comments or rewrites only a few surface forms rescues a small fraction of refusals. The refusals are structural, not orthographic, so the real fix is in generation.

Training on `t` moves that gate and nothing else. A model trained from random weights on the project's own corpus writes valid `t` much more often, but still struggles with the real problem-solving aspect. This is why the project focuses both on generator-side grammar constraints and on the semantics of answers.

Three moves follow, in this order:

1. A grammar the generator decodes against.
2. Prompt fixes that need no grammar.
3. Whether anything can hold both ends: notation and problem-solving at the same time.

This remains one of the highest-value workstreams because it directly determines whether the data pipeline ever reaches the proof gate.

## WS-22: beating the baseline

The project exists to settle one comparison: a small model trained from filtered verified data against the fixed Phi-4-mini baseline on the held-out 232-problem set. The target is not a tie.

The measured state is that the project has achieved valid `t` output and proof-checked answers in some rounds, but not at the level needed to beat the baseline consistently. The workstream is structured in the order the measurements suggest:

| step | what it does | finish line |
|---|---|---|
| 22.1 | Condition on the signature. | Remove a large class of structurally invalid answers. |
| 22.2 | Grow the pool with the best converter measured. | Add the data source that converts best under the proof gates. |
| 22.3 | Train at a size the data can support. | Train a model sized to the real corpus, not a guessed memory budget. |
| 22.4 | Decode against `t`'s own grammar. | Keep the model from emitting syntax the parser refuses. |
| 22.5 | The win. | The model scores at least 4 clean answers out of 232, beating the fixed baseline. |

The rule is strict: every round registers its predictions before it runs, and the baseline is regraded beside the new model in the same session.

## Closed and kept for the record

- WS-7, the verifier gauntlet. Seven verifiers were installed without root, each with an adapter that reads its verdict honestly.
- WS-8, tup as a virtual machine guest by decision. Bare-metal installation was excluded as a project goal.
- WS-9, going public. Public once, private again while claims were in motion.
- WS-10, the audit's bill. Ground-truth fuzzing, definedness fixes, and the rule that a refutation is minted only on evidence.
- WS-11, a package manager for tup. Proposed and costed, but not built.
- WS-12, the six sessions that paid the bill. The lifter, sweep, spec experiment, and the measured construct order.

## Not on this road

Mechanizing `t`'s core in Rocq or Lean; running the verifiers inside tup; floating point; and an operating system written in t. Each is recorded as direction, not scheduled.

## Decisions taken

- A task whose twin verifies is refused.
- `.t` files are the input and the JSON form is derived.
- The lifter's semantic decisions stand as recorded.
- The project tracks the measured bottleneck and does not claim success on a weaker gate.

## Engineering lessons that survived

1. The bottleneck is often not proof search. It is the path to a valid task and a valid witness.
2. A single bad verdict rule can silently make a whole table wrong. The project now checks numbers against the underlying script and the underlying witness.
3. A twin that does not differ at a concrete witness is not a twin; it is a decorative no-op.
4. A parse failure is not a minor issue. It is a hard cutoff on the training loop.
5. The project is intentionally conservative: an honest abstention is preferred to a false verdict.

## Public-facing summary

The roadmap is simple. The project aims to show that a model trained on proofs and verified examples can outperform a raw-code baseline under the same held-out evaluation. The work is measured, not guessed. The public record continues to track:

- the language and its proof semantics,
- the coverage and agreement tables,
- the training and grading loop,
- the bottleneck signals, and
- the specific next steps that will produce a real win if the hypothesis is correct.

The project does not claim a result until the script, the witnesses, and the verdicts line up.
