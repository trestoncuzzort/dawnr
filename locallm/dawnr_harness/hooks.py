"""hooks.py: deterministic handlers the harness runs before a tool call, after it, and before the model stops.

Claude Code's hook contract (code.claude.com/docs/en/hooks, read 2026-09-26),
kept where it applies:

* three events, PreToolUse, PostToolUse, Stop; configuration is
  {"hooks": {event: [{"matcher": ..., "hooks": [handler, ...]}]}};
* a matcher that is "*", "" or absent matches every tool; one made only of
  letters, digits, _, -, spaces, "," and "|" is a list of exact names;
  anything else is an unanchored regular expression;
* a command handler receives the event as JSON on stdin; exec form when
  "args" is given, shell form otherwise; exit 0 with a JSON object is a
  decision, exit 2 blocks (reason from the JSON, else stderr), any other exit
  is a non-blocking error whose valid JSON is still honoured;
* PreToolUse: hookSpecificOutput.permissionDecision (deny over ask over
  allow), permissionDecisionReason, updatedInput, additionalContext;
  PostToolUse: decision "block" + reason, additionalContext,
  updatedToolOutput; Stop: decision "block" + reason, and stop_hook_active in
  the input so a hook does not block forever.

What differs: handlers run in configuration order, not in parallel, so the
outcome never depends on scheduling; a "builtin" handler type runs one of the
harness's own Python hooks (the t checker is the first) under the same JSON
contract; and a hook can tighten the operator's policy but never loosen a
deny or offline mode (runtime.py applies that).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

EVENTS = ("PreToolUse", "PostToolUse", "Stop")
TOOL_EVENTS = ("PreToolUse", "PostToolUse")
DEFAULT_TIMEOUT = 60.0
MAX_REASON = 2048
_EXACT = re.compile(r"^[A-Za-z0-9_\-, |]+$")

BUILTINS: dict[str, Callable[[dict], dict]] = {}


def builtin(name: str):
    """Register a Python hook under `name`, for {"type": "builtin", "name": name} handlers."""
    def register(fn):
        BUILTINS[name] = fn
        return fn
    return register


class HookConfigError(ValueError):
    pass


def _type_name(value) -> str:
    return "null" if value is None else f"a {type(value).__name__}"


def matches(matcher: str | None, value: str | None) -> bool:
    if matcher in (None, "", "*"):
        return True
    if value is None:
        return False
    if _EXACT.match(matcher):
        return value in {m.strip() for m in re.split(r"[|,]", matcher) if m.strip()}
    return re.search(matcher, value) is not None


def substitute(text: str, env: dict) -> str:
    for key, val in env.items():
        text = text.replace("${" + key + "}", val)
    return text


@dataclass
class Handler:
    type: str
    command: str = ""
    args: list | None = None
    name: str = ""
    timeout: float = DEFAULT_TIMEOUT

    def describe(self) -> str:
        if self.type == "builtin":
            return f"builtin:{self.name}"
        return self.command if self.args is None else " ".join([self.command, *self.args])


@dataclass
class Outcome:
    handler: str
    output: dict = field(default_factory=dict)
    blocked: bool = False          # exit 2
    reason: str = ""
    error: str = ""                # a non-blocking failure, recorded


@dataclass
class PreDecision:
    decision: str | None = None    # allow | ask | deny | None (no opinion)
    reason: str = ""
    updated_input: dict | None = None
    contexts: list = field(default_factory=list)
    messages: list = field(default_factory=list)
    errors: list = field(default_factory=list)


@dataclass
class PostDecision:
    block: bool = False
    reason: str = ""
    updated_output: str | None = None
    contexts: list = field(default_factory=list)
    messages: list = field(default_factory=list)
    errors: list = field(default_factory=list)


@dataclass
class StopDecision:
    block: bool = False
    reason: str = ""
    messages: list = field(default_factory=list)
    errors: list = field(default_factory=list)


class Hooks:
    """The operator's hook configuration, validated when loaded so a typo fails loudly, not silently."""

    def __init__(self, config: dict | None = None, base_dir: str | Path | None = None):
        config = config or {}
        if not isinstance(config, dict):
            raise HookConfigError(f"a hook configuration is a {{event: [group, ...]}} object, not "
                                  f"{_type_name(config)}")
        if "hooks" in config and isinstance(config["hooks"], dict):
            config = config["hooks"]
        self.base_dir = Path(base_dir).resolve() if base_dir else Path.cwd()
        self.env = {"DAWNR_HARNESS_DIR": str(self.base_dir), "PYTHON": sys.executable}
        self.groups: dict[str, list[tuple[str | None, list[Handler]]]] = {e: [] for e in EVENTS}
        for event, groups in config.items():
            if event not in EVENTS:
                raise HookConfigError(f"unknown hook event {event!r}; dawnr has {', '.join(EVENTS)}")
            if not isinstance(groups, list):
                raise HookConfigError(f"{event}: expected a list of matcher groups")
            for g in groups:
                if not isinstance(g, dict) or not isinstance(g.get("hooks"), list):
                    raise HookConfigError(f"{event}: each group is {{\"matcher\": ..., \"hooks\": [...]}}")
                matcher = g.get("matcher")
                if matcher is not None and not isinstance(matcher, str):
                    raise HookConfigError(f"{event}: \"matcher\" is a string, not {_type_name(matcher)}")
                if matcher not in (None, "", "*") and not _EXACT.match(matcher):
                    try:
                        re.compile(matcher)
                    except re.error as e:
                        raise HookConfigError(f"{event}: matcher {matcher!r} is not a regular expression: {e}")
                self.groups[event].append((matcher, [self._handler(event, h) for h in g["hooks"]]))

    def _handler(self, event: str, h: dict) -> Handler:
        if not isinstance(h, dict):
            raise HookConfigError(f"{event}: a handler is an object")
        kind = h.get("type")
        raw_timeout = h.get("timeout", DEFAULT_TIMEOUT)
        try:
            timeout = float(raw_timeout)
        except (TypeError, ValueError):
            raise HookConfigError(f"{event}: \"timeout\" must be a number, not {raw_timeout!r}") from None
        if kind == "builtin":
            if h.get("name") not in BUILTINS:
                raise HookConfigError(f"{event}: no builtin hook {h.get('name')!r} (have {', '.join(sorted(BUILTINS))})")
            return Handler("builtin", name=h["name"], timeout=timeout)
        if kind == "command":
            if not isinstance(h.get("command"), str) or not h["command"]:
                raise HookConfigError(f"{event}: a command handler needs \"command\"")
            args = h.get("args")
            if args is not None and not (isinstance(args, list) and all(isinstance(a, str) for a in args)):
                raise HookConfigError(f"{event}: \"args\" is a list of strings")
            return Handler("command", command=h["command"], args=args, timeout=timeout)
        raise HookConfigError(f"{event}: handler type {kind!r} is not supported (command, builtin)")

    @classmethod
    def from_file(cls, path: str | Path) -> "Hooks":
        path = Path(path)
        return cls(json.loads(path.read_text(encoding="utf-8")), base_dir=path.parent)

    def has(self, event: str) -> bool:
        return bool(self.groups.get(event))

    def run(self, event: str, payload: dict, match_value: str | None = None) -> list[Outcome]:
        outcomes = []
        for matcher, handlers in self.groups.get(event, []):
            if event in TOOL_EVENTS and not matches(matcher, match_value):
                continue
            for h in handlers:
                outcomes.append(self._run(h, dict(payload, hook_event_name=event)))
        return outcomes

    def _run(self, h: Handler, payload: dict) -> Outcome:
        if h.type == "builtin":
            try:
                out = BUILTINS[h.name](payload) or {}
            except Exception as e:                                   # noqa: BLE001  (a hook's bug is recorded, not raised)
                return Outcome(h.describe(), error=f"raised {type(e).__name__}: {e}")
            return Outcome(h.describe(), output=out if isinstance(out, dict) else {})
        return self._run_command(h, payload)

    def _run_command(self, h: Handler, payload: dict) -> Outcome:
        env = dict(os.environ, **self.env)
        command = substitute(h.command, self.env)
        try:
            if h.args is not None:
                p = subprocess.run([command, *(substitute(a, self.env) for a in h.args)], input=json.dumps(payload),
                                   capture_output=True, text=True, encoding="utf-8", errors="replace",
                                   timeout=h.timeout, env=env, cwd=str(self.base_dir))
            else:
                p = subprocess.run(command, shell=True, input=json.dumps(payload), capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", timeout=h.timeout, env=env,
                                   cwd=str(self.base_dir))
        except subprocess.TimeoutExpired:
            return Outcome(h.describe(), error=f"timed out after {h.timeout:g}s")
        except OSError as e:
            return Outcome(h.describe(), error=f"could not run: {e}")
        out, parsed, parse_error = p.stdout.strip(), {}, ""
        if out.startswith("{") and out.endswith("}"):
            try:
                parsed = json.loads(out)
            except ValueError as e:
                parse_error = f"stdout is not JSON: {e}"
        stderr = p.stderr.strip()
        if p.returncode == 2:
            reason = _reason(parsed) or stderr or "blocked by a hook (exit 2)"
            return Outcome(h.describe(), output=parsed, blocked=True, reason=reason[:MAX_REASON])
        if p.returncode == 0:
            return Outcome(h.describe(), output=parsed, error=parse_error)
        first = stderr.splitlines()[0] if stderr else ""
        return Outcome(h.describe(), output=parsed, error=f"exit {p.returncode}: {first}".strip())


def _specific(out: dict) -> dict:
    s = out.get("hookSpecificOutput")
    return s if isinstance(s, dict) else {}


def _reason(out: dict) -> str:
    s = _specific(out)
    for v in (s.get("permissionDecisionReason"), s.get("reason"), out.get("reason")):
        if isinstance(v, str) and v:
            return v
    return ""


def _decision(out: dict) -> str | None:
    s = _specific(out)
    d = s.get("decision", out.get("decision"))
    return d if isinstance(d, str) else None


def _strictest(a: str | None, b: str) -> str:
    rank = {"allow": 0, "ask": 1, "deny": 2}
    return b if a is None or rank[b] > rank[a] else a


def aggregate_pre(outcomes: list[Outcome]) -> PreDecision:
    d = PreDecision()
    for o in outcomes:
        if o.error:
            d.errors.append(f"{o.handler}: {o.error}")
        s = _specific(o.output)
        if o.blocked:
            if d.decision != "deny":
                d.decision, d.reason = "deny", o.reason
            continue
        pd = s.get("permissionDecision")
        if pd == "block" or _decision(o.output) == "block":        # the older top-level spelling
            pd = "deny"
        if pd in ("allow", "ask", "deny"):
            before = d.decision
            d.decision = _strictest(d.decision, pd)
            if d.decision != before and pd != "allow":
                d.reason = _reason(o.output) or f"{o.handler} said {pd}"
        if isinstance(s.get("updatedInput"), dict):
            d.updated_input = s["updatedInput"]
        if isinstance(s.get("additionalContext"), str) and s["additionalContext"].strip():
            d.contexts.append(s["additionalContext"][:MAX_REASON])
        if isinstance(o.output.get("systemMessage"), str):
            d.messages.append(o.output["systemMessage"][:MAX_REASON])
    return d


def aggregate_post(outcomes: list[Outcome]) -> PostDecision:
    d = PostDecision()
    for o in outcomes:
        if o.error:
            d.errors.append(f"{o.handler}: {o.error}")
        s = _specific(o.output)
        if _decision(o.output) == "block":
            d.block, d.reason = True, d.reason or _reason(o.output) or f"{o.handler} withheld the output"
        if isinstance(s.get("updatedToolOutput"), str):
            d.updated_output = s["updatedToolOutput"]
        if isinstance(s.get("additionalContext"), str) and s["additionalContext"].strip():
            d.contexts.append(s["additionalContext"][:MAX_REASON])
        if isinstance(o.output.get("systemMessage"), str):
            d.messages.append(o.output["systemMessage"][:MAX_REASON])
    return d


def aggregate_stop(outcomes: list[Outcome]) -> StopDecision:
    d = StopDecision()
    for o in outcomes:
        if o.error:
            d.errors.append(f"{o.handler}: {o.error}")
        if o.blocked or _decision(o.output) == "block":
            d.block = True
            d.reason = d.reason or (o.reason if o.blocked else _reason(o.output)) or f"{o.handler} blocked the stop"
        if isinstance(o.output.get("systemMessage"), str):
            d.messages.append(o.output["systemMessage"][:MAX_REASON])
    return d
