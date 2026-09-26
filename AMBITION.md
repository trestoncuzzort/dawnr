# What this project is actually for

The operator's goals, in the operator's terms, with the measured state beside
each one so the gap is always visible. This file is the target. `ROADMAP.md` is
the route, and every number here links to the run that produced it. The ideas
being worked toward are kept at the end of this file, stated plainly, with
where each one stands.

## The north star: dawnr, a model you could trust on a spaceship

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
  graded in all seven kernels. *State:* the first lift added 108 documents;
  the proved corpus went from 194 to 302 (`t/LIFT-2026-09-26.md`). More lifts
  are being graded.
- **Denoising training.** Corrupt spans of each training document and train
  the model to restore them, so each document teaches many ways instead of
  being memorised one way (the T5 and BART objectives). *State:* being built.
- **Stop before memorising, keep the best.** Training stops when validation
  stops improving by more than run-to-run noise and keeps the best weights,
  not the last. *State:* in the product (`locallm/train.py`, the studio).
- **Weight decay against memorisation in pretraining.** A three-arm sweep of
  the core's pretraining (`internal/PRETRAIN-R12-2026-09-25.md`). *State:*
  one arm done, two running.
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
| a brain that understands language and code | transformer pretraining from random weights | **built**: the locallm core; the weight-decay sweep is running |
| to learn, not memorise | regularisation, denoising (fill in the middle), early stopping, more verified data | **in progress** |
| to know when it is right | verification as the judge, calibration, uncertainty, refusal | **the seven-kernel proof engine is this**; calibration not started |
| to get better at reasoning | reinforcement learning with the verifier as the reward | **started**: the reward and the feasibility gate first (`t/RL-DESIGN-2026-09-26.md`); the best fit of anything here, because the reward cannot be fooled |
| to know what it was not trained on | retrieval, embeddings, a vector index | not started |
| to remember the person and past work | long-term memory, continual learning without forgetting | not started (replay against forgetting exists in the fine-tune) |
| to do things, not only talk | tool use, agents, planning | not started; write a program, prove it, then run it |
| to hear and speak | speech recognition, text to speech | not started |
| to see | vision encoders, multimodal models | later |
| to fit small hardware | quantisation, distillation, mixture of experts | partly: runs with no PyTorch, on a CPU |
| to be understood from inside | interpretability, sparse autoencoders | planned |
| to improve itself safely | the data engine: generate, verify, keep only what is proved, retrain | **built** |

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
