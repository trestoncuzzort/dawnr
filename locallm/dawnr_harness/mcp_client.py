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
import time
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

    def _wait(self, timeout: float) -> bool:
        """True once the process has exited; never raises (a stuck server must not make close() unsafe)."""
        try:
            self.proc.wait(timeout=timeout)
            return True
        except subprocess.TimeoutExpired:
            return False

    def close(self) -> None:
        if self.proc is None or self._closed:
            return
        self._closed = True
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        if not self._wait(2):
            try:
                self.proc.terminate()
            except OSError:
                pass
            if not self._wait(2):
                self._kill()
                # a killed process is not guaranteed to be reaped promptly: SIGKILL cannot be blocked, but a
                # process stuck in uninterruptible I/O only dies once that syscall returns, so this can still
                # time out. Nothing more can be done from here, so this is the last wait: close() itself must
                # still return rather than raise, the same contract _kill() already gives kill() a few lines
                # up, and the one terminate() just above -- a caller (Harness.close(), __exit__) must be able
                # to treat "clean up this connection" as something that cannot fail.
                self._wait(2)
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

    def _paginate(self, method: str, key: str, max_pages: int, max_items: int,
                  overall_timeout: float | None = None) -> list[dict]:
        """Page through `method` by nextCursor, bounded three ways: a page count, an item count, and a total
        wall-clock budget across every page (default: one request's worth, self.timeout). The first two
        bound a server that answers instantly forever; without the third, one that always answers just
        inside its own per-request timeout could still hold up the whole listing for max_pages * timeout
        (mcp_client.py's own module docstring: "every request has a timeout" -- true per request, but
        pagination is many requests, and nothing previously bounded their sum).

        Each request still gets the full self.timeout, unshrunk: an earlier version of this method gave
        each page only the deadline's remaining time, so a slow-but-honest server (each page legitimately
        taking close to self.timeout) could have every one of its later pages time out for arriving a
        little late, losing tools already listed on the earlier ones -- register_server has no way to
        retry mid-list, so that failure is the whole server, not one page. Only *starting* another page is
        gated on the deadline; a page already in flight is judged the same as any single request everywhere
        else in this client, and its own timeout still raises on failure exactly as before this method
        existed. Total worst case is therefore one more self.timeout past overall_timeout, not unbounded.
        """
        deadline = time.monotonic() + (self.timeout if overall_timeout is None else overall_timeout)
        items, cursor = [], None
        for _ in range(max_pages):
            if time.monotonic() > deadline:
                break
            res = self.request(method, {"cursor": cursor} if cursor else {})
            page = res.get(key)
            if isinstance(page, list):
                items += [x for x in page if isinstance(x, dict)]
            cursor = res.get("nextCursor")
            if not cursor or len(items) >= max_items:
                break
        return items[:max_items]

    def list_tools(self, max_pages: int = 20, max_tools: int = 256) -> list[dict]:
        return self._paginate("tools/list", "tools", max_pages, max_tools)

    def list_resources(self, max_pages: int = 20, max_resources: int = 256) -> list[dict]:
        return self._paginate("resources/list", "resources", max_pages, max_resources)

    def list_prompts(self, max_pages: int = 20, max_prompts: int = 256) -> list[dict]:
        return self._paginate("prompts/list", "prompts", max_pages, max_prompts)

    def call_tool(self, name: str, arguments: dict, timeout: float | None = None) -> dict:
        return self.request("tools/call", {"name": name, "arguments": arguments}, timeout)

    def read_resource(self, uri: str, timeout: float | None = None) -> dict:
        return self.request("resources/read", {"uri": uri}, timeout)


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


def resource_to_tool_result(raw: dict, max_chars: int = 20000) -> ToolResult:
    """An MCP ReadResourceResult as the harness's answer, always untrusted (modelcontextprotocol.io's
    schema, github.com/modelcontextprotocol/modelcontextprotocol schema/draft/schema.ts,
    LATEST_PROTOCOL_VERSION "2026-07-28": ReadResourceResult.contents is (TextResourceContents |
    BlobResourceContents)[], each a {uri, mimeType?} plus either `text` or a base64 `blob`).

    A blob is never decoded or returned: its bytes are meant for a file or an image, not the model's
    context, and a hostile server can put anything at all in `blob` (up to mcp_client.py's own MAX_LINE
    cap on a single JSON-RPC message); only its declared size and type are reported, same as
    result_to_tool_result already does for a non-text content block from tools/call.
    """
    contents = raw.get("contents")
    if not isinstance(contents, list):
        return ToolResult("the server's resources/read answer had no contents array", is_error=True,
                          trust="untrusted")
    parts = []
    for item in contents:
        if not isinstance(item, dict):
            continue
        uri = item["uri"] if isinstance(item.get("uri"), str) else "?"
        if isinstance(item.get("text"), str):
            parts.append(item["text"])
        elif isinstance(item.get("blob"), str):
            mime = item.get("mimeType") if isinstance(item.get("mimeType"), str) else "unknown type"
            parts.append(f"[binary resource {uri}: {len(item['blob'])} base64 characters, {mime}, not shown]")
        else:
            parts.append(f"[resource {uri}: no text or blob content]")
    text = "\n".join(parts) if parts else "(empty resource)"
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n[truncated at {max_chars} characters]"
    return ToolResult(text, trust="untrusted")


def _one_line_entry(spec: dict, *fields: str, limit: int = 200) -> str:
    """A Resource or Prompt's own name/title/uri and description, on one line -- the server's untrusted
    text about itself, shown only inside an already-untrusted tool result (never the index; see
    register_server's `describe`), same treatment as a tool's own description gets there."""
    head = " ".join(one_line(str(spec[f]), 300) for f in fields if isinstance(spec.get(f), str))
    desc = spec.get("description")
    return one_line(head + (f" - {desc}" if isinstance(desc, str) and desc.strip() else ""), limit)


def _mcp_tool(name: str, description: str, schema: dict, run, *, permission: str, network: bool) -> Tool:
    """A harness-authored query tool for one server (resources_list, resources_read, prompts_list): unlike
    a tool the server itself declares, `description` here is dawnr's own fixed text, never the server's, so
    it is always shown in the index -- there is no tool-poisoning concern to gate it behind `describe`
    (DAWNR-HARNESS.md section 5) because nothing the server writes ever reaches this string."""
    return Tool(name, description, schema, run, permission=permission, trust="untrusted", network=network,
               consequential=True, origin=f"mcp:{name.split('__')[1]}")


def _register_resources(registry, server: str, client: StdioClient, *, permission: str, network: bool,
                        timeout: float | None, max_chars: int, skipped: list[str]) -> list[str]:
    """mcp__<server>__resources_list and ...resources_read, only if the server answers resources/list at
    all: registering a query tool for a feature the server does not have would just be one more line in
    the index that always answers "not supported". A server's own claim of support (its capabilities, from
    server/discover or initialize) is not trusted for this either (DAWNR-HARNESS.md section 5: "never used
    for permissions" -- the same reasoning applies to what gets offered at all), so this calls the real
    method and goes by whether it answers, not by what the server says about itself."""
    list_name, read_name = f"mcp__{server}__resources_list", f"mcp__{server}__resources_read"
    if list_name in registry or read_name in registry:
        skipped.append(f"resources: {list_name} or {read_name} already registered")
        return []
    try:
        client.list_resources()
    except MCPError as e:
        if e.code != METHOD_NOT_FOUND:
            skipped.append(f"resources/list: {e.message} ({e.code})")
        return []
    except TimeoutError as e:
        skipped.append(f"resources/list: {e}")
        return []

    def run_list(args: dict, ctx: CallContext) -> ToolResult:
        try:
            rows = client.list_resources()
        except MCPError as e:
            return ToolResult(f"the {server} server refused resources/list: {e.message} ({e.code})", is_error=True)
        except TimeoutError as e:
            return ToolResult(str(e), is_error=True)
        lines = [_one_line_entry(r, "name", "title", "uri") for r in rows if isinstance(r.get("uri"), str)]
        text = "\n".join(lines) if lines else "(no resources)"
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n[truncated at {max_chars} characters]"
        return ToolResult(text, trust="untrusted")

    def run_read(args: dict, ctx: CallContext) -> ToolResult:
        try:
            raw = client.read_resource(args["uri"], timeout)
        except MCPError as e:
            return ToolResult(f"the {server} server refused the read: {e.message} ({e.code})", is_error=True)
        except TimeoutError as e:
            return ToolResult(str(e), is_error=True)
        return resource_to_tool_result(raw, max_chars)

    read_schema = {"type": "object", "properties": {"uri": {"type": "string", "minLength": 1, "maxLength": 4096}},
                  "required": ["uri"], "additionalProperties": False}
    registry.add(_mcp_tool(list_name, f"List resources the {server} server exposes.",
                          {"type": "object", "properties": {}, "additionalProperties": False}, run_list,
                          permission=permission, network=network))
    registry.add(_mcp_tool(read_name, f"Read one resource the {server} server exposes, named by its uri "
                                     f"({list_name} lists them).", read_schema, run_read, permission=permission,
                          network=network))
    return [list_name, read_name]


def _register_prompts(registry, server: str, client: StdioClient, *, permission: str, network: bool,
                      max_chars: int, skipped: list[str]) -> list[str]:
    """mcp__<server>__prompts_list, under the same only-if-it-answers rule as _register_resources. Not
    prompts/get: dawnr's harness turns a prompt into a listing the model can read about, not one it can
    have the server render and inject as if it were dawnr's own -- the same reason a skill's instructions
    only ever come from the operator's own installed folder (DAWNR-HARNESS.md section 4), never a server."""
    list_name = f"mcp__{server}__prompts_list"
    if list_name in registry:
        skipped.append(f"prompts: {list_name} already registered")
        return []
    try:
        client.list_prompts()
    except MCPError as e:
        if e.code != METHOD_NOT_FOUND:
            skipped.append(f"prompts/list: {e.message} ({e.code})")
        return []
    except TimeoutError as e:
        skipped.append(f"prompts/list: {e}")
        return []

    def run_list(args: dict, ctx: CallContext) -> ToolResult:
        try:
            rows = client.list_prompts()
        except MCPError as e:
            return ToolResult(f"the {server} server refused prompts/list: {e.message} ({e.code})", is_error=True)
        except TimeoutError as e:
            return ToolResult(str(e), is_error=True)
        lines = [_one_line_entry(r, "name", "title") for r in rows if isinstance(r.get("name"), str)]
        text = "\n".join(lines) if lines else "(no prompts)"
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n[truncated at {max_chars} characters]"
        return ToolResult(text, trust="untrusted")

    registry.add(_mcp_tool(list_name, f"List prompt templates the {server} server exposes.",
                          {"type": "object", "properties": {}, "additionalProperties": False}, run_list,
                          permission=permission, network=network))
    return [list_name]


def register_server(registry, server: str, client: StdioClient, *, permission: str = "ask",
                    network: bool = True, describe: bool = False, max_tools: int = 64,
                    timeout: float | None = None, max_chars: int = 20000) -> tuple[list[str], list[str]]:
    """Register a connected server's tools as mcp__<server>__<tool>, plus, if it supports them,
    mcp__<server>__resources_list, ...resources_read and ...prompts_list: (names added, entries skipped
    with why).

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
    # resources and prompts are not individually registered tools (a resource is named by an open-ended
    # URI, not a small fixed menu the way tools are): one query tool per capability instead, added only if
    # the server actually answers it. Errors here must never drop the tools already added above, so each
    # helper catches its own (register_server as a whole already stands between a bad server and the rest
    # of the harness for tools/list; resources/list or prompts/list misbehaving must not cost the caller
    # tools that work fine).
    added += _register_resources(registry, server, client, permission=permission, network=network,
                                 timeout=timeout, max_chars=max_chars, skipped=skipped)
    added += _register_prompts(registry, server, client, permission=permission, network=network,
                               max_chars=max_chars, skipped=skipped)
    return added, skipped
