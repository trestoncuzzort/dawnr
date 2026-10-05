"""mcp_server.py: dawnr's checker as an MCP server on stdio, for any MCP client.

    python locallm/dawnr_harness/mcp_server.py [--legacy-only | --modern-only]

One tool, `t_check`: parse, type check and run a t program on `Example:`
lines, answered with the t tool's verdict lines (locallm/t_tool.py) as text,
and {"lines", "passes"} as structured content.

Both protocol eras of the Model Context Protocol
(modelcontextprotocol.io/specification/2026-07-28): a modern request carries
`_meta` with io.modelcontextprotocol/protocolVersion and clientCapabilities;
one missing either is malformed (-32602), one naming a version this server
does not speak gets UnsupportedProtocolVersion (-32022) with the supported
list; `server/discover` answers versions, capabilities and identity. A legacy
client opens with `initialize` (2025-11-25 and earlier) and is answered with
the version it asked for when this server speaks it, else the newest legacy
one. Results carry resultType "complete" and the server's identity in
`_meta`; tools/list carries ttlMs and cacheScope. Batches (removed from the
protocol in 2025-06-18) are refused. Only valid MCP messages go to stdout.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

if __name__ == "__main__" and __package__ in (None, ""):
    # run as a file: import this module as part of its package and run that copy
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from dawnr_harness.mcp_server import main as _main
    raise SystemExit(_main())

from .mcp_common import (INTERNAL_ERROR, INVALID_PARAMS, INVALID_REQUEST, LEGACY_VERSIONS, MAX_LINE,  # noqa: E402
                         META_CAPS, META_SERVER, META_VERSION, METHOD_NOT_FOUND, MODERN_VERSIONS, PARSE_ERROR,
                         UNSUPPORTED_VERSION, encode, error, result)
from .tools import validate  # noqa: E402

SERVER_INFO = {"name": "dawnr-t-checker", "version": "0.1.0"}
MAX_PROGRAM = 65536
INSTRUCTIONS = "t_check runs dawnr's t checker: parse, type check, then run the program on Example lines."
T_CHECK = {
    "name": "t_check",
    "title": "dawnr's t checker",
    "description": "Parse, type check and run a t program on Example lines (Example: f(1, [2]) == 3); "
                   "answers one verdict per line: parses, well formed, then each example's pass or failure.",
    "inputSchema": {"type": "object",
                    "properties": {"program": {"type": "string", "maxLength": MAX_PROGRAM,
                                               "description": "a t program, from its `t 1` line"},
                                   "examples": {"type": "string", "maxLength": MAX_PROGRAM,
                                                "description": "Example: lines to run the program on"}},
                    "required": ["program"], "additionalProperties": False},
    "outputSchema": {"type": "object",
                     "properties": {"lines": {"type": "array", "items": {"type": "string"}},
                                    "passes": {"type": "boolean"}},
                     "required": ["lines", "passes"]},
}


class Server:
    info, instructions = SERVER_INFO, INSTRUCTIONS            # a subclass serving other tools names itself

    def __init__(self, *, modern: bool = True, legacy: bool = True):
        if not (modern or legacy):
            raise ValueError("a server must speak at least one era")
        self.modern, self.legacy = modern, legacy
        self.legacy_version: str | None = None

    def _complete(self, value: dict) -> dict:
        return {"resultType": "complete", **value, "_meta": {META_SERVER: self.info}}

    def handle(self, msg) -> dict | None:
        """One incoming message -> the reply to write, or None (notifications, stray responses)."""
        if isinstance(msg, list):
            return error(None, INVALID_REQUEST, "batches are not part of MCP")
        if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
            return error(msg.get("id") if isinstance(msg, dict) else None, INVALID_REQUEST, "not a JSON-RPC 2.0 message")
        method = msg.get("method")
        if not isinstance(method, str):
            return None                                   # a response: this server sends no requests
        if "id" not in msg:
            return None                                   # notifications/initialized, notifications/cancelled
        rid = msg["id"]
        params = msg.get("params") if isinstance(msg.get("params"), dict) else {}
        try:
            return self._request(rid, method, params)
        except Exception as e:                            # noqa: BLE001  (a bug answers, it does not kill the server)
            return error(rid, INTERNAL_ERROR, f"{type(e).__name__}: {e}")

    def _request(self, rid, method: str, params: dict) -> dict:
        if method == "initialize":
            if not self.legacy:
                return error(rid, METHOD_NOT_FOUND, "this server speaks only modern MCP (no initialize)",
                             {"supported": list(MODERN_VERSIONS)})
            asked = params.get("protocolVersion")
            self.legacy_version = asked if asked in LEGACY_VERSIONS else LEGACY_VERSIONS[0]
            return result(rid, {"protocolVersion": self.legacy_version,
                                "capabilities": {"tools": {"listChanged": False}},
                                "serverInfo": self.info, "instructions": self.instructions})
        meta = params.get("_meta") if isinstance(params.get("_meta"), dict) else {}
        if self.modern and META_VERSION in meta:
            if META_CAPS not in meta:
                return error(rid, INVALID_PARAMS, f"_meta is missing {META_CAPS}")
            asked = meta[META_VERSION]
            if asked not in MODERN_VERSIONS:
                return error(rid, UNSUPPORTED_VERSION, "Unsupported protocol version",
                             {"supported": list(MODERN_VERSIONS), "requested": asked})
        elif method == "server/discover" and not self.modern:
            return error(rid, METHOD_NOT_FOUND, f"unknown method {method}")
        elif self.legacy_version is None:
            return error(rid, INVALID_PARAMS, f"_meta is missing {META_VERSION} (or send initialize first)")
        if method == "server/discover":
            return result(rid, self._complete({"supportedVersions": list(MODERN_VERSIONS),
                                               "capabilities": {"tools": {}}, "instructions": self.instructions}))
        if method == "tools/list":
            return result(rid, self._complete({"tools": self.tools(), "ttlMs": 3600000, "cacheScope": "public"}))
        if method == "tools/call":
            if params.get("name") not in {t["name"] for t in self.tools()}:
                return error(rid, INVALID_PARAMS, f"Unknown tool: {params.get('name')}")
            return result(rid, self._complete(self.call(params["name"], params.get("arguments"))))
        return error(rid, METHOD_NOT_FOUND, f"unknown method {method}")

    def tools(self) -> list[dict]:
        """The tools this server lists. A subclass serving other tools overrides this and call()."""
        return [T_CHECK]

    def call(self, name: str, arguments) -> dict:
        """A CallToolResult for one tools/call of a listed tool."""
        return self._t_check(arguments)

    def _t_check(self, arguments) -> dict:
        errs = validate(T_CHECK["inputSchema"], arguments if arguments is not None else {})
        if errs:
            return {"content": [{"type": "text", "text": "; ".join(errs)}], "isError": True}
        from .checker import check
        passes, verdict = check(arguments["program"], arguments.get("examples", ""))
        lines = verdict.splitlines()
        return {"content": [{"type": "text", "text": verdict}], "structuredContent": {"lines": lines, "passes": passes},
                "isError": False}

    def serve(self, stdin=None, stdout=None) -> None:
        stdin = stdin or sys.stdin.buffer
        stdout = stdout or sys.stdout.buffer
        while True:
            raw = stdin.readline(MAX_LINE + 1)
            if not raw:
                return
            if len(raw) > MAX_LINE and not raw.endswith(b"\n"):
                while raw and not raw.endswith(b"\n"):
                    raw = stdin.readline(MAX_LINE + 1)
                reply = error(None, INVALID_REQUEST, f"message over {MAX_LINE} bytes")
            elif not raw.strip():
                continue
            else:
                try:
                    reply = self.handle(json.loads(raw.decode("utf-8")))
                except (UnicodeDecodeError, ValueError) as e:
                    reply = error(None, PARSE_ERROR, f"not JSON: {e}")
            if reply is not None:
                stdout.write(encode(reply))
                stdout.flush()


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    era = ap.add_mutually_exclusive_group()
    era.add_argument("--legacy-only", action="store_true", help="answer only the initialize handshake (tests)")
    era.add_argument("--modern-only", action="store_true", help="answer only per-request _meta (tests)")
    a = ap.parse_args(argv)
    Server(modern=not a.legacy_only, legacy=not a.modern_only).serve()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
