"""checker.py: dawnr's checker in the harness, as the `t` tool and as the first hook, `t_check`.

The t tool is locallm/t_tool.py unchanged (parse, type check, run on the
conversation's Example lines); here it is registered as a tool with a schema
and a permission. The hook runs the same checker on every t program that
arrives through any other tool (a web page, an MCP result, a skill's script)
and on the final answer, so a program from outside is checked before
anything relies on it and a failing answer does not end the reply
(DAWNR-HARNESS.md section 3).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOCALLM = HERE.parent
if str(LOCALLM) not in sys.path:
    sys.path.insert(0, str(LOCALLM))

from . import hooks  # noqa: E402
from .tools import CallContext, Tool  # noqa: E402

T_HEAD = re.compile(r"^t[ \t]+\d+[ \t]*$", re.M)
MAX_PROGRAM = 65536
MAX_PROGRAMS = 3

T_SCHEMA = {"type": "object",
            "properties": {"program": {"type": "string", "maxLength": MAX_PROGRAM,
                                       "description": "a t program, from its `t 1` line"}},
            "required": ["program"], "additionalProperties": False}


def t_tool_entry(fn=None) -> Tool:
    """The t tool as a registry entry; `fn(program, context) -> str` defaults to t_tool.call."""
    if fn is None:
        import t_tool
        fn = t_tool.call

    def run(args: dict, ctx: CallContext) -> str:
        return fn(args["program"], ctx.context)
    return Tool("t", "Check a t program: parse, type check, and run it on the Example lines in the conversation.",
                T_SCHEMA, run, permission="allow", trust="trusted", network=False, consequential=False)


def find_programs(text: str, limit: int = MAX_PROGRAMS) -> list[str]:
    """Every t program in text: a `t N` line through the brace that closes its body (or the text's end)."""
    out = []
    for m in T_HEAD.finditer(text or ""):
        depth, opened, end = 0, False, len(text)
        for i in range(m.end(), len(text)):
            c = text[i]
            if c == "{":
                depth, opened = depth + 1, True
            elif c == "}" and opened:
                depth -= 1
                if depth == 0:
                    nl = text.find("\n", i)
                    end = len(text) if nl < 0 else nl + 1
                    break
        program = text[m.start():end]
        program = program if program.endswith("\n") else program + "\n"
        if program not in out:
            out.append(program)
        if len(out) == limit:
            break
    return out


def failing(verdict: str) -> list[str]:
    """The lines of a t tool verdict that are not a pass."""
    bad = []
    for line in verdict.splitlines():
        line = line.strip()
        if line.startswith(("parses: no", "well formed: no")):
            bad.append(line)
        elif line.startswith("example ") and not line.endswith(": pass"):
            bad.append(line)
    return bad


def check(program: str, context: str = "") -> tuple[bool, str]:
    """(passes, the t tool's verdict) for one program."""
    import t_tool
    if len(program) > MAX_PROGRAM:
        return False, f"parses: no: the program is over {MAX_PROGRAM} characters"
    try:
        verdict = t_tool.call(program, context)
    except Exception as e:                                           # noqa: BLE001  (unchecked is not passed)
        return False, f"parses: no: the checker failed: {type(e).__name__}: {e}"
    return not failing(verdict), verdict


def _strings(value, out: list[str]) -> list[str]:
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, dict):
        for v in value.values():
            _strings(v, out)
    elif isinstance(value, list):
        for v in value:
            _strings(v, out)
    return out


@hooks.builtin("t_check")
def t_check_hook(payload: dict) -> dict:
    event = payload.get("hook_event_name")
    context = payload.get("context") or ""
    if event == "PostToolUse":
        if payload.get("tool_name") == "t":
            return {}                  # the t tool's answer already is the checker's verdict
        tool = payload.get("tool_name", "the tool")
        sources = [(f"{tool}'s input", s) for s in _strings(payload.get("tool_input"), [])]
        response = payload.get("tool_response") or {}
        sources.append((f"{tool}'s output", response.get("text") or ""))
        notes, seen = [], set()
        for where, text in sources:
            for program in find_programs(text):
                if program in seen or len(seen) == MAX_PROGRAMS:
                    continue
                seen.add(program)
                _ok, verdict = check(program, context)
                notes.append(f"dawnr's checker on the t program in {where}: " + "; ".join(verdict.splitlines()))
        if not notes:
            return {}
        return {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "\n".join(notes)}}
    if event == "Stop":
        # the final program: the last one in the answer's program (the last t call, or its text), else in the
        # assistant's message; tool outputs are not part of either
        program = ""
        for text in (payload.get("final_program") or "", payload.get("last_assistant_message") or ""):
            found = find_programs(text, limit=64)
            if found:
                program = found[-1]
                break
        if not program:
            return {}
        ok, verdict = check(program, context)
        if ok:
            return {}
        summary = "; ".join(failing(verdict))
        if payload.get("stop_hook_active"):
            return {"systemMessage": f"dawnr's checker still fails on the final program: {summary}"}
        return {"decision": "block", "reason": "dawnr's checker on the final program:\n" + verdict}
    return {}
