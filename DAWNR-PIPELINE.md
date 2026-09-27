# dawnr's pipeline, mapped against nanochat

nanochat (Andrej Karpathy, MIT licence, https://github.com/karpathy/nanochat)
builds a small chat assistant end to end on one machine and drives every stage
from one script. This file maps its stages one by one onto what locallm and
the proof engine already have, says what is missing and what to take, and
where dawnr should differ and why. It ends with the order to port in.

The nanochat described here is the `master` branch as read on 2026-09-26 (a
read-only clone plus the GitHub pages for `runs/speedrun.sh`,
`nanochat/tokenizer.py`, `nanochat/engine.py`, `scripts/chat_sft.py`,
`scripts/chat_rl.py`, `scripts/chat_cli.py`). Two things changed there since
its first release and both matter here: mid-training was a separate
`scripts/mid_train.py` and is now folded into `chat_sft.py`, and the
`report.md` report card was deleted on 2026-07-02 (commit `f10bd751`, "delete
the whole report thing i think it was a bad idea it just bloats the code").

## The stages

### 0. The driver (`runs/speedrun.sh`)

**nanochat.** One bash script, top to bottom: environment, dataset download
(in the background while the tokenizer trains), tokenizer train and eval, base
pretraining and eval, SFT and eval, then "talk to it". Artifacts go to
`$NANOCHAT_BASE_DIR` (`~/.cache/nanochat`). About 1.5 hours on 8xH100 for the
d24 model. Stages are not individually resumable; `base_train.py` has
`--resume-from-step`.

**locallm/tup today.** No driver. Each stage is a separate command written out
in a handoff document (`t/RUN-NEXT-locallm-r12.md` section C: build the corpus,
`continue_from_checkpoint.py`, `t/pick_stopping_step.py`, `loop_locallm.py
generate`, `t/score_heldout.py`, `t/compare_arms.py`).

**Missing.** One command that runs every stage in order, skips a stage whose
outputs already exist for the same inputs, and refuses to continue from a
stage whose inputs changed.

**Take.** The shape (one script, stages in order, one output root), not bash:
a Python driver can hash each stage's inputs, record them, and be tested.
**Differ:** every stage writes a `stage.json` with the input hashes it ran on,
and a stage is "done" only when its outputs exist *and* its recorded inputs
match; a changed corpus reruns everything downstream. dawnr's rule is that a
number without the run behind it does not count, and a skipped stage whose
inputs silently changed is exactly that.

### 1. Tokenizer (`scripts/tok_train.py`, `scripts/tok_eval.py`)

**nanochat.** GPT-4-style byte-level BPE trained with `rustbpe`, served with
`tiktoken`; vocabulary 32,768 (2^15) on the first ~2B characters of the
pretraining data, each document capped at 10,000 characters; split pattern
with `\p{N}{1,2}` (numbers in pairs, measured best at 32K). Nine special
tokens are reserved at training time, *inside* the vocabulary size:
`<|bos|>`, `<|user_start|>` `<|user_end|>`, `<|assistant_start|>`
`<|assistant_end|>`, `<|python_start|>` `<|python_end|>`, `<|output_start|>`
`<|output_end|>`. `tok_eval` reports compression (bytes per token) against
GPT-2 and GPT-4 tokenizers on several text kinds. A `token_bytes` table lets
the loss be reported in bits per byte, invariant to vocabulary size.

**locallm today.** `locallm/data.py`: `CharTokenizer` (one id per corpus
character) and `BPETokenizer` (byte-level BPE via the `tokenizers` library,
full 256-byte alphabet, trained on whole documents of the training split,
refuses a tokenizer that cannot reproduce its own training text). The r12
core uses an 8,192-entry BPE. Sentinel tokens are appended *past* the base
vocabulary (`with_sentinels`, used by FIM in `locallm/fim.py`) where no
`encode()` of text can reach them. `tokenizer_fingerprint` identifies ids and
rules. No tokenizer evaluation (compression) is recorded anywhere.

**Missing.** Chat special tokens; a tokenizer report (characters per token on
the training and held-out documents).

**Take.** The special-token set and its roles. **Differ:** (a) they are
appended past the vocabulary end the way the FIM sentinels are, not reserved
at training time, because the core's tokenizer is frozen with its weights and
new rows are initialised to the mean embedding (Hewitt; already how
`continue_from_checkpoint.py` adds FIM rows); (b) the tool pair is
`<|t_start|>`/`<|t_end|>` (a t program for the t tool) rather than python;
(c) no `<|bos|>`: locallm documents are delimited by `DOC_END` ("\n\n") and
every chat row starts at its first token anyway (one conversation per row,
below). The tokenizer report is characters per token, since locallm reports
loss in nats per token and per character already.

### 2. Base pretraining (`scripts/base_train.py`, `scripts/base_eval.py`)

**nanochat.** GPT with a single dial, `--depth` (width = 64 x depth, head dim
128), context 2,048, sliding-window pattern `SSSL`; Muon for matrices, AdamW
for embeddings (lr 0.3) and unembedding (0.008), matrix lr 0.02, cautious
weight decay 0.28; 40 warmup steps, warmdown over the last 65% to 5% of peak;
the step count is set from a tokens:parameters ratio (default 12, speedrun
uses 8 for d24; Chinchilla is 20). Data is ClimbMix web text in parquet
shards (~170 shards for the speedrun), with a BOS-aligned best-fit packing
loader. `base_eval` reports the DCLM CORE score (22 tasks, centered
accuracy; GPT-2 is 0.2565), bits per byte on train and validation, and
samples.

**locallm today.** Built. `locallm/model.py` (GPT, `gpt` or `modern` with
RoPE/RMSNorm/SwiGLU), `train.py` (from scratch, early stopping with best-kept
weights), `train_distributed.py` (multi-GPU pretraining of the core on a
46M-character source corpus, weight-decay sweep done, `best.pt` kept),
`continue_from_checkpoint.py` (continued training on the proved corpus with
whole-document rows, hash split, deterministic mode, kept steps, replay, DPOP,
FIM). Loss is reported in nats per token on a document-level holdout.

**Missing.** Nothing structural. No CORE-like benchmark exists for t; the
held-out loss plus tests on a dev split is the base report.

**Take.** Nothing now. Muon and the depth dial are measured ideas for a
separate pretraining study, not part of porting the pipeline. **Differ:** the
data. nanochat's base data is the web; dawnr's is source code for the core and
then the proved corpus (358 documents, 171,182 characters, every one clean in
all seven kernels), which is the whole thesis. Memorisation of that small
corpus is the measured problem (0.11 nats/token train against 0.68 held out),
so the base stage keeps early stopping and whole-document rows.

### 3. Mid-training (first release: `scripts/mid_train.py`; now inside `chat_sft.py`)

**nanochat.** Teaches the conversation format, the special tokens, tool use
and multiple choice on a mixture of conversations: SmolTalk (460K general
conversations), MMLU auxiliary train (100K rows per epoch, 3 epochs; teaches
multiple choice), GSM8K (8K per epoch, 4 epochs; teaches arithmetic *and the
calculator tool*: GSM8K's `<<expr=result>>` annotations become a
`python`/`python_output` pair). Conversations are rendered by
`render_conversation`: user turns and tool output are not supervised (mask 0),
assistant text, tool calls and `<|assistant_end|>` are (mask 1). Rows are
BOS-aligned and best-fit packed, padded instead of cropped.

**locallm today.** None. The model is trained on documents whose head
(`Problem:`/`Signature:`/`Example:` lines, 77 of the 358) precedes the
program, and it is prompted with that head. There is no turn structure, no
end-of-answer token (a reply is cut by a regex on the next head,
`loop_locallm.REPLY_BOUNDARY`), and no way to call a tool.

**Missing.** Everything: the special tokens, the renderer with its loss mask,
conversations built from our data, and a trainer that uses the mask.

**Take.** `render_conversation` and `render_for_completion` nearly verbatim
(the masking rules are the valuable part), the part types (`text`, tool call,
tool output), the rule that tool output is never supervised, and padding
rather than cropping. **Differ:** (a) the data: every conversation is built
from a proved document, so the assistant's program is one seven kernels
verified, not a web answer; a headed document becomes "user: the Problem,
Signature and Examples; assistant: the proved program", and a head-less one
(281 of 358) becomes "user: implement this specification (the declaration,
requires and ensures); assistant: the proved program", a real task whose
answer the proof covers; (b) a share of conversations show the tool: the
assistant writes its program inside `<|t_start|>...<|t_end|>`, the t tool's
real output is recorded after it (computed by running the tool, never
written by hand), and the assistant ends with the program; (c) one
conversation per row, not packed (the corpus is tens of thousands of tokens,
the same reason `DocumentBatches` pads), a conversation longer than the block
is refused by name rather than cropped; (d) the decontamination gates
(`loop_filter.validate_training_data`, the dev ids) run over the
conversations, as they do over the corpus.

### 4. Supervised fine-tuning (`scripts/chat_sft.py`)

**nanochat.** The same mixture and loader as mid-training, inheriting
batch sizes and learning rates from the base checkpoint, warm-starting the
optimizer state, lr at 0.8 of base with a 50% warmdown to zero; ChatCORE
(ARC-Easy, ARC-Challenge, MMLU, GSM8K, HumanEval) every 200
steps.

**locallm today.** `continue_from_checkpoint.py` is locallm's SFT: whole
proved documents, lr 3e-5, dropout 0.1, stopping step chosen by tests passed
on 100 dev problems (`t/pick_stopping_step.py`), never by validation loss.
DPOP preference pairs against the recited attractors exist.

**Missing.** SFT in the chat format (the same stage as mid-training for us:
with a corpus this size there is no separate larger mixture to "mid-train"
on first).

**Take.** One chat trainer with nanochat's loss masking, used for both
mid-training (format, tool) and SFT. **Differ:** the stopping step is chosen
by tests on the dev split as r12 already does, not by loss or ChatCORE.

### 5. Reinforcement learning (`scripts/chat_rl.py`)

**nanochat.** "GRPO" reduced to on-policy REINFORCE on GSM8K: no KL to a
reference, no ratio or clip (on-policy), token-level (DAPO) normalisation,
advantage = reward minus the group mean (no division by the standard
deviation); 16 samples per question, 16 questions per step, temperature 1.0,
top-k 50, 256 new tokens, pass@k evaluated every 60 steps. Reward is 0/1 on
the final number.

**locallm today.** Built and waiting on data: `t/rl_grpo.py` (GRPO with
clip, KL k3 to the start policy, Dr. GRPO mean-only advantages available,
DAPO dynamic-sampling filter) and `t/rl_reward.py` (a tiered reward from the
project's own grader: parses 0.05, well formed 0.10, tests and drawn inputs
0.50, proved with a weak specification 0.75, proved 1.00). The feasibility
measurement says the model solves 0.6% of problems outside its corpus, too
few to reinforce (`t/RL-DESIGN-2026-09-26.md`).

**Missing.** Nothing to port; nanochat's RL is simpler than ours and ours
already measured that plain GRPO standardisation unlearned while mean-only
advantages held, which is nanochat's choice too.

**Take.** Nothing. **Differ:** the reward is the proof engine, graded, not a
string match; the driver runs RL only when asked, because the measured
precondition (enough solvable prompts) is not met yet.

### 6. Evaluation and the report card (`scripts/chat_eval.py`, formerly `nanochat/report.py`)

**nanochat.** `chat_eval` runs categorical tasks (ARC, MMLU: pick the letter
with the highest logit) and generative ones (GSM8K, HumanEval: sample,
check), and reduces them to ChatCORE, the mean centered accuracy. The first
release gathered every stage's numbers (tokenizer compression, base CORE and
bpb, mid/SFT/RL task scores, timings, cost) into one `report.md`; that module
has since been deleted as bloat.

**locallm today.** The judges exist and are strong: `t/score_heldout.py`
(tests passed and clean answers on all 232 and on the clean 200, refusing
partial or mixed-decoding answer sets), `t/rl_reward.py` (the tier of each
answer), `t/pick_stopping_step.py` (dev-split tests), `t/compare_arms.py`
(seeds, exact permutation test). Every run writes `run.json` and
`metrics.jsonl`. Nothing puts one pipeline run's numbers in one place.

**Missing.** A report card for one pipeline run.

**Take.** The idea of one `report.md` per run with a section per stage.
**Differ:** built the way the deletion argues for: one small module that
*reads* what the stages already wrote (`stage.json`, `run.json`,
`metrics.jsonl`, the tier file) instead of every script calling into a report
object. Our metrics, not theirs: characters per token; held-out loss; tests
passed on dev problems; the tier distribution from `t/rl_reward.py`
(parses / typed / tests locally, proved when a kernel is given); clean answers
on the clean 200 only when an existing answer set is named, never as a new
held-out round.

### 7. Inference engine with tool use (`nanochat/engine.py`)

**nanochat.** `Engine.generate` prefills once, clones the KV cache per
sample, and runs a per-row state machine: between `<|python_start|>` and
`<|python_end|>` it collects tokens; at the end it decodes them, runs the
calculator (a restricted `eval` with a 3-second alarm), and queues
`<|output_start|> result <|output_end|>` as forced tokens that the model then
reads as if it had written them. Each yielded token carries a mask (1
sampled, 0 forced), which RL uses to exclude tool output from the loss. A row
ends on `<|assistant_end|>` or `<|bos|>`.

**locallm today.** `model.generate` / `sample_many` with a KV cache
(`forward_cached`), stop callbacks, and the torch-free `plain_generate.py`.
No tool, no forced tokens.

**Missing.** The state machine and a tool.

**Take.** The state machine as is (tool span, forced-token queue, the
sampled/forced mask, end tokens). **Differ:** the tool is the proof engine's
fastest part, the t interpreter and well-formedness checker, run in-process
(stdlib only, no network): the model's draft is parsed, type checked, and run
on every `Example:` line the user gave; the tool answers with the verdicts.
That is dawnr's rule in miniature: the model does not guess silently, it
checks its draft and sees the result. The verifier (Dafny, seconds per call)
is the next tool behind the same interface.

### 8. CLI and web UI (`scripts/chat_cli.py`, first release `scripts/chat_web.py`)

**nanochat.** A terminal loop that appends user tokens and streams the
assistant's tokens through the engine (`clear`, `quit`, `-p` for one shot),
and a FastAPI server with an HTML page.

**locallm today.** A Tk app (`home.py`, `studio.py`) that trains and writes
text, including with no PyTorch (`plain_generate.py`).

**Missing.** A chat loop.

**Take.** The CLI. **Differ:** no web server: dawnr runs where it is with
nothing behind it, and the Tk app is already the window. The Tk chat pane is a
later step that needs the torch-free generator to learn the special tokens and
the tool loop first.

## Where dawnr differs, in one place

- **Data.** Proved t documents and conversations built from them, instead of
  web text and SmolTalk. Every conversation passes the held-out and dev gates.
- **Tasks.** Writing t programs from English or from a specification, judged
  by tests, drawn inputs and proof, instead of multiple choice and GSM8K.
- **Size.** A 92M core and much smaller tiny runs; one GPU. One conversation
  per row, no packing.
- **Tool.** The t interpreter now, the verifier next, instead of a calculator.
- **RL.** The provers are the reward (`t/rl_reward.py`, `t/rl_grpo.py`); it is
  run only when enough prompts are solvable.
- **Report.** Reads what stages wrote; small by design.

## The order to port

1. **The driver** (`locallm/dawnr_pipeline.py`): tokenizer -> base -> mid
   (chat format and tool) -> SFT -> (RL, off unless asked) -> eval -> report,
   each stage resumable by input hashes. Everything below plugs into it.
2. **The chat format** (`locallm/chat.py`): special tokens past the
   vocabulary end, `render_conversation` with nanochat's mask, embedding
   growth for a pretrained core.
3. **Mid-training on proved conversations** (`locallm/chat_data.py`,
   `locallm/chat_train.py`): conversations from the proved corpus, a share
   with real t-tool calls, a masked trainer.
4. **The report card** (`locallm/dawnr_report.py`): one `report.md` per run.
5. **The engine with the t tool** (`locallm/t_tool.py`, `locallm/engine.py`):
   nanochat's state machine, the t interpreter as the tool.
6. **The CLI** (`locallm/chat_cli.py`).
7. Later, in this order: the verifier as a second tool behind the same
   interface; conversations where the tool finds a fault and the assistant
   repairs it (from the twins and the recorded failing answers); RL through
   the engine, so the reward sees answers that used the tool; the Tk chat
   pane with the torch-free generator.

## What has been ported (2026-09-26)

Items 1 to 6 of the list above, tested by `locallm/test_dawnr_chat.py` (19
tests, CPU, under a second) and run end to end on the desktop GPU inside
`systemd-run --user --scope -p MemoryMax=8G`:

    python locallm/dawnr_pipeline.py --corpus <proved corpus> --out <dir> --core <core dir> \
        --mid-steps 400 --mid-lr 1e-4 --dev 100

On the 358-document proved corpus from the r12 weight-decay core (92.9M
parameters, 8 chat tokens added), the whole run took under three minutes;
a second invocation skipped every stage, and a changed module reran only the
stages that read it. The numbers, from that run's `report.md` (tiny smoke
numbers, not a result):

- conversations: 358 (325 train, 33 validation by the hash split); 77 with a
  Problem head, 281 from the specification; 345 with Example lines computed
  by running the proved program; 189 with a tool call, whose 354 recorded
  example verdicts all pass.
- mid: loss on the assistant's tokens 2.23 -> 0.015 on training
  conversations and 2.30 -> 0.28 on validation ones in 400 steps: it
  memorises, as every fine-tune on this corpus has.
- validation conversations (documents no stage trained on), greedy with the
  tool live: 29 of 33 parse, 24 are well formed, 15 pass every example, 7
  are the proved program exactly; the model called the tool on 7 and opened a
  call without closing it on 7 more.
- 100 dev problems (MBPP, English prompts, named by no training document):
  29 well formed, 0 pass their tests (the r12 measurement was 0.6% solvable).
  4 used the tool; one tool answer read "example 1: fail: got 55, expected 17",
  a wrong program caught by its own examples. 31 opened a call and ended the
  answer inside it: the model learned when to open the call better than when
  to close it.

What was deliberately not taken: Muon, the depth dial and FP8 (pretraining
studies of their own, not pipeline); packing (the corpus is small enough to
pad); nanochat's RL loop (`t/rl_grpo.py` is already stricter and measured);
the web server (the Tk app is dawnr's window); ChatCORE's task set (MMLU,
ARC, GSM8K have no t form).

## Repair conversations and the tool-call grammar (2026-09-26)

Measured in `locallm/FINDINGS-repair-2026-09-26.md` (predictions and rules
committed before each run; 3 registered seeds, a post-hoc re-analysis, then 6
fresh registered seeds).

- **`locallm/repair_data.py`** builds repair conversations from TRAINING
  problems only: the training conversations go in 5 folds, a mid model is
  trained on the other four (cross-fitting, so the drafts are the model's
  mistakes on problems it has not seen, against SCoRe's distribution
  mismatch, arXiv:2409.12917) and drafts its fold (1 greedy, 3 sampled);
  each failing draft becomes `[call: draft (unsupervised)] [verdict] [call:
  proved program] [verdict]` (SAFE's self-debugging triple,
  arXiv:2410.15756; STaR, arXiv:2203.14465), and a passing draft that is the
  proved program a pass conversation. From 1,300 drafts: 436 repairs, 84
  passes. `dawnr_pipeline.py --extra-conversations` adds them to the mid
  stage; off by default.
- **Result:** the model acts on a failed check (a different program after
  55-70% of failing verdicts, against 5-12% without repair data) but answers
  that pass their examples rise by +2.3 of 133 at three seeds and +1.2 at six
  fresh ones, INCONCLUSIVE both times, inside seed noise (about 24 seeds a
  side would be needed). Not adopted.
- **The unclosed call:** `engine.py` has a grammar on the chat tokens
  (Outlines-style logit masking, arXiv:2307.09702): inside a call only text
  and `<|t_end|>` are legal, so a call always closes and the tool runs (0 of
  399 answers ended inside a call, against 41, 28 and 7 of 133). Off by
  default: its registered rule failed because the last call was taken as the
  answer. Arm B needed no grammar: when nearly every training conversation
  calls the tool, the model closes calls on its own.
- **`chat_eval.py`** now reports what an answer did with its verdicts (acted,
  repeated, repaired), where calls ended, `--answer best-verdict` (the call
  whose verdict ranks highest, AlphaCode's filtering by example tests,
  arXiv:2203.07814; with it, the repair-trained model's dev well formed goes
  from 5 to 28), `--max-calls N` (a budget of calls, after s1's budget
  forcing, arXiv:2501.19393; without one the repair-trained model retried
  until its tokens ran out on 82 of 100 dev answers) and `--rescore` (any
  rule recomputed from an earlier run's rows).

**The next stage to port:** the t tool checks that a draft keeps the
specification the user gave (101 of 285 passing fold drafts had rewritten
it); repairs as edits of the draft rather than a whole new program (the
model rewrote the loop three times while the verdict named a missing
parameter name in the signature); conversations that end in an honest stop
after repeated failures; then RL through the engine (SCoRe's multi-turn
RL), pointing `t/rl_grpo.py`'s sampler at `engine.py` so the reward sees
answers that used the tool.

## Tool conversations (2026-09-27)

`locallm/tool_conversations.py` builds conversations for every row of
`DAWNR-HARNESS.md` section 8 through the real harness (the fixture web is
recorded once by `locallm/tool_fixtures.py`); `dawnr_pipeline.py
--extra-conversations` adds them to the mid stage and `--harness-tokens`
gives a control arm the same ids. Measured against the base conversations at
three seeds (`locallm/prereg_tool_conversations_2026-09-27.json`, numbers in
`locallm/tool-conversations-results-2026-09-27.json`): the right first tool on
0.97 of 238 held-out items against 0.42, 88% of registry calls well formed,
calls closed on their own; pass all examples over the 133 prompts 14.7 against
17.0, past the registered guard of 2, so they stay opt-in. Injection following
on held-out pages is near zero in every arm, and a positive control shows why:
the model does not follow those instructions from the person either.
`chat.final_program`
now takes a registry `t` call or an MCP `t_check` as submitting a program, and
`chat_eval.py` ranks only the calls that submit one.
