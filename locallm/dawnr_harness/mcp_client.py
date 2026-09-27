"""mcp_client.py: a minimal MCP client over stdio, and the registration of a server's tools into the registry.

The Model Context Protocol, revision 2026-07-28, with the stdio fallback to
the handshake revisions (modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio,
"Backward Compatibility"): the client launches the server as a subprocess and
writes one JSON-RPC message per line to its stdin, reading the same from its
stdout. It first probes with `server/discover`, its preferred version in
`_meta`:

* a DiscoverResult, or a modern error such as UnsupportedProtocolVersion
  (-32022) listing the versions the server speaks: a modern server; pick a
  mutual version and send `_meta` (version, client info, capabilities) on
  every request;
* any other error, or no answer within the probe timeout: a legacy server;
  send `initialize` and `notifications/initialized`, as revisions up to
  2025-11-25 require. The fallback is not keyed to one error code, as the
  specification says it must not be.

Then `tools/list` (paged by nextCursor, bounded) and `tools/call`. Results
without `resultType` are "complete" (legacy); an "input_required" result asks
for elicitation, which dawnr does not offer, so it is refused by name. Every
request has a timeout after which `notifications/cancelled` is sent. A
request the server sends (legacy servers may ask for roots or sampling) is
answered "method not found": this client declares no capabilities. Shutdown
closes stdin, waits, then terminates and kills.

Standard library only; reader threads rather than select(), which does not
work on pipes on Windows. The official Python SDK is an async framework with
third-party dependencies, which dawnr's harness does not take on.
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
from collections import deque
from itertools import count

from .mcp_common import (LEGACY_VERSIONS, MAX_LINE, META_CAPS, META_CLIENT, META_VERSION, METHOD_NOT_FOUND,
                         MODERN_ERRORS, MODERN_VERSIONS, UNSUPPORTED_VERSION, encode, error)
from .tools import NAME, CallContext, Tool, ToolResult, one_line

CLIENT_INFO = {"name": "dawnr-harness", "version": "0.1.0"}
_EOF = object()


class MCPError(Exception):
    def __init__(self, code: int, message: str, data=None):
        super().__init__(f"{message} ({code})")
        self.code, self.message, self.data = code, message, data


class StdioClient:
    def __init__(self, command: list[str], *, env: dict | None = None, cwd: str | None = None,
                 timeout: float = 30.0, probe_timeout: float = 5.0, name: str = "server",
                 max_line: int = MAX_LINE):
        if not command:
            raise ValueError("an MCP server needs a command")
        self.command, self.env, self.cwd, self.name = list(command), env, cwd, name
        self.timeout, self.probe_timeout, self.max_line = timeout, probe_timeout, max_line
        self.proc: subprocess.Popen | None = None
        self.era = self.version = None
        self.server_info: dict = {}
        self.capabilities: dict = {}
        self.instructions = ""          # untrusted: recorded, never shown to the model
        self.notifications: deque = deque(maxlen=100)
        self.stderr_tail: deque = deque(maxlen=50)
        self.stray: deque = deque(maxlen=20)
        self._ids = count(1)
        self._pending: dict = {}
        self._lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._closed = False

    # ------------------------------------------------------------- process --

    def start(self) -> "StdioClient":
        env = None if self.env is None else dict(os.environ, **self.env)
        self.proc = subprocess.Popen(self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, env=env, cwd=self.cwd)
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()
        return self

    def _read_stderr(self):
        for raw in iter(self.proc.stderr.readline, b""):
            self.stderr_tail.append(raw.decode("utf-8", errors="replace").rstrip())

    def _read_stdout(self):
        out = self.proc.stdout
        while True:
            raw = out.readline(self.max_line + 1)
            if not raw:
                break
            if len(raw) > self.max_line and not raw.endswith(b"\n"):
                self.stray.append(f"a message over {self.max_line} bytes; the connection is closed")
                self._kill()
                break
            try:
                msg = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                self.stray.append(raw[:200].decode("utf-8", errors="replace"))
                continue
            if not isinstance(msg, dict):
                self.stray.append(str(msg)[:200])
                continue
            if "method" in msg and "id" in msg:
                try:
                    self._send(error(msg["id"], METHOD_NOT_FOUND, "this client offers no capabilities"))
                except MCPError:
                    pass
            elif "method" in msg:
                self.notifications.append(msg)
            elif "id" in msg:
                with self._lock:
                    q = self._pending.get(msg["id"])
                if q is not None:
                    q.put(msg)
        with self._lock:
            for q in self._pending.values():
                q.put(_EOF)

    def _send(self, message: dict) -> None:
        if self.proc is None or self.proc.stdin is None or self._closed:
            raise MCPError(-1, f"the {self.name} server is not running")
        with self._write_lock:
            try:
                self.proc.stdin.write(encode(message))
                self.proc.stdin.flush()
            except (BrokenPipeError, OSError, ValueError) as e:
                raise MCPError(-1, f"the {self.name} server closed its input: {e}") from None

    def _kill(self):
        try:
            self.proc.kill()
        except OSError:
            pass

    def close(self) -> None:
        if self.proc is None or self._closed:
            return
        self._closed = True
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=2)
        for stream in (self.proc.stdout, self.proc.stderr):
            try:
                stream.close()
            except OSError:
                pass

    def __enter__(self):
        try:
            if self.proc is None:
                self.start()
            if self.era is None:
                self.connect()
        except BaseException:
            self.close()
            raise
        return self

    def __exit__(self, *exc):
        self.close()

    # ------------------------------------------------------------ requests --

    def _meta(self, version: str) -> dict:
        return {META_VERSION: version, META_CLIENT: CLIENT_INFO, META_CAPS: {}}

    def _raw(self, method: str, params: dict | None, timeout: float) -> dict:
        rid = next(self._ids)
        q: queue.Queue = queue.Queue(maxsize=1)
        with self._lock:
            self._pending[rid] = q
        try:
            message = {"jsonrpc": "2.0", "id": rid, "method": method}
            if params is not None:
                message["params"] = params
            self._send(message)
            try:
                reply = q.get(timeout=timeout)
            except queue.Empty:
                try:
                    self._send({"jsonrpc": "2.0", "method": "notifications/cancelled",
                                "params": {"requestId": rid, "reason": f"no answer in {timeout:g}s"}})
                except MCPError:
                    pass
                raise TimeoutError(f"the {self.name} server did not answer {method} in {timeout:g}s") from None
        finally:
            with self._lock:
                self._pending.pop(rid, None)
        if reply is _EOF:
            tail = "; ".join(list(self.stderr_tail)[-3:])
            raise MCPError(-1, f"the {self.name} server exited" + (f" ({tail})" if tail else ""))
        if "error" in reply:
            e = reply["error"] if isinstance(reply["error"], dict) else {}
            raise MCPError(e.get("code", -1), str(e.get("message", "error")), e.get("data"))
        res = reply.get("result")
        return res if isinstance(res, dict) else {}

    def request(self, method: str, params: dict | None = None, timeout: float | None = None) -> dict:
        if self.era is None:
            raise MCPError(-1, "connect() first")
        params = dict(params or {})
        if self.era == "modern":
            params["_meta"] = {**(params.get("_meta") or {}), **self._meta(self.version)}
        return self._raw(method, params, self.timeout if timeout is None else timeout)

    def notify(self, method: str, params: dict | None = None) -> None:
        message = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        self._send(message)

    def connect(self) -> dict:
        """Find the server's era and version (the stdio probe), and remember what it says about itself."""
        if self.proc is None:
            self.start()
        try:
            res = self._raw("server/discover", {"_meta": self._meta(MODERN_VERSIONS[0])}, self.probe_timeout)
            versions = res.get("supportedVersions")
            if isinstance(versions, list):
                self._modern(versions)
                self.capabilities = res.get("capabilities") or {}
                self.server_info = (res.get("_meta") or {}).get("io.modelcontextprotocol/serverInfo") or {}
                self.instructions = res.get("instructions") or ""
            else:
                self._legacy()
        except MCPError as e:
            if e.code == UNSUPPORTED_VERSION:
                self._modern((e.data or {}).get("supported") or [])
            elif e.code in MODERN_ERRORS:
                raise
            elif e.code == -1:
                raise
            else:
                self._legacy()
        except TimeoutError:
            self._legacy()
        return {"era": self.era, "version": self.version, "server_info": self.server_info}

    def _modern(self, versions) -> None:
        mutual = [v for v in MODERN_VERSIONS if v in versions]
        if not mutual:
            self.close()
            raise MCPError(UNSUPPORTED_VERSION, f"the {self.name} server speaks {versions}; this client speaks "
                                                f"{list(MODERN_VERSIONS)} and, by initialize, {list(LEGACY_VERSIONS)}")
        self.era, self.version = "modern", mutual[0]

    def _legacy(self) -> None:
        res = self._raw("initialize", {"protocolVersion": LEGACY_VERSIONS[0], "capabilities": {},
                                       "clientInfo": CLIENT_INFO}, self.timeout)
        version = res.get("protocolVersion")
        if version not in LEGACY_VERSIONS:
            self.close()
            raise MCPError(UNSUPPORTED_VERSION, f"the {self.name} server answered protocol version {version!r}")
        self.era, self.version = "legacy", version
        self.capabilities = res.get("capabilities") or {}
        self.server_info = res.get("serverInfo") or {}
        self.instructions = res.get("instructions") or ""
        self.notify("notifications/initialized")

    def list_tools(self, max_pages: int = 20, max_tools: int = 256) -> list[dict]:
        tools, cursor = [], None
        for _ in range(max_pages):
            res = self.request("tools/list", {"cursor": cursor} if cursor else {})
            page = res.get("tools")
            if isinstance(page, list):
                tools += [t for t in page if isinstance(t, dict)]
            cursor = res.get("nextCursor")
            if not cursor or len(tools) >= max_tools:
                break
        return tools[:max_tools]

    def call_tool(self, name: str, arguments: dict, timeout: float | None = None) -> dict:
        return self.request("tools/call", {"name": name, "arguments": arguments}, timeout)


def result_to_tool_result(raw: dict, max_chars: int = 20000) -> ToolResult:
    """An MCP CallToolResult as the harness's answer: text blocks joined, others named, always untrusted."""
    if raw.get("resultType", "complete") == "input_required":
        return ToolResult("the server asked for more input (elicitation), which dawnr does not provide",
                          is_error=True, trust="trusted")
    parts = []
    for block in raw.get("content") or []:
        if not isinstance(block, dict):
            continue
        kind = block.get("type")
        if kind == "text" and isinstance(block.get("text"), str):
            parts.append(block["text"])
        elif kind == "resource" and isinstance((block.get("resource") or {}).get("text"), str):
            parts.append(block["resource"]["text"])
        elif kind == "resource_link":
            parts.append(f"[resource link: {block.get('uri', '?')}]")
        else:
            parts.append(f"[{kind or 'unknown'} content not shown]")
    if not parts and "structuredContent" in raw:
        parts.append(json.dumps(raw["structuredContent"], ensure_ascii=False))
    text = "\n".join(parts)
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n[truncated at {max_chars} characters]"
    return ToolResult(text, is_error=bool(raw.get("isError")), trust="untrusted",
                      data={"structuredContent": raw.get("structuredContent")} if "structuredContent" in raw else None)


def register_server(registry, server: str, client: StdioClient, *, permission: str = "ask",
                    network: bool = True, describe: bool = False, max_tools: int = 64,
                    timeout: float | None = None, max_chars: int = 20000) -> tuple[list[str], list[str]]:
    """Register a connected server's tools as mcp__<server>__<tool>: (names added, tools skipped with why).

    The permission and `network` come from the operator's configuration, never
    from the server; descriptions are shown in the index only when the
    operator sets `describe`, because they are the server's own untrusted text.
    """
    if not NAME.match(server) or "__" in server:
        raise ValueError(f"MCP server name {server!r} must be A-Za-z0-9_.- without a double underscore")
    added, skipped = [], []
    for spec in client.list_tools(max_tools=max_tools):
        tname = spec.get("name")
        if not isinstance(tname, str) or not NAME.match(tname):
            skipped.append(f"{tname!r}: not a valid tool name")
            continue
        full = f"mcp__{server}__{tname}"
        if not NAME.match(full) or full in registry:
            skipped.append(f"{tname}: {full} is too long or already registered")
            continue
        schema = spec.get("inputSchema")
        if not isinstance(schema, dict) or schema.get("type", "object") != "object":
            skipped.append(f"{tname}: its inputSchema is not an object schema")
            continue

        def run(args: dict, ctx: CallContext, _name=tname) -> ToolResult:
            try:
                raw = client.call_tool(_name, args, timeout)
            except MCPError as e:
                return ToolResult(f"the {server} server refused the call: {e.message} ({e.code})", is_error=True)
            except TimeoutError as e:
                return ToolResult(str(e), is_error=True)
            return result_to_tool_result(raw, max_chars)

        registry.add(Tool(full, one_line(spec.get("description") or "", 300), schema, run, permission=permission,
                          trust="untrusted", network=network, consequential=True, origin=f"mcp:{server}",
                          show_description=describe))
        added.append(full)
    return added, skipped
