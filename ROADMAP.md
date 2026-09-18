# Roadmap

This is the plan for t and tup: what is done, what is next, and what 1.0 means. Every item has a finish line a third person can check. There are no dates. The dated engineering log behind this page, with every measurement and the reasoning, is [`internal/ROADMAP-LOG.md`](internal/ROADMAP-LOG.md); the numbers here are copied from it and from the tables it cites.

Numbers on this page are as of 2026-09-16.

## Words used below

- A **task** is a t program: a typed signature, preconditions, postconditions, loop invariants and a body.
- A **verifier** is one of the seven proof systems that check a task: Dafny, Verus, SPARK, Frama-C, Lean 4, Rocq, F\*. Each has a **lowering**, t's translation into its language.
- The **twin** of a task is a deliberately broken copy. A verifier's cell reads **verified / refuted** when it proves the real task and rejects the twin through a **certificate**, a small proof that the specification fails at a concrete input. **All seven** means every verifier's cell reads that way.
- The **matrix** ([`t/AGREEMENT.md`](t/AGREEMENT.md)) is that table over the 34 committed tasks. The **sweep** ([`t/COVERAGE-lifted-785.md`](t/COVERAGE-lifted-785.md)) is the same table over programs the **lifter** translated into t from **DafnyBench**, 785 Dafny programs; **MBPP-DFY** is its subset of 164 programs written from MBPP problems.
- The **fragment** is the set of constructs t has today. A **census** counts which programs of a corpus fall inside it.

## The bar for 1.0

Two halves. Both must hold before the tag.

1. **Coverage.** At least 82 of the 164 MBPP-DFY programs lift into t and read all seven, and someone other than the author reproduces the table from a clean checkout. Today: 57 of 164 read all seven and 99 of 164 lift ([`t/COVERAGE-mbpp-dfy-lifter.md`](t/COVERAGE-mbpp-dfy-lifter.md)).
2. **Usability.** A fresh checkout opens a `.t` file in VS Code on Linux and Windows, and in Visual Studio on Windows, with syntax highlighting, errors at the token, hover, go to definition, formatting, and the seven verdicts for the real task and its twin with the witness input. The steps are a committed walk-through that a second person has repeated. Today: everything is built for VS Code; no second person has run the walk-through, and the Visual Studio extension is not built.

## Where things stand

| Workstream | State |
|---|---|
| WS-13 the language | 13.2 and 13.3 done; 13.4 at 457 of 462 conformance cells; 13.1 open |
| WS-14 the notation | done |
| WS-15 the editors | library, cache and language server done; VS Code built, walk-through not yet run by a second person; Visual Studio open |
| WS-16 the claims | 16.1 done; 16.2 at 57 of 82; 16.3 open |
| WS-17 the release | install pages written for three operating systems; public since 2026-09-17; second-person clause and the tag open |
| WS-18 the training loop | round 4 measured on 232 held-out problems 2026-09-17: the student ties Phi-4-mini at 3 clean with 1.5B against 3.8B, training on 55 problems moved it none, locallm from scratch went 0 to 2 with 204 proven but wrong; round 5 (the models' own failures on training problems as negatives) is set up |
| WS-19 the frontier moves | moves 1, 4, 6 and 7 done (7 went against the framing, see below); move 2 has a local 27B; move 3 next |
| WS-20 what caps the corpus | chosen 2026-09-17 from the run's abstains: nested-loop lowering for Lean, Rocq and F\*, then more problem sources, then test quality (added after the ablation), then the twins and witnesses as an artifact |

## WS-13: the language

**13.1 Constructs to the coverage bar.** Open. Each construct that DafnyBench or nl/ needs is added to the language, given a meaning in every verifier, and its table reproduced by an adversarial reader before it is claimed. Done when the census over the 164 shows at least 82 inside the fragment and the lifter lifts them. Today 131 of 164 are inside the fragment by census and 99 lift; the difference is lifter rules still to write (function contracts, real numbers, sets, heap use, the remaining array shapes) and verifier gaps on the lifted rows.

**13.2 Names in all seven columns.** Done. A single renaming pass makes every identifier legal in every verifier ([`t/names.py`](t/names.py)).

**13.3 What a verified twin means.** Done. A twin that verifies reads `decorative` beside its real, never as agreement; a twin the interpreter refutes but a verifier proves reads `unsound`, the signal of a verifier bug ([`t/SPEC.md`](t/SPEC.md), "The twins").

**13.4 The spec freeze and the conformance probes.** Nearly done. [`t/SPEC.md`](t/SPEC.md) is frozen at 1.0-rc1. The conformance suite, 66 probe tasks with a declared verdict per verifier, reads 457 of 462 cells ([`t/CONFORMANCE.md`](t/CONFORMANCE.md)). The five open cells are all Frama-C: two are open by design (a bound on an unbounded length), two abstain, one times out. Done when all seven columns pass.

## WS-14: from a JSON tree to a language you type

Done. `.t` files are the input ([`t/tasks/`](t/tasks/)); parse and well-formedness errors carry a file, line, column and the rule they break; the checker is a module ([`t/check_wf.py`](t/check_wf.py)); one command parses, checks, formats, lowers, verifies and explains ([`t/cli.py`](t/cli.py), [`t/COMMAND.md`](t/COMMAND.md)); every code block in the documentation is parsed and checked by a test ([`t/doc_test.py`](t/doc_test.py)).

## WS-15: the editors

**15.1 The harness as a library, with a cache.** Done. An unchanged task costs no verifier run ([`t/tlib.py`](t/tlib.py), [`t/cache.py`](t/cache.py)).

**15.2 The language server.** Done. Diagnostics, hover, definition, formatting and a verdicts notification over standard input and output, standard library only ([`t/lsp.py`](t/lsp.py), [`t/LSP.md`](t/LSP.md)).

**15.3 VS Code.** Built, not yet witnessed. The extension and its walk-through exist ([`t/editors/`](t/editors/)). Done when a second person follows the walk-through from a fresh checkout on Linux and on Windows and sees every behaviour the bar lists.

**15.4 Visual Studio.** Open. Reuses the language server; builds only on Windows with the Visual Studio SDK. Done when the same walk-through holds in Visual Studio 2022 with the five verifiers that run natively on Windows.

**15.5 Verdicts in the editor.** Built, not yet witnessed. Each verifier's real and twin verdict, with the twin's operator and the witness input, shown in the editor.

## WS-16: the claims

**16.1 The lifter, the sweep, the spec experiment.** Done. The lifter translates DafnyBench programs into t and checks each translation by lemma and by a differential run ([`t/LIFTER-DESIGN.md`](t/LIFTER-DESIGN.md), 35 recorded decisions in [`t/LIFTER-DECISIONS.md`](t/LIFTER-DECISIONS.md)). The sweep grades every lifted task in every verifier ([`t/COVERAGE-lifted-785.md`](t/COVERAGE-lifted-785.md)). The spec experiment asks a model to write a t task from a problem statement and grades the answer with all seven verifiers and the problem's tests ([`t/SPEC-EXPERIMENT-mbpp.md`](t/SPEC-EXPERIMENT-mbpp.md)). One script reproduces all three from scratch ([`t/reproduce.sh`](t/reproduce.sh)).

**16.2 MBPP-DFY to half.** Open, at 57 of 82. The count has moved 5, 34, 48, 53, 56, 45, 54, 56, 57, 57 across the sweeps since 2026-09-06 (the wider lifted corpus went 182 to 192 of 326 on the last one); the drop to 45 was the cost of a stricter twin rule (a refuted twin must be a program whose output differs at a verifier-confirmed input), and the rows have been earned back since. What blocks the remaining rows, by name: a membership invariant over a growing sequence that Verus, Lean and F\* do not yet prove; a Frama-C size bound that must come from a loop invariant; a Rocq bound lemma for recursive specification functions; then the lifter rules 13.1 names. The next sweep after each fix says the number.

**16.3 The next corpora.** Open. HumanEval and MBPP bodies from nl/ through the same pipeline. Done when a second coverage table, in the same format, exists over a second corpus.

## WS-17: the release

**17.1 Install stories per operating system.** Pages exist for Linux, macOS and Windows ([`t/RUN-ON-LINUX.md`](t/RUN-ON-LINUX.md), [`t/RUN-ON-MACOS.md`](t/RUN-ON-MACOS.md), [`t/RUN-ON-WINDOWS.md`](t/RUN-ON-WINDOWS.md)); macOS and Windows were measured on real machines. Done when a second person follows each page from a fresh machine to the editor walk-through.

**17.2 The tag.** Open. A 1.0 tag contains the frozen SPEC with its conformance suite, the matrix and the coverage table regenerated from a clean checkout by an adversarial reader, the install pages, the walk-through, the licensing appendix and the two editor extensions, with nothing beyond the Python standard library required. Done when both halves of the bar hold and the tag is cut.

**17.3 Going public.** The repository is private while its claims move. Public again at the tag.

## WS-18: the training loop

A model writes a t task from a problem statement; the verifiers grade it; the refuted twin with its witness input is the bug it trains on. Built and measured twice with a 1.5B model ([`t/LOOP-CURVE.md`](t/LOOP-CURVE.md)): on 161 held-out problems, answers that verify with a refuted twin went from 9 to 15 after two rounds, and the share of answers that fail to parse did not move. Paused until a model that can read a verifier's error is in the loop (WS-19, move 2). The next hurdle is that parse wall, and as of 2026-09-18 it is measured rather than guessed at ([`t/FUNNEL-2026-09-18.md`](t/FUNNEL-2026-09-18.md)): it loses more answers than every other gate together. Of the two ways out named here, the repair pass has since been measured and does not work, so the wall is WS-21.

## WS-19: the frontier moves

Seven moves chosen from a survey of the field ([`t/FRONTIER-2026.md`](t/FRONTIER-2026.md)), in the order decided on 2026-09-10.

1. **The grader as the artifact.** Done. One entry point grades committed tasks or model replies and reproduces the matrix cell for cell ([`t/grade.py`](t/grade.py), [`t/GRADER.md`](t/GRADER.md)).
2. **A model that reads an error through the grader.** Blocked. The script exists ([`t/bedrock_generate.py`](t/bedrock_generate.py)); it waits on API access to a large model.
3. **The data multiplier over the verified corpus.** Waits on move 2.
4. **The bottleneck column on the sweep.** Done. Every table names which verifier alone blocks each row ([`t/blockers.py`](t/blockers.py)); working those rows took one sweep from 60 to 136 of 277 in a night.
5. **The construct line.** The order of 13.1.
6. **The twin ladder as a completeness measurement.** Done ([`t/LADDER-COMPLETENESS.md`](t/LADDER-COMPLETENESS.md)).
7. **The preregistered reward ablation.** Done, 2026-09-17, and it went against the project's own framing. Declared in [`t/PREREG-2026-09-17-ablation.md`](t/PREREG-2026-09-17-ablation.md), measured by [`t/ablation.py`](t/ablation.py), reported in [`t/ABLATION-2026-09-17.md`](t/ABLATION-2026-09-17.md). On answers to training problems one prover admits wrong answers 17.4 percent of the time against 12.9 percent for all seven with the twin refuted, at half the problem coverage, which fails the declared bar of a fivefold reduction. On answers to held-out problems, where the model writes its own specification, every gate admits about 97 percent wrong and the tests catch what no proof gate does. The claim that survives is tests and proofs together. `pool_pick.py --control` now sends failing answers to the checkers as well, so every later round can measure this instead of inferring it.

## WS-20: what caps the corpus, chosen 2026-09-17

Measured on this day's run: 463 answers passed their tests and 96 were clean in all seven; 10 were blocked only
by a lowering that cannot express them; 150 carried at least one abstain. The abstains name their reason, and
the reasons are nested loops (Rocq 37, Lean 37 plus 14 for a second top-level loop, F* 33), a sequence return
whose length no parameter determines (44), and string-library members not lowered yet. Three moves follow from
that, in this order.

1. **Nested-loop lowering for Lean, Rocq and F\*.** Until it exists the corpus cannot hold a real algorithm: any
   program with a loop inside a loop, or two loops in a body, abstains in three of the seven and can never be
   clean. This caps the corpus's worth more than its volume does, which is why it comes first even though only
   10 answers today were blocked by an abstain alone: the 96 clean answers are short and loop-shallow *because*
   nothing else can pass. The work is proof synthesis for nested invariants (an inner loop's invariant under the
   outer one's, and a decreases for each), not a translation gap. Dafny, Verus, SPARK and Frama-C already take
   them, so the measurement to open the move with is how many of the corpus's nested-loop programs those four
   already prove: that is the upper bound the three have to reach.
2. **More problem sources.** Pool v4 is 737 problems (MBPP 649 plus 88 HumanEval whose `check` parses), and
   split-v4 leaves 505 for training. `nl/` already holds 24,748 problems, of which 4,239 are function-shaped and
   772 read as inside t's fragment; APPS and CodeContests are not downloaded on the desktop that runs the loop.
   Admitting the function-shaped ones with parseable input and output raises the ceiling from about 505 training
   problems to thousands. The gate is a test reader per source, not new language features, and the held-out
   split must stay exactly split-v3's 232 MBPP problems so every earlier number keeps its meaning.
3. **Test quality, added 2026-09-18 after the ablation.** The ablation measured every proof gate admitting about
   97 percent wrong answers on held-out problems, where the model writes its own specification, and the tests
   catching what no proof gate did. The tests are therefore on the critical path and they are thin: MBPP gives
   about three assertions a problem. The move is to strengthen the one gate that demonstrably works: property
   checks over the specification's own preconditions, and differential testing of each accepted answer against
   the problem's reference solution on random inputs inside the precondition. The measurement that opens it is
   how many currently clean answers a differential check refutes; anything it refutes was a false accept that
   the seven provers and the twin rule both missed.
4. **The twins and witnesses as a first-class artifact.** Every clean task carries a deliberately broken copy and
   a concrete input at which the copy breaks its own specification, refuted by all seven. Nobody else ships that:
   a pile of verified programs can be had from any corpus, but a program *paired with a near-miss and the input
   that separates them, with seven independent refutations on record*, is the part with no substitute. Today it is
   a by-product inside `kernels.md` and the loop's pair files. It becomes an artifact: one file per task with the
   real program, the twin, the operator that made it, the witness, and the seven verdicts, with its own README,
   count and licence line, published and versioned like `AGREEMENT.md`.

## WS-21: the parse wall, chosen 2026-09-18

[`t/funnel.py`](t/funnel.py) walked 14,130 replies from every model this project has run, through each gate an
answer must pass before it can become a training example. The numbers decide the order of what follows.

| models | replies | parse | well formed | tests pass |
|---|---|---|---|---|
| stock, prompted | 13,434 | 38% | 23% | 17% |
| the fine-tuned student | 232 | 32% | 16% | 5% |
| locallm, trained on t from scratch | 464 | 98% | 88% | <1% |

Two findings, and the second is the uncomfortable one.

**The syntax gate loses more answers than every other gate together.** Sixty-two percent of a prompted stock
model's replies never reach a proof system at all, because they are not t. The provers are not the bottleneck
and never were; the notation is. The tokens the parser found where it wanted something else say the same thing
plainly: `spec` (a spec function written after the task rather than before it), `if` and `forall` in expression
positions the grammar does not allow, and `^`, `|`, `&`, `?`, `/` -- operators t does not have.

**Training on t moves that gate and nothing else.** locallm, built from random numbers on t's own corpus, writes
t the parser accepts 98 percent of the time, and 2 of its 464 answers pass the problem's own tests. It has the
notation and not the problem. The fine-tuned student parses 32 percent, which is where the untrained 1.5B
already was, so its QLoRA and DPO rounds moved neither end. A round that adds more answers of the same kind
will not change any of these three rows, which is why round 4 tied Phi-4-mini at 3 of 232 instead of beating it.

Three moves follow, in this order.

1. **A grammar the generator decodes against.** The lab workstation's vLLM (0.29, xgrammar 0.2.6) accepts a
   grammar per request (`structured_outputs.grammar`), so a model can be made unable to emit anything the
   parser would refuse. The work is a GBNF for t's surface syntax, and the test that it is the *same* language
   is mechanical: every committed task and every answer that parses today must be accepted by the grammar, and
   nothing the parser refuses may be. The prize is the 62 percent, but only if constraining a model does not
   simply turn it into locallm -- syntactically perfect and semantically empty -- which is exactly what the
   measurement below is for, and why the number that decides this is the clean count and not the parse rate.
   Preregistered in [`t/PREREG-2026-09-18-constrained.md`](t/PREREG-2026-09-18-constrained.md).
2. **The prompt fixes that need no grammar.** Three of the four most common refusals are orthography, not
   ability: spec functions written after the task, chained comparisons, and `/` for integer division. If a
   prompt change moves the parse rate on a held-out sample, it costs one generation run and is worth having
   whether or not move 1 lands. Measured the same way, against the same sample.
3. **Whether anything can hold both ends.** The gap between locallm's row and the stock row is the whole
   distance to a higher clean count: one model has the notation, the others have the problem, and no model here
   has both. Once move 1 removes the syntax gate, the question is answered directly -- a constrained stock model
   has locallm's notation by construction, so its test-pass rate is the first honest measurement of whether the
   semantics were ever the limit. If it is, the pool's job changes from teaching syntax to teaching proof, and
   [`t/loop_train.py`](t/loop_train.py)'s objective changes with it.

## Closed and kept for the record

- **WS-7, the verifier gauntlet.** Seven verifiers installed without root, each with an adapter that reads its verdict honestly ([`t/WITNESS-2026-08-31-dell.md`](t/WITNESS-2026-08-31-dell.md)). Three adversarial campaigns against t's own instruments followed and produced WS-10.
- **WS-8, tup is a virtual machine guest by decision.** Bare-metal installation is deleted scope. tup 0.1 boots to a login prompt on three hosts ([`tup/receipts/`](tup/receipts/)); the x86_64 build is scripted and waits on a virtualization group membership ([`tup/X86-FEASIBILITY.md`](tup/X86-FEASIBILITY.md)).
- **WS-9, going public.** Public once on 2026-08-31, private again while claims move.
- **WS-10, the audit's bill.** Ground-truth fuzzing (1,009 tasks, 7,063 cells, no error shared by all seven); a Frama-C definedness hole fixed in the lowering; the rule that a refutation is minted only from a proof the verifier accepts, never from a failure to prove ([`t/WITNESS-2026-09-02-refuted-purge.md`](t/WITNESS-2026-09-02-refuted-purge.md), [`t/WITNESS-2026-09-02-dafny-door.md`](t/WITNESS-2026-09-02-dafny-door.md)); the loop frame rule pinned in SPEC. Still open from it: the seven verifiers run on the host, not inside tup (10.5).
- **WS-11, a package manager for tup.** Proposed and costed, nothing built: every variant would be built twice, raw and managed, and the file-level difference published as the receipt.
- **WS-12, the six sessions that paid the bill.** The lifter, the sweep, the spec experiment, and the constructs that DafnyBench and nl/ asked for, in the order the censuses ranked them: integer division and modulus, early return, sequences as values, break, sequence literals with concatenation and slices, strings as sequences of code points, pairs, nested sequences, and a seventeen-member string library. Each is in SPEC with a meaning per verifier and lowered in all seven; the adversarial reproduction of each flip table is still owed.

## Not on this road

Mechanizing t's core in Rocq or Lean; running the verifiers inside tup; floating point; an operating system written in t. Each is recorded as direction, not scheduled.

## Decisions taken

A task whose twin verifies is refused. `.t` files are the input and the JSON form is derived. The lifter's 35 semantic decisions stand as recorded. Visual Studio 2022 is the target, built on a Windows machine. No editors beyond the two for 1.0. Public at the tag.
