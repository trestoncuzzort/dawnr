"""span.py: the memory span that opens the first reply of a conversation, in the model's own tokens.

The engine (engine.py) asks this module, once per generate call, for the tokens to force before the model writes:
nothing unless this is the conversation's first reply (the prompt holds exactly one <|assistant_start|>, its last
token) and the harness has SessionStart hooks. Then the harness runs them with the person's first message, and
each context they add (dawnr's recall first) becomes

    <|output_start|><|memory|> the context's lines <|output_end|>

cut to whole lines so that every span together stays inside the memory budget as the model's tokenizer counts it
(retrieval.fit_lines), and never more than half the room left in the context. Forced tokens, as a tool's answer is:
the model reads them as if it had written them, the mask marks them 0, and a caller that keeps the reply keeps the
span with it, so later turns see the same memory without recalling again.

A model without the <|memory|> token is shown nothing: the context is withheld and the person is told why, as the
harness withholds untrusted text from a model without <|untrusted|> (DAWNR-HARNESS.md section 7). Text can never
produce the token (it sits past the vocabulary end), so nothing a page says can open or close a memory span.
"""
from __future__ import annotations

from .retrieval import fit_lines

DEFAULT_BUDGET = 256


def first_message(tokenizer, tokens: list[int]) -> str:
    """The text of the first user turn in a prompt (between the first <|user_start|> and its <|user_end|>)."""
    import chat
    start, end = chat.special(tokenizer, chat.USER_START), chat.special(tokenizer, chat.USER_END)
    if start not in tokens:
        return ""
    i = tokens.index(start) + 1
    j = tokens.index(end, i) if end in tokens[i:] else len(tokens)
    return tokenizer.decode(tokens[i:j])


def is_first_reply(tokenizer, tokens: list[int]) -> bool:
    import chat
    a_start = chat.special(tokenizer, chat.ASSISTANT_START)
    return bool(tokens) and tokens[-1] == a_start and tokens.count(a_start) == 1


def session_start_ids(harness, tokenizer, tokens: list[int], session, room: int) -> list[int]:
    """The forced tokens that open the first reply: one memory span per SessionStart context, or []."""
    import chat
    hooks = getattr(harness, "hooks", None)
    if hooks is None or not hooks.has("SessionStart") or not is_first_reply(tokenizer, tokens):
        return []
    contexts = harness.session_start(session, prompt=first_message(tokenizer, tokens))
    if not contexts:
        return []
    if not chat.has_memory_tokens(tokenizer):
        harness.messages.append("memory: not shown to this model, which has no <|memory|> token "
                                "(chat.with_memory_tokens; DAWNR-MEMORY.md)")
        return []
    memory = getattr(harness, "memory", None)
    budget = min(int(getattr(memory, "budget", DEFAULT_BUDGET)), max(0, room // 2))
    sp = lambda name: chat.special(tokenizer, name)                    # noqa: E731
    count = lambda text: len(tokenizer.encode(text))                   # noqa: E731
    ids: list[int] = []
    for context in contexts:
        text = fit_lines(context, budget - len(ids), count)
        if text:
            ids += [sp(chat.OUTPUT_START), sp(chat.MEMORY)] + tokenizer.encode(text) + [sp(chat.OUTPUT_END)]
    return ids
