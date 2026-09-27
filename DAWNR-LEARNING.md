# dawnr learns from each person

AMBITION.md asks for an assistant that "learns like a child from every
session", per person, with the person in control. This file is the account of
the first working loop: what dawnr keeps when a person tells it an answer was
right, wrong or not what they wanted; the two ways it learns from that (a
small adapter of weights that is theirs alone, and a visible profile of their
taste); how the shared model is protected while it happens; and what the
measurement found. The code is `locallm/dawnr_learning/` and the LoRA layer in
`locallm/model.py`; the tests are `locallm/test_learning.py`.

The loop: **a session** (dawnr answers; the person rates, edits or says
"that's wrong") → **the person's store** (every answer with its feedback and
provenance, checked by the t tool) → **between sessions** a sleep (a LoRA
adapter for that person on the frozen base, kept only if its guards pass) and a
refreshed style profile → **the next session** runs with both.

## What was found (2026-09-27; section 7 has the numbers)

On four simulated persons with distinct, fixed tastes (section 6), each giving
four sessions of ten corrections on dawnr's r12 chat model (92.9M parameters),
measured on 53 held-out prompts and the 100 dev problems, with the predictions
committed before every run:

- **The style profile works now.** Inferred from the person's own edits by vote
  (section 5), it knew each person's whole mechanical taste after one session
  and cut their relative edit cost by 26% (ada), 51% (bo), 43% (cy) and 53% (di)
  with **nothing made worse**: the held-out answers the t tool passes stayed 33
  of 53 and dev problems at least typed 37 of 100, for every person. After the
  first session bo, cy and di accept every answer the t tool passes unchanged;
  what they still correct is the answers dawnr gets wrong. ada still edits every
  answer, for the explanation line the profile does not write.
- **A per-person adapter learns the person, but only in likelihood.** With the
  default sleep (arm A, two seeds) each person's held-out loss on their own style
  fell by 27% to 65%, and each person's own adapter fitted them best of the four
  in 8 of 8 person-seeds. But for three of four persons dawnr's greedy answers
  hardly changed (adherence +0.005 to +0.030) and their edit cost did not fall
  (bo's rose by a third).
- **Where an adapter did change the writing, it cost correct answers.** cy's
  adapter wrote cy's style (adherence 0.77 to 0.98) and the held-out answers the
  t tool passes fell from 33 to 17 and 16 of 53 in the two seeds (dev 37 to 21
  and 16), while the canonical validation loss moved by only +0.03 and +0.02,
  and the 8-prompt behaviour guard passed 7 or 8 of 8 at every check it
  accepted (it stopped one of cy's eight sleeps, at its fifth check). At a
  higher learning rate with no behaviour guard (arm B) every person's style was
  adopted more (adherence +0.09 to +0.41) and correct held-out answers fell for
  all four (by 7 to 25). On this memorised base, what an adapter changes in
  dawnr's writing and what it costs move together.
- **A larger guard halves the damage but does not remove it.** With 24 guard
  prompts instead of 8 (arm C) cy's adapter kept 24 of the 33 correct held-out
  answers instead of 16 or 17, and was the one adapter whose person edited a
  little less (relative cost 0.215 to 0.197); the others learned almost nothing
  visible and cost 2 correct answers each. The guard's prompts are ones the base
  memorised, and every state it accepted for cy passed 21 to 23 of 24 while
  cy's held-out answers fell: it measures recall, and the damage is to what
  dawnr does on prompts it has not seen. The next guard asks unfamiliar prompts
  (section 8).
- **The measurement caught three defects in this track's own code**, each fixed,
  tested and re-run (section 7), and one in the base: chat mid-training raised
  the core's loss on held-out plain code from 2.70 to 4.42 nats per token.

So the loop runs end to end with the person in control, and today dawnr learns a
person's taste safely through the profile; the per-person adapter, its exact
forgetting and its guards are in place for a base that generalises, and the
measurement says plainly that on this one it does not help yet.

## 1. Feedback, per person (`feedback.py`, standard library only)

Every answer dawnr gives in a conversation can become a record in the person's
store, with what came before it (the last few turns), the answer, the weights
that wrote it (the base checkpoint's sha256), the session, the time, and then
the person's feedback:

| feedback | what the person did | what is learned from |
|---|---|---|
| `up` | "Good": the answer is what they wanted | the answer as it is |
| `down` | "Not this", with nothing better given | nothing (kept, counted) |
| `edit` | "Correct...": they rewrote it | their version |
| `wrong` | a "that's wrong" turn | their program, if the same message carries one; otherwise nothing |

Two rules decide what may be learned from, and both are counted rather than
silently applied: **a target whose program fails the t tool on the prompt's own
Example lines is not used** (dawnr's checker, `dawnr_harness.checker`), and
**an answer that carries text from outside** (a tool output marked
`<|untrusted|>`: a web page, an MCP result) is kept for the person to read but
never trained on. Every example also passes the held-out gates every trainer
here applies (`loop_filter.validate_training_data` over the evaluation ids and
same-task exclusions, plus the r12 dev ids), whatever the person typed --
`training_examples()` applies this gate itself, for every reader (a sleep, the
style profile, the measurement protocol) and not only at sleep time; section 8
discloses the gap this closed.

The "that's wrong" detector is a regular expression anchored at the start of
the person's message, following the self-feeding chatbot (Hancock et al.,
arXiv:1901.05415), whose own regular-expression detector measured precision
0.91 and recall 0.27. The trade is taken deliberately: a match marks an answer
wrong, so false alarms must be rare, and the buttons carry what the expression
misses. It never trains on anything by itself.

**The person controls it.** Learning is off until the person turns it on in
the chat window's settings, with a name for their own folder; every step says
in the transcript what was kept. From a terminal:

    python3 locallm/dawnr_learning people
    python3 locallm/dawnr_learning show NAME            # read every record
    python3 locallm/dawnr_learning export NAME --out me.json
    python3 locallm/dawnr_learning forget NAME ID       # erase one record
    python3 locallm/dawnr_learning forget-all NAME --yes
    python3 locallm/dawnr_learning profile NAME [--pin indent=4]
    python3 locallm/dawnr_learning status NAME --model <chat checkpoint>
    python3 locallm/dawnr_learning sleep NAME --model <chat checkpoint> \
        --replay <its chat_data conversations> --guard-text <held-out plain source>
    python3 locallm/dawnr_learning sleep-all --model <chat checkpoint> ...   # a nightly timer

Erasing keeps only a tombstone (the record's id and the time), never content.
The data lives in the platform's per-user data folder (platformdirs'
`user_data_dir` convention: `~/.local/share/dawnr/people` on Linux), never
beside a checkpoint in this public repository; `DAWNR_PEOPLE_DIR` moves it, and
only folders the store creates are made private.

**Hooks in shared files, a line or two each.** `chat_pane.py`: an optional
`people_root`; before every reply the model is made to carry exactly what the
settings say (`PaneLearning.sync`: the named person's fresh adapter on, anyone
else's off, nothing when learning is off); each user turn is shown to the
detector; each finished reply is put in the person's style when their profile
knows it (shown open as "in your style") and recorded; three buttons (Good,
Not this, Correct...) and a settings checkbox with a name field. `home.py`:
passes the per-user folder to the pane. Everything else is in
`dawnr_learning/pane.py`. The engine needs no hook: an adapter sits inside the
model's own layers, so generation, the KV cache and the tool loop are unchanged.

## 2. LoRA in the model (`model.py`, off by default)

`add_lora(model, r, alpha, dropout)` freezes every parameter and wraps each
block's attention projections and MLP (`attn.c_attn`, `attn.c_proj`, and
`mlp.c_fc`/`mlp.c_proj` or `mlp.gate_up`/`mlp.c_proj` in the modern
architecture) in a `LoRALinear`: h = W0 x + (alpha / r) B A x, A initialised as
`nn.Linear` initialises its weight and B zero, so the adapted model starts
exactly at the base (Hu et al., arXiv:2106.09685; the layer follows
microsoft/LoRA's `loralib/layers.py`). The paper adapts attention only; the
MLP is adapted too, as the operator asked and as the repo's peft recipe for the
Phi student already does. Two deliberate differences from loralib: merging is
an explicit call (`merge_lora`, an export), never a side effect of `.eval()`,
and an adapter can be switched off in place (`set_lora_enabled`), which gives
the frozen base's own predictions as the reference. `remove_lora` restores the
model bit for bit (`base_fingerprint` is checked by the tests and by every
sleep). At rank 8 on the 92.9M core an adapter is 1,179,648 parameters,
4.7 MB; the cap is 16 MB.

## 3. One adapter per person (`adapters.py`)

The shape is OPPU's (Tan et al., arXiv:2402.04401): one small PEFT module per
user, plugged into a shared, frozen, already task-adapted base; the base never
sees anyone's data. Each adapter is stored under
`<person>/adapters/<first 16 hex of the base's sha256>/` with a manifest: the
base (checkpoint sha256 and tokenizer fingerprint; an adapter is refused on any
other base), every example it was trained on by record id and content hash,
its size, and the sleep's own record. **Exact forgetting:** if the person
erases or corrects an example the adapter learned from, the adapter is stale
and is not attached again until a sleep rebuilds it without that example
(retraining from what remains is the exact unlearning baseline that SISA,
arXiv:1912.03817, makes cheaper; at this size it is cheap on its own).

## 4. The sleep (`sleep.py`)

Between sessions, for one person:

1. their examples, checked and gated (section 1); beyond a cap, a seeded random
   subset (Rolnick et al., arXiv:1811.11682: random discarding from a capped
   replay buffer does almost as well as keeping everything);
2. a hash split into train and validation;
3. a fresh LoRA adapter (`rebuild`, the default: exact, an erased example is
   simply absent) trained on batches mixing the person's rows with a fixed
   number of rows replayed from the base's own training conversations
   (Ibrahim et al., arXiv:2403.08763, the repo's replay rule), loss on the
   assistant's tokens only; a batch over 5,120 padded tokens is accumulated in
   parts weighted by supervised tokens, so it is the same step
   (https://huggingface.co/blog/gradient_accumulation);
4. the product's early stopping (`train.EarlyStopper`: stop after `patience`
   checks without improvement beyond noise, keep the best), with every
   candidate state first checked by the **behaviour guard** (below);
5. the **plain-code guard**: the adapter's loss on fixed windows of held-out
   plain source code (the core's own validation text) against the base's; a
   rise over 0.05 nats per token refuses the adapter;
6. save with the manifest; the person keeps their previous adapter when a
   sleep is refused.

**The behaviour guard** exists because of the pilot (section 6): a loss cannot
see the failure that matters. Prompts from the base's training side (never the
person's, never held out, never replayed in the same sleep) are answered
greedily with the adapter on and judged by the t tool; a state is kept only
while it passes at least as many as the frozen base, less one. The first check
that falls below ends the sleep, and the last accepted state is the result; if
none was accepted, the person keeps what they had. It is dawnr's rule that
nothing is relied on before it is checked, applied to dawnr's own weights.
Arm A measured it with 8 prompts and arm C with 24; 8 were too few to see the
damage that mattered, and 24 saw half of it (section 7). The product's sleep
asks 24; without the base's conversations on the machine it asks the person's
own validation prompts instead, and every sleep also refreshes the person's
style profile.

`continue` mode (built and tested, **not measured**): starts from the previous
adapter, plans its steps from the examples it has not seen, draws half of the
person's rows from the older ones (Rolnick's replay of past events), and can
anchor to the previous adapter with EWC (Kirkpatrick et al., arXiv:1612.00796:
a quadratic penalty weighted by the diagonal Fisher of the examples it was
trained on, computed with `fisher=True` and saved beside it). Its cost grows
with the new examples, not the whole store. It refuses a stale adapter, since
continuing would keep what the person asked to forget.

## 5. The style profile (`style_profile.py`, no weights)

Some of a person's taste is mechanical and can be learned without touching the
model. CIPHER (Gao et al., PRELUDE, arXiv:2404.15269) keeps the base frozen,
infers a preference from each of the user's edits, aggregates the past ones and
applies them to the next answer, and the user can read and change what was
inferred. The same shape without a language model in the loop (a 92M model
cannot describe a preference): five dimensions are voted on by the person's own
targets (the local naming convention, semicolons, indentation, the if form of
a two-way assignment, and whether they want the checker's verdict shown), a
dimension is decided only with at least three votes of which three quarters
agree, and the person can pin any of them by hand. The next answer is rewritten
on the decided dimensions with the same capture-free, tree-preserving rewrites
the synthetic persons use; a rewrite the t tool fails where the original passed
is not used, and an answer that is not well formed is shown as dawnr wrote it
(a rename is only capture-free in a well-formed program: section 7 has the
defect that taught this). What it cannot see (free text such as an explanation
before the program, or any taste outside the five) it does not guess; the
adapter remains the learner for everything else.

## 6. The measurement

**The protocol is PRELUDE's** (Gao et al., arXiv:2404.15269): every round the
assistant answers, a simulated person edits the answer to their latent
preference, and the token edit distance between answer and edit is the cost
of the round; a learner should drive it down. Here the persons are programs
over t's syntax tree (`persons.py`), so every edit is exact, reproducible
offline, and checked by the t tool:

| person | local names | semicolons | indent | two-way assignment | before the program | shows the checker |
|---|---|---|---|---|---|---|
| ada | `myIndex` | yes | 2 | if statement | "Approach: 1 loop with 2 invariants; local myI; the result is s." | yes |
| bo | `k1`, `k2` | no | 2 | if statement | nothing | no |
| cy | `cur_index` | yes | 2 | `x := if c then a else b` | nothing | yes |
| di | `INDEX` | yes | 4 | if statement | nothing | no |

A person keeps dawnr's program when the t tool passes it on the prompt's
examples (rewritten in their style: an edit, or a thumbs up if it already was),
and otherwise says "that's wrong" and gives the reference program in their
style. Renames are capture-free and case-insensitively distinct (SPARK does not
distinguish case), formatting is checked to leave the parse tree unchanged, and
all 358 programs of the proved corpus restyle for every person, pass the t tool
restyled, and are fixed points of their own person (checked over the corpus
while this was built; `test_learning.py` checks the same properties on
programs with a loop, a two-way branch and a quantifier that shadows a local).

**The base** is the chat model the pipeline measured (the r12 core,
chat mid-trained on the 358-document proved corpus: 92.9M parameters). Every
prompt comes from its training side; four sessions of ten prompts per person;
held out: twenty training-side prompts (also the fixed probe of the learning
curve) and the 33 validation-side conversations (documents the base never
trained on); the behaviour guard's prompts come from the rest of the training
side, and what remains is the replay pool. The same problems for every arm,
seed and person. Dev: the 100 r12 dev problems (MBPP, English prompts), graded
by `rl_reward`'s tiers as `chat_eval.py` does, with the answer's program taken
as its last t call, else the first program in its text. Predictions were
committed before each run: `locallm/PREDICT-learning-2026-09-27.md` (arms A and
B), `locallm/PREDICT-learning-profile-2026-09-27.md` (arm P, whose module was
then named `profile.py`) and `locallm/PREDICT-learning-guard-2026-09-27.md`
(arm C).

| arm | learner | learning rate | behaviour guard | seeds |
|---|---|---|---|---|
| A | adapter | 3e-4 | 8 prompts, tolerance 1 | 1, 2 |
| B | adapter | 1e-3 | none (the plain-code guard stays) | 1 |
| C | adapter | 3e-4 | 24 prompts, tolerance 1 | 1 |
| P | style profile | - | - | deterministic |

**The pilot** (declared in the prediction; the pilot person `eve` only, other
problems, never part of a result) is why the behaviour guard exists: at a
learning rate of 1e-3 and no guard the adapter fitted eve's style to 0.46 nats
per token on held-out examples of it (the base: 2.42) and wrote it (adherence
0.11 to 0.62), while the answers that passed the t tool fell from 22 of 39 to 5.
At 3e-4 with the guard nothing broke and nothing visible changed; at 1e-3 with
the guard every sleep was refused at its first check.

## 7. Results

Every number here is printed by
`python3 locallm/dawnr_learning/summarize.py <run dir>` from what `measure.py`
and `measure_profile.py` wrote; the verdict lines at the end of that output are
`check_predictions`, which reads the same numbers. The base, on the 53 held-out
prompts: 33 answers pass the t tool (41 well formed, 49 parse); 37 of the 100
dev problems at least typed and none passing its tests; plain-code loss 4.421
nats per token; canonical validation loss 0.277.

Relative edit cost is the person's token edit distance divided by the length of
the version they wanted (lower is better); adherence is the share of their
preferences an answer follows; "pass" is held-out answers the t tool passes (of
53, base 33); "dev" is dev problems at least typed (of 100, base 37).

| arm | person | own style loss | relative edit cost | adherence | pass | dev | sleeps the guard stopped |
|---|---|---|---|---|---|---|---|
| A-s1 | ada | 1.784 → 1.301 | 0.295 → 0.299 | 0.548 → 0.562 | 30 | 33 | 3 of 4 |
| A-s1 | bo | 0.700 → 0.426 | 0.269 → 0.356 | 0.542 → 0.570 | 33 | 33 | 4 of 4 |
| A-s1 | cy | 0.661 → 0.234 | 0.215 → 0.262 | 0.767 → 0.978 | **17** | **21** | 0 of 4 |
| A-s1 | di | 0.894 → 0.569 | 0.294 → 0.294 | 0.542 → 0.561 | 32 | 35 | 4 of 4 |
| A-s2 | ada | 1.784 → 1.299 | 0.295 → 0.300 | 0.548 → 0.553 | 31 | 33 | 3 of 4 |
| A-s2 | bo | 0.700 → 0.434 | 0.269 → 0.362 | 0.542 → 0.566 | 32 | 32 | 4 of 4 |
| A-s2 | cy | 0.661 → 0.241 | 0.215 → 0.296 | 0.767 → 0.982 | **16** | **16** | 1 of 4 |
| A-s2 | di | 0.894 → 0.565 | 0.294 → 0.314 | 0.542 → 0.572 | 31 | 34 | 4 of 4 |
| B-s1 | ada | 1.784 → 0.389 | 0.295 → **2.506** | 0.548 → 0.638 | **8** | **7** | (the plain-code guard refused sleeps 2 to 4) |
| B-s1 | bo | 0.700 → 0.217 | 0.269 → 0.268 | 0.542 → 0.918 | **21** | 32 | none |
| B-s1 | cy | 0.661 → 0.228 | 0.215 → 0.318 | 0.767 → 0.979 | **26** | **21** | none |
| B-s1 | di | 0.894 → 0.273 | 0.294 → 0.254 | 0.542 → 0.955 | **23** | 40 | none |
| C-s1 | ada | 1.784 → 1.301 | 0.295 → 0.305 | 0.548 → 0.553 | 31 | 35 | 3 of 4 |
| C-s1 | bo | 0.700 → 0.436 | 0.269 → 0.361 | 0.542 → 0.570 | 31 | 35 | 4 of 4 (3 refused outright) |
| C-s1 | cy | 0.661 → 0.250 | 0.215 → 0.197 | 0.767 → 0.909 | **24** | 31 | 1 of 4 |
| C-s1 | di | 0.894 → 0.564 | 0.294 → 0.302 | 0.542 → 0.551 | 31 | 35 | 4 of 4 |
| P | ada | - | 0.295 → 0.219 | 0.548 → 0.712 | 33 | 37 | - |
| P | bo | - | 0.269 → 0.131 | 0.542 → 0.904 | 33 | 37 | - |
| P | cy | - | 0.215 → 0.121 | 0.767 → 0.942 | 33 | 37 | - |
| P | di | - | 0.294 → 0.138 | 0.542 → 0.904 | 33 | 37 | - |

**The adapter is personal.** In both seeds each person's own adapter gives the
lowest loss on that person's style of the four adapters, and barely moves the
others' (seed 1; rows are whose adapter, columns whose style):

| adapter | ada | bo | cy | di |
|---|---|---|---|---|
| base | 1.784 | 0.700 | 0.661 | 0.894 |
| ada | **1.301** | 0.690 | 0.602 | 0.843 |
| bo | 1.776 | **0.426** | 0.642 | 0.928 |
| cy | 1.692 | 0.712 | **0.234** | 0.873 |
| di | 1.740 | 0.733 | 0.630 | **0.569** |

**The learning curve** on the fixed probe (20 held-out training-side prompts),
relative edit cost and answers passing the t tool after each sleep (0 is the
base), seed 1:

| person | arm | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|---|
| bo | A | 0.181 / 17 | 0.173 / 17 | 0.479 / 15 | 0.478 / 15 | 0.465 / 16 |
| cy | A | 0.119 / 17 | 0.093 / 17 | 0.119 / 17 | 0.219 / 12 | 0.236 / 8 |
| bo | P | 0.181 / 17 | 0.012 / 17 | 0.012 / 17 | 0.012 / 17 | 0.012 / 17 |
| cy | P | 0.119 / 17 | 0.021 / 17 | 0.021 / 17 | 0.009 / 17 | 0.009 / 17 |

The profile has learned the whole mechanical taste after one session of ten
edits; from then on bo, cy and di rate every answer that passes the t tool
"Good" unchanged (33 of 33 on the held-out prompts), and what they still edit is
the 20 answers dawnr gets wrong. ada still edits every answer: her Approach line
is free text the profile does not write.

**Two things only the generation-and-check measurements saw.** For cy (seed 1)
the canonical validation loss moved from 0.277 to 0.305 and the plain-code loss
fell (4.421 to 4.272) while held-out answers passing the t tool halved; and the
8-prompt behaviour guard passed 7 or 8 of 8 at every one of cy's seed-1 checks
while the fixed probe fell from 17 to 8. A loss could not see the damage, and a
guard of 8 memorised prompts was too small an instrument to. With 24 (arm C)
the guard stopped cy's fourth sleep (16 of 24 at its fourth check) but had
accepted states that already cost 9 correct held-out answers.

**The registered predictions** (`summarize.py`'s verdict lines, verbatim; P is
the fixed re-run of the profile arm, whose first run gave the same verdicts):

- held: A1 own style loss lower for every person-seed, median cut >= 20%: median 37%, not lower: none (8 person-seeds)
- held: A2 own adapter lowest on own style in >= 7 of 8: 8 of 8
- held: A3 (A-s1) adherence gain < 0.1 for at least 3 of 4: gains ada +0.014, bo +0.028, cy +0.211, di +0.019
- held: A3 (A-s2) adherence gain < 0.1 for at least 3 of 4: gains ada +0.005, bo +0.024, cy +0.215, di +0.030
- **FALSIFIED**: A4 not worse (held-out pass >= base-3, dev typed >= base-5, plain code <= base+0.05): A-s1/cy held-out pass 33->17; A-s1/cy dev typed 37->21; A-s2/cy held-out pass 33->16; A-s2/cy dev typed 37->16
- held: A5 the behaviour guard stops >= 4 of the sleeps: 23 of 32
- held: B6 adherence gain >= 0.2 for at least 3 of 4: ada +0.090, bo +0.376, cy +0.212, di +0.413
- held: B7 held-out pass falls by >= 5 for at least 3 of 4: ada -25, bo -12, cy -7, di -10
- held: B8 edit cost higher than base for at least 3 of 4: ada +362.2, bo +2.8, cy +18.5, di -5.1
- **FALSIFIED**: P1 adherence gain >= 0.3 for all 4: ada +0.164, bo +0.362, cy +0.175, di +0.362
- held: P2 relative cost cut >= 30% (ada 15%): ada 26%, bo 51%, cy 43%, di 53%
- held: P3 held-out pass and dev typed exactly the base's: ada 33/37, bo 33/37, cy 33/37, di 33/37
- held: P4 every decided dimension true, the four main ones decided: wrong none, undecided none
- held: C1 the 24-prompt guard stops or refuses >= 12 of 16 sleeps: 12 of 16
- **FALSIFIED**: C2 not worse (held-out pass >= base-3, dev typed >= base-5): cy pass 33->24, dev 37->31
- **FALSIFIED**: C3 adherence gain < 0.1 for every person: ada +0.005, bo +0.028, cy +0.142, di +0.009

What the failures say. A4 and C2 are the same failure at two guard sizes: the
guard's prompts are memorised ones, and an adapter can keep those while losing
unfamiliar ones. C3 failed on cy, the one person whose adapter changed the
writing, and it changed it at a cost (C2). P1 failed on the two persons with
the least room: cy's base adherence was already 0.77, so the most any learner
could add was 0.23, which the bar of 0.3 did not allow for (the base's numbers
were on disk when the prediction was written, and were not looked at); ada's
explanation line is a preference the profile cannot learn by design.

**Defects the measurement found in this track's own code**, each fixed and
tested before any number here was taken from it:

1. `dawnr_learning/profile.py` shadowed the standard library's `profile`
   module: `measure.py` runs as a script, so its folder is first on the path,
   and torch's import of `cProfile` imported it and failed. Five of the six
   first adapter jobs died at import; they were re-run on the renamed module
   (`style_profile.py`) with a byte-identical measurement path.
2. The first run of arm P changed one answer: the model had written a program
   whose local shadows a parameter (ill formed by t's scope rule), and the
   capture-free rename, which assumes a well-formed program, renamed every use
   of the name and so chose which name each use meant; the answer became well
   formed (41 to 42) though it still failed its examples. The profile now leaves
   an ill-formed answer as written; arm P was re-run (the table's P rows are
   the re-run; the first run's pass and dev counts were the same).
3. Arm B's first two jobs ran out of the 4.5 GB budget on a batch of eight long
   conversations; long batches are now accumulated in parts (section 4). Arm A
   seed 1 ran before this change, A seed 2, B and C after it.

**One finding about the base, not this track.** On the same 16 fixed windows of
the core's own held-out source code (`plain_code_loss.py`), the r12 core before
chat mid-training has a loss of 2.70 nats per token and the chat model built on
it 4.42: the 400 steps of chat mid-training forgot plain code. Every adapter
lowered it a little (4.15 to 4.38).

## 8. What is not done

- **The held-out gate was applied inconsistently, until 2026-09-27 (found by
  review, not by a run).** `sleep.gate_examples` screened a person's examples
  against the held-out ids, the same-task exclusions and the r12 dev ids
  before a sleep trained on them, but `style_profile.refresh` -- run from the
  chat pane's `sync()` on every window session and every person switch, and
  again after every sleep -- read `feedback.PersonStore.training_examples()`
  directly and never gated them. A person's feedback on a held-out or dev
  prompt could shape their style profile, and so dawnr's output, with no
  decontamination check at all; nothing in section 6 or 7's numbers depends on
  the style profile having seen a held-out prompt, since the simulated persons
  are only ever given training-side problems (measure.py, section 6), but the
  gap was real and undisclosed until now. Fixed at the root instead of at the
  one call site found: the gate (`feedback.held_out_gate`, the same function
  `sleep.gate_examples` now names) moved onto `training_examples()` itself, so
  every reader -- a sleep, the style profile, the measurement protocol -- gets
  only gated examples by default, and the one place that needs the person's
  unscreened words, export and an adapter's own erasure bookkeeping, asks for
  that by name (`include_ungated=True`); a test greps the package for any
  other reader asking for it. Needs `t/` (`loop_filter` and what it imports,
  which needs POSIX `fcntl`) wherever `training_examples()` is now called,
  including every pane sync; on a platform without it the pane's existing
  never-silent handling reports the profile as unreadable rather than
  crashing, but the profile stops working -- not measured on Windows, and no
  evidence this repository has ever run there.
- **Negative feedback is kept, not learned from.** A "Not this" or a "that's
  wrong" without a correction is recorded and counted and never trained on.
  KTO (arXiv:2402.01306) learns from unpaired good and bad examples against a
  reference model, and the frozen base with its adapter switched off is a free
  reference; not built.
- **`continue` mode and EWC** are built and tested, not measured.
- **The profile has five dimensions.** Free text (ada's explanation line) and any
  taste outside them need a learner that can describe a preference, which a
  model this size is not.
- **The terminal chat** (`chat_cli.py`) records nothing and attaches no adapter;
  the window does. A `--person` flag is the next step there.
- **No satisfaction classifier** for "that's wrong": there are no labelled dawnr
  conversations to train one on (Hancock et al.'s classifier beat their regular
  expression by 0.42 F1 at 1,000 examples).
- **Only simulated persons.** No real person's sessions have been measured.
- **A behaviour guard on unfamiliar prompts** is the next measurement: the same
  arm with the guard asking held-out conversations the base never trained on
  (kept out of the evaluation), since the damage an adapter does is to what
  dawnr writes on prompts it has not seen, which memorised guard prompts cannot
  show.
- **Adapters need a better base.** On today's memorised 92.9M chat core, what an
  adapter changes in dawnr's writing and what it costs in correct answers moved
  together in every arm; the machinery (per-person adapters, exact forgetting,
  two guards, the nightly sleep) is ready for a base that generalises.

## Sources, each fetched and read before the code it shaped

| what | source | taken | differs |
|---|---|---|---|
| the adapter | Hu et al., LoRA, arXiv:2106.09685; github.com/microsoft/LoRA `loralib/layers.py` | frozen W0, B A beside it, A random and B zero, alpha / r, untuned alpha | MLP adapted too; merge is explicit; switch-off in place |
| forgetting | Biderman et al., "LoRA Learns Less and Forgets Less", arXiv:2405.09673 | LoRA keeps the base's out-of-domain skill better than weight decay or dropout | measured here, not assumed |
| one module per person | Tan et al., OPPU, arXiv:2402.04401 | a per-user LoRA on a frozen, task-adapted base | attention and MLP; guards before keeping |
| learning from edits | Gao et al., PRELUDE/CIPHER, arXiv:2404.15269; github.com/gao-g/prelude | simulated users with latent preferences; token edit distance as the cost per round; a frozen base with preferences inferred from edits, aggregated and shown to the user | the persons and the profile are programs over t's syntax tree, and every edit and rewrite is checked by the t tool |
| deployment feedback | Hancock et al., arXiv:1901.05415 | keep the person's feedback as data; a high-precision regex first; retrain between batches | no satisfaction classifier yet (no labelled data) |
| replay | Rolnick et al., arXiv:1811.11682; Ibrahim et al., arXiv:2403.08763 | replay past events; a random-discard cap; a fixed share of each batch from the old data | |
| consolidation | Kirkpatrick et al., EWC, arXiv:1612.00796 | diagonal Fisher, quadratic anchor | on the adapter only; not measured |
| exact forgetting | Bourtoule et al., SISA, arXiv:1912.03817 | retraining without the erased data is exact | no sharding: the store is small |
| accumulation | https://huggingface.co/blog/gradient_accumulation | divide the summed token loss by the whole batch's token count | split only past a token budget |
| where data lives | github.com/tox-dev/platformdirs | the per-user data folder per platform | standard library, no dependency |
