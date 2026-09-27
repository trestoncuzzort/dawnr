"""engine.py: generation in dawnr's chat format, with the model calling the t tool mid-answer.

Ported from nanochat's Engine (https://github.com/karpathy/nanochat,
nanochat/engine.py: RowState, Engine.generate, Engine.generate_batch; MIT
licence, notice below). Kept: one prefill of the prompt, its key/value cache
copied to every sample row, a per-row state machine that collects the tokens
between the tool-call pair and, on the closing token, runs the tool and queues
<|output_start|> result <|output_end|> as FORCED tokens the model then reads
as if it had written them, a per-token mask (1 sampled, 0 forced) so RL can
leave tool output out of the loss, and a row ends on <|assistant_end|>.

Changed for dawnr: the tool pair is <|t_start|> ... <|t_end|> and the tool is
t_tool.call (parse, type check, run on the user's Example lines) given the
decoded prompt as its context, where nanochat's calculator got only the
expression. The cache is locallm's own (model.GPT.forward_cached, a tuple of
per-layer key/value tensors), expanded along the batch after the prefill.
Generation stops at the model's context window instead of sliding it: a
conversation is one row that fits the window, as it was in training. With a
character tokenizer, characters of the tool's answer that the vocabulary
lacks are dropped when it is encoded (data.CharTokenizer.encode), as they are
from any text; byte-level BPE loses nothing.

----------------------------------------------------------------------------
nanochat's notice (for the parts of RowState and Engine.generate ported here):

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

import sys
from collections import deque
from pathlib import Path

import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import chat  # noqa: E402
from model import _next_token  # noqa: E402


class RowState:
    """Per-row state during generation (nanochat's RowState, python -> t)."""

    def __init__(self, current_tokens=None):
        self.current_tokens = current_tokens or []
        self.forced_tokens = deque()
        self.in_tool_block = False
        self.tool_tokens = []
        self.completed = False
        self.tool_calls = []          # (program, output) per call, for the caller


class Engine:

    def __init__(self, model, tokenizer, tool=None):
        if not chat.has_chat_tokens(tokenizer):
            raise ValueError("the engine needs a tokenizer carrying the chat tokens (chat.with_chat_tokens)")
        self.model = model
        self.tokenizer = tokenizer
        if tool is None:
            import t_tool
            tool = t_tool.call
        self.tool = tool              # tool(program: str, context: str) -> str

    @torch.no_grad()
    def generate(self, tokens, num_samples=1, max_tokens=None, temperature=1.0, top_k=None, seed=42):
        """Yield (token_column, mask_column), one entry per row, until every row ends or the budget is spent.

        After the loop, self.rows holds each row's RowState (its tool calls included).
        """
        if not (isinstance(tokens, list) and tokens and all(isinstance(t, int) for t in tokens)):
            raise ValueError("expecting a nonempty list of ints")
        model = self.model
        model.eval()
        device = next(model.parameters()).device
        block = model.config.block_size
        if len(tokens) >= block:
            raise ValueError(f"the prompt is {len(tokens)} tokens; the context is {block}")
        room = block - len(tokens)
        max_tokens = room if max_tokens is None else min(max_tokens, room)
        rng = torch.Generator(device=device)
        rng.manual_seed(seed)
        sp = lambda name: chat.special(self.tokenizer, name)                 # noqa: E731
        t_start, t_end = sp(chat.T_START), sp(chat.T_END)
        output_start, output_end = sp(chat.OUTPUT_START), sp(chat.OUTPUT_END)
        assistant_end = sp(chat.ASSISTANT_END)
        context = plain_text(self.tokenizer, tokens)

        # 1) prefill once, 2) copy the cache to every row
        ids = torch.tensor([tokens], dtype=torch.long, device=device)
        logits, cache = model.forward_cached(ids, only_last=True)
        logits = logits[:, -1, :].expand(num_samples, -1)
        cache = tuple((k.expand(num_samples, -1, -1, -1).contiguous(), v.expand(num_samples, -1, -1, -1).contiguous())
                      for k, v in cache)
        rows = self.rows = [RowState(list(tokens)) for _ in range(num_samples)]

        generated = 0
        while generated < max_tokens and not all(r.completed for r in rows):
            sampled = _next_token(logits.float(), temperature, top_k, rng)[:, 0].tolist()
            column, masks = [], []
            for i, row in enumerate(rows):
                forced = len(row.forced_tokens) > 0
                masks.append(0 if forced else 1)
                token = row.forced_tokens.popleft() if forced else sampled[i]
                column.append(token)
                row.current_tokens.append(token)
                if token == assistant_end:
                    row.completed = True
                if token == t_start:
                    row.in_tool_block, row.tool_tokens = True, []
                elif token == t_end and row.in_tool_block:
                    row.in_tool_block = False
                    program = self.tokenizer.decode(row.tool_tokens)
                    result = self.tool(program, context)
                    row.tool_calls.append((program, result))
                    row.forced_tokens.append(output_start)
                    row.forced_tokens.extend(self.tokenizer.encode(result))
                    row.forced_tokens.append(output_end)
                    row.tool_tokens = []
                elif row.in_tool_block:
                    row.tool_tokens.append(token)
            yield column, masks
            generated += 1
            if generated >= max_tokens or all(r.completed for r in rows):
                break
            step = torch.tensor(column, dtype=torch.long, device=device).unsqueeze(1)
            logits, cache = model.forward_cached(step, cache, only_last=True)
            logits = logits[:, -1, :]

    def generate_batch(self, tokens, num_samples=1, **kwargs):
        """Every row's new tokens and masks, <|assistant_end|> not included (nanochat's generate_batch)."""
        end = chat.special(self.tokenizer, chat.ASSISTANT_END)
        results = [[] for _ in range(num_samples)]
        masks = [[] for _ in range(num_samples)]
        done = [False] * num_samples
        for column, mask_column in self.generate(tokens, num_samples, **kwargs):
            for i, (token, mask) in enumerate(zip(column, mask_column)):
                if done[i]:
                    continue
                if token == end:
                    done[i] = True
                else:
                    results[i].append(token)
                    masks[i].append(mask)
            if all(done):
                break
        return results, masks


def plain_text(tokenizer, tokens: list[int]) -> str:
    """The text of a token sequence with every chat token as a line break.

    What the tool reads as its context. Decoding the special tokens by name
    would glue "<|user_end|>" onto the user's last line, and a line-anchored
    reader (t_tool.parse_examples) would then lose that line.
    """
    specials = {chat.special(tokenizer, n) for n in chat.CHAT_TOKENS}
    out, run = [], []
    for t in tokens:
        if t in specials:
            out.append(tokenizer.decode(run))
            run = []
        else:
            run.append(t)
    out.append(tokenizer.decode(run))
    return "\n".join(out)


def reply_parts(tokenizer, new_tokens: list[int]) -> list[dict]:
    """An assistant reply's tokens as chat parts (text, t, t_output), the inverse of rendering."""
    sp = {chat.special(tokenizer, n): n for n in chat.CHAT_TOKENS}
    parts, run, kind = [], [], "text"

    def flush():
        if run:
            parts.append({"type": kind, "text": tokenizer.decode(run)})

    for token in new_tokens:
        name = sp.get(token)
        if name in (chat.T_START, chat.OUTPUT_START):
            flush()
            run, kind = [], "t" if name == chat.T_START else "t_output"
        elif name in (chat.T_END, chat.OUTPUT_END):
            flush()
            run, kind = [], "text"
        elif name == chat.ASSISTANT_END:
            break
        elif name is None:
            run.append(token)
    flush()
    return [p for p in parts if p["type"] != "text" or p["text"].strip()]
