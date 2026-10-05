"""config.py: the "agent" section of the harness configuration, and the Agent it builds into a harness.

    "agent": {
      "roots": [{"name": "project", "path": "~/work/project", "mode": "write"},
                {"name": "notes", "path": "~/notes"}],
      "commands": [{"argv": ["git", "status"], "permission": "allow", "network": false, "writes": false},
                   {"argv": ["python3", "-m", "pytest", "-q", "--", "{path}..."], "network": false}],
      "sandbox": "bwrap",
      "state": "~/.local/state/dawnr-agent"
    }

Only the operator's configuration adds roots, rules or protections; nothing a
tool returns can. With no "agent" key the harness has none of these tools.
With one: the file tools over the roots (read tools allowed, write tools ask),
run_command (denied until the operator both allows the tool in "permissions"
and lists a rule; each rule asks unless it says "allow"), ps_list, and the
plan tool. A missing or wrong field fails loudly when the configuration loads,
never silently at the first call.

What the model may never write is fixed here too: the configuration file, the
audit log, the agent's state (journal and backups), the skill folders, every
hook and MCP server program named in the configuration, and the code that
enforces all of it (dawnr_harness, dawnr_agent, and the engine and chat
modules that mark untrusted text), matched by identity, plus `.git` by name
and whatever the operator lists under "protect".
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import threading
import time
from dataclasses import fields
from pathlib import Path

from . import paths
from .commands import (DEFAULT_MAX_OUTPUT, DEFAULT_TIMEOUT, HIDE_UNDER_HOME, MAX_TIMEOUT, PLACEHOLDERS, Bwrap,
                       CommandRule, CommandTools, ps_tool, safe_exec_path)
from .files import FileOps, FileTools, Limits, Preview
from .journal import Journal
from .loop import Budget
from .paths import DEFAULT_PROTECT, DEFAULT_SECRETS, Space

AGENT_KEYS = {"roots", "protect", "secrets", "commands", "command_path", "env", "sandbox", "processes",
              "check_writes", "state", "limits", "budget", "dry_run", "shell", "system", "sysinfo"}
RULE_KEYS = {"argv", "permission", "network", "writes", "timeout", "max_output", "env", "cwd"}
HERE = Path(__file__).resolve().parent
LOCALLM = HERE.parent
ENFORCEMENT = [LOCALLM / "dawnr_harness", HERE] + [LOCALLM / n for n in
                                                    ("engine.py", "chat.py", "chat_cli.py", "chat_pane.py",
                                                     "t_tool.py")]


class AgentConfigError(ValueError):
    pass


def default_state_dir() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "dawnr-agent"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "dawnr-agent"
    return Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state") / "dawnr-agent"


def _type(value, types, where: str):
    types = types if isinstance(types, tuple) else (types,)
    if not isinstance(value, types) or (isinstance(value, bool) and bool not in types):
        names = "/".join(t.__name__ for t in types)
        raise AgentConfigError(f"agent: {where} must be {names}, not {type(value).__name__}")
    return value


class Agent:
    """The agent's parts, attached to a harness as harness.agent."""

    def __init__(self, harness, space: Space, ops: FileOps | None, files: FileTools | None,
                 commands: CommandTools | None, budget: Budget, dry_run: bool = False, audit_path: Path | None = None,
                 shell=None):
        self.harness = harness
        self.space = space
        self.ops = ops
        self.files = files
        self.commands = commands
        self.shell = shell                 # shell.ShellTools: any command, over an overlay ("shell": true)
        self.system = None                 # system.SystemTools: the computer itself; `sysinfo` reads its state unasked
                                           # ("sysinfo": true), `pc` acts on it, asked every time ("system": true)
        self.budget = budget
        self.dry_run = dry_run
        self.plan_approver = None          # set by a front end: callable(DryRun) -> bool; never by the model
        self.audit_path = audit_path
        self.home_scan: dict = {}          # what the home directory's secret scan covered (register_agent)
        self.plans: list = []
        self._lock = threading.Lock()

    def preview(self, name: str, args: dict, overlay: dict, context: str = "") -> Preview:
        if self.files is not None and name.startswith("fs_"):
            return self.files.preview(name, args, overlay, context)
        if self.commands is not None and name == "run_command":
            return self.commands.preview(args)
        if self.shell is not None and name == "sh":
            return self.shell.preview(args, overlay)
        if self.system is not None and name == "sysinfo":
            decision, why = self.system.decide_sysinfo(args)
            return Preview(error=why) if decision == "deny" else Preview(
                summary="reads the state of the computer; changes nothing; its output enters as untrusted data",
                detail=[f"$ {args.get('command')}"])
        if self.system is not None and name == "pc":
            decision, why = self.system.decide(args)
            return Preview(error=why) if decision == "deny" else Preview(
                summary="runs on the computer itself, outside the sandbox; not simulated, not undone",
                detail=[f"$ {args.get('command')}"] + ([f"why: {args['why']}"] if args.get("why") else []))
        if name == "ps_list":
            return Preview(summary="lists the processes on this machine; the listing enters as untrusted data")
        tool = self.harness.registry.get(name)
        if tool is not None and tool.trust == "untrusted":
            return Preview(summary=f"calls {name}; its output enters as untrusted data (not simulated)")
        return Preview(summary=f"calls {name} (not simulated)")

    def record_plan(self, dry, outcome, session) -> None:
        row = {"time": round(time.time(), 3), "session": session.id if session else "", "plan": dry.digest,
               "steps": len(dry.views), "approved": outcome.approved, "ran": outcome.steps_run,
               "stopped": outcome.stopped}
        with self._lock:
            self.plans.append(row)
            if self.audit_path is not None:
                try:
                    self.audit_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(self.audit_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps(row, ensure_ascii=True) + "\n")
                except (OSError, ValueError) as e:
                    self.harness.messages.append(f"agent plan log not written: {e}")


def _rules(spec, space: Space, exec_path: str, problems: list, limits: dict) -> list:
    out = []
    for i, r in enumerate(_type(spec, list, "commands"), 1):
        where = f"commands[{i - 1}]"
        _type(r, dict, where)
        unknown = set(r) - RULE_KEYS
        if unknown:
            raise AgentConfigError(f"agent: {where}: unknown keys {', '.join(sorted(unknown))} "
                                   f"(known: {', '.join(sorted(RULE_KEYS))})")
        argv = r.get("argv")
        if (not isinstance(argv, list) or not argv or not all(isinstance(a, str) and a for a in argv)
                or len(argv) > 64):
            raise AgentConfigError(f"agent: {where}: argv is a list of 1 to 64 nonempty strings")
        if argv[0] in PLACEHOLDERS:
            raise AgentConfigError(f"agent: {where}: the program itself cannot be a placeholder")
        for k, tok in enumerate(argv):
            if tok.endswith("...") and tok in PLACEHOLDERS and k != len(argv) - 1:
                raise AgentConfigError(f"agent: {where}: {tok} must be the last token")
            if tok.startswith("{") and tok.endswith("}") and tok not in PLACEHOLDERS:
                raise AgentConfigError(f"agent: {where}: unknown placeholder {tok} "
                                       f"(known: {', '.join(PLACEHOLDERS)})")
        permission = r.get("permission", "ask")
        if permission not in ("allow", "ask"):
            raise AgentConfigError(f"agent: {where}: permission is allow or ask, not {permission!r} "
                                   "(a command that must not run is simply not listed)")
        timeout = float(_type(r.get("timeout", limits.get("command_timeout", DEFAULT_TIMEOUT)), (int, float),
                              f"{where}.timeout"))
        if not 0 < timeout <= MAX_TIMEOUT:
            raise AgentConfigError(f"agent: {where}: timeout must be in (0, {MAX_TIMEOUT:g}] seconds")
        max_output = int(_type(r.get("max_output", limits.get("command_output", DEFAULT_MAX_OUTPUT)), int,
                               f"{where}.max_output"))
        env = _type(r.get("env", {}), dict, f"{where}.env")
        if not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()):
            raise AgentConfigError(f"agent: {where}: env maps names to strings")
        program = argv[0]
        resolved = program if os.path.isabs(program) else shutil.which(program, path=exec_path)
        if not resolved or not os.path.isfile(resolved) or not os.access(resolved, os.X_OK):
            problems.append(f"command rule {i} ({' '.join(argv)}): {program} is not an executable on the command "
                            "PATH; the rule is not used")
            continue
        real = os.path.realpath(resolved)
        inside = space.display_of(real)
        if inside is not None and space.root(inside.split("/")[0]).write:
            problems.append(f"command rule {i} ({' '.join(argv)}): {program} is {inside}, inside a writable root, "
                            "where the agent could replace it; the rule is not used")
            continue
        cwd = r.get("cwd")
        if cwd is not None:
            _type(cwd, str, f"{where}.cwd")
        out.append(CommandRule(i, tuple(argv), real, permission, bool(r.get("network", True)),
                               bool(r.get("writes", True)), timeout, max_output, tuple(sorted(env.items())), cwd))
    return out


def _protected(harness, config: dict, config_path, base: Path, space: Space, state: Path, extra: list) -> None:
    """Fill the space's protected identities: what the model may read but never write."""
    targets = [state]
    if config_path is not None:
        targets.append(Path(config_path))
    if harness.audit_path is not None:
        targets.append(harness.audit_path)
    targets += [s.path for s in (harness.skills or {}).values()]
    for event_groups in (harness.hooks.groups.values() if hasattr(harness.hooks, "groups") else []):
        for _matcher, handlers in event_groups:
            for h in handlers:
                for word in [h.command] + list(h.args or []):
                    targets += _existing_path(word, base)
    for spec in (config.get("mcp_servers") or {}).values():
        if isinstance(spec, dict):
            for word in [spec.get("command", "")] + list(spec.get("args") or []):
                targets += _existing_path(word, base)
    targets += ENFORCEMENT
    targets += [Path(os.path.expanduser(p)) for p in extra]
    for t in targets:
        t = Path(t)
        try:
            st = os.stat(t)
        except (OSError, ValueError):
            # not there yet (an audit log before its first line): protect the name in its directory
            try:
                pst = os.stat(t.parent)
            except (OSError, ValueError):
                continue
            space.protected_entries.add((paths.ident(pst), t.name.casefold()))
            continue
        space.protected_ids.add(paths.ident(st))
        if Path(t).is_dir() and t not in (state,):
            space.protected_ids |= paths.identities([t], recurse=True, max_files=5000)
    # the state directory's contents too (its backups are the person's old bytes, not the model's to rewrite)
    space.protected_ids |= paths.identities([state], recurse=True, max_files=5000)
    try:
        space.protected_entries.add((paths.ident(os.stat(state)), "journal.jsonl"))
    except OSError:
        pass


def _existing_path(word: str, base: Path) -> list:
    if not isinstance(word, str) or not word or word.startswith("-"):
        return []
    word = word.replace("${DAWNR_HARNESS_DIR}", str(base)).replace("${PYTHON}", sys.executable)
    p = Path(os.path.expanduser(word))
    p = p if p.is_absolute() else base / p
    try:
        return [p] if p.exists() and p.resolve() != Path(sys.executable).resolve() else []
    except OSError:
        return []


def register_agent(harness, spec: dict, *, base: Path | None = None, config: dict | None = None,
                   config_path=None) -> Agent:
    """Build the agent the operator's "agent" section describes and add its tools to the harness's registry."""
    base = Path(base or Path.cwd())
    _type(spec, dict, "the agent section")
    unknown = set(spec) - AGENT_KEYS
    if unknown:
        raise AgentConfigError(f"agent: unknown keys {', '.join(sorted(unknown))} "
                               f"(known: {', '.join(sorted(AGENT_KEYS))})")

    def resolve(p: str) -> Path:
        q = Path(os.path.expanduser(p))
        return q if q.is_absolute() else base / q

    roots = []
    for k, r in enumerate(_type(spec.get("roots", []), list, "roots")):
        _type(r, dict, f"roots[{k}]")
        extra = set(r) - {"name", "path", "mode"}
        if extra:
            raise AgentConfigError(f"agent: roots[{k}]: unknown keys {', '.join(sorted(extra))}")
        mode = r.get("mode", "read")
        if mode not in ("read", "write"):
            raise AgentConfigError(f"agent: roots[{k}]: mode is read or write, not {mode!r}")
        try:
            roots.append(paths.make_root(r.get("name"), str(resolve(_type(r.get("path"), str, f"roots[{k}].path"))),
                                         mode == "write"))
        except ValueError as e:
            raise AgentConfigError(f"agent: roots[{k}]: {e}") from None
    protect = _type(spec.get("protect", []), list, "protect")
    names = [p for p in protect if isinstance(p, str) and not (p.startswith(("/", "~")) or os.path.isabs(p))]
    abs_paths = [p for p in protect if isinstance(p, str) and p not in names]
    secrets = spec.get("secrets")
    secret_names = DEFAULT_SECRETS if secrets is None else tuple(_type(secrets, list, "secrets"))
    space = Space(tuple(roots), secret_names=secret_names, protect_names=tuple(DEFAULT_PROTECT) + tuple(names))

    state = resolve(spec["state"]) if spec.get("state") else default_state_dir()
    lim = dict(_type(spec.get("limits", {}), dict, "limits"))
    limit_fields = {f.name for f in fields(Limits)}
    bad = set(lim) - limit_fields - {"command_timeout", "command_output"}
    if bad:
        raise AgentConfigError(f"agent: unknown limits {', '.join(sorted(bad))}")
    for k, v in lim.items():
        _type(v, (int, float), f"limits.{k}")
        if v <= 0:
            raise AgentConfigError(f"agent: limits.{k} must be positive")
    limits = Limits(**{k: v for k, v in lim.items() if k in limit_fields})
    space.link_scan_entries = int(limits.link_scan_entries)
    space.link_scan_seconds = float(limits.link_scan_seconds)
    # Every secret name, anywhere under the home directory, known by identity: DEFAULT_SECRETS, the sandbox's own
    # extra hardening dirs (HIDE_UNDER_HOME: .config/gh, .local/share/keyrings) and the operator's "secrets", which
    # adds to this list rather than replacing it (an override that leaves a default out still leaves the file
    # refused when it is hard-linked into a root). The scan is bounded; what it cannot reach, the read-time link
    # check still refuses (paths.home_secret_identities and Space.link_problem).
    home_secret_names = tuple(dict.fromkeys(DEFAULT_SECRETS + HIDE_UNDER_HOME + tuple(secret_names)))
    found, home_scan = paths.home_secret_identities(
        Path.home(), home_secret_names, skip={r.ident for r in roots}, devices={r.ident[0] for r in roots},
        max_entries=int(limits.home_scan_entries), seconds=float(limits.home_scan_seconds))
    space.secret_ids |= found
    command_limits = {k: v for k, v in lim.items() if k in ("command_timeout", "command_output")}
    budget_spec = _type(spec.get("budget", {}), dict, "budget")
    unknown_budget = set(budget_spec) - {f.name for f in fields(Budget)}
    if unknown_budget:
        raise AgentConfigError(f"agent: unknown budget keys {', '.join(sorted(unknown_budget))}")
    try:
        budget = Budget(**budget_spec)
    except ValueError as e:
        raise AgentConfigError(f"agent: {e}") from None
    check_writes = spec.get("check_writes", "block")
    if check_writes not in ("block", "note", "off"):
        raise AgentConfigError(f"agent: check_writes is block, note or off, not {check_writes!r}")

    try:
        state.mkdir(parents=True, exist_ok=True, mode=0o700)
    except OSError as e:
        raise AgentConfigError(f"agent: the state directory {state} cannot be made: {e.strerror}") from None
    _protected(harness, config or {}, config_path, base, space, state, abs_paths)
    try:
        space.hidden_ids.add(paths.ident(os.stat(state)))
    except OSError:
        pass

    journal = Journal(state)
    ops = FileOps(space, journal, limits, check_writes) if roots else None
    files = FileTools(ops) if roots else None

    exec_path = safe_exec_path(space, spec.get("command_path"))
    problems: list = []
    rules = _rules(spec.get("commands", []), space, exec_path, problems, command_limits)
    sandbox, sandbox_problem = None, None
    kind = spec.get("sandbox", "none")
    if kind not in ("none", "bwrap"):
        raise AgentConfigError(f"agent: sandbox is none or bwrap, not {kind!r}")
    if kind == "bwrap":
        program = shutil.which("bwrap", path=exec_path) or shutil.which("bwrap")
        if not program:
            sandbox_problem = "bwrap is not installed"
        else:
            sandbox = Bwrap(space, program)
            sandbox_problem = sandbox.probe()
        if sandbox_problem:
            problems.append(f"sandbox: {sandbox_problem}; no command will run")
    env = _type(spec.get("env", {}), dict, "env")
    commands = (CommandTools(space, rules, exec_path=exec_path, env=env, sandbox=sandbox,
                             sandbox_problem=sandbox_problem, offline=lambda: harness.policy.offline)
                if roots else None)

    shell = None
    if _type(spec.get("shell", False), bool, "shell") and ops is not None:
        from .shell import ShellTools
        program = shutil.which("bwrap", path=exec_path) or shutil.which("bwrap")
        shell = ShellTools(space, ops, program=program, state=state, exec_path=exec_path, env=env) if program else None
        if shell is None or shell.problem:
            problems.append(f"shell: {shell.problem if shell else 'bwrap is not installed'}; sh is not offered")
            shell = None

    agent = Agent(harness, space, ops, files, commands, budget, dry_run=bool(spec.get("dry_run", False)),
                  audit_path=state / "plans.jsonl", shell=shell)
    agent.home_scan = home_scan
    if home_scan["stopped"]:
        problems.append(f"agent: the home directory's secret scan stopped {home_scan['stopped']}, every level to "
                        f"depth {home_scan['whole_levels']} read whole: a secret deeper than that is not known by "
                        "identity; a hard link to it is still refused when read, because it has a name outside the "
                        "roots (limits home_scan_entries and home_scan_seconds raise the caps)")
    tools = []
    if files is not None:
        tools += files.tools()
    if commands is not None:
        tools += commands.tools()
    if shell is not None:
        tools += shell.tools()
        harness.clients.append(shell)      # closed with the harness: runs left unanswered are dropped
        if files is not None:
            files.count_hint = "with sh: grep -c, or sort | uniq -c"
    act, looks = _type(spec.get("system", False), bool, "system"), _type(spec.get("sysinfo", False), bool, "sysinfo")
    if act or looks:
        from .system import SystemTools
        agent.system = SystemTools(offline=lambda: harness.policy.offline, act=act,
                                   cwd=space.roots[0].path if space.roots else None)
        tools += agent.system.tools()
        if shell is not None:
            shell.elsewhere = "To look at the computer call `sysinfo` with this line" + ("; to change something on it, `pc`." if act else ".")
    if spec.get("processes", True):
        tools.append(ps_tool())
    from .plan import plan_tool
    tools.append(plan_tool(agent))
    for t in tools:
        harness.registry.add(t)
    harness.problems += problems
    if not roots:
        harness.problems.append("agent: no roots are configured, so there are no file tools and no commands")
    harness.agent = agent
    return agent


def build_agent(config: dict | str | Path, *, approver=None, plan_approver=None, connect_mcp: bool = True):
    """(harness, agent) from a harness configuration with an "agent" section."""
    from dawnr_harness import build_harness
    harness = build_harness(config, approver=approver, connect_mcp=connect_mcp)
    agent = getattr(harness, "agent", None)
    if agent is None:
        harness.close()
        raise AgentConfigError("the configuration has no \"agent\" section")
    agent.plan_approver = plan_approver
    return harness, agent
