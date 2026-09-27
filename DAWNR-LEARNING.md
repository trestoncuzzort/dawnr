# dawnr learns from each person

AMBITION.md asks for an assistant that "learns like a child from every
session", per person, with the person in control. This file is the account of
the first working loop: what dawnr keeps when a person tells it an answer was
right, wrong or not what they wanted; how that becomes a small adapter that is
theirs alone; how the shared model is protected while it happens; and what the
measurement found. The code is `locallm/dawnr_learning/` and the LoRA layer in
`locallm/model.py`; the tests are `locallm/test_learning.py`.

The loop, in one line: **a session** (dawnr answers, the person rates, edits or
says "that's wrong") → **the person's store** (every answer with its feedback
and provenance, checked by the t tool) → **a sleep** between sessions (a LoRA
adapter for that person on the frozen base, trained on their examples with
replay, kept only if two guards pass) → **the next session** runs with the
adapter on.

RESULTS_PLACEHOLDER

## 1. Feedback, per person (`feedback.py`, standard library only)

Every answer dawnr gives in a conversation can become a record in the person's
store, with what came before it (the conversation), the answer, the weights that
wrote it (the base checkpoint's sha256), the session, the time, and then the
person's feedback:

| feedback | what the person did | what is trained on |
|---|---|---|
| `up` | "Good": the answer is what they wanted | the answer as it is |
| `down` | "Not this", with nothing better given | nothing (kept, counted) |
| `edit` | "Correct...": they rewrote it | their version |
| `wrong` | a "that's wrong" turn | their program, if the same message carries one; otherwise nothing |

Two rules decide what may be trained on, and both are counted rather than
silently applied: **a target whose program fails the t tool on the prompt's own
Example lines is not trained on** (dawnr's checker, `dawnr_harness.checker`,
the same check the harness uses), and **an answer that carries text from
outside** (a tool output marked `<|untrusted|>`: a web page, an MCP result) is
kept for the person to read but never trained on. At sleep time every example
also passes the held-out gates every trainer here applies
(`loop_filter.validate_training_data` over the evaluation ids and same-task
exclusions, plus the r12 dev ids), whatever the person typed.

The "that's wrong" detector is a regular expression anchored at the start of
the person's message, following the self-feeding chatbot (Hancock et al.,
arXiv:1901.05415), whose own regular-expression detector measured precision
0.91 and recall 0.27. The trade is taken deliberately: a match marks an answer
wrong, so false alarms must be rare, and the buttons carry what the expression
misses. It never trains on anything by itself.

**The person controls it.** Learning is off until the person turns it on in
the chat window's settings (with a name for their own folder). Every step says
in the transcript what was kept. From a terminal:

    python3 locallm/dawnr_learning people
    python3 locallm/dawnr_learning show NAME            # read every record
    python3 locallm/dawnr_learning export NAME --out me.json
    python3 locallm/dawnr_learning forget NAME ID       # erase one record
    python3 locallm/dawnr_learning forget-all NAME --yes
    python3 locallm/dawnr_learning status NAME --model <chat checkpoint>
    python3 locallm/dawnr_learning sleep NAME --model <chat checkpoint> \
        --replay <its chat_data conversations> --guard-text <held-out plain source>

Erasing keeps only a tombstone (the record's id and the time), never content.
The data lives in the platform's per-user data folder (platformdirs'
`user_data_dir` convention: `~/.local/share/dawnr/people` on Linux), never
beside a checkpoint in this public repository; `DAWNR_PEOPLE_DIR` moves it.

**Hooks in shared files, kept to a line each.** `chat_pane.py`: an optional
`people_root`; after the model loads, the person's adapter is attached; each
user turn is shown to the detector; each finished reply is recorded; three
buttons (Good, Not this, Correct...) and a settings checkbox with a name field.
`home.py`: passes the per-user folder to the pane. Everything else is in
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
   assistant's tokens only;
4. the product's early stopping (`train.EarlyStopper`: stop after `patience`
   checks without improvement beyond noise, keep the best), with every
   candidate state first checked by the **behaviour guard** (below);
5. the **plain-code guard**: the adapter's loss on fixed windows of held-out
   plain source code (the core's own validation text) against the base's; a
   rise over 0.05 nats per token refuses the adapter;
6. save with the manifest; the person keeps their previous adapter when a
   sleep is refused.

**The behaviour guard** exists because of the pilot (section 5): a loss cannot
see the failure that matters. Eight prompts from the base's training side
(never the person's, never held out, never replayed in the same sleep) are
answered greedily with the adapter on and judged by the t tool; a state is
kept only while it passes at least as many as the frozen base, less one. The
first check that falls below ends the sleep, and the last accepted state is
the result; if none was accepted, the person keeps what they had. It is
dawnr's rule that nothing is relied on before it is checked, applied to
dawnr's own weights.

`continue` mode (built and tested, **not measured**): starts from the previous
adapter, plans its steps from the examples it has not seen, draws half of the
person's rows from the older ones (Rolnick's replay of past events), and can
anchor to the previous adapter with EWC (Kirkpatrick et al., arXiv:1612.00796:
a quadratic penalty weighted by the diagonal Fisher of the examples it was
trained on, computed with `fisher=True` and saved beside it). Its cost grows
with the new examples, not the whole store. It refuses a stale adapter, since
continuing would keep what the person asked to forget.

## 5. The measurement

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
trained on); eight more training-side prompts are the behaviour guard's, and
the rest are the replay pool. The same problems for every arm, seed and person.
Dev: the 100 r12 dev problems (MBPP, English prompts), graded by `rl_reward`'s
tiers as `chat_eval.py` does. Predictions were committed before the runs:
`locallm/PREDICT-learning-2026-09-27.md` (arms A and B) and
`locallm/PREDICT-learning-profile-2026-09-27.md` (arm P).

**The pilot** (declared in the prediction; the pilot person `eve` only, other
problems, never part of a result) is why the behaviour guard exists: at a
learning rate of 1e-3 and no guard the adapter fitted eve's style to 0.46 nats
per token on held-out examples of it (the base: 2.42) and wrote it (adherence
0.11 to 0.62), while the answers that passed the t tool fell from 22 of 39 to 5.
At 3e-4 with the guard nothing broke and nothing visible changed; at 1e-3 with
the guard every sleep was refused at its first check.

MEASUREMENT_RESULTS_PLACEHOLDER

## Sources, each fetched and read before the code it shaped

| what | source | taken | differs |
|---|---|---|---|
| the adapter | Hu et al., LoRA, arXiv:2106.09685; github.com/microsoft/LoRA `loralib/layers.py` | frozen W0, B A beside it, A random and B zero, alpha / r, untuned alpha | MLP adapted too; merge is explicit; switch-off in place |
| forgetting | Biderman et al., "LoRA Learns Less and Forgets Less", arXiv:2405.09673 | LoRA keeps the base's out-of-domain skill better than weight decay or dropout | measured here, not assumed |
| one module per person | Tan et al., OPPU, arXiv:2402.04401 | a per-user LoRA on a frozen, task-adapted base | attention and MLP; guards before keeping |
| learning from edits | Gao et al., PRELUDE/CIPHER, arXiv:2404.15269 | simulated users with latent preferences; edit distance in tokens as the cost per round | the persons are programs over t's syntax tree, and every edit is checked by the t tool |
| deployment feedback | Hancock et al., arXiv:1901.05415 | keep the person's feedback as data; a high-precision regex first; retrain between batches | no satisfaction classifier yet (no labelled data) |
| replay | Rolnick et al., arXiv:1811.11682; Ibrahim et al., arXiv:2403.08763 | replay past events; a random-discard cap; a fixed share of each batch from the old data | |
| consolidation | Kirkpatrick et al., EWC, arXiv:1612.00796 | diagonal Fisher, quadratic anchor | on the adapter only; not measured |
| exact forgetting | Bourtoule et al., SISA, arXiv:1912.03817 | retraining without the erased data is exact | no sharding: the store is small |
| where data lives | github.com/tox-dev/platformdirs | the per-user data folder per platform | standard library, no dependency |
