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

The tool now runs through dawnr's harness (dawnr_harness, DAWNR-HARNESS.md):
the t tool is the registry's `t` entry, and a model whose tokenizer carries
the harness tokens can also call any registry tool with
<|tool_start|> name {json} <|tool_end|>; an answer from outside is forced
as <|output_start|><|untrusted|> ... <|output_end|>, and the harness's own
notes (the checker hook's verdicts) follow as separate trusted spans. When
the harness has Stop hooks, a sampled <|assistant_end|> is first shown to
them: a block (dawnr's checker failing the final program) forces its reason
as an output span instead, and the row continues so the model can repair.
With no harness given, the engine is exactly what it was: the t tool, no
hooks.

Generation stops at the model's context window instead of sliding it: a
conversation is one row that fits the window, as it was in training. With a
character tokenizer, characters of the tool's answer that the vocabulary
lacks are dropped when it is encoded (data.CharTokenizer.encode), as they are
from any text; byte-level BPE loses nothing.

Added for dawnr: a grammar on the chat tokens (off by default: see below).
The first pipeline run ended 28 of 100 dev answers with <|assistant_end|> inside an
open <|t_start|> call, so the tool never ran on them. Outlines
(Willard and Louf, arXiv:2307.09702) guides generation by masking, at each
step, the logits of tokens illegal in the current state of a finite-state
machine. The assistant turn here is a two-state machine: inside a call only
text and <|t_end|> are legal; outside one only text, <|t_start|> and
<|assistant_end|>. The tool-output pair is only ever forced, and the turn
tokens never appear inside an assistant turn, so neither is ever sampled.
A call can therefore end only by <|t_end|>, after which the tool runs. Each
row counts the steps where the model's own top token was illegal
(grammar_overrides), since the closed-call rate is guaranteed by the mask and
says nothing by itself. It is off by default because it failed the rule
registered for it (FINDINGS-repair-2026-09-26.md): it closed every call, but
with the last call taken as the answer, dev well formed fell by 2 on the mean;
it passed post hoc with the best-verdict answer (chat_eval.py), and
Engine(..., grammar=True) turns it on. A completed row is inert: it is fed
<|assistant_end|> with mask 0 and no tool runs for it, so extra samples in a
batch cannot add tool calls after their own end.

A call budget (max_calls, off by default, with the grammar only): once a row
has made max_calls calls, <|t_start|> is illegal for it, so a model that
retries forever must end or write text. s1's budget forcing
(Muennighoff et al., arXiv:2501.19393) ends a segment when its token budget is
spent; this budget is of tool calls. A model trained on repair conversations
retried until its tokens ran out on 82 of 100 dev answers
(FINDINGS-repair-2026-09-26.md). Each row counts the steps where the budget
refused the model's top token (budget_refusals).

With the harness tokens (dawnr_harness) the grammar has a third state: inside a
<|tool_start|> call only text and <|tool_end|> are legal, inside a <|t_start|>
call only text and <|t_end|>, no call opens inside another, <|untrusted|> is
never sampled, and the call budget counts both kinds of call.

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
    """Per-row state during generation (nanochat's RowState, python -> t, plus the harness's session)."""

    def __init__(self, current_tokens=None, session=None):
        self.current_tokens = current_tokens or []
        self.forced_tokens = deque()
        self.in_tool_block = False    # inside <|t_start|> or <|tool_start|>
        self.tool_kind = None         # "t" or "tool"
        self.tool_tokens = []
        self.completed = False
        self.tool_calls = []          # (program or call text, output text) per call, for the caller
        self.call_kinds = []          # "t" (a <|t_start|> span) or "tool" (a registry call), per call
        self.session = session        # the harness's per-conversation state (taint, stop blocks)
        self.stops = []               # reasons a Stop hook gave for not ending
        self.ended_in_call = False    # <|assistant_end|> while a call was open (only without the grammar)
        self.grammar_overrides = 0    # sampled steps whose unmasked top token was illegal
        self.budget_refusals = 0      # sampled steps whose top token was <|t_start|> past the call budget


class Engine:

    def __init__(self, model, tokenizer, tool=None, harness=None, grammar=False, max_calls=None):
        if not chat.has_chat_tokens(tokenizer):
            raise ValueError("the engine needs a tokenizer carrying the chat tokens (chat.with_chat_tokens)")
        self.model = model
        self.tokenizer = tokenizer
        if tool is None:
            import t_tool
            tool = t_tool.call
        self.tool = tool              # tool(program: str, context: str) -> str, when no harness is given
        if harness is None:
            from dawnr_harness import Harness
            harness = Harness.with_t_tool(tool)
        self.harness = harness
        self.harness_tokens = chat.has_harness_tokens(tokenizer)
        self.grammar = grammar
        if max_calls is not None and (not grammar or max_calls < 0):
            raise ValueError("a call budget needs the grammar and a count of at least 0")
        self.max_calls = max_calls

    def _output_tokens(self, result) -> list[int]:
        """A harness answer as forced tokens: one output span per part, untrusted ones marked."""
        sp = lambda name: chat.special(self.tokenizer, name)                 # noqa: E731
        out = []
        for untrusted, text in result.spans():
            out.append(sp(chat.OUTPUT_START))
            if untrusted:
                if self.harness_tokens:
                    out.append(sp(chat.UNTRUSTED))
                else:
                    text = "[untrusted output withheld: this model has no <|untrusted|> token]"
            out.extend(self.tokenizer.encode(text))
            out.append(sp(chat.OUTPUT_END))
        return out

    def illegal_ids(self) -> dict[str, list[int]]:
        """The chat-token grammar: ids illegal inside a t call, inside a harness tool call, and outside any call.

        Output spans, <|untrusted|> and the turn tokens are only ever forced, never sampled. Inside a call
        only text and that call's own closer are legal; outside one, no closer is legal."""
        sp = lambda name: chat.special(self.tokenizer, name)                 # noqa: E731
        never = [sp(x) for x in (chat.OUTPUT_START, chat.OUTPUT_END, chat.USER_START, chat.USER_END,
                                 chat.ASSISTANT_START)]
        openers, closers = [sp(chat.T_START)], {"t": sp(chat.T_END)}
        if self.harness_tokens:
            never.append(sp(chat.UNTRUSTED))
            openers.append(sp(chat.TOOL_START))
            closers["tool"] = sp(chat.TOOL_END)
        inside = never + [sp(chat.ASSISTANT_END)] + openers
        table = {kind: inside + [c for other, c in closers.items() if other != kind] for kind in closers}
        table["outside"] = never + list(closers.values())
        return table

    @torch.no_grad()
    def generate(self, tokens, num_samples=1, max_tokens=None, temperature=1.0, top_k=None, seed=42, sessions=None):
        """Yield (token_column, mask_column), one entry per row, until every row ends or the budget is spent.

        After the loop, self.rows holds each row's RowState (its tool calls included). `sessions`, one
        per row, carries the harness's state (taint, stop blocks) across the turns of a conversation.
        """
        if sessions is not None and len(sessions) != num_samples:
            raise ValueError(f"{len(sessions)} sessions for {num_samples} rows")
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
        tool_start = sp(chat.TOOL_START) if self.harness_tokens else None
        tool_end = sp(chat.TOOL_END) if self.harness_tokens else None
        stop_hooks = self.harness.hooks.has("Stop")
        prompt_len = len(tokens)
        rows = self.rows = [RowState(list(tokens), sessions[i] if sessions else self.harness.session())
                            for i in range(num_samples)]
        for row in rows:
            row.session.new_turn()
        if self.grammar:
            vocab = logits.size(-1)
            masks_by_state = {}
            for state, bad in self.illegal_ids().items():
                m = torch.zeros(vocab, dtype=torch.bool, device=device)
                m[bad] = True
                masks_by_state[state] = m

        generated = 0
        while generated < max_tokens and not all(r.completed for r in rows):
            logits = logits.float()
            if self.grammar:
                illegal = torch.stack([masks_by_state[(r.tool_kind or "t") if r.in_tool_block else "outside"]
                                       for r in rows])
                top = logits.argmax(dim=-1).tolist()
                for i, row in enumerate(rows):
                    if not row.completed and not row.forced_tokens and bool(illegal[i, top[i]]):
                        row.grammar_overrides += 1
                if self.max_calls is not None:
                    spent = [not r.in_tool_block and len(r.tool_calls) >= self.max_calls for r in rows]
                    for i, row in enumerate(rows):
                        if spent[i]:
                            openers = [t_start] + ([tool_start] if tool_start is not None else [])
                            illegal[i, openers] = True           # the budget counts every kind of call
                            if not row.completed and not row.forced_tokens and top[i] in openers:
                                row.budget_refusals += 1
                logits = logits.masked_fill(illegal, float("-inf"))
            sampled = _next_token(logits, temperature, top_k, rng)[:, 0].tolist()
            column, masks = [], []
            for i, row in enumerate(rows):
                if row.completed:
                    column.append(assistant_end)
                    masks.append(0)
                    continue
                forced = len(row.forced_tokens) > 0
                token = row.forced_tokens.popleft() if forced else sampled[i]
                if token == assistant_end and not forced and stop_hooks and not row.in_tool_block:
                    reason = self._stop_reason(row, prompt_len, context)
                    if reason is not None:
                        # the reply may not end yet: the reason is forced in as an output span instead
                        row.stops.append(reason)
                        row.forced_tokens.extend(self.tokenizer.encode(reason))
                        row.forced_tokens.append(output_end)
                        token, forced = output_start, True
                masks.append(0 if forced else 1)
                column.append(token)
                row.current_tokens.append(token)
                if token == assistant_end:
                    row.completed = True
                    row.ended_in_call = row.in_tool_block
                if token == t_start or (tool_start is not None and token == tool_start):
                    row.in_tool_block, row.tool_tokens = True, []
                    row.tool_kind = "t" if token == t_start else "tool"
                elif row.in_tool_block and ((token == t_end and row.tool_kind == "t")
                                            or (tool_end is not None and token == tool_end
                                                and row.tool_kind == "tool")):
                    row.in_tool_block = False
                    text = self.tokenizer.decode(row.tool_tokens)
                    if row.tool_kind == "t":
                        result = self.harness.call("t", {"program": text}, context=context, session=row.session)
                    else:
                        result = self.harness.call_text(text, context=context, session=row.session)
                    row.tool_calls.append((text, result.text))
                    row.call_kinds.append(row.tool_kind)
                    row.forced_tokens.extend(self._output_tokens(result))
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

    def _stop_reason(self, row, prompt_len: int, context: str):
        """The Stop hooks' reason for not ending this row now, or None to let it end."""
        parts = reply_parts(self.tokenizer, row.current_tokens[prompt_len:])
        program = chat.final_program(parts) if parts else None
        # the assistant's own words and programs, never the tool outputs it was shown
        own = "\n".join(p["text"] for p in parts if p["type"] in ("text", "t"))
        decision = self.harness.stop(own, program=program, context=context, session=row.session)
        return decision.reason if decision.block else None

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
    if chat.has_harness_tokens(tokenizer):
        specials |= {chat.special(tokenizer, n) for n in chat.HARNESS_TOKENS}
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
    """An assistant reply's tokens as chat parts (text, t, t_output, tool, tool_output), the inverse of rendering.

    The output span right after a t call is "t_output"; any other (after a
    registry call, a harness note, a Stop hook's reason) is "tool_output";
    one opened by <|untrusted|> carries "untrusted": True.
    """
    names = chat.CHAT_TOKENS + (chat.HARNESS_TOKENS if chat.has_harness_tokens(tokenizer) else ())
    sp = {chat.special(tokenizer, n): n for n in names}
    parts, run, kind, untrusted, last_call = [], [], "text", False, None

    def flush():
        if run:
            part = {"type": kind, "text": tokenizer.decode(run)}
            if untrusted:
                part["untrusted"] = True
            parts.append(part)

    for token in new_tokens:
        name = sp.get(token)
        if name in (chat.T_START, chat.TOOL_START, chat.OUTPUT_START):
            flush()
            if name == chat.OUTPUT_START:
                kind = "t_output" if last_call == "t" else "tool_output"
            else:
                kind = last_call = "t" if name == chat.T_START else "tool"
            run, untrusted = [], False
        elif name == chat.UNTRUSTED and kind in ("t_output", "tool_output") and not run:
            untrusted = True
        elif name in (chat.T_END, chat.TOOL_END, chat.OUTPUT_END):
            flush()
            if name == chat.OUTPUT_END:
                last_call = None
            run, kind, untrusted = [], "text", False
        elif name == chat.ASSISTANT_END:
            break
        elif name is None:
            run.append(token)
    flush()
    return [p for p in parts if p["type"] != "text" or p["text"].strip()]
