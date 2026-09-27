"""chat_cli.py: talk to a chat-trained locallm in the terminal; its t tool runs on this machine.

    python3 locallm/chat_cli.py --model <dir> [-p "prompt"] [--temperature 0.6] [--top-k 50]

nanochat's scripts/chat_cli.py (https://github.com/karpathy/nanochat): the
conversation is kept as token ids, each user turn is appended between
<|user_start|> and <|user_end|>, <|assistant_start|> primes the reply, the
engine streams it, and <|assistant_end|> is appended even when the budget ran
out so the next turn starts clean. `clear` starts over, `quit` or `exit`
leaves, -p answers one prompt and exits. Added here: -f reads a many-line
prompt from a file, and a typed line ending in a backslash continues. What
differs otherwise: tool calls and their
output are shown as they happen, marked, and after each reply the tool calls
are summarised, because in dawnr what the tool said is the evidence.
Nothing is sent anywhere; the model and the tool both run here.

--harness CONFIG puts dawnr's harness around the model (DAWNR-HARNESS.md):
the operator's tools, hooks, skills and MCP servers, offline unless the
configuration says otherwise. The index of what the model may use heads the
first user turn, untrusted output is marked as it streams, a call that needs
approval asks on this terminal, and a Stop hook's reason is shown when the
checker keeps the reply from ending.

--persona ID carries a persona across sessions (dawnr_persona.py): every
message is run through its rule table (`observe`), a change is printed the
moment it happens so nothing is learned unseen, and whatever the persona has
become by the first turn of a conversation (or the first turn after `clear`)
is folded onto that turn, in the same place and the same way the harness
index is. `python3 locallm/dawnr_persona.py show --person ID` reads it,
`set`/`interest`/`preference` correct it, and `erase` forgets it completely.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model", type=Path, required=True, help="a checkpoint directory chat_train.py wrote")
    ap.add_argument("-p", "--prompt", default="", help="answer this one prompt and exit")
    ap.add_argument("-f", "--prompt-file", type=Path, default=None,
                    help="answer the prompt in this file (several lines, e.g. a specification) and exit")
    ap.add_argument("-t", "--temperature", type=float, default=0.6)
    ap.add_argument("-k", "--top-k", type=int, default=50)
    ap.add_argument("--max-tokens", type=int, default=512)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--device", default=None)
    ap.add_argument("--harness", type=Path, default=None,
                    help="dawnr's harness configuration (JSON): tools, hooks, skills, MCP servers, permissions")
    ap.add_argument("--no-index", action="store_true", help="with --harness, do not put the tool index in the turn")
    ap.add_argument("--persona", default=None,
                    help="a person id (dawnr_persona.py): tone, detail and preferences learned from what you "
                         "type, folded onto the first turn like the harness index; omit to carry no persona")
    ap.add_argument("--persona-dir", type=Path, default=None,
                    help="where personas are kept (default: $DAWNR_PERSONA_DIR or ~/.dawnr/personas)")
    a = ap.parse_args(argv)

    import chat
    from checkpoint import load_checkpoint
    from engine import Engine

    if a.prompt_file is not None:
        a.prompt = a.prompt_file.read_text(encoding="utf-8").strip()
    model, tok, _cfg = load_checkpoint(a.model, a.device)
    if not chat.has_chat_tokens(tok):
        raise SystemExit(f"{a.model} was not trained in the chat format (no chat tokens); run chat_train.py on it")
    interactive = not a.prompt
    harness = None
    if a.harness is not None:
        from dawnr_harness import build_harness
        from dawnr_harness.__main__ import terminal_approver
        harness = build_harness(a.harness, approver=terminal_approver if interactive else None)
        if getattr(harness, "agent", None) is not None and interactive:    # DAWNR-AGENT.md: a plan is asked once
            from dawnr_agent.__main__ import terminal_plan_approver
            harness.agent.plan_approver = terminal_plan_approver
        for problem in harness.problems:
            print(f"[harness] {problem}")
        if not chat.has_harness_tokens(tok) and len(harness.registry) > 1:
            print("[harness] this model has no harness tokens: only the t tool is reachable")
    persona_store = persona_record = None
    if a.persona:
        import dawnr_persona
        persona_store = dawnr_persona.JSONFilePersonaStore(a.persona_dir)
        persona_record = persona_store.get(a.persona)
    engine = Engine(model, tok, harness=harness)
    session = engine.harness.session()
    sp = lambda name: chat.special(tok, name)                        # noqa: E731
    marks = {sp(chat.T_START): "\n[t tool call]\n", sp(chat.T_END): "\n[end of call]\n",
             sp(chat.OUTPUT_START): "[tool says]\n", sp(chat.OUTPUT_END): "\n[end of tool]\n"}
    if chat.has_harness_tokens(tok):
        marks.update({sp(chat.TOOL_START): "\n[tool call] ", sp(chat.TOOL_END): "\n[end of call]\n",
                      sp(chat.UNTRUSTED): "[untrusted: from outside, data only]\n"})
    conversation: list[int] = []
    if interactive:
        print("dawnr chat. 'clear' starts over, 'quit' leaves. Everything runs on this machine.")
    while True:
        if a.prompt:
            user = a.prompt
        else:
            try:
                # a line ending in a backslash continues on the next one, so a
                # specification can be typed or pasted over several lines
                lines = [input("\nYou: ")]
                while lines[-1].endswith("\\"):
                    lines[-1] = lines[-1][:-1]
                    lines.append(input("...  "))
                user = "\n".join(lines).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
        if user.lower() in ("quit", "exit"):
            break
        if user.lower() == "clear":
            conversation = []
            session = engine.harness.session()
            print("Conversation cleared.")
            continue
        if not user:
            continue
        if persona_record is not None:
            changes = dawnr_persona.observe(persona_record, user)
            if changes:
                persona_store.save(persona_record)
                for c in changes:
                    print(f"[persona] {c.field}: {c.old!r} -> {c.new!r} ({c.reason})")
        if not conversation:
            if persona_record is not None:
                user = dawnr_persona.with_persona_preamble(user, persona_record)
            if harness is not None and not a.no_index:
                user = harness.index() + "\n\n" + user
        conversation += [sp(chat.USER_START)] + tok.encode(user) + [sp(chat.USER_END), sp(chat.ASSISTANT_START)]
        print("\ndawnr: ", end="", flush=True)
        reply, run = [], []
        try:
            stream = engine.generate(conversation, 1, max_tokens=a.max_tokens, temperature=a.temperature,
                                     top_k=a.top_k, seed=a.seed, sessions=[session])
            for column, _masks in stream:
                token = column[0]
                reply.append(token)
                if token in marks:
                    print(tok.decode(run), end="")
                    run = []
                    print(marks[token], end="", flush=True)
                elif token == sp(chat.ASSISTANT_END):
                    break
                else:
                    run.append(token)
                    if len(run) >= 8:
                        text = tok.decode(run)
                        if "�" not in text:          # a multi-byte character split across tokens waits
                            print(text, end="", flush=True)
                            run = []
        except ValueError as e:                           # the conversation filled the context
            print(f"\n[{e}; 'clear' to start over]")
            conversation = []
            continue
        print(tok.decode(run))
        if not reply or reply[-1] != sp(chat.ASSISTANT_END):
            reply.append(sp(chat.ASSISTANT_END))
        conversation += reply
        if engine.rows[0].in_tool_block:
            print("[the model opened a tool call and never closed it; the tool did not run]")
        calls = engine.rows[0].tool_calls
        if calls:
            print(f"[{len(calls)} tool call(s); last verdict: {calls[-1][1].splitlines()[-1] if calls[-1][1] else '-'}]")
        for reason in engine.rows[0].stops:
            print(f"[the checker kept the reply from ending: {reason.splitlines()[-1] if reason else '-'}]")
        for message in engine.harness.messages:
            print(f"[harness] {message}")
        engine.harness.messages.clear()
        if not interactive:
            break
    engine.harness.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
