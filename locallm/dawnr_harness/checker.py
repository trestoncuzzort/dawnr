"""checker.py: dawnr's checker in the harness, as the `t` tool and as the first hook, `t_check`.

The t tool is locallm/t_tool.py unchanged (parse, type check, run on the
conversation's Example lines); here it is registered as a tool with a schema
and a permission. The hook runs a checker on every t program that arrives
through any other tool (a web page, an MCP result, a skill's script) and on
the final answer, so a program from outside is checked before anything
relies on it and a failing answer does not end the reply (DAWNR-HARNESS.md
section 3).

Two verdict functions, deliberately not one: check() answers the model about
its own program (the `t` tool, dawnr's MCP server) and may quote it freely --
there is no attacker between the model and its own text. redacted_verdict()
answers about a program the hook found in another tool's input or output (or
in the final answer), and never quotes that text: only a fixed vocabulary
(parses/well formed yes-no, examples passed k of n, a closed set of error
classes), so a hostile page cannot put its own words into the model's
context through the checker's note (see redacted_verdict's docstring).
"""
from __future__ import annotations

import json
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
    """(passes, the t tool's verdict) for one program: the model's own, submitted directly to the `t` tool or
    to dawnr's MCP server (mcp_server.py's t_check), never text found inside another tool's input or output.
    Its verdict quotes the program (t_tool.py's `_short`), which is safe here because there is no attacker
    between the program and the model: the model wrote it, or is asking dawnr's server about one of its own.
    Text that arrived from outside goes through redacted_verdict() instead, never through this function."""
    import t_tool
    if len(program) > MAX_PROGRAM:
        return False, f"parses: no: the program is over {MAX_PROGRAM} characters"
    try:
        verdict = t_tool.call(program, context)
    except Exception as e:                                           # noqa: BLE001  (unchecked is not passed)
        return False, f"parses: no: the checker failed: {type(e).__name__}: {e}"
    return not failing(verdict), verdict


def _wf_classes(errs) -> str:
    """The SPEC rule key of each well-formedness error (check_wf.py's own RULES table keys, such as
    "valid-type" or "ensures-bool"): a small, fixed vocabulary the well-formedness checker itself chooses
    from, never the error's `.message`, which quotes the program's own parameter names, types and clause
    text and so is exactly the quoting redacted_verdict() exists to avoid."""
    return ",".join(sorted({getattr(e, "rule", None) or "error" for e in errs}))


def redacted_verdict(program: str, context: str = "") -> tuple[bool, str]:
    """(passes, a verdict on text the harness does not trust) for one program found inside another tool's
    input or output, or in the assistant's own final answer at Stop.

    Unlike check() (the `t` tool's own answer to the model's own program), nothing this returns is drawn
    from the program's or a page's own text: only a fixed vocabulary -- "parses: yes/no", "well formed:
    yes/no", "examples: passed k of n", and, on a failure, an error class from a small closed set (a Python
    exception's class name -- chosen by dawnr's own parser code, never by the input -- or check_wf's SPEC
    rule keys, or one of t_tool.run's own verdict tags: "arity", "undefined", "budget", "crash",
    "requires-excluded", or "fail" for a value mismatch). Before this fix the hook quoted the program's own
    parse/well-formedness error text (t_tool.py's `_short`, up to MAX_WHY=160 characters) into its note, and
    ToolResult.spans() rendered every note as trusted (see tools.py, runtime.py): an attacker who controls a
    fetched page or an MCP result could put an identifier or token of their choice into a program, and that
    text would reach the model unmarked and indistinguishable from the harness's own words (OWASP LLM01:2025;
    Beurer-Kellner et al., arXiv:2506.08837). Marking the note untrusted (tools.py, runtime.py) closes the
    channel the model is taught to distrust; this closes it structurally, so nothing the source chooses to
    write can appear in the note at all, marked or not.
    """
    import t_tool
    import surface
    import fuzz_lower
    if len(program) > MAX_PROGRAM:
        return False, "parses: no: class=too-long"
    try:
        task = surface.parse(program)
    except Exception as e:                                            # noqa: BLE001  (the class name is the answer)
        return False, f"parses: no: class={type(e).__name__}"
    try:
        errs = fuzz_lower.check_wf(task, positions={})                # positions=dict, not None: WfError.rule, not text
    except Exception as e:                                            # noqa: BLE001
        return False, f"parses: yes\nwell formed: no: class={type(e).__name__}"
    if errs:
        return False, f"parses: yes\nwell formed: no: class={_wf_classes(errs)}"
    lines = ["parses: yes", "well formed: yes"]
    examples = t_tool.parse_examples(context)
    if not examples:
        return True, "\n".join(lines)
    types = [p["type"] for p in task["params"]]
    passed, classes = 0, []
    for ex in examples:
        if "error" in ex:
            classes.append("unreadable")
            continue
        try:
            args = [t_tool._value(ty, v) for ty, v in zip(types, ex["args"])]
        except TypeError:
            classes.append("cannot-run")
            continue
        if len(ex["args"]) != len(types):
            classes.append("arity")
            continue
        got = t_tool.run(task, args)
        if got["verdict"] != "ok":
            classes.append(got["verdict"])
        elif json.dumps(got["got"]) == json.dumps(ex["expected"]):
            passed += 1
        else:
            classes.append("fail")
    total = len(examples)
    lines.append(f"examples: passed {passed} of {total}")
    if classes:
        lines.append("class=" + ",".join(sorted(set(classes))))
    return passed == total, "\n".join(lines)


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
                # redacted_verdict, not check(): this text came from another tool's input or output, so its
                # verdict must never quote the program's own words back into the model's context (issue 1)
                _ok, verdict = redacted_verdict(program, context)
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
        ok, verdict = redacted_verdict(program, context)
        if ok:
            return {}
        summary = "; ".join(verdict.splitlines())
        if payload.get("stop_hook_active"):
            return {"systemMessage": f"dawnr's checker still fails on the final program: {summary}"}
        return {"decision": "block", "reason": "dawnr's checker on the final program:\n" + verdict}
    return {}
