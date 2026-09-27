"""mcp_common.py: what dawnr's MCP client and server share: versions, _meta keys, error codes, framing.

From the Model Context Protocol specification, revision 2026-07-28
(modelcontextprotocol.io/specification/2026-07-28: basic/index `_meta`,
basic/versioning, basic/transports/stdio, server/discover) and the legacy
revisions it stays compatible with (2025-11-25 and earlier, which open with
an `initialize` handshake).
"""
from __future__ import annotations

import json

MODERN_VERSIONS = ("2026-07-28",)
LEGACY_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")

META_VERSION = "io.modelcontextprotocol/protocolVersion"
META_CLIENT = "io.modelcontextprotocol/clientInfo"
META_CAPS = "io.modelcontextprotocol/clientCapabilities"
META_SERVER = "io.modelcontextprotocol/serverInfo"

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
MISSING_CAPABILITY = -32021
UNSUPPORTED_VERSION = -32022
MODERN_ERRORS = (MISSING_CAPABILITY, UNSUPPORTED_VERSION)

MAX_LINE = 4 * 1024 * 1024        # one message; a longer line is refused, not buffered without end


def encode(message: dict) -> bytes:
    """One newline-delimited JSON-RPC message. json.dumps escapes newlines inside strings, so none is embedded."""
    return (json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def error(id_, code: int, message: str, data=None) -> dict:
    err = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": id_, "error": err}


def result(id_, value: dict) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "result": value}
