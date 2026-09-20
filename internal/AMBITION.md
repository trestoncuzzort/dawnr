# What this project is actually for

The operator's goals, in the operator's terms, with the measured state beside
each one so the gap is always visible. This file is the target. `ROADMAP.md` is
the route, and every number here links to the run that produced it.

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
data buys parameter efficiency**, stated as a curve rather than a point: 3.2M,
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

The twins are the artifact most likely to outlive the score: 426 verified
programs, each paired with a near-miss, the input that separates them, and
seven independent refutations. Nothing comparable has been found published.

---

**The one-line version.** A model trained on one desk, on data that seven proof
systems agreed was correct, that beats a model forty-one times its size at
writing programs you can prove — and an engine that made the data to do it.
