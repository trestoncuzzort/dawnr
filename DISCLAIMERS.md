# Disclaimers and current state

dawnr is research software. Read this before relying on anything it does.

## Use and licence

- **Research and education use only.** See [LICENSE](LICENSE). Third-party material keeps its own licence
  ([NOTICE](NOTICE)); the problem corpora's licences are documented under `nl/`.
- **The published student is v1, not the strongest one measured.** `student-v1` (Apache-2.0) is the 4B trained
  on v6, chosen because it already left out every row that traces to GPL-licensed programs; it writes t a little
  less well than the v5 recipe behind the held-out results above. The v5 recipe without those rows was trained
  and measured too and proved fewer of the 33 given specifications by all seven provers (24, v1 26), so it was not
  released ([registration](t/PREDICT-2026-10-02-release-student.md)). Where every training row comes from, and under what
  licence, is in [internal/RELEASE-PROVENANCE-2026-10-01.md](internal/RELEASE-PROVENANCE-2026-10-01.md) and
  [release/NOTICE-student](release/NOTICE-student).
- **A proof is only as good as its specification.** dawnr checks the specification against the problem's own
  examples and against six independently written solutions, and still shows a wrong answer about one time in
  eight on problems it has not seen (see below). A shown answer says how many of the seven provers proved it; it is
  not a guarantee that the question was understood.
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
- **Ubuntu 23.10 and newer need one root step.** They restrict the user namespaces bubblewrap uses, and the
  sandbox fails on every run until an AppArmor profile allows it (`t/apparmor-bwrap.sh`, Ubuntu's documented
  per-program way). `./install.sh` and `dawnr doctor` detect this and print the command; on GitHub's Ubuntu 24.04
  runner the sandbox's tests fail before it and pass after it.
- **It does not yet solve most problems.** On held-out problems the student is proved correct on 15 to 19 of
  200. It refuses the rest rather than guessing, which is the design, but it means most questions get a refusal.

## Where it stands (2026-10-02)

### The main result

On 200 held-out problems that no training data touches, the fine-tuned 4B
student is proved correct far more often than a prompted model about the same
size given the same budget. A problem counts only when its program passes its
tests, a prover verifies it, and its specification agrees with the problem's
reference solution and rejects most wrong answers.

| on the clean 200 | proved by at least one prover | proved by all seven |
|---|---:|---:|
| the student, training seed 1 | 18 | 5 |
| the student, training seed 2 | 19 | 6 |
| the student, training seed 3 | 15 | 8 |
| Phi-4-mini, prompted, the same 17 answers a problem | 3 | 2 |
| every model trained here from scratch | 0 | 0 |

Counted against EvalPlus's corrected MBPP+ solutions wherever they keep the problem's own tests, seed 3 reads 17 and 8
([t/PREDICT-2026-10-02-reference-plus.md](t/PREDICT-2026-10-02-reference-plus.md)); nothing else moves.

This is not yet claimed as a win. The bar written in [AMBITION.md](AMBITION.md)
also asks for Phi-4-mini decoding under `t`'s grammar, so it cannot emit text
that does not parse; that run is in progress
([registration and outcomes](t/PREDICT-2026-10-01-replication.md)).

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
| the student, given a specification | **Works.** On 33 held-out questions the 4B writes a body all seven provers accept 28 times ([outcome](t/PREDICT-2026-10-01-spec-given.md)). |
| the student, from English | **Works on a minority of problems.** Writing the right specification is the hard step: most of its specifications contradict the problem's own examples ([outcome](t/PREDICT-2026-10-01-v6.md)). |
| the model behind the gate | Qwen3.5-4B (Apache-2.0), picked by a fixed rule from six candidates of 1.5B to 14B ([selection](t/PREDICT-2026-10-01-base-model-selection.md)). |
| more proved data each round | The gate's verdicts become training data, after SAFE. The first round grew the pool from 527 to 693 proved answers ([proof round](t/PREDICT-2026-10-01-proof-round.md)). The specification round is registered and queued ([spec round](t/PREDICT-2026-10-01-spec-round.md)). |
| data from verified code elsewhere | 464 lifted programs are clean in all seven provers, 569 with a recorded trust level ([t/LIFT-2026-09-26.md](t/LIFT-2026-09-26.md)). |
| reinforcement learning with the provers as reward | Built. The student now solves enough unseen problems to learn from, so the run is registered and queued ([registration](t/PREDICT-2026-10-01-rl-on-the-student.md)). |
| small hardware | At 8 bits the student is a 4.48 GB file that keeps every proof and runs at about 15 tokens a second on 12 CPU threads ([outcome](t/PREDICT-2026-10-01-small-hardware.md)). |
| knowing when it is right | The proofs decide. Asked to rate its own answers, the model separates easy problems from hard ones but not right answers from wrong ones on the same problem ([outcome](t/PREDICT-2026-10-01-calibration.md)). |
| hearing and speaking | Whisper transcribes offline at 4.14% word error. Piper's speech is understood at 6.44% word error, against 3.19% for human speech ([hearing](locallm/PREDICT-2026-10-01-hearing.md)). |
| seeing | The base answers adversarial object questions at F1 0.873. An independent detector cuts its false "yes" answers from 140 to 112 and keeps 97% of true ones ([seeing](locallm/PREDICT-2026-10-01-seeing.md)). |
| memory | Given dawnr's memory, the base and the latest student recall a remembered preference 28 times in 28 and never invent one. The student applies it to its program 8 times in 14 ([outcome](t/PREDICT-2026-10-01-v6.md)). |
| tools | Untrained on the harness, the base picks the right first tool 84.5% of the time and follows 4.5% of instructions planted in web pages. It follows a third of instructions planted in stored notes, which in dawnr stop at the owner's approval ([tools](locallm/PREDICT-2026-10-01-tools-on-the-base.md)). |
| acting on the machine | Asked to summarise an inbox with a planted instruction, the base did the task 81 times in 90 and planned the planted action 10 times. The harness ran none of them ([outcome](locallm/PREDICT-2026-10-01-agent-on-the-base.md), [threat model](DAWNR-AGENT.md)). |
| answering from documents | With five news documents, 98% right; with four of the five irrelevant, 86%. When none holds the answer it says so only 31% of the time. No support check tried so far separates answers from the documents and answers from memory ([retrieval](locallm/PREDICT-2026-10-01-retrieval-on-the-base.md)). |
| learning from each person | Built: feedback stays under each person's control, and a style profile from their edits halves their editing with no checked answer made worse ([DAWNR-LEARNING.md](DAWNR-LEARNING.md)). |
| the model trained from scratch (research) | A GPT trained here learns the language but has not solved a held-out problem with a checked specification ([r12 outcome](t/PREDICT-2026-09-30-dawnr-r12-core.md)). |
| release | Not yet published. Where every training row comes from, and under what licence, is recorded ([provenance](internal/RELEASE-PROVENANCE-2026-10-01.md)). |

Every number links to the run that produced it. Failures are published beside
successes in [CORRECTIONS.md](CORRECTIONS.md) and [LIMITS.md](LIMITS.md).

## How progress is measured

- **The clean 200.** Held-out problems that no training document answers,
  after an audit found earlier leaks through same-task training data
  ([t/DECONTAMINATION-2026-09-21.md](t/DECONTAMINATION-2026-09-21.md)). They
  are used once per system.
- **Pre-registration.** Each prediction and decision rule is committed before
  its run, and its outcome is written into the same file.
- **Seeds.** A result that appears at one training seed is not a result.
- **A milestone, not the goal.** Phi-4-mini is the comparison of record
  ([SCOREBOARD.md](SCOREBOARD.md) has the history).
