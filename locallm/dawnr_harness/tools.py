"""tools.py: the tool registry, the call syntax, the permission policy and the per-conversation session.

A tool declares what MCP's Tool type declares (name, description, a JSON
Schema for its input; modelcontextprotocol.io/specification/2026-07-28/server/tools)
plus what the harness needs to decide whether it may run: its default
permission (allow, ask, deny, as in Claude Code's permission rules), whether
its output is trusted, whether it reaches the network, and whether it is
consequential (effects outside this process). The policy is the operator's;
nothing a tool returns can change it.

The call syntax inside <|tool_start|> ... <|tool_end|> is the tool's name,
then its arguments as one JSON object (DAWNR-HARNESS.md section 1).
"""
from __future__ import annotations

import fnmatch
import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Callable

PERMISSIONS = ("allow", "ask", "deny")
TRUST = ("trusted", "untrusted")
_RANK = {"allow": 0, "ask": 1, "deny": 2}
NAME = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")          # MCP's tool-name rule
_CALL = re.compile(r"\s*([A-Za-z0-9_.-]{1,128})(.*)\Z", re.S)
MAX_INDEX_DESCRIPTION = 240


def strictest(*decisions: str) -> str:
    """deny over ask over allow (Claude Code's precedence when rules or hooks disagree)."""
    return max(decisions, key=_RANK.__getitem__)


class CallError(ValueError):
    """A call the harness cannot read; its message is what the model is told."""


@dataclass
class ToolResult:
    text: str
    is_error: bool = False
    trust: str = "trusted"
    notes: list[str] = field(default_factory=list)      # the harness's own annotations about a trusted call
    untrusted_notes: list[str] = field(default_factory=list)  # ... about a call whose input or output is untrusted
    source: str = ""
    data: dict | None = None                            # side data for the caller, never rendered

    def spans(self) -> list[tuple[bool, str]]:
        """(untrusted?, text) per output span: the tool's own text, then each trusted note, then each note that
        annotates an untrusted call. A note inherits the call's trust rather than always being marked trusted
        (runtime.py): the harness's own commentary on a page or an MCP result can itself quote a few words of
        that page's text (dawnr_harness/checker.py's verdicts), and OWASP LLM01:2025 is that outside text is
        marked and segregated, never blended into a trusted span unmarked."""
        return ([(self.trust == "untrusted", self.text)]
                + [(False, n) for n in self.notes]
                + [(True, n) for n in self.untrusted_notes])


@dataclass
class Session:
    """What the harness remembers about one conversation (one engine row)."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    tainted: bool = False            # untrusted text has entered this conversation
    stop_hook_active: bool = False   # a Stop hook has already blocked once in this reply
    stop_blocks: int = 0

    def new_turn(self) -> None:
        """A new reply: Stop-hook state is per reply (Claude Code's stop_hook_active); taint lasts the conversation."""
        self.stop_hook_active, self.stop_blocks = False, 0


@dataclass
class CallContext:
    context: str = ""                # the conversation as plain text (the t tool reads Example lines from it)
    session: Session | None = None


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict
    fn: Callable[[dict, CallContext], "str | ToolResult"]
    permission: str = "ask"
    trust: str = "trusted"
    network: bool = False
    consequential: bool = False
    origin: str = "builtin"
    show_description: bool = True    # False: the index shows the name and argument names only

    def __post_init__(self):
        if not NAME.match(self.name or ""):
            raise ValueError(f"tool name {self.name!r} is not 1-128 of A-Za-z0-9_.-")
        if self.permission not in PERMISSIONS:
            raise ValueError(f"tool {self.name}: permission {self.permission!r} is not one of {PERMISSIONS}")
        if self.trust not in TRUST:
            raise ValueError(f"tool {self.name}: trust {self.trust!r} is not one of {TRUST}")
        if not isinstance(self.input_schema, dict) or self.input_schema.get("type", "object") != "object":
            raise ValueError(f"tool {self.name}: the input schema must be a JSON Schema object of type object")

    def signature(self) -> str:
        props = self.input_schema.get("properties") or {}
        required = set(self.input_schema.get("required") or ())
        args = [p if p in required else p + "?" for p in props]
        return f"{self.name}({', '.join(args)})"

    def index_line(self) -> str:
        if not self.show_description or not self.description.strip():
            return self.signature()
        return f"{self.signature()}: {one_line(self.description, MAX_INDEX_DESCRIPTION)}"


def one_line(text: str, limit: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[:limit - 3] + "..."


class Registry:
    """Tools by name. Only code the operator runs adds to it; nothing a tool returns does."""

    def __init__(self, tools=()):
        self._tools: dict[str, Tool] = {}
        for t in tools:
            self.add(t)

    def add(self, tool: Tool, *, replace: bool = False) -> Tool:
        if tool.name in self._tools and not replace:
            raise ValueError(f"a tool named {tool.name} is already registered")
        self._tools[tool.name] = tool
        return tool

    def remove(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def __contains__(self, name) -> bool:
        return name in self._tools

    def __iter__(self):
        return iter(self._tools[n] for n in self.names())

    def __len__(self) -> int:
        return len(self._tools)


@dataclass
class Policy:
    """The operator's permissions: exact names and globs to allow, ask or deny."""
    rules: dict = field(default_factory=dict)
    offline: bool = True
    taint_escalates: bool = True

    def __post_init__(self):
        for pattern, decision in self.rules.items():
            if decision not in PERMISSIONS:
                raise ValueError(f"permission rule {pattern!r}: {decision!r} is not one of {PERMISSIONS}")

    def decide(self, tool: Tool, session: Session | None = None) -> tuple[str, str]:
        """(allow|ask|deny, why)."""
        if self.offline and tool.network:
            return "deny", "offline: the harness is offline and this tool reaches the network"
        if tool.name in self.rules:
            decision, why = self.rules[tool.name], f"the operator's rule for {tool.name}"
        else:
            matched = [(p, d) for p, d in self.rules.items()
                       if any(c in p for c in "*?[") and fnmatch.fnmatchcase(tool.name, p)]
            if matched:
                decision = strictest(*(d for _, d in matched))
                why = "the operator's rule " + ", ".join(p for p, d in matched if d == decision)
            else:
                decision, why = tool.permission, "the tool's default"
        if (decision == "allow" and self.taint_escalates and tool.consequential
                and session is not None and session.tainted):
            return "ask", "untrusted text is in this conversation and this tool has effects outside it"
        return decision, why


def parse_call(text: str) -> tuple[str, dict]:
    """`name {json}` -> (name, arguments). Raises CallError with what the model should fix."""
    m = _CALL.match(text or "")
    if not m:
        raise CallError("call: expected a tool name (A-Za-z0-9_.-), then its arguments as one JSON object")
    name, rest = m.group(1), m.group(2).strip()
    if not rest:
        return name, {}
    try:
        args = json.loads(rest)
    except ValueError as e:
        raise CallError(f"call {name}: the arguments are not JSON: {e}") from None
    if not isinstance(args, dict):
        raise CallError(f"call {name}: the arguments must be one JSON object, not {_json_type(args)}")
    return name, args


def format_call(name: str, arguments: dict | None = None) -> str:
    return name if not arguments else f"{name} {json.dumps(arguments, ensure_ascii=False)}"


# ---------------------------------------------------------------- schema --

def _json_type(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, int):
        return "integer"
    if isinstance(v, float):
        return "number"
    if isinstance(v, str):
        return "string"
    if isinstance(v, list):
        return "array"
    if isinstance(v, dict):
        return "object"
    return type(v).__name__


def _is(ty: str, v) -> bool:
    if ty == "integer":
        return (isinstance(v, int) and not isinstance(v, bool)) or (isinstance(v, float) and v.is_integer())
    if ty == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    return _json_type(v) == ty


def _same(a, b) -> bool:
    return _json_type(a) == _json_type(b) and json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def validate(schema: dict, value, path: str = "arguments", depth: int = 0) -> list[str]:
    """Errors of `value` against the JSON Schema subset the harness enforces (DAWNR-HARNESS.md section 2).

    Keywords outside the subset are left to the tool, which must validate
    its own input anyway (MCP: servers MUST validate all tool inputs).
    """
    if depth > 32:
        return [f"{path}: nested too deeply"]
    if not isinstance(schema, dict):
        return []
    ty = schema.get("type")
    if ty is not None:
        types = ty if isinstance(ty, list) else [ty]
        if not any(_is(t, value) for t in types):
            return [f"{path}: expected {' or '.join(types)}, got {_json_type(value)}"]
    errs = []
    if "enum" in schema and not any(_same(value, e) for e in schema["enum"]):
        errs.append(f"{path}: must be one of {json.dumps(schema['enum'])}")
    if "const" in schema and not _same(value, schema["const"]):
        errs.append(f"{path}: must be {json.dumps(schema['const'])}")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errs.append(f"{path}: shorter than {schema['minLength']} characters")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errs.append(f"{path}: longer than {schema['maxLength']} characters")
    if _is("number", value):
        if "minimum" in schema and value < schema["minimum"]:
            errs.append(f"{path}: below the minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errs.append(f"{path}: above the maximum {schema['maximum']}")
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            errs.append(f"{path}: not above {schema['exclusiveMinimum']}")
        if "exclusiveMaximum" in schema and value >= schema["exclusiveMaximum"]:
            errs.append(f"{path}: not below {schema['exclusiveMaximum']}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errs.append(f"{path}: fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errs.append(f"{path}: more than {schema['maxItems']} items")
        if isinstance(schema.get("items"), dict):
            for i, item in enumerate(value):
                errs += validate(schema["items"], item, f"{path}[{i}]", depth + 1)
    if isinstance(value, dict):
        props = schema.get("properties") or {}
        for key in schema.get("required") or ():
            if key not in value:
                errs.append(f"{path}: missing required {key!r}")
        extra = schema.get("additionalProperties", True)
        for key, v in value.items():
            if key in props:
                errs += validate(props[key], v, f"{path}.{key}", depth + 1)
            elif extra is False:
                errs.append(f"{path}: unexpected {key!r} (allowed: {', '.join(props) or 'none'})")
            elif isinstance(extra, dict):
                errs += validate(extra, v, f"{path}.{key}", depth + 1)
    return errs
