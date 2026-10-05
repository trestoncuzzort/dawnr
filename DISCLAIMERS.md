# Disclaimers and current state

dawnr is research software. Read this before relying on anything it does.

## Use and licence

- **Research and education use only.** See [LICENSE](LICENSE). Third-party material keeps its own licence
  ([NOTICE](NOTICE)); the problem corpora's licences are documented under `nl/`.
- **The published model is dawnr v5** (released as `student-v5`; dawnr is the models' name from now on). It (Apache-2.0) is the 4B trained on v3's rows plus 1,068 rows from
  documents the provers admitted since, some written by two openly licensed teacher models on Amazon Bedrock. **Corrected
  2026-10-05:** it was published as holding no row from GPL-licensed programs, and 61 of its 5,095 rows descend from
  MBPP-DFY (GPL-3.0 at the source) under a second benchmark's names; `student-v1` holds 48 of 3,835
  ([the audit](t/DECONTAMINATION-2026-10-05.md)). The next release is trained without them. At 8 bits it proves 27 of 33 held-out given specifications by all seven provers (v1 26); 19 of those 33 have a
  program of the same behaviour in the training rows under another name, and on the 14 that do not it proves 10. Where every training row comes from, and under what licence, is in
  [internal/RELEASE-PROVENANCE-2026-10-01.md](internal/RELEASE-PROVENANCE-2026-10-01.md) and
  [release/NOTICE-student-v5](release/NOTICE-student-v5).
- **A proof is only as good as its specification.** dawnr checks the specification against the problem's own
  examples and against six independently written solutions, on drawn inputs up to several times the size of the
  examples (larger ones since 2026-10-05: [why](t/LARGER-INPUTS-2026-10-05.md)), and still shows a wrong answer about one time in
  eight on problems it has not seen (see below). A shown answer says how many of the seven provers proved it; it is
  not a guarantee that the question was understood.
- **A certificate replays; it does not vouch.** `dawnr check` establishes again, on the reader's machine and with
  the reader's provers, what a certificate records: the tests, a search for an input that breaks the specification,
  the proof and its sabotaged twin, the Python handed back, the measurements of the specification. A prover that
  machine lacks is named and not counted, and a slower machine can read `UNDECIDED HERE` where the first one proved.
  It cannot say that the specification is what was meant. A certificate written by `dawnr verify` contains the
  Python file it was run on. The format is new (2026-10-05); how certificates travel between machines and whether
  forged ones are caught is registered in `t/PREDICT-2026-10-05-verify-python.md` and not yet measured.
- **`dawnr verify` proves a twin, not your Python.** The `t` program is proved against its specification; that it
  and your function are the same function is tested on drawn inputs inside the twin's `requires`, not proved. When
  you give no examples they are taken from your function, so a bug in it is recorded as its behaviour and shows up
  only in the specification you are asked to read. How many functions get a twin is registered in the same file and
  not yet measured; on four hand-written files the published model verified two and refused two, one of them a
  function written to stop one short of what its docstring says, which the refusal pointed at with the example.
- **"Proved" covers two different things, and about half of the scoreboard's count is the lesser one.** When a
  specification gives the result as a formula and the program is that formula again (`r := d1 * d2 / 2` under
  `ensures r == d1 * d2 / 2`, or a recursion held to a specification function that is the same recursion), the
  proof says only that the two writings agree; what the answer rests on is the specification, which was tested
  against a solution, not proved. Of the published model's 17 proved problems, 8 are of that kind and 9 are a
  loop, another recursion or a property proved; Phi-4-mini's 7 are all of the first kind, the untrained 4B's 9 hold
  2 of the second, and the prompted 27B's 32 hold 17 (`t/PROOF-KIND-2026-10-05.md`, by a rule that reads the
  answer's text; it was checked by hand on 58 answers and is not a measure of difficulty). `dawnr ask`, `prove` and
  `verify` say beside each answer which kind it is.
- **`dawnr cite` and `dawnr extract` say where words came from, not that they are the right words.** Neither can
  show text that is not in your files, by construction. `cite` is measured (below). `extract` was measured three
  times on 2026-10-05 (SQuAD 2.0, each time 300 questions the paragraph answers and 300 it does not, none repeated,
  the base model) and changed after the first two. As it stands, for a text field: a value was shown for 270 of
  the 300 answerable questions and was exactly right for 224; 230 of the 300 absent ones were left empty; of all
  340 values shown 65.9% were exactly right. The same model filling a JSON schema showed 378 values, 64.5% exactly
  right, left 215 absent ones empty, and 9 of its values were not in the paragraph as words. So `extract` is about
  as often right as a schema, more often silent where the document does not say, and never shows words that are
  not there; one field in four that is not in the document is still filled with something that is, and the
  printed sentence is what you check. What did not work, for the record: holding the value to a run of the
  sentence's words by grammar (39 to 43% exactly right, three samples), and a prompt of my own in place of the
  measured one (56%). Number and date fields are not measured.
- **Documents in other languages are read, and only English is measured.** Until 2026-10-05 `cite` and `extract`
  split sentences by an English rule, so a Chinese or Japanese document was one sentence, any sentence was cut at
  400 characters with the rest silently dropped, a long document not in the Latin alphabet could not be searched,
  and `1.250,00` could not be read as a number. Sentences are now found by a stated profile of Unicode's rules
  (`locallm/cite_docs.py`), nothing is dropped, the search indexes any script, and a number is read the English or
  the continental way as the document itself writes numbers (where it writes both ways an ambiguous one is refused).
  This was tried by hand on one Chinese, one German and one Spanish invoice, where every field came back right
  and the absent one empty; that is three documents, not a measurement. Known gaps: a number such as `1.250` in a
  document that nowhere writes a decimal comma is read the English way; abbreviations of other languages
  (`Nr. 2291`) still end a sentence; dates are read only when written with English month names or as numbers. On
  English text the sentences are the ones every measurement here used, except that the tail of an over-long
  sentence is kept (39 of 767 SQuAD paragraphs had lost one) and a sentence may begin with an accented capital.
- **`dawnr calc` computes a working exactly; it does not know the right reading of the question.** Its first form
  (the model writes the working, an answer is shown when workings agree) was measured on 300 GSM8K problems with
  the base model: it showed 203 answers, 94.6% of them right, where the same model simply reasoning in words
  answered all 300 and was right on 93.0%. Held to lines of arithmetic the model sets a problem up worse than
  when it reasons freely. The command was changed because of that: the number the model reasons its way to is
  shown only when a working written separately and computed exactly gives the same number. On those same 300
  problems, computed afterwards, that shows 269 answers with 97.4% right; its own measurement on problems it has
  not seen is registered in `locallm/PREDICT-2026-10-05-calc.md` (K6 to K9) and not yet made. A misreading that the
  reasoning and the working share is shown; the working is printed so that it can be read.
- **`dawnr tools` checks where a call's values came from, not that they are the right ones.** A call is handed
  back only when each value it passes was said in the conversation (its words as written, its number), or is the
  tool's default, or a choice among the tool's listed values that the conversation makes. Measured on When2Call's
  test items (900 the rule had not been fitted on, the base model): on 300 requests with a required value
  removed, the model alone called a tool 203 times and 50 with the check, and 142 of the 153 questions the check
  asked named the removed parameter; on 300 complete requests, 203 of the model's 214 right calls were still
  handed back (eleven became questions). What it cannot see: a word of the request passed to the wrong parameter,
  an identifier assembled from the request's own words, a truth value nobody stated, and a value the person
  implied without saying. Words the model writes when it calls nothing are passed on as they are, unchecked, and
  the reply says so. One turn at a time was measured; conversations of several turns were not.
- **With `DAWNR_WRITER_URL` set, what you ask leaves your machine.** The question, its tests, a specification or the
  Python file you give `verify` are sent to the address you named, to be written into `t` by the model there; dawnr
  prints a line saying so each time. Nothing it returns is trusted unchecked, so a wrong or hostile writer costs
  refusals, not wrong answers that pass; but the privacy of what you send is that service's, not dawnr's. Without
  the variable, dawnr sends nothing anywhere. The option is new (2026-10-05) and not yet measured on a panel.
- **`dawnr mcp` checks what another assistant writes; it does not make that assistant right.** The tools run the
  same gate on whatever they are given, and say which check stopped it. Whether the assistant calls them, and what
  it does with a refusal, is the assistant's. It is new (2026-10-05), tested against the protocol's messages and
  with stand-in provers, and has been driven by no assistant on a panel.
- **`dawnr serve api` is for one person on one machine.** It binds to 127.0.0.1, requires a token made at start on
  every request, refuses a request whose Host is not this machine's own or whose Origin is another site's, and runs
  each job as the same command the terminal runs. It has no accounts, no encryption in transit and no per-project
  separation, so it is not something to expose to a network. It is new (2026-10-05) and has been driven end to end
  on one desktop.
- **The installer is new.** It was tested from an empty home directory on Linux x86_64 against the published
  release (about 9 minutes, almost all of it downloading 7.5 GB; the first question was answered and proved by
  Dafny in about a minute). It installs only Dafny
  of the seven provers; an answer is shown with how many of the installed provers proved it. The independent
  Python check runs model-written code only inside a sandbox: `bwrap` on Linux, and on macOS Apple's Seatbelt with
  the policies OpenAI's Codex CLI uses. The whole path, install
  then a question answered and proved, passes on GitHub's Ubuntu 24.04 and Apple-silicon Mac runners
  (`.github/workflows/install-smoke.yml`). That Mac is a 3-core virtual machine whose virtual GPU generated under a
  token a second, so there the models ran on its CPU (`DAWNR_GPU_LAYERS=0`), about 5 minutes for the first
  question; a physical Mac, where llama.cpp uses Metal, has not been tried. If answers come back as "no reply from
  the model", set `DAWNR_GPU_LAYERS=0`.
- **Tested on a gaming laptop through Windows (2026-10-03).** Windows 11, an RTX 5050 Laptop GPU (8 GB) and 16 GB
  of memory, with WSL2's default Ubuntu (26.04, which sees 8 GB of it). The installer picked llama.cpp's CUDA build by
  itself. The README's three lines then failed twice, and both failures are fixed: a fresh Ubuntu lacks the OpenMP
  runtime llama.cpp's Linux builds link (`libgomp1`, which llama.cpp's own Docker images add), and the ICU library
  Dafny's .NET runtime stops without, so every answer came back unproved. The installer now asks for what is
  missing before downloading anything (`sudo apt install libgomp1 unzip bubblewrap` at most), and runs Dafny in
  .NET's invariant mode where ICU is missing (164 Dafny verdicts were measured identical in both modes first). WSL's
  Ubuntu 24.04 was then installed bare beside it: it lacked libgomp1, unzip and bubblewrap but had ICU, and after the
  one line the installer printed, the README's example was shown proved in 25 s, starting the models included. Measured there: the models start in
  5 to 6 seconds and generate about 50 tokens a second, using 7.6 GB of the card and at most 2.2 GB of memory; the
  README's example was shown proved by Dafny in 15.9 s, a second question in 10.7 s, a first question that also
  started the models in 18.6 s; `dawnr cite` quoted its answer in 2.0 s and refused an unanswerable question in
  0.85 s. A third question (the sum of a list's even numbers) was refused in 27 s there and in 213 s on a desktop
  CPU, with the same reasons: the model's limit, not the machine's. The models were copied to the laptop over the
  local network rather than downloaded (its connection ran at 0.8 MB/s); the installer checked each against its
  published SHA-256 as it checks a download. No AMD or Intel graphics card has been tried; those run on the CPU.
- **Ubuntu 23.10 and newer need one root step.** They restrict the user namespaces bubblewrap uses, and the
  sandbox fails on every run until an AppArmor profile allows it (`t/apparmor-bwrap.sh`, Ubuntu's documented
  per-program way). `./install.sh` and `dawnr doctor` detect this and print the command; on GitHub's Ubuntu 24.04
  runner the sandbox's tests fail before it and pass after it. WSL2's Ubuntu needs no such step: its kernel
  has no such restriction, and the sandbox ran there as installed.
- **It does not yet solve most problems.** On held-out problems the published model is proved correct on 18 of
  182, one in ten. It refuses the rest rather than guessing, which is the design, but it means most questions get a
  refusal.

## Where it stands (2026-10-02)

### The main result

On 182 held-out problems that no training row touches, the fine-tuned 4B
is proved correct more often than a prompted model about the same
size given the same budget. A problem counts only when its program passes its
tests, a prover verifies it, and its specification agrees with the problem's
reference solution and rejects most wrong answers.

**Corrected 2026-10-05.** Every row below was published on 200 problems. An audit of the training rows found 18
of the 200 in them under other names (six are the problem itself, by way of a second benchmark; the rest are
programs that behave as the problem's solution does), so the panel is the other 182 and every row is counted again
on it, the prompted models too. The number first published is in brackets
([the audit, and how the rows got in](t/DECONTAMINATION-2026-10-05.md)).

**Corrected again 2026-10-05.** The check of a specification drew inputs no larger than the problem's examples (a
list two longer than the longest example, a number twice the example), so a specification that lists the small cases
and says nothing after them read as complete. Each row is counted a third time with every specification also held
to larger inputs, which is the reading of record from now on; the two earlier readings follow it in brackets
([what was found, and every row](t/LARGER-INPUTS-2026-10-05.md)).

| on the clean 182, specifications held to larger inputs (the clean 182 before that; the 200 as first published) | proved by at least one prover | proved by all seven |
|---|---:|---:|
| the 4B on v5's rows, training seed 1 | 12 (13; 18) | 5 (5; 7) |
| the 4B on v5's rows, training seed 2 | 12 (13; 18) | 5 (5; 8) |
| the 4B on v5's rows, training seed 3 | 9 (9; 15) | 6 (6; 7) |
| v3's rows, training seed 1 | 11 (12; 17) | 7 (7; 10) |
| v3's rows, training seed 2 | 9 (10; 16) | 4 (4; 8) |
| v3's rows, training seed 3 | 10 (11; 17) | 4 (4; 8) |
| v3's rows plus 182 rows from a teacher's proved documents, training seed 3 | 14 (15; 21) | 9 (9; 12) |
| the same, training seed 1 | 14 (15; 19) | 5 (5; 8) |
| the same, training seed 2 | 9 (9; 13) | 5 (5; 7) |
| v3's rows plus 598 rows from every document admitted since (teachers and the specification round), seed 1 | 13 (16; 23) | 9 (10; 13) |
| the same, seed 3 | 18 (19; 27) | 10 (10; 13) |
| the same, seed 2 | 16 (17; 24) | 10 (10; 15) |
| those rows without the 46 a name filter removed, plus round 3's 129 APPS documents, seed 2 | 17 (18; 27) | 10 (10; 15) |
| the same, seed 3 | 12 (14; 23) | 7 (8; 13) |
| the same, seed 1: **dawnr v5**, the published model | 17 (18; 26) | 12 (12; 16) |
| Qwen3.5-4B, dawnr's own starting weights, prompted, the same 17 answers a problem | 9 (9; 15) | 6 (6; 8) |
| Qwen3.5-9B, prompted, the same 17 answers a problem | 14 (15; 18) | 6 (6; 7) |
| Qwen3.5-2B, prompted, the same 17 answers a problem | 2 (2; 4) | 2 (2; 3) |
| a Qwen3.5-2B fine-tuned on the release-v4 candidate's rows, seed 1 | 4 (4; 8) | 3 (3; 6) |
| Qwen3.5-0.8B, prompted, the same 17 answers a problem | 1 (1; 1) | 1 (1; 1) |
| Qwen3.5-27B (fp8), prompted, the same 17 answers a problem | 32 (33; 43) | 22 (23; 29) |
| Phi-4-mini, prompted, the same 17 answers a problem | 2 (2; 3) | 2 (2; 3) |
| Phi-4-mini decoding under t's grammar, the same 17 answers a problem | 7 (7; 9) | 5 (5; 7) |
| every model trained here from scratch | 0 | 0 |

v3's rows were not released: their first seed missed the release gate on the 33 given specifications by two (25 of 33 by all seven, against 27; [v3](t/PREDICT-2026-10-02-release-v3.md)); `student-v5`, published 2026-10-05, is the last row of the fine-tuned block. Every row is counted the same way: each program's specification checked against the problem's reference (EvalPlus's corrected MBPP+ solution where it keeps the problem's tests) on 1,000 drawn inputs, and every set's answers normalised alike ([correction](t/PREDICT-2026-10-01-replication.md)).

This is not yet the win the project set itself. Given every advantage, decoding under t's grammar so it cannot write unparseable output, Phi-4-mini proves 7 at one prover and 5 at all seven on the 182. Every training seed of the published recipe is above both (17 and 12, 17 and 10, 12 and 7); the written bar asks for double on every seed, 14 and 10, and the third seed has 12 and 7. The same 4B before any fine-tuning proves 9 and 6, so the rows the provers admitted add 9 problems and 6 by all seven to the published model, and much of the lead over Phi is the base model.

Without a reference solution, the gate can still tell most right answers from
wrong ones. It checks the specification against a tested Python solution
written beside the question. On the student's held-out answers it shows 18
problems and 15 are right, where tests and proofs alone would show 31 with 18
right ([the gate](t/PREDICT-2026-10-01-gate-without-reference.md)). Across the three training seeds it shows 56
answers and 45 are right (80%). Holding each specification to five more sampled Python solutions as well, so that
a question two solutions read differently is refused with the input they split on (ClarifyGPT's consistency check),
it shows 47 and 41 are right (87%) ([ambiguity](t/PREDICT-2026-10-02-ambiguity.md)); `dawnr ask` does this. Read
by hand, most of the remaining "wrong" answers are faults in the benchmark's reference solutions.

### Part by part

| part | state |
|---|---|
| proof engine: `t`, seven provers, twins, specification checks | **Works.** Across 4,700 graded programs no prover has verified what another refuted ([t/README.md](t/README.md)). |
| the model, given a specification | **Works, and the 33 questions say less than they seemed to.** The published model writes a body all seven provers accept on 27 of 33 held-out questions ([outcome](t/PREDICT-2026-10-05-release-v5.md)); 19 of the 33 have a program of the same behaviour in the training rows under another name, and on the other 14 it proves 10 ([the audit](t/DECONTAMINATION-2026-10-05.md)). A panel of 54 questions with no such program is what the next model is measured on. `dawnr prove SPEC.t` is this, for a specification you wrote; `dawnr spec` proposes specifications to read and pick from. |
| the model, from English | **Works on a minority of problems** (17 of 182 held-out ones). Writing the right specification is the hard step: most of its specifications contradict the problem's own examples ([outcome](t/PREDICT-2026-10-01-v6.md)). |
| the model behind the gate | Qwen3.5-4B (Apache-2.0), picked by a fixed rule from six candidates of 1.5B to 14B ([selection](t/PREDICT-2026-10-01-base-model-selection.md)). |
| more proved data each round | The gate's verdicts become training data, after SAFE. The first round grew the pool from 527 to 693 proved answers ([proof round](t/PREDICT-2026-10-01-proof-round.md)). The specification round (the student writing specifications for training problems from their reference solutions) added 63 more, 28 of them proved by all seven ([spec round](t/PREDICT-2026-10-01-spec-round.md)). A teacher model on Amazon Bedrock (Qwen3-235B, openly licensed, $3.47) wrote 123 documents the provers admitted at six or seven kernels, 89 of them at all seven ([teacher round](t/PREDICT-2026-10-03-teacher-round-bedrock.md)); a student trained on them is being measured. |
| data from verified code elsewhere | 464 lifted programs are clean in all seven provers, 569 with a recorded trust level ([t/LIFT-2026-09-26.md](t/LIFT-2026-09-26.md)). |
| reinforcement learning with the provers as reward | Run once on the student (2026-10-03, GRPO, 60 problems in the difficulty band, 960 answers): the reward rose a little on the training problems (0.240 to 0.255) and nothing moved on unseen ones (dev tests 13 and 13, proofs 4 and 4; the 33 given specifications 28 and 28). Not adopted ([outcome](t/PREDICT-2026-10-01-rl-on-the-student.md)). |
| small hardware | At 8 bits the student is a 4.48 GB file that keeps every proof and runs at about 15 tokens a second on 12 CPU threads ([outcome](t/PREDICT-2026-10-01-small-hardware.md)). |
| knowing when it is right | The proofs decide. Asked to rate its own answers, the model separates easy problems from hard ones but not right answers from wrong ones on the same problem ([outcome](t/PREDICT-2026-10-01-calibration.md)). |
| hearing and speaking | Whisper transcribes offline at 4.14% word error. Piper's speech is understood at 6.44% word error, against 3.19% for human speech ([hearing](locallm/PREDICT-2026-10-01-hearing.md)). |
| seeing | The base answers adversarial object questions at F1 0.873. An independent detector cuts its false "yes" answers from 140 to 112 and keeps 97% of true ones ([seeing](locallm/PREDICT-2026-10-01-seeing.md)). |
| memory | Given dawnr's memory, the base and the latest student recall a remembered preference 28 times in 28 and never invent one. The student applies it to its program 8 times in 14 ([outcome](t/PREDICT-2026-10-01-v6.md)). |
| tools | Untrained on the harness, the base picks the right first tool 84.5% of the time and follows 4.5% of instructions planted in web pages. It follows a third of instructions planted in stored notes, which in dawnr stop at the owner's approval. Marking untrusted text so the model can tell it apart (spotlighting), which works for GPT-4-class models, made this 4B model follow planted instructions more, not less (15% of web pages), so it is not used. Restating the request after each tool output (BIPIA's reminder) cut planted notes followed from 10 of 33 to 2 but left web pages where they were (7 of 132 against 6), so it is not used either ([tools](locallm/PREDICT-2026-10-01-tools-on-the-base.md)). |
| acting on the machine | Asked to summarise an inbox with a planted instruction, the base did the task 81 times in 90 and planned the planted action 10 times. The harness ran none of them ([outcome](locallm/PREDICT-2026-10-01-agent-on-the-base.md), [threat model](DAWNR-AGENT.md)). |
| answering from documents | With five news documents, 98% right; with four of the five irrelevant, 86%. When none holds the answer it says so only 31% of the time. Made to quote, word for word, the document sentence behind each claim (the decoder allows nothing else), it says so 286 times in 300 and answers 78% of the questions whose answer is present, at least 79% of them right, each with a sentence the reader can check. Choosing the quote before writing the claim answers more but refuses less when the answer is absent, so it is not used. A model judge of whether the quote supports the claim adds nothing ([retrieval](locallm/PREDICT-2026-10-01-retrieval-on-the-base.md)). |
| learning from each person | Built: feedback stays under each person's control, and a style profile from their edits halves their editing with no checked answer made worse ([DAWNR-LEARNING.md](DAWNR-LEARNING.md)). |
| the model trained from scratch (research) | A GPT trained here learns the language but has not solved a held-out problem with a checked specification ([r12 outcome](t/PREDICT-2026-09-30-dawnr-r12-core.md)). |
| release | Published: `student-v5`, dawnr v5, on 2026-10-05, Apache-2.0, and installed from the release into an empty home the same hour. Where every training row comes from is recorded, with the correction of 2026-10-05 about 61 rows of GPL-3.0 lineage ([provenance](internal/RELEASE-PROVENANCE-2026-10-01.md)). |

Every number links to the run that produced it. Failures are published beside
successes in [CORRECTIONS.md](CORRECTIONS.md) and [LIMITS.md](LIMITS.md).

## How progress is measured

- **The clean 182.** Held-out problems that no training row answers, after two
  audits: the first found same-task training documents and left 200 of 232
  ([t/DECONTAMINATION-2026-09-21.md](t/DECONTAMINATION-2026-09-21.md)); the
  second read the training rows themselves and found 18 more under other names
  ([t/DECONTAMINATION-2026-10-05.md](t/DECONTAMINATION-2026-10-05.md)). A row
  build now fails if a row matches a problem still in the panel
  (`t/heldout_audit.py`). They are used once per system.
- **Pre-registration.** Each prediction and decision rule is committed before
  its run, and its outcome is written into the same file.
- **Seeds.** A result that appears at one training seed is not a result.
- **A milestone, not the goal.** Phi-4-mini is the comparison of record
  ([SCOREBOARD.md](SCOREBOARD.md) has the history).
