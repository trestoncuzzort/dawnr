# What this project is actually for

The operator's goals, in the operator's terms, with the measured state beside
each one so the gap is always visible. This file is the target. `ROADMAP.md` is
the route, and every number here links to the run that produced it. The ideas
being worked toward are kept at the end of this file, stated plainly, with
where each one stands.

## The direction since 2026-10-01

The operator, the evening of 2026-09-30, after the question "are we holding out for math that does
not exist" was answered yes for the from-scratch model
(`internal/RESEARCH-2026-10-01-is-the-bet-supported.md`):

- **Nothing it says is relied on until it is proved. That is the whole point.**
- **Build from the ladders others have made.** No step may rest on a maybe; every step cites the
  published method or the measurement it stands on.
- **Other people's weights are fine**, if they are the best for this job and usable by everyone:
  chosen by measurement through the gate, permissively licensed, small enough for ordinary
  hardware.
- **Meet every goal below on those weights.** `internal/LADDER-PLAN-2026-10-01.md` maps each one
  to its ladder and its measurement.

Sections 1 to 3 below were written for the from-scratch model. They stand as the record of what
was aimed at and are re-read as follows: section 1's comparison is now the student against the
same reference on the clean 200; section 2's product is the gate with the student behind it;
section 3's curve is fine-tuned small models against prompted large ones.

## The north star: dawnr, a model you could trust on a spaceship

**dawnr is the track this project is on** (the operator, 2026-09-26). Work is
chosen by which row of the dawnr table it moves.

A model trained so well that it could do its job on a spaceship: no network,
no one to ask, small hardware, and a mistake that cannot be taken back. That
sets the bar for everything below.

- **It runs where it is.** Trained and run on one machine, on ordinary
  hardware, with nothing uploaded and no service behind it.
- **It does not guess silently.** What it writes is a program with a
  specification, checked by proof before anyone relies on it; what cannot be
  checked is refused, not passed along.
- **It learned, not memorised.** It is judged on problems no training document
  answers, and a model that recites its training text has not met the bar.
- **Every claim about it carries its evidence.** A number without the run that
  produced it does not count.

Beating Phi-4-mini (section 1) is a milestone on the way, not the destination.

## 1. Beat Phi-4-mini. Not tie it. Beat it.

**The state:** level. 3 clean answers of 232 for locallm, 3 for Phi, on a
baseline regraded the same day by the same evaluator
(`locallm/FINDINGS-round8-2026-09-19.md`). On the column that survives the
specification check it is 3 against 2.

**2026-09-29:** with the specification check applied to the held-out 200 (each
answer's specification against the problem's own solution on 200 drawn inputs),
every locallm arm measured so far reads 0: the ten r11 seeds, the r12 head-prompt
seeds, and the chat pipeline's three seeds, whose 2 and 5 "clean" answers were
the same trivial program fitting two shown examples by coincidence
(`t/PREDICT-2026-09-29-dawnr-chat-heldout.md`). The bar in this section is
measured on that column from now on.

**2026-10-01, the clean 200 with the specification check and the completeness rule:** the pretrained 4B student, fine-tuned on what the gate admitted, is proved on 18 problems by at least one kernel and 5 by all seven; Phi-4-mini, given the same 17 answers a problem, the same gate and the same day, on 3 and 2 (`t/PREDICT-2026-10-01-several-answers.md`). Three seeds of the same recipe read 18 and 5, 19 and 6, 15 and 8 (mean 17.3 and 6.3; 2026-10-02 02:08Z), so the seeds condition below is met. Phi under `t`'s grammar is being generated (`t/PREDICT-2026-10-01-replication.md`); until it is graded, this is not the win written below.

**What counts as the win, written down so it cannot be softened later:**

- **4 clean of 232**, which is beating Phi on its own scoreboard.
- **With seeds.** Three initializations of the same recipe, all reported. A
  result that appears at one seed is a story, not a number.
- **With Phi given every advantage.** Decoding against t's grammar so it cannot
  emit unparseable output (`phi4-mini-g`, half generated, never graded), the
  same prompt, the same token budget, the same day, the same evaluator. The
  point is not to win a rigged comparison. The point is to win one nobody can
  call rigged.
- **Then double it.** 6 clean against Phi's 3, which is the first number that
  makes the method, not the margin, the story.

## 2. locallm is the product (until 2026-10-01; now the gate with the student behind it)

Not the fine-tuned student, which is someone else's base model. Not the
prompted 27B or the prover, which are tools this pipeline uses. **The claim is
a model trained here, from random numbers, on one machine, on data seven proof
systems agreed was correct.**

Everything else in the repository exists to feed that model or to measure it
honestly. The README leads with locallm and says which rows are baselines.

## 3. Make the size difference the headline

92M against 3.8B is **41 times fewer parameters**. Trained from random weights
in minutes of GPU time on one shared card, against a cluster. On a formal
language that did not exist a month ago, at a bar far harder than passing unit
tests: seven independent proof systems verifying the program against the
specification, and all seven catching a deliberately sabotaged twin.

**The ambition is not a smaller model that keeps up. It is proof that verified
data buys parameter efficiency**, stated as a curve rather than a point: 10.9M,
92M, 312M on one recipe and one evaluator, with Phi's fixed point beside it.
Capacity is already measured to 875M on a single shared card
(`locallm/FINDINGS-capacity-2026-09-19.md`); the data to justify it is the
missing half.

## 4. Scale the engine, not just the model

The rare thing here is not the model. It is the machine that manufactures
training data nobody has to trust: an answer is kept only if it passes the
problem's own tests, seven provers verify it, all seven refute its twin, and
its specification agrees with the problem's own solution.

**The ambition is to run that engine at a scale where the pool stops being the
constraint.** Measured today: the specification check nobody had run was
holding 246 answers out of the pool, and running it took the training set from
87 preference pairs to 733. The prover converts 31 of 88 graded cells into
clean answers and 2,354 training problems have never been asked. Three corpora
are open and none is exhausted: MBPP, APPS at 2,266 problems, DafnyBench at
785 lifted.

## 5. Own the whole loop

No paid API in the critical path. The generator is already local. The trainer,
the verifiers, the scorer and the data engine are already local. What has been
rented is judgment, and the way to stop renting it is to make the engine loud:
every silent failure fixed, every claim carrying the file that produced it,
every round registering its prediction before it runs
(`internal/LOCAL-AGENT-2026-09-20.md` is the honest account of what a local
model can and cannot take over).

## 6. Make it matter to people who were not here

Three attacks land on the current result and all three are fair: 3 of 232 is
1.3 percent, Phi has never seen t, and there are no seeds yet. **The ambition
is to retire all three with measurements rather than argument**, and to keep
publishing the failures beside the wins, because a repository that corrects its
own published claims is worth more than one that never had to.

The twins are the artifact most likely to outlive the score: 426 pairs over
**213** verified programs answering 90 problems, each paired with a near-miss,
the input that separates them, and seven independent refutations
(`t/twins/README.md`). Nothing comparable has been found published.

## The ideas being worked toward

Plainly stated, with where each one stands. When one lands or is abandoned,
its line changes here.

- **More verified documents, because data is the limit.** A fine-tune on the
  old ~300-document corpus reached 0.11 nats per token on its training text
  against 0.68 on held-out text: it memorised. Released corpora of verified
  Dafny programs are lifted into t, proved equivalent to their sources and
  graded in all seven kernels, and now Verus, Lean and C/ACSL corpora too.
  *State:* the proved corpus went from 194 documents (66,569 characters) to
  358 on 2026-09-26, and after the Lean, Rocq and Frama-C lowering fixes were
  regraded over every lifted set, to 431 documents on 2026-09-27, with no
  document lost; and after the features track (seven lifter features, lemmas
  in Rocq, seq-valued spec_funs) was merged and the staged corpora re-lifted
  and graded the same day, then regraded on the lab on 2026-09-28, and after
  a third re-lift (casts under a bound, row 55) with the Dafny and Frama-C
  refutation certificates walking through spec_fun calls, to **463 documents
  (281,188 characters) clean in all seven kernels**, 147 with an English
  head; that build (531 documents with the 68 teacher answers) is the r12
  corpus, registered by hash in `t/PREDICT-r12.md`. Six sources whose
  differential check had only timed out at the 120 s budget passed at 900 s
  the same night, and one of their tasks (`replace`) is clean in seven,
  two more in six (`t/COVERAGE-lifted-2026-09-28-recheck.md`), so the data
  engine stands at **464 clean in all seven kernels** (a 532-document build
  with the answers, 312,476 bytes by the builder's own count), joining the
  corpus at its next registration, not r12's. With graded trust (six kernels
  clean, none contradicting, the gap recorded) it is **569** (a 637-document
  build, 408,419 bytes), 105 of them with a gap. Tables:
  `t/out/COVERAGE-lifted-*-regrade3.md`, `-lab.md` and `-features3-c.md`. The
  lab's regrade of the 140 new tasks agreed with the desktop's cell for cell
  (2 of 980 cells differ), so the timeouts there are the provers' own limits.
- **Denoising training.** Corrupt spans of each training document and train
  the model to restore them (fill in the middle, arXiv:2207.14255). *State:*
  measured twice, and the two disagree. From scratch on the 302 proved
  documents, fill in the middle cut best held-out loss from 1.221 to 0.571
  nats per character, and random windows alone reached 0.694
  (`locallm/FINDINGS-denoising-2026-09-26.md`). On the r12 path (the
  pretrained core, its BPE tokenizer) the layout effect inverts: whole
  documents 0.591, random windows 0.664 (worse), fill in the middle 0.580
  (not better than whole documents beyond noise;
  `locallm/FINDINGS-r12-row-layout-2026-09-26.md`). r12 keeps whole-document
  rows; fill in the middle stays available for infilling, not as the fix for
  memorisation. The lesson: a result from a from-scratch model does not carry
  to a pretrained one without being re-measured.
- **Stop before memorising, keep the best.** Training stops when validation
  stops improving by more than run-to-run noise and keeps the best weights,
  not the last. *State:* in the product (`locallm/train.py`, the studio).
- **Weight decay against memorisation in pretraining.** A three-arm sweep of
  the core's pretraining (`internal/PRETRAIN-R12-2026-09-25.md`). *State:*
  done. Best: weight decay 0.8 at lr 1e-3, validation 1.166 at step 7,400,
  after which it memorises its pretraining corpus too (train 0.60, validation
  1.29 by the end); the control at lr 3e-3 diverged. The best state was not
  kept; the pretraining trainer now keeps the best checkpoint (`best.pt`) and
  can stop at the validation minimum.
- **Runs anywhere with nothing installed.** The window talks to a model with
  no PyTorch, streaming, 1.8 times faster than before, and past the context
  window without the per-token wall; sampling on a CPU uses the cache (about
  14 times faster on the included model). *State:* in the product.
- **Reads only what it can read correctly.** Ingest refuses files that would
  arrive as garbage (legacy non-Latin encodings) instead of training on them.
  *State:* in the product; wrong Latin code pages are the known gap.
- **Product, next:** the product installs the right PyTorch for the machine and brings
  its own Python; a sparse autoencoder to see whether the model learned
  concepts or memorised text.
- **t grows as dawnr does.** t is not kept small and novel for its own sake:
  it takes whatever it needs from any language or data source (Dafny, Verus,
  SPARK, Rust, Python, Haskell, OCaml, Lean, TLA+, anything), copies the best
  existing design and its semantics without apology, cites it, and differs only
  where checking in seven kernels or training a small model makes it better.
  Features are added in the order of the documents they unlock (the lift
  refuses 139 files for method calls, 123 for nested sequences, 108 for
  datatypes, 88 for arrays). Data is admitted by recorded trust (clean in
  seven, or six with the gap named) rather than all or nothing; only the
  held-out boundary stays absolute. *State:* the track started with method
  calls (`t/FEATURES-TRACK.md`).
- **A checker as careful as the model.** The lift's equivalence check refused
  154 methods; 111 of those were the checker's own defects (compiler-internal
  names printed, characters compared with integers, a renaming that captured a
  bound variable, a verdict read from whichever block printed last). Fixed
  without weakening the gate; 2 of the rest are real lift defects. *State:*
  merged; the refused methods are being re-checked and graded.

## dawnr: what the whole thing grows into

dawnr is the assistant this project is building: running on its own hardware
with nothing behind it, able to understand, reason, act and remember, and
trustworthy because what it produces is checked before anyone relies on it
(its weights are borrowed and openly licensed since 2026-10-01; the proof is
what is its own). It is a system, not one model. Each
machine-learning idea earns its place by doing one job in it, and every part
is judged by the same rule: nothing is trusted without evidence.

| dawnr needs | the machine-learning idea | where it stands |
|---|---|---|
| a brain that understands language and code | an openly licensed pretrained model chosen by measurement (`t/PREDICT-2026-10-01-base-model-selection.md`); before 2026-10-01, transformer pretraining from random weights | **built**: the locallm core from the weight-decay sweep (wd 0.8, lr 1e-3). The general-English pilot ran 2026-09-29 (`internal/PRETRAIN-DAWNR-GENERAL.md` section 8): English before code beats code alone at matched tokens on held-out loss and form. r12's core ran 2026-09-30 (section 9): 3.7B English tokens and a short code stage reached the lowest code validation loss of any core (1.140) and judged no better than the sweep's core (well formed 45 of 100, held-out loss 3.7125, specification column 0). No core moves the specification column off 0; by that run's registration the proved corpus is the next lever. The 16.4B-token English set stays staged for the 312M core when a free allocation exists |
| to learn, not memorise | regularisation, denoising (fill in the middle), early stopping, more verified data | **first held-out result on the chosen weights (2026-10-01)**: the 4B student, fine-tuned only on what the gate admitted, is proved with a complete, reference-checked specification on 18 of the clean 200 problems no training row touches (5 by all seven provers), and the gate with no reference shows 18 of which 15 are right (`t/PREDICT-2026-10-01-several-answers.md`). From scratch, **in progress**: the chat pipeline on the 531-document corpus and the early-stopped core answers 49 of 100 dev problems well formed (from 19) and passes all examples on 1.3 (from 0.3) at three seeds (`locallm/PREDICT-2026-09-29-dawnr-r12-corpus.md`); on the held-out 232 it is well formed on 130 (the head-prompt fine-tune: 91) but 0 of 200 survive the specification check, like every other arm (`t/PREDICT-2026-09-29-dawnr-chat-heldout.md`); still memorises (validation loss 0.23 against train 0.07) |
| to know when it is right | verification as the judge, calibration, uncertainty, refusal | **the seven-kernel proof engine is this**; calibration measured (2026-10-01): asked whether its own answer is right (P(True), Kadavath et al.), the student separates easy problems from hard ones (AUROC 0.86 zero-shot, 0.98 four-shot) but not its right answer from its wrong ones to the same problem (0.13 and 0.62), where the gate shows 21 answers and all 21 are right ([`t/PREDICT-2026-10-01-calibration.md`](t/PREDICT-2026-10-01-calibration.md)) |
| to get better at reasoning | reinforcement learning with the verifier as the reward | **built, waiting on data**: tiered proof reward inspected by hand, GRPO trainer (Dr. GRPO advantages hold; plain GRPO unlearned). The from-scratch model solved 0.6% of problems outside its corpus, too few to reinforce. On the chosen weights (2026-10-01) the 4B student has a test-passing answer among ten samples on 27 of 100 dev problems it never trained on, 25 of them with mixed outcomes: the design's start rule (about 10%) is met for the first time (`t/RL-DESIGN-2026-09-26.md` section 9); the run is next on the card after the v6 student |
| to know what it was not trained on | retrieval, embeddings, a vector index | **built in the harness**: a BM25 index over the proved corpus ranks a problem's own proved document first 35 times in 37, and indexes the person's files and fetched pages too (`DAWNR-RETRIEVAL.md`); on the chosen weights, proved examples retrieved into the prompt did not help the 4B student (3 dev problems proved on complete specifications against 4 without, `t/PREDICT-2026-10-01-several-answers.md`); on the chosen weights (2026-10-01, RGB, arXiv:2309.01431): the base answers from five retrieved documents 98% right, 86% with four of them noise, but says the documents lack the answer on only 31% of questions where they do (`locallm/PREDICT-2026-10-01-retrieval-on-the-base.md`); a support check on every reply (AlignScore) keeps 93% of right answers but shows 69% of replies whose documents lack the answer: measured, the cause is not its averaging: no reading of its scores separates an answer the documents state from one the model knew on their topic, a gate that asks for GopherCite's verified quotes (arXiv:2203.11147) refused everything when only prompted, because the base rarely keeps the quote syntax; GopherCite trained its model on it and constrained its decoding, which is what comes next |
| to remember the person and past work | long-term memory, continual learning without forgetting | **built and measured on the chosen weights (2026-10-01)**: with dawnr's memory in the conversation, the base Qwen3.5-4B recalls the remembered preference 28 times in 28 and invents none where there is none; the `t` student on v4 only 17 times in 28; trained on 177 memory conversations, the student on v6 recalls 28 of 28, says so when there is nothing, and applies the preference to the program it writes on 8 of 14 (`t/PREDICT-2026-10-01-v6.md`); replay against forgetting exists in the fine-tune |
| to do things, not only talk | tool use, agents, planning | **started**: a chat pipeline adapted from nanochat (`DAWNR-PIPELINE.md`) runs end to end; the model can call the t interpreter on its own draft mid-answer, and every call closes. Repair conversations from its own cross-fitted drafts taught it to act on a failed check (a new program after 55-70% of failing verdicts) but not yet to fix more answers than seed noise (+1.2 of 133 at six fresh seeds; `locallm/FINDINGS-repair-2026-09-26.md`); next: the tool checks the user's specification is kept, repairs as edits, RL through the engine |
| to hear and speak | speech recognition, text to speech | **works, offline, on pretrained weights (2026-10-01)**: Whisper base.en (MIT) under whisper.cpp on a CPU transcribes LibriSpeech test-clean at 4.14% word error rate, the paper's 4.2, sixteen times faster than real time; it speaks with Piper (MIT) and a voice trained on public-domain recordings, which the same recogniser transcribes at 6.44% word error rate against 3.19% for people reading the same 200 sentences ([`locallm/PREDICT-2026-10-01-hearing.md`](locallm/PREDICT-2026-10-01-hearing.md)). Before: a from-scratch CTC recogniser that overfits a handful of utterances (`DAWNR-SPEECH.md`) |
| to see | vision encoders, multimodal models | **works on the base's own vision input (2026-10-01)**: Qwen3.5-4B at 4 bits with its vision projector, offline on a CPU, answers POPE's adversarial object-hallucination questions with F1 0.873 (accuracy 0.877), naming an absent object on 9.3% of the questions where it is absent; with an independent detector (OWLv2) as the image gate, a claim is shown only when both agree, which cuts the false claims shown from 140 to 112 keeping 97% of the true ones, or to 16 keeping 54%, depending on the trust level chosen ([`locallm/PREDICT-2026-10-01-seeing.md`](locallm/PREDICT-2026-10-01-seeing.md)) |
| to fit small hardware | quantisation, distillation, mixture of experts | partly: runs with no PyTorch, on a CPU. **The pretrained student at 4 bits (2026-10-01):** the fine-tuned Qwen3.5-4B exported to a 2.71 GB GGUF (Q4_K_M) answers at 15.5 tokens a second on 12 CPU threads; on unseen dev problems it does what the full-precision student does (the same two proved on a complete specification), and given a specification it proves 23 of 33 where full precision proves 28, so the quantisation costs about one proof in six; at 8 bits (Q8_0, 4.48 GB) it proves the same 28, the same 26 by all seven, at about 15 tokens a second ([`t/PREDICT-2026-10-01-small-hardware.md`](t/PREDICT-2026-10-01-small-hardware.md)) |
| to be understood from inside | interpretability, sparse autoencoders | **started**: a dictionary over one residual-stream layer's activations runs end to end on a real checkpoint and real training-split text (`locallm/dawnr_interp/`, arXiv:2309.08600's recipe); whether any feature tracks specifications rather than boilerplate is not yet answered past one exploratory, not pre-registered, first pass (its README). With a published SAE on the chosen family (2026-10-01): Qwen-Scope's SAE for Qwen3.5-2B-Base explains 56% of the 2B student's layer-12 variance, and its best feature for "this specification is right" tracks how short the answer is (AUROC 0.81 overall, 0.60 within length quarters) ([`locallm/PREDICT-2026-10-01-sae.md`](locallm/PREDICT-2026-10-01-sae.md)) |
| to improve itself safely | the data engine: generate, verify, keep only what is proved, retrain | **built** |

### dawnr's harness: reaching past itself

dawnr is meant to be a full assistant built on everything machine learning and
the sciences around it can contribute, not only a model. Around the model sits
a harness, the way an agent runtime wraps a language model:

| dawnr needs | the idea | where it stands |
|---|---|---|
| to act through tools | a tool-calling engine: the model emits a call, the runtime executes it, the result returns into the context | **measured on the chosen weights (2026-10-01)**: the base Qwen3.5-4B at 4 bits on a CPU, with native tool calls through the harness and no training on it, picks the right first tool on 84.5% of 238 held-out items, follows 4.5% of injected web pages, never repeats a denied call, but follows an instruction planted in a stored note 10 times in 33, which in dawnr stops at the owner's approval prompt (`locallm/PREDICT-2026-10-01-tools-on-the-base.md`). Before, on the from-scratch core, **built and first measured**: a tool registry with a permission per tool (allow, ask, deny) and a call syntax in the chat format; with 1,007 tool conversations built by running the real harness on a recorded fixture web, the model picks the right tool on 97% of held-out items (42% without) and closes its calls; injection following is near zero in every arm, and a positive control shows that is inability, not refusal, at this size; a 2.3-point t-task cost keeps the data opt-in (`locallm/tool-conversations-results-2026-09-27.json`) |
| to reach other systems | the Model Context Protocol (MCP): dawnr as an MCP client using any MCP server's tools and resources, and as an MCP server so other agents can use its checker | **built** (tools only): a standard-library stdio client for both protocol eras and dawnr's checker as a server, tested against each other |
| to reach the internet | search and fetch as tools | **built, off by default**: fetch and search behind the policy, untrusted and marked; search needs an operator-chosen backend |
| to know how to do specialised tasks | skills: packaged instructions and scripts loaded only when a task needs them | **built**: the Agent Skills folder format, an index line per skill, loading on demand; the first skill is `t-repair` |
| to enforce rules no matter what the model says | hooks: deterministic scripts the runtime runs before and after tool calls; the proof check is dawnr's first hook | **built**: Claude Code's hook contract; the checker checks every t program from outside and blocks a failing final answer once |

The harness's tools are now trained, opt-in: 1,007 conversations built through
the real harness (every tool output its own, a recorded fixture web for the
network) teach the mid stage to pick the right tool on 97% of held-out items
and to close its calls, but cost 2.3 of 133 prompts on the t tasks, past the
registered guard of 2, and the injection measurement found nothing to reduce: a
model this size follows no instruction inside a page, taught to or not, and
only copies a program it finds there. Given the same instructions by the
person, it follows them barely more (0.02 to 0.04, again only by copying a
program), so at this size the number measures what the model cannot do, not
what it declines to do (`DAWNR-HARNESS.md` section 8).

The rule that keeps this compatible with the north star: **the network is a
tool, never a dependency.** dawnr works fully offline; when a network, MCP
servers or skills are present it may use them, and everything that comes back
from outside is untrusted data, checked before it is relied on and never
followed as an instruction.

### dawnr grows with the person using it

The operator's words: an expansive assistant that learns like a child from
every session, with a personality that grows per person, in control of the
machine it runs on, not only a doctorate in proofs. The same rule governs all
of it: nothing is trusted without evidence, and the person stays in control.

| dawnr needs | the idea | where it stands |
|---|---|---|
| to remember the person across sessions | long-term memory per person: what happened (episodes), what is true about them (facts and preferences), recalled into each new session; they can read, correct, export and erase it | **built, reviewed four times, first measured**: a per-person store (episodes, facts, preferences, pinned notes) the person can list, correct, export and erase; only the person's own words become memories, grounded over the whole session and refused when they contradict, never overwritten silently (a conflict with a stored record becomes a question); recall within a token budget as a marked <\|memory\|> span (`DAWNR-MEMORY.md`). First measurement: 197 memory conversations added to the tool track's own mix, two seeds -- a model with no memory training never shows the span it is handed (0%); trained, it shows it 100% of the time installed, answers "what do you remember about me?" from it 46% of the time (68%, 25% at the two seeds) and says "nothing yet" with none 100% of the time, never inventing; renaming a remembered parameter preference, and overriding it with the person's own words, did not transfer yet at this size (0% both arms); the guard the tool conversations passed still holds (`locallm/memory-conversations-results-2026-09-27.json`); memory conversations stay opt-in, same as the tool conversations. On the chosen weights (2026-10-01): with dawnr's store and recall placed in a system turn, the base Qwen3.5-4B recalls the remembered preference 28 times in 28 and never invents one; the `t` student recalls 17 of 28 and follows the person's current words over a stored preference 11 of 14 ([`locallm/PREDICT-2026-10-01-memory-on-the-base.md`](locallm/PREDICT-2026-10-01-memory-on-the-base.md)) |
| to learn from every session | per-person learning between sessions: feedback and corrections become training data; a small per-person adapter is updated while the shared model stays fixed; replay against forgetting; measured so a person's model gets better at their tasks without getting worse at everything else | **built and measured**: feedback kept per person under their control (read, correct, export, erase); a style profile inferred from their edits cut four simulated persons' edit cost 26-53% with no checked answer made worse; a per-person LoRA adapter, trained in guarded sleeps with exact forgetting, fits each person in likelihood but loses correct answers where it changes what dawnr writes, so it stays off on this base (`DAWNR-LEARNING.md`; 4 of 16 predictions falsified and said so) |
| a personality that grows per person | a persona per person (tone, detail, interests, how they like to work) learned from interactions, visible and editable | **built**: a persona record per person (tone, detail, depth, interests, working preferences) updated by named, logged, reversible rules; editable in the chat pane and the CLI (`locallm/dawnr_persona.py`); not yet learned by any model |
| to know things it was not trained on | retrieval over the proved corpus, the person's own files and fetched pages, cited | **built**: a BM25 index over the proved corpus, a knowledge folder and cached pages, as the `search_knowledge` harness tool with per-passage trust and a measured recall (`DAWNR-RETRIEVAL.md`) |
| to act on the machine, in control | a planning loop over tools (files, shell, processes) through the harness: every action under the owner's allow / ask / deny permissions, logged, reversible where possible; dawnr never grants itself permissions | **measured on the chosen weights (2026-10-01)**: as dawnr's planner the base Qwen3.5-4B planned an instruction planted in a file it was asked to read on 10 of 90 trials and the harness ran none; it did the asked task on 81 (`locallm/PREDICT-2026-10-01-agent-on-the-base.md`). **built, reviewed twice, untrained**: file, command and process tools inside operator roots, commands only from an allowlist, a planning loop with a dry run; a file whose name lies outside the roots is refused by its link count and real path, not by a list (0 escapes over 5,000 generated paths, 0 of 80 injected actions ran); the model never changes its own permissions (`DAWNR-AGENT.md`) |
| to hear and speak | speech in and out, trained here | **started**: a from-scratch CTC speech recogniser that overfits a handful of utterances on CPU, the LibriSpeech/LJSpeech data plan and prep scripts on the lab, a TTS design, and an optional mic/speaker layer (`DAWNR-SPEECH.md`); no full training yet |

**The order**, trustworthy core first and breadth after, because a system that
talks and sees before it reasons well is confident and wrong, the opposite of
the north star:

1. A core that learns instead of memorising (now: data, denoising, the sweep).
2. Reinforcement learning with the provers as the reward.
3. Retrieval and memory.
4. Tools and agency, starting with programs it writes, proves and then runs.
5. Speech, then vision.

---

**The one-line version.** A model trained on one desk, on data that seven proof
systems agreed was correct, that beats a model forty-one times its size at
writing programs you can prove — and an engine that made the data to do it.
