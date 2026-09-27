"""runtime.py: the harness: one call's path through registry, policy, hooks and approval, the stop check, the index.

A call's path (DAWNR-HARNESS.md section 2): look the tool up, validate its
arguments, let the operator's policy decide (offline denies network tools;
taint raises allow to ask for consequential tools once untrusted text is in
the conversation, after Beurer-Kellner et al., arXiv:2506.08837), run the
PreToolUse hooks (which may tighten, answer an ask, rewrite or annotate, but
never loosen a deny), ask the approver when the answer is ask (no approver:
deny), run the tool, run the PostToolUse hooks, mark the conversation tainted
if the output came from outside, and log it all.

build_harness() reads the operator's configuration; nothing else adds tools,
hooks, skills, servers or permissions.
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import checker, hooks as hooks_mod
from .hooks import Hooks, aggregate_post, aggregate_pre, aggregate_stop
from .tools import CallContext, CallError, Policy, Registry, Session, Tool, ToolResult, parse_call, strictest, validate

DEFAULT_HOOKS = {"PostToolUse": [{"matcher": "*", "hooks": [{"type": "builtin", "name": "t_check"}]}],
                 "Stop": [{"hooks": [{"type": "builtin", "name": "t_check"}]}]}
MAX_AUDIT_ARGS = 500
Approver = Callable[[str, dict, str], bool]


@dataclass
class StopResult:
    block: bool = False
    reason: str = ""
    messages: list = field(default_factory=list)


class Harness:
    def __init__(self, registry: Registry | None = None, policy: Policy | None = None, hooks: Hooks | None = None,
                 *, skills: dict | None = None, approver: Approver | None = None, audit_path: str | Path | None = None,
                 max_stop_blocks: int = 2, cwd: str | None = None):
        self.registry = registry if registry is not None else Registry([checker.t_tool_entry()])
        self.policy = policy if policy is not None else Policy()
        self.hooks = hooks if hooks is not None else Hooks()
        self.skills = skills or {}
        self.approver = approver
        self.audit: list[dict] = []
        self.audit_path = Path(audit_path) if audit_path else None
        self.max_stop_blocks = max_stop_blocks
        self.cwd = cwd or os.getcwd()
        self.messages: list[str] = []          # for the person (systemMessage), never for the model
        self.clients: list = []                # MCP clients to close
        self.problems: list[str] = []          # what loading the configuration skipped, with why

    @classmethod
    def with_t_tool(cls, fn=None) -> "Harness":
        """The engine's default: the t tool only, no hooks, offline. What the engine was before the harness."""
        return cls(Registry([checker.t_tool_entry(fn)]), Policy(), Hooks())

    def session(self) -> Session:
        return Session()

    # ------------------------------------------------------------- calls --

    def call_text(self, text: str, *, context: str = "", session: Session | None = None) -> ToolResult:
        """A call as the model writes it, `name {json}`."""
        try:
            name, args = parse_call(text)
        except CallError as e:
            self._log(session, "?", {"text": text[:MAX_AUDIT_ARGS]}, "unreadable", str(e))
            return ToolResult(str(e), is_error=True, source="harness")
        return self.call(name, args, context=context, session=session)

    def call(self, name: str, arguments: dict, *, context: str = "", session: Session | None = None) -> ToolResult:
        session = session or Session()
        tool = self.registry.get(name)
        if tool is None:
            self._log(session, name, arguments, "unknown", "")
            return ToolResult(f"unknown tool {name!r}; tools: {', '.join(self.visible_names()) or 'none'}",
                              is_error=True, source="harness")
        errs = validate(tool.input_schema, arguments)
        if errs:
            self._log(session, name, arguments, "invalid", "; ".join(errs))
            return ToolResult(f"{name}: " + "; ".join(errs), is_error=True, source="harness")
        decision, why = self.policy.decide(tool, session)
        if decision == "deny":
            self._log(session, name, arguments, "deny", why)
            return ToolResult(f"denied: {why}", is_error=True, source="harness")
        notes: list[str] = []
        untrusted_notes: list[str] = []
        if self.hooks.has("PreToolUse"):
            pre = aggregate_pre(self.hooks.run("PreToolUse", self._payload(session, context, tool_name=name,
                                                                             tool_input=arguments), name))
            self._note_errors(pre.errors, pre.messages)
            if pre.decision == "deny":
                self._log(session, name, arguments, "deny", f"hook: {pre.reason}")
                return ToolResult(f"blocked by a hook: {pre.reason or 'no reason given'}", is_error=True,
                                  source="harness")
            if pre.decision == "ask":
                decision, why = strictest(decision, "ask"), f"a hook asks: {pre.reason}"
            elif pre.decision == "allow" and decision == "ask":
                decision, why = "allow", "a hook allowed it"
            if pre.updated_input is not None:
                errs = validate(tool.input_schema, pre.updated_input)
                if errs:
                    self._log(session, name, pre.updated_input, "invalid", "hook input: " + "; ".join(errs))
                    return ToolResult(f"{name}: a hook rewrote the input into an invalid one: " + "; ".join(errs),
                                      is_error=True, source="harness")
                arguments = pre.updated_input
            # a note about an untrusted tool's own input (its arguments) is untrusted too: an attacker who gets
            # the model to echo a page's text into a call's arguments must not get an unmarked span out of it
            (untrusted_notes if tool.trust == "untrusted" else notes).extend(pre.contexts)
        if decision == "ask":
            approved = False
            if self.approver is not None:
                try:
                    approved = bool(self.approver(name, arguments, why))
                except Exception:                                  # noqa: BLE001  (a broken prompt is a no)
                    approved = False
            if not approved:
                reason = why if self.approver is None else f"{why}; not approved"
                self._log(session, name, arguments, "not approved", reason)
                return ToolResult(f"not run: {name} needs approval ({reason})" +
                                  ("" if self.approver else "; nobody is here to approve it"),
                                  is_error=True, source="harness")
        started = time.monotonic()
        try:
            out = tool.fn(arguments, CallContext(context=context, session=session))
        except Exception as e:                                     # noqa: BLE001  (a tool's bug is an answer)
            out = ToolResult(f"{name} failed: {type(e).__name__}: {e}", is_error=True, trust="trusted")
        result = out if isinstance(out, ToolResult) else ToolResult(str(out), trust=tool.trust)
        if tool.trust == "untrusted":
            result.trust = "untrusted"          # a tool declared untrusted never produces trusted text, errors included
        result.source = name
        if self.hooks.has("PostToolUse"):
            post = aggregate_post(self.hooks.run("PostToolUse", self._payload(
                session, context, tool_name=name, tool_input=arguments,
                tool_response={"text": result.text, "is_error": result.is_error, "trust": result.trust}), name))
            self._note_errors(post.errors, post.messages)
            if post.block:
                result = ToolResult(f"[output withheld by a hook: {post.reason}]", is_error=True, source=name)
            elif post.updated_output is not None:
                result.text = post.updated_output
            # same rule as PreToolUse's notes, now against the call's actual result: a hook's commentary on an
            # untrusted output (dawnr's checker quoting a few words of a fetched page, say) is itself untrusted,
            # never blended into a trusted span (ToolResult.spans(), DAWNR-HARNESS.md section 7)
            (untrusted_notes if result.trust == "untrusted" else notes).extend(post.contexts)
        result.notes = notes + result.notes
        result.untrusted_notes = untrusted_notes + result.untrusted_notes
        if result.trust == "untrusted":
            session.tainted = True
        self._log(session, name, arguments, "run", why, result=result, seconds=time.monotonic() - started)
        return result

    # -------------------------------------------------------------- stop --

    def stop(self, reply: str, *, program: str | None = None, context: str = "",
             session: Session | None = None) -> StopResult:
        """Run the Stop hooks on a finished reply: block (with the reason the model reads) or let it end."""
        session = session or Session()
        if not self.hooks.has("Stop"):
            return StopResult()
        d = aggregate_stop(self.hooks.run("Stop", self._payload(
            session, context, stop_hook_active=session.stop_hook_active, last_assistant_message=reply,
            final_program=program or "")))
        self._note_errors(d.errors, d.messages)
        if d.block and session.stop_blocks < self.max_stop_blocks:
            session.stop_blocks += 1
            session.stop_hook_active = True
            self._log(session, "Stop", {}, "block", d.reason)
            return StopResult(True, d.reason, d.messages)
        if d.block:
            self.messages.append(f"a Stop hook blocked again after {self.max_stop_blocks} blocks; the reply ends: "
                                 f"{d.reason}")
        return StopResult(False, "", d.messages)

    # ------------------------------------------------------------- index --

    def visible(self) -> list[Tool]:
        """Tools the model is offered: every tool the policy does not deny outright."""
        return [t for t in self.registry if self.policy.decide(t)[0] != "deny"]

    def visible_names(self) -> list[str]:
        return [t.name for t in self.visible()]

    def index(self) -> str:
        """The lines the model sees at the head of the first user turn."""
        lines = ["Tools:"] + [t.index_line() for t in self.visible()]
        if self.skills and "skill" in self.visible_names():
            lines += ["Skills:"] + [s.index_line() for s in self.skills.values()]
        return "\n".join(lines)

    # ------------------------------------------------------------ helpers --

    def _payload(self, session: Session, context: str, **fields) -> dict:
        return {"session_id": session.id, "cwd": self.cwd, "context": context, **fields}

    def _note_errors(self, errors: list, messages: list) -> None:
        self.messages += [f"hook error: {e}" for e in errors] + list(messages)

    def _log(self, session, tool, arguments, decision, why, result: ToolResult | None = None, seconds: float = 0.0):
        text = json.dumps(arguments, ensure_ascii=False)
        row = {"time": time.time(), "session": session.id if session else "", "tool": tool,
               "arguments": text if len(text) <= MAX_AUDIT_ARGS else text[:MAX_AUDIT_ARGS] + "...",
               "decision": decision, "why": why}
        if result is not None:
            row.update(is_error=result.is_error, trust=result.trust, chars=len(result.text),
                       notes=len(result.notes) + len(result.untrusted_notes), seconds=round(seconds, 3))
        self.audit.append(row)
        if self.audit_path is not None:
            try:
                with self.audit_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
            except OSError as e:
                self.messages.append(f"audit log not written: {e}")

    def close(self) -> None:
        for client in self.clients:
            try:
                client.close()
            except Exception:                                      # noqa: BLE001
                pass
        self.clients = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


# ------------------------------------------------------------ configuration --

CONFIG_KEYS = {"offline", "permissions", "taint_escalates", "hooks", "skills", "web", "mcp_servers", "audit"}


def _expand(value: str, env: dict) -> str:
    return hooks_mod.substitute(value, env)


def build_harness(config: dict | str | Path | None = None, *, approver: Approver | None = None,
                  connect_mcp: bool = True) -> Harness:
    """The harness an operator's configuration describes. No configuration: the t tool, the checker hook, offline."""
    base = Path.cwd()
    if isinstance(config, (str, Path)):
        path = Path(config)
        base = path.resolve().parent
        config = json.loads(path.read_text(encoding="utf-8"))
    config = dict(config or {})
    unknown = set(config) - CONFIG_KEYS
    if unknown:
        raise ValueError(f"unknown harness configuration keys: {', '.join(sorted(unknown))} "
                         f"(known: {', '.join(sorted(CONFIG_KEYS))})")
    env = {"DAWNR_HARNESS_DIR": str(base), "PYTHON": sys.executable}

    def resolve(p: str) -> Path:
        q = Path(_expand(p, env))
        return q if q.is_absolute() else base / q

    policy = Policy(rules=dict(config.get("permissions") or {}), offline=bool(config.get("offline", True)),
                    taint_escalates=bool(config.get("taint_escalates", True)))
    hooks_cfg = config.get("hooks", DEFAULT_HOOKS)
    hooks = Hooks.from_file(resolve(hooks_cfg)) if isinstance(hooks_cfg, str) else Hooks(hooks_cfg, base_dir=base)
    registry = Registry([checker.t_tool_entry()])
    harness = Harness(registry, policy, hooks, approver=approver,
                      audit_path=resolve(config["audit"]) if config.get("audit") else None)

    if config.get("skills"):
        from .skills import discover, script_tool, skill_tool
        skills, problems = discover([resolve(d) for d in config["skills"]])
        harness.skills, harness.problems = skills, harness.problems + problems
        if skills:
            registry.add(skill_tool(skills))
            if any((s.path / "scripts").is_dir() for s in skills.values()):
                registry.add(script_tool(skills))

    web = config.get("web")
    if web is not None:
        from .web import WebConfig, web_tools
        web = dict(web)
        search = web.pop("search", None)
        known = set(WebConfig.__dataclass_fields__)
        if set(web) - known:
            raise ValueError(f"unknown web keys: {', '.join(sorted(set(web) - known))}")
        for tool in web_tools(WebConfig(**web), search):
            registry.add(tool)

    for server, spec in (config.get("mcp_servers") or {}).items():
        if not connect_mcp:
            break
        from .mcp_client import MCPError, StdioClient, register_server
        spec = dict(spec)
        network = bool(spec.get("network", True))
        if policy.offline and network:
            harness.problems.append(f"mcp server {server}: not started, the harness is offline and the server is not "
                                    "marked \"network\": false")
            continue
        command = [_expand(spec["command"], env)] + [_expand(a, env) for a in spec.get("args", [])]
        cwd = str(resolve(spec["cwd"])) if spec.get("cwd") else str(base)
        client = StdioClient(command, env=spec.get("env"), cwd=cwd, timeout=float(spec.get("timeout", 30)),
                             probe_timeout=float(spec.get("probe_timeout", 5)), name=server)
        try:
            client.start()
            client.connect()
            _added, skipped = register_server(registry, server, client, permission=spec.get("permission", "ask"),
                                              network=network, describe=bool(spec.get("describe", False)),
                                              max_tools=int(spec.get("max_tools", 64)))
        except (MCPError, TimeoutError, OSError, ValueError) as e:
            client.close()
            harness.problems.append(f"mcp server {server}: {e}")
            continue
        harness.clients.append(client)
        harness.problems += [f"mcp server {server}: skipped {s}" for s in skipped]
    return harness
