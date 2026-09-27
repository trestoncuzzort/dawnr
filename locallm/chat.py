"""chat.py: dawnr's conversation format, the special tokens and the loss mask.

Taken from nanochat (https://github.com/karpathy/nanochat, nanochat/tokenizer.py
SPECIAL_TOKENS, render_conversation, render_for_completion; MIT licence, the
notice is reproduced below). What is kept exactly: the turn tokens, the part
types of an assistant message (text, a tool call, the tool's output), and the
mask rule that supervises the assistant's text, its tool calls and its
<|assistant_end|>, and never the user's turn or the tool's output (the output
comes from the tool at inference time, so the model must not be trained to
invent it).

Where dawnr differs, and why:

* The tool pair is <|t_start|> ... <|t_end|>: the assistant hands a t program
  to the t tool (t_tool.py), not a Python expression to a calculator.
* The tokens are appended past the end of the base vocabulary, as the FIM
  sentinels are (data.CharTokenizer / BPETokenizer `sentinels`), instead of
  being reserved when the tokenizer is trained. A pretrained core's tokenizer
  is frozen with its weights, and a sentinel id sits where no encode() of
  text can reach it, so a document that spells out "<|user_start|>" is text.
  grow_embeddings() gives the new rows the mean of the existing rows (Hewitt,
  "Initializing New Word Embeddings for Pretrained Language Models"), as
  continue_from_checkpoint.add_fim_sentinels does.
* dawnr's harness (DAWNR-HARNESS.md) adds three more, appended the same way
  and only when asked for (with_harness_tokens), so checkpoints trained
  before it keep their ids: <|tool_start|> ... <|tool_end|> around a call to
  any tool in the registry (`name {json arguments}`), and <|untrusted|> as the
  first token of an output span whose text came from outside. Text cannot
  produce any of them, so a fetched page can neither close its span nor forge
  the mark (spotlighting, arXiv:2403.14720, done with tokens).
* No <|bos|>: every row holds one conversation and starts at its first token
  (data.DocumentBatches' rule), so nothing needs delimiting.
* A system message is refused, not merged into the user turn: dawnr has none.
* render_conversation never truncates. ConversationBatches refuses a
  conversation longer than the block by name, as PairBatches refuses a pair,
  because a cut conversation can end inside the program being taught.
* A text or tool-call part may carry "train": false, and then its text is
  context, not a target. A repair conversation (repair_data.py) holds a draft
  that failed the tool's check: the draft is the input to the repair, as the
  incorrect proof is in SAFE's self-debugging triples (arXiv:2410.15756), so
  the model is not trained to write it; the tokens that open and close the
  call around it still are, because calling the tool and closing the call are
  what the conversation teaches.

----------------------------------------------------------------------------
nanochat's notice (for the parts of render_conversation and
render_for_completion copied here):

MIT License

Copyright (c) 2025 Andrej Karpathy

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
----------------------------------------------------------------------------
"""
from __future__ import annotations

import copy
import math

USER_START, USER_END = "<|user_start|>", "<|user_end|>"
ASSISTANT_START, ASSISTANT_END = "<|assistant_start|>", "<|assistant_end|>"
T_START, T_END = "<|t_start|>", "<|t_end|>"            # the assistant calls the t tool
OUTPUT_START, OUTPUT_END = "<|output_start|>", "<|output_end|>"   # the tool's answer
CHAT_TOKENS = (USER_START, USER_END, ASSISTANT_START, ASSISTANT_END, T_START, T_END, OUTPUT_START, OUTPUT_END)

TOOL_START, TOOL_END = "<|tool_start|>", "<|tool_end|>"   # the assistant calls a registry tool: name {json}
UNTRUSTED = "<|untrusted|>"                                 # opens an output span whose text came from outside
HARNESS_TOKENS = (TOOL_START, TOOL_END, UNTRUSTED)

PART_TYPES = ("text", "t", "t_output", "tool", "tool_output")
IGNORE_INDEX = -1            # model.GPT's cross-entropy ignores -1 (data.IGNORE_INDEX)


# ------------------------------------------------------------ the tokens --

def has_chat_tokens(tokenizer) -> bool:
    return all(name in tuple(getattr(tokenizer, "sentinels", ())) for name in CHAT_TOKENS)


def with_chat_tokens(tokenizer):
    """The same ids, with the chat tokens appended after any sentinels already there.

    A tokenizer that already carries FIM sentinels keeps them at their ids and
    gets the chat tokens after them, so one checkpoint can hold both.
    """
    from data import BPETokenizer, CharTokenizer
    present = tuple(getattr(tokenizer, "sentinels", ()))
    missing = tuple(name for name in CHAT_TOKENS if name not in present)
    if not missing:
        return tokenizer
    if isinstance(tokenizer, CharTokenizer):
        return CharTokenizer(tokenizer.chars, present + missing)
    if isinstance(tokenizer, BPETokenizer):
        return BPETokenizer(tokenizer.backend, tokenizer.training, present + missing)
    raise TypeError(f"unsupported tokenizer type: {type(tokenizer).__name__}")


def has_harness_tokens(tokenizer) -> bool:
    return all(name in tuple(getattr(tokenizer, "sentinels", ())) for name in HARNESS_TOKENS)


def needs_harness_tokens(conversations) -> bool:
    """True when an assistant turn calls a registry tool or reads an untrusted output."""
    return any(isinstance(m.get("content"), list)
               and any(p.get("type") == "tool" or p.get("untrusted") for p in m["content"])
               for c in conversations for m in c["messages"] if m.get("role") == "assistant")


def with_harness_tokens(tokenizer):
    """The chat tokens (with_chat_tokens), then the harness's, each appended only if missing."""
    from data import BPETokenizer, CharTokenizer
    tokenizer = with_chat_tokens(tokenizer)
    present = tuple(tokenizer.sentinels)
    missing = tuple(name for name in HARNESS_TOKENS if name not in present)
    if not missing:
        return tokenizer
    if isinstance(tokenizer, CharTokenizer):
        return CharTokenizer(tokenizer.chars, present + missing)
    if isinstance(tokenizer, BPETokenizer):
        return BPETokenizer(tokenizer.backend, tokenizer.training, present + missing)
    raise TypeError(f"unsupported tokenizer type: {type(tokenizer).__name__}")


def special(tokenizer, name: str) -> int:
    return tokenizer.sentinel_id(name)


def grow_embeddings(model, new_vocab_size: int) -> int:
    """Grow a tied embedding/unembedding to new_vocab_size rows; return how many were added.

    New rows are the mean of the existing rows (Hewitt), old rows are copied
    exactly, so every ordinary id embeds and scores as before.
    """
    import torch
    old = model.lm_head.weight.data
    added = new_vocab_size - old.shape[0]
    if added < 0:
        raise ValueError(f"cannot shrink the vocabulary from {old.shape[0]} to {new_vocab_size}")
    if added == 0:
        return 0
    grown = torch.cat([old, old.mean(dim=0, keepdim=True).repeat(added, 1)])
    head = torch.nn.Linear(old.shape[1], grown.shape[0], bias=False).to(device=old.device, dtype=old.dtype)
    head.weight.data.copy_(grown)
    model.lm_head = head
    model.transformer.wte.weight = model.lm_head.weight
    model.config.vocab_size = grown.shape[0]
    return added


# ------------------------------------------------------------ rendering --

def _check_messages(conversation: dict) -> list[dict]:
    messages = conversation["messages"]
    if not messages:
        raise ValueError("a conversation needs at least one message")
    for i, message in enumerate(messages):
        must_be_from = "user" if i % 2 == 0 else "assistant"
        if message.get("role") != must_be_from:
            raise ValueError(f"message {i} is from {message.get('role')!r} but should be from {must_be_from}"
                             + (" (dawnr has no system message)" if message.get("role") == "system" else ""))
    return messages


def render_conversation(tokenizer, conversation: dict) -> tuple[list[int], list[int]]:
    """Token ids of one conversation, and a mask: 1 where the assistant is trained.

    nanochat's render_conversation with t tool parts. The mask is per token,
    for that token as a prediction target.
    """
    ids: list[int] = []
    mask: list[int] = []

    def add(token_ids, mask_val):
        if isinstance(token_ids, int):
            token_ids = [token_ids]
        ids.extend(token_ids)
        mask.extend([mask_val] * len(token_ids))

    for message in _check_messages(conversation):
        content = message["content"]
        if message["role"] == "user":
            if not isinstance(content, str):
                raise ValueError("user messages are strings")
            add(special(tokenizer, USER_START), 0)
            add(tokenizer.encode(content), 0)
            add(special(tokenizer, USER_END), 0)
            continue
        add(special(tokenizer, ASSISTANT_START), 0)
        if isinstance(content, str):
            add(tokenizer.encode(content), 1)
        elif isinstance(content, list):
            for part in content:
                kind, text = part.get("type"), part.get("text")
                if kind not in PART_TYPES or not isinstance(text, str):
                    raise ValueError(f"unknown assistant part {part!r}")
                trained = part.get("train", True)
                if not isinstance(trained, bool) or (kind == "t_output" and "train" in part):
                    raise ValueError(f"'train' is a bool on a text or t part, never on tool output: {part!r}")
                if kind == "text":
                    add(tokenizer.encode(text), int(trained))
                elif kind == "t":
                    add(special(tokenizer, T_START), 1)
                    add(tokenizer.encode(text), int(trained))
                    add(special(tokenizer, T_END), 1)
                elif kind == "tool":
                    if not has_harness_tokens(tokenizer):
                        raise ValueError("a tool part needs the harness tokens (chat.with_harness_tokens)")
                    add(special(tokenizer, TOOL_START), 1)
                    add(tokenizer.encode(text), 1)
                    add(special(tokenizer, TOOL_END), 1)
                else:
                    # the tool (or the harness) writes this at inference time: never supervised
                    add(special(tokenizer, OUTPUT_START), 0)
                    if part.get("untrusted"):
                        if not has_harness_tokens(tokenizer):
                            raise ValueError("an untrusted output needs the harness tokens (chat.with_harness_tokens)")
                        add(special(tokenizer, UNTRUSTED), 0)
                    add(tokenizer.encode(text), 0)
                    add(special(tokenizer, OUTPUT_END), 0)
        else:
            raise ValueError(f"unknown assistant content type {type(content).__name__}")
        add(special(tokenizer, ASSISTANT_END), 1)
    return ids, mask


def render_for_completion(tokenizer, conversation: dict) -> list[int]:
    """The ids that prime the assistant to answer: every message but a final
    assistant one, then <|assistant_start|> (nanochat's render_for_completion)."""
    conversation = copy.deepcopy(conversation)
    messages = conversation["messages"]
    if messages and messages[-1].get("role") == "assistant":
        messages.pop()
    if not messages or messages[-1].get("role") != "user":
        raise ValueError("the conversation must end with a user message to be completed")
    ids, _ = render_conversation(tokenizer, conversation)
    return ids + [special(tokenizer, ASSISTANT_START)]


def final_program(content) -> str | None:
    """The program an assistant message answers with: the last t tool call, or its text."""
    if isinstance(content, str):
        return content.strip() or None
    calls = [p["text"] for p in content if p.get("type") == "t"]
    if calls:
        return calls[-1].strip() or None
    text = "".join(p["text"] for p in content if p.get("type") == "text").strip()
    return text or None


# -------------------------------------------------------------- batches --

class ConversationBatches:
    """One conversation per row: inputs, and targets masked to the assistant's tokens.

    Target t is ids[t + 1] where mask[t + 1] is 1, else IGNORE_INDEX; the row
    is right-padded with pad_id and ignored targets. Row order: epoch e is the
    (e+1)-th randperm of one generator seeded with `seed`, exactly as
    data.DocumentBatches draws it, so get_batch(step) is a pure function of
    (seed, step) and a resumed run continues the same sequence.
    """

    def __init__(self, conversations, tokenizer, block_size: int, seed: int, device: str = "cpu",
                 pad_id: int = 0):
        import torch
        conversations = list(conversations)
        if not conversations:
            raise ValueError("no conversations to batch")
        if block_size < 1:
            raise ValueError(f"block_size must be positive, not {block_size}")
        self.block_size, self.seed = block_size, seed
        self.conversations = len(conversations)
        self.target_tokens = self.tokens = self.longest_tokens = self.tool_calls = 0
        rows_x, rows_y = [], []
        for i, conv in enumerate(conversations):
            ids, mask = render_conversation(tokenizer, conv)
            self.longest_tokens = max(self.longest_tokens, len(ids))
            if len(ids) > block_size + 1:
                raise ValueError(f"conversation {i} ({conv.get('source', '?')}) is {len(ids)} tokens, over the "
                                 f"block of {block_size}; raise the block size, a cut conversation is not the "
                                 f"conversation that was built")
            targets = [t if m else IGNORE_INDEX for t, m in zip(ids[1:], mask[1:])]
            pad = block_size - (len(ids) - 1)
            rows_x.append(ids[:-1] + [pad_id] * pad)
            rows_y.append(targets + [IGNORE_INDEX] * pad)
            self.tokens += len(ids)
            self.target_tokens += sum(mask[1:])
            self.tool_calls += sum(1 for m in conv["messages"] if m["role"] == "assistant"
                                   and isinstance(m["content"], list)
                                   for p in m["content"] if p.get("type") in ("t", "tool"))
        self.x = torch.tensor(rows_x, dtype=torch.long).to(device)
        self.y = torch.tensor(rows_y, dtype=torch.long).to(device)
        self._generator = torch.Generator().manual_seed(seed)
        self._orders: list[list[int]] = []

    def order(self, epoch: int) -> list[int]:
        import torch
        while len(self._orders) <= epoch:
            self._orders.append(torch.randperm(self.conversations, generator=self._generator).tolist())
        return self._orders[epoch]

    def batches_per_epoch(self, batch_size: int) -> int:
        return math.ceil(self.conversations / batch_size)

    def get_batch(self, step: int, batch_size: int):
        import torch
        epoch, k = divmod(step, self.batches_per_epoch(batch_size))
        idx = self.order(epoch)[k * batch_size:(k + 1) * batch_size]
        ix = torch.tensor(idx, dtype=torch.long, device=self.x.device)
        return self.x[ix], self.y[ix]

    def in_order(self, batch_size: int):
        import torch
        for start in range(0, self.conversations, batch_size):
            ix = torch.arange(start, min(start + batch_size, self.conversations), device=self.x.device)
            yield self.x[ix], self.y[ix]

    def record(self) -> dict:
        return {"conversations": self.conversations, "tokens": self.tokens, "target_tokens": self.target_tokens,
                "longest_tokens": self.longest_tokens, "tool_calls": self.tool_calls,
                "block_size": self.block_size, "order_seed": self.seed, "ignore_index": IGNORE_INDEX}
