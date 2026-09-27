# What this project is actually for

The operator's goals, in the operator's terms, with the measured state beside
each one so the gap is always visible. This file is the target. `ROADMAP.md` is
the route, and every number here links to the run that produced it. The ideas
being worked toward are kept at the end of this file, stated plainly, with
where each one stands.

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

## 2. locallm is the product

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
  **358 (171,182)** on 2026-09-26: Dafny lifts 136, Verus 21, Lean 5, ACSL 2
  (`t/LIFT-2026-09-26.md`, `t/LIFT-VERICODING-VERUS-LEAN.md`,
  `t/LIFT-ACSL-BY-EXAMPLE.md`). With graded trust (`--min-kernels 6`: six
  provers clean, none contradicting, the gap recorded per document) it is
  **470 documents (260,157 characters)**; the 112 admitted with a gap miss
  Lean 35, Rocq 35, Frama-C 28, SPARK 10, others 4. Those three lowerings
  are the next lever.
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

dawnr is the assistant this project is building: trained here from random
weights, running on its own hardware with nothing behind it, able to
understand, reason, act and remember, and trustworthy because what it produces
is checked before anyone relies on it. It is a system, not one model. Each
machine-learning idea earns its place by doing one job in it, and every part
is judged by the same rule: nothing is trusted without evidence.

| dawnr needs | the machine-learning idea | where it stands |
|---|---|---|
| a brain that understands language and code | transformer pretraining from random weights | **built**: the locallm core; the weight-decay sweep is running. It has no general-English layer underneath (pretrained directly on ~150 MB of source code); surveyed, budgeted and decontaminated but not yet run (`internal/PRETRAIN-DAWNR-GENERAL.md`) |
| to learn, not memorise | regularisation, denoising (fill in the middle), early stopping, more verified data | **in progress** |
| to know when it is right | verification as the judge, calibration, uncertainty, refusal | **the seven-kernel proof engine is this**; calibration not started |
| to get better at reasoning | reinforcement learning with the verifier as the reward | **built, waiting on data**: tiered proof reward inspected by hand, GRPO trainer (Dr. GRPO advantages hold; plain GRPO unlearned). The model solves 0.6% of problems outside its corpus, too few to reinforce, so new verified data comes first (`t/RL-DESIGN-2026-09-26.md`) |
| to know what it was not trained on | retrieval, embeddings, a vector index | not started |
| to remember the person and past work | long-term memory, continual learning without forgetting | not started (replay against forgetting exists in the fine-tune) |
| to do things, not only talk | tool use, agents, planning | **started**: a chat pipeline adapted from nanochat (`DAWNR-PIPELINE.md`) runs end to end; the model can call the t interpreter on its own draft mid-answer, and every call closes. Repair conversations from its own cross-fitted drafts taught it to act on a failed check (a new program after 55-70% of failing verdicts) but not yet to fix more answers than seed noise (+1.2 of 133 at six fresh seeds; `locallm/FINDINGS-repair-2026-09-26.md`); next: the tool checks the user's specification is kept, repairs as edits, RL through the engine |
| to hear and speak | speech recognition, text to speech | not started |
| to see | vision encoders, multimodal models | later |
| to fit small hardware | quantisation, distillation, mixture of experts | partly: runs with no PyTorch, on a CPU |
| to be understood from inside | interpretability, sparse autoencoders | planned |
| to improve itself safely | the data engine: generate, verify, keep only what is proved, retrain | **built** |

### dawnr's harness: reaching past itself

dawnr is meant to be a full assistant built on everything machine learning and
the sciences around it can contribute, not only a model. Around the model sits
a harness, the way an agent runtime wraps a language model:

| dawnr needs | the idea | where it stands |
|---|---|---|
| to act through tools | a tool-calling engine: the model emits a call, the runtime executes it, the result returns into the context | **built, untrained**: a tool registry with a permission per tool (allow, ask, deny) and a call syntax in the chat format; the t interpreter is its first tool (`DAWNR-HARNESS.md`) |
| to reach other systems | the Model Context Protocol (MCP): dawnr as an MCP client using any MCP server's tools and resources, and as an MCP server so other agents can use its checker | **built** (tools only): a standard-library stdio client for both protocol eras and dawnr's checker as a server, tested against each other |
| to reach the internet | search and fetch as tools | **built, off by default**: fetch and search behind the policy, untrusted and marked; search needs an operator-chosen backend |
| to know how to do specialised tasks | skills: packaged instructions and scripts loaded only when a task needs them | **built**: the Agent Skills folder format, an index line per skill, loading on demand; the first skill is `t-repair` |
| to enforce rules no matter what the model says | hooks: deterministic scripts the runtime runs before and after tool calls; the proof check is dawnr's first hook | **built**: Claude Code's hook contract; the checker checks every t program from outside and blocks a failing final answer once |

None of the harness is learned yet: today's checkpoints can use only the t
tool. `DAWNR-HARNESS.md` section 8 lists the conversations each piece needs.

The rule that keeps this compatible with the north star: **the network is a
tool, never a dependency.** dawnr works fully offline; when a network, MCP
servers or skills are present it may use them, and everything that comes back
from outside is untrusted data, checked before it is relied on and never
followed as an instruction.

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
