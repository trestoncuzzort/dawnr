"""dawnr_api.py: an OpenAI-compatible chat completions server over dawnr's engine and harness.

    python3 locallm/dawnr_api.py --model <dir> [--harness CONFIG] [--host 127.0.0.1] [--port 8080]

Serves the subset of OpenAI's chat completions API (platform.openai.com/docs/api-reference/chat;
mirrored here from openai/openai-python's own type definitions, since the docs page is a JS shell
and the openapi.yaml is 2.7MB -- see the research receipt attached to this change) that an agent
framework, IDE plugin or eval harness expects from "an OpenAI-compatible endpoint": GET /v1/models,
GET /v1/models/{id}, and POST /v1/chat/completions with `messages`, `temperature`, `max_tokens` /
`max_completion_tokens`, `stream` (server-sent events), `stop`, `seed`, and the OpenAI
`tools`/`tool_calls` machinery for function-style tools the CLIENT declares. Standard library only
(http.server.ThreadingHTTPServer, no third-party dependency); the model, tokenizer and dawnr's own
harness (DAWNR-HARNESS.md) load once at startup and every request shares that one instance behind a
lock -- "one GPU job at a time" (AGENTS.md): never two generations running together.

WHAT A CLIENT-DECLARED TOOL IS, HERE. dawnr's chat format already has one call syntax for every
tool, <|tool_start|> name {json} <|tool_end|> (DAWNR-HARNESS.md section 1), used today only by tools
the OPERATOR configured (the t checker, skills, web, MCP servers). A client's OpenAI-style `tools`
array is offered to the model the same way, through the same tokens and the same call syntax, as
entries added into the harness's OWN registry for the lifetime of one request (removed again in a
`finally`, since only one request runs at a time behind the lock, so there is never a moment when
one request's tools are visible to another's). What differs from dawnr's own registry tools: the
harness never gets to force a client tool's output back into the model's context. Each client tool's
stub `fn` only records that a *validated* call happened (its arguments are checked against the JSON
Schema the client supplied, the same schema check every registry tool gets,
dawnr_harness.tools.validate, before `fn` ever runs) and generation stops the instant that call
closes, before the harness would force anything back into the stream. The call is reported to the
caller as `tool_calls`, exactly as OpenAI's own API stops generation for a function call rather than
answering it itself. dawnr's OWN registry tools (the t checker, an operator's skills, web or MCP
tools) are unaffected: they still run in-band under the harness's existing policy the moment their
call closes, their output is forced back into the model's context as always, and none of that ever
reaches the client -- an OpenAI-style caller did not ask for them and does not know their schemas, so
only the model's own text becomes the response `content`. A client's tool RESULT (its `tool`-role
message) is folded back into the conversation as a `tool_output` part marked `untrusted`
(chat.render_conversation's existing "untrusted" flag, the same one a fetched web page's text gets;
DAWNR-HARNESS.md section 7): computation this server did not run and cannot vouch for is exactly what
"untrusted" means here, whether it came from a web page or from the other tool driving this API.

DEVIATIONS FROM THE REFERENCE (recorded on the research receipt too):
* No `function_call`/`function` role (deprecated in OpenAI's own spec); `n` must be 1 (dawnr answers
  one choice at a time; batching samples would need its own client-tool bookkeeping per row for
  little benefit here); no `logprobs`, `presence_penalty`, `frequency_penalty`, `logit_bias`, image
  or audio content parts, or `service_tier`. `tool_choice` is `"auto"` (default) or `"none"`, never
  `"required"` or a named tool -- dawnr's grammar (engine.py) has no way to force a specific call.
  `top_p` is accepted and ignored (the engine samples by temperature and top_k only); `top_k` is
  accepted as a dawnr-specific extension, like `seed`'s use here to pick the sampling RNG. Defaults
  for `temperature` (0.6) and `top_k` (50) follow chat_cli.py's own choice for talking to dawnr, not
  OpenAI's raw defaults (temperature 1, no top_k) -- OpenAI's defaults read noticeably worse from a
  model this size. Every request is served strictly one at a time (a global lock), so this is not a
  high-throughput endpoint. A system/developer message is folded into the first user turn (dawnr has
  no system role, chat.py); the optional `name` field on a message is ignored. Only one open
  (unresolved) tool call is supported per assistant turn from the client's side, matching how the
  engine itself works: it calls one tool, waits for that call to close, and only then can call again.
  `tool_choice` or `n` given a value this server cannot honour is a 400, not a silent approximation.
  A finished reply that ran past its wall-clock deadline (--timeout) or its call budget (--max-calls)
  is reported as `finish_reason: "length"`; OpenAI's enum has no "timeout" value to use instead.

Bound to 127.0.0.1 by default. --api-key (or $DAWNR_API_KEY) requires a matching `Authorization:
Bearer <token>` on every request, compared with secrets.compare_digest. Request bodies are capped
(--max-request-bytes) and every reply is bounded by a wall-clock deadline (--timeout); a request that
cannot get the generation lock within --lock-timeout gets a clear 503 rather than hanging forever.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterator

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import chat  # noqa: E402
from dawnr_harness.tools import Tool, ToolResult, format_call  # noqa: E402
from engine import Engine, reply_parts  # noqa: E402

SERVER_NAME = "dawnr-api"
DEFAULT_TEMPERATURE = 0.6           # chat_cli.py's own default, not OpenAI's (see the module docstring)
DEFAULT_TOP_K = 50
DEFAULT_MAX_TOKENS = 512
MAX_TOKENS_CAP = 4096
MAX_REQUEST_BYTES = 1 << 20         # 1 MiB: ample for a chat request, small enough to bound memory
MAX_MESSAGES = 200
DEFAULT_TIMEOUT = 120.0             # seconds, wall clock, per reply
DEFAULT_LOCK_TIMEOUT = 300.0        # seconds waiting for another request's generation to finish


class ApiError(Exception):
    """Answered as OpenAI's {"error": {...}} envelope, with the HTTP status to send it under."""

    def __init__(self, status: int, message: str, *, type_: str = "invalid_request_error",
                code: str | None = None, param: str | None = None):
        super().__init__(message)
        self.status, self.message, self.type_, self.code, self.param = status, message, type_, code, param

    def body(self) -> dict:
        return {"error": {"message": self.message, "type": self.type_, "param": self.param, "code": self.code}}


# ------------------------------------------------------- OpenAI messages -> a dawnr conversation --

def flatten_content(content) -> str:
    """A message's `content` (a string, or a list of content parts) as plain text; dawnr is text-only."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out = []
        for part in content:
            if not isinstance(part, dict) or part.get("type") != "text" or not isinstance(part.get("text"), str):
                raise ApiError(400, f"unsupported content part {part!r}; dawnr is text-only", param="messages")
            out.append(part["text"])
        return "".join(out)
    raise ApiError(400, f"unsupported message content of type {type(content).__name__}", param="messages")


def _assistant_turn(message: dict, tool_results: list[dict]) -> dict:
    """One OpenAI assistant message, plus the `tool` messages answering every one of its tool_calls,
    as one dawnr assistant message: a list of parts (an optional leading text part, then a (tool,
    tool_output) pair per call, in the order the calls were made). Every declared call must have a
    matching result -- real OpenAI's own API enforces the same thing before it will answer again, so
    this is not an added restriction; dawnr's engine also never leaves a call without an answer."""
    parts = []
    text = flatten_content(message.get("content"))
    if text:
        parts.append({"type": "text", "text": text})
    by_id: dict[str, dict] = {}
    for call in message.get("tool_calls") or []:
        if not isinstance(call, dict) or call.get("type") != "function" or not isinstance(call.get("function"), dict):
            raise ApiError(400, f"unsupported tool_calls entry {call!r}; only type \"function\" is supported",
                           param="messages")
        cid = call.get("id")
        if not isinstance(cid, str) or not cid:
            raise ApiError(400, "a tool_calls entry needs a string \"id\"", param="messages")
        if cid in by_id:
            raise ApiError(400, f"tool_call id {cid!r} is declared twice", param="messages")
        fn = call["function"]
        name = fn.get("name")
        if not isinstance(name, str) or not name:
            raise ApiError(400, "a tool_calls entry's function needs a \"name\"", param="messages")
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except ValueError as e:
            raise ApiError(400, f"tool_calls[].function.arguments is not JSON: {e}", param="messages") from None
        if not isinstance(args, dict):
            raise ApiError(400, "tool_calls[].function.arguments must be a JSON object", param="messages")
        by_id[cid] = {"type": "tool", "text": format_call(name, args)}
    results_by_id: dict[str, dict] = {}
    for tm in tool_results:
        cid = tm.get("tool_call_id")
        if cid not in by_id:
            raise ApiError(400, f"a \"tool\" message answers tool_call_id {cid!r}, which the preceding "
                           "assistant message did not call", param="messages")
        if cid in results_by_id:
            raise ApiError(400, f"tool_call_id {cid!r} is answered more than once", param="messages")
        results_by_id[cid] = {"type": "tool_output", "text": flatten_content(tm.get("content")), "untrusted": True}
    missing = [cid for cid in by_id if cid not in results_by_id]
    if missing:
        raise ApiError(400, f"tool_call_id(s) {missing} have no matching \"tool\" message", param="messages")
    for cid, part in by_id.items():
        parts.append(part)
        parts.append(results_by_id[cid])
    if not parts:
        raise ApiError(400, "an assistant message needs content or tool_calls", param="messages")
    content_out = text if len(parts) == 1 and parts[0]["type"] == "text" else parts
    return {"role": "assistant", "content": content_out}


def to_conversation(messages) -> tuple[dict, bool]:
    """OpenAI `messages` as a dawnr conversation, and whether the last turn is unfinished (the last
    message is a tool result, so the model should CONTINUE the assistant turn it belongs to, rather
    than start a new one). system/developer messages fold into the next user turn (dawnr has no
    system role, chat.py); consecutive user turns merge the same way."""
    if not isinstance(messages, list) or not messages:
        raise ApiError(400, "\"messages\" must be a non-empty array", param="messages")
    if len(messages) > MAX_MESSAGES:
        raise ApiError(400, f"\"messages\" has {len(messages)} entries; the limit is {MAX_MESSAGES}",
                       param="messages")
    out: list[dict] = []
    pending: list[str] = []
    i = 0
    while i < len(messages):
        m = messages[i]
        if not isinstance(m, dict):
            raise ApiError(400, f"messages[{i}] must be an object", param="messages")
        role = m.get("role")
        if role in ("system", "developer", "user"):
            text = flatten_content(m.get("content"))
            if text:
                pending.append(text)
            i += 1
            continue
        if role == "assistant":
            if pending:
                out.append({"role": "user", "content": "\n\n".join(pending)})
                pending = []
            elif not out or out[-1]["role"] != "user":
                raise ApiError(400, "the first message dawnr answers must be a user (or system) message",
                               param="messages")
            j = i + 1
            results = []
            while j < len(messages) and isinstance(messages[j], dict) and messages[j].get("role") == "tool":
                results.append(messages[j])
                j += 1
            out.append(_assistant_turn(m, results))
            i = j
            continue
        if role == "tool":
            raise ApiError(400, f"messages[{i}]: a \"tool\" message must directly follow the assistant "
                           "message whose tool_calls it answers", param="messages")
        raise ApiError(400, f"messages[{i}]: unknown role {role!r}", param="messages")
    if pending:
        out.append({"role": "user", "content": "\n\n".join(pending)})
    if not out:
        raise ApiError(400, "\"messages\" has nothing for dawnr to answer", param="messages")
    return {"messages": out}, out[-1]["role"] == "assistant"


def render_for_continuation(tokenizer, conversation: dict) -> list[int]:
    """Ids that resume an assistant turn already in progress (the last message left the model mid
    reply, e.g. the client just supplied a tool result): the conversation renders as usual and the
    trailing <|assistant_end|> is trimmed off, so generation picks up right where that turn left off
    -- chat.render_for_completion's counterpart for a turn that is not starting fresh."""
    messages = conversation.get("messages") or []
    if not messages or messages[-1].get("role") != "assistant":
        raise ValueError("render_for_continuation needs a conversation ending in an assistant message")
    ids, _ = chat.render_conversation(tokenizer, conversation)
    end = chat.special(tokenizer, chat.ASSISTANT_END)
    if not ids or ids[-1] != end:
        raise ValueError("the rendered conversation does not end in <|assistant_end|>")
    return ids[:-1]


# ---------------------------------------------------------------------------- client-declared tools --

def parse_client_tools(tools_field, tool_choice, reserved_names: set[str], record: list) -> dict[str, Tool]:
    """The request's OpenAI-shaped `tools` as registry Tool entries, keyed by name. Each one's `fn`
    only appends (name, arguments) to `record` once its arguments pass the client's own JSON Schema
    (dawnr_harness.tools.validate, run by the harness before `fn` is ever called) -- the caller
    (run_turn) watches `record` grow to know a call happened and to answer with it, never letting the
    harness force anything back into the model's context for it (the module docstring)."""
    if tool_choice not in (None, "auto", "none"):
        raise ApiError(400, f"tool_choice {tool_choice!r} is not supported; dawnr offers \"auto\" or \"none\" "
                       "(it has no way to force one specific call)", param="tool_choice")
    if not tools_field or tool_choice == "none":
        return {}
    if not isinstance(tools_field, list):
        raise ApiError(400, "\"tools\" must be an array", param="tools")
    out: dict[str, Tool] = {}
    for t in tools_field:
        if not isinstance(t, dict) or t.get("type") != "function" or not isinstance(t.get("function"), dict):
            raise ApiError(400, f"unsupported tool {t!r}; only {{\"type\": \"function\", \"function\": "
                           "{...}}} is supported", param="tools")
        fn = t["function"]
        name = fn.get("name")
        if not isinstance(name, str) or not name:
            raise ApiError(400, "a tool's function needs a \"name\"", param="tools")
        if name in reserved_names:
            raise ApiError(400, f"tool name {name!r} is already one of dawnr's own tools", param="tools")
        if name in out:
            raise ApiError(400, f"tool name {name!r} is declared twice", param="tools")
        schema = fn.get("parameters")
        if schema is None:
            schema = {"type": "object", "properties": {}}
        if not isinstance(schema, dict):
            raise ApiError(400, f"tool {name!r}: \"parameters\" must be a JSON Schema object", param="tools")

        def make_fn(name):
            def fn(args, _ctx):
                record.append((name, dict(args)))
                return ToolResult("", trust="untrusted", source=name)
            return fn
        try:
            out[name] = Tool(name, fn.get("description") or "", schema, make_fn(name), permission="allow",
                             trust="untrusted", network=False, consequential=False, origin="client")
        except ValueError as e:
            raise ApiError(400, f"tool {name!r}: {e}", param="tools") from None
    return out


# ------------------------------------------------------------------------------- driving the engine --

def _stop_cut(text: str, stops) -> int | None:
    """The earliest index where some stop string fully occurs in text, or None."""
    hits = [text.index(s) for s in stops if s and s in text]
    return min(hits) if hits else None


def _safe_flush_len(text: str, stops) -> int:
    """How much of text is safe to show now: its end trimmed back to before any tail that is itself a
    prefix of a stop string, since the next token could still complete one. A stop string spans
    several tokens more often than not (each one usually a single character or sub-word), so text
    cannot simply be shown as it arrives -- it has to be held back exactly as far as it might still
    turn into part of a match (real streaming APIs face the same problem: a stop sequence is checked
    against the accumulated text, not token by token)."""
    limit = len(text)
    for s in stops or ():
        if not s:
            continue
        for k in range(min(len(s), len(text)) - 1, 0, -1):
            if text.endswith(s[:k]):
                limit = min(limit, len(text) - k)
                break
    return limit


def run_turn(engine: Engine, tok, prompt_ids: list[int], *, max_tokens: int, temperature: float,
            top_k: int | None, seed: int, record: list, deadline: float, stop: list[str] | None):
    """Drive one assistant turn through the engine, yielding ("text", str) for each new slice of
    visible content, ("tool_call", name, arguments) at most once, then exactly one ("done",
    finish_reason) -- always the last event. `record` is the list parse_client_tools' stub `fn`s
    append onto: the moment it grows, the call that grew it is the answer and generation stops there,
    before the harness's forced output for that call is ever produced (the module docstring). Only
    the model's plain-language text reaches "text": dawnr's own registry tool calls (and their
    output) run in band as always but never leave this function, matching reply_parts' own part
    types."""
    prompt_len = len(prompt_ids)
    seen_calls = len(record)
    stops = stop or ()
    emitted, flushed = "", 0
    row = None

    def flush_all():
        nonlocal flushed
        if flushed < len(emitted):
            yield ("text", emitted[flushed:])
            flushed = len(emitted)

    for _column, _masks in engine.generate(prompt_ids, 1, max_tokens=max_tokens, temperature=temperature,
                                           top_k=top_k, seed=seed):
        row = engine.rows[0]
        if len(record) > seen_calls:
            yield from flush_all()
            name, args = record[-1]
            yield ("tool_call", name, args)
            yield ("done", "tool_calls")
            return
        parts = reply_parts(tok, row.current_tokens[prompt_len:])
        text = "".join(p["text"] for p in parts if p["type"] == "text")
        if text != emitted:
            emitted = text
            cut = _stop_cut(emitted, stops)
            if cut is not None:
                if cut > flushed:
                    yield ("text", emitted[flushed:cut])
                yield ("done", "stop")
                return
            safe = _safe_flush_len(emitted, stops)
            if safe > flushed:
                yield ("text", emitted[flushed:safe])
                flushed = safe
        if row.completed:
            yield from flush_all()
            yield ("done", "length" if row.ended_in_call else "stop")
            return
        if time.monotonic() >= deadline:
            yield from flush_all()
            yield ("done", "length")
            return
    yield from flush_all()
    yield ("done", "length")           # the token budget ran out without the row ever completing


def run_sync(engine: Engine, tok, prompt_ids: list[int], **kw) -> tuple[str, tuple | None, str, int]:
    """(content, (name, arguments) or None, finish_reason, completion_tokens) for one whole turn."""
    text_parts: list[str] = []
    tool_call, finish_reason = None, "stop"
    for event in run_turn(engine, tok, prompt_ids, **kw):
        if event[0] == "text":
            text_parts.append(event[1])
        elif event[0] == "tool_call":
            tool_call = (event[1], event[2])
        else:
            finish_reason = event[1]
    completion_tokens = len(engine.rows[0].current_tokens) - len(prompt_ids)
    return "".join(text_parts), tool_call, finish_reason, completion_tokens


def stream_chat_completion(model_id: str, cid: str, created: int, engine: Engine, tok, prompt_ids: list[int],
                           *, include_usage: bool, **kw) -> Iterator[dict]:
    """chat.completion.chunk dicts for one turn, ending with a usage-only chunk when asked (matching
    the shape stream_options: {"include_usage": true} adds to real streamed replies) -- the caller
    appends the final "data: [DONE]" line, which is not itself a chunk."""
    base = {"id": cid, "object": "chat.completion.chunk", "created": created, "model": model_id}
    role_sent, tool_call = False, None
    for event in run_turn(engine, tok, prompt_ids, **kw):
        if event[0] == "text":
            delta = {"content": event[1]}
            if not role_sent:
                delta, role_sent = {"role": "assistant", **delta}, True
            yield {**base, "choices": [{"index": 0, "delta": delta, "finish_reason": None}]}
        elif event[0] == "tool_call":
            tool_call = (event[1], event[2])
        else:
            delta: dict = {} if role_sent else {"role": "assistant"}
            role_sent = True
            if tool_call is not None:
                name, args = tool_call
                delta["tool_calls"] = [{"index": 0, "id": "call_" + uuid.uuid4().hex,
                                        "type": "function",
                                        "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}]
            yield {**base, "choices": [{"index": 0, "delta": delta, "finish_reason": event[1]}]}
    if include_usage:
        completion_tokens = len(engine.rows[0].current_tokens) - len(prompt_ids)
        yield {**base, "choices": [], "usage": {"prompt_tokens": len(prompt_ids),
                                                "completion_tokens": completion_tokens,
                                                "total_tokens": len(prompt_ids) + completion_tokens}}


def chat_completion_response(model_id: str, content: str, tool_call, finish_reason: str, prompt_tokens: int,
                             completion_tokens: int) -> dict:
    message = {"role": "assistant", "content": content or None}
    if tool_call is not None:
        name, args = tool_call
        message["tool_calls"] = [{"id": "call_" + uuid.uuid4().hex, "type": "function",
                                  "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}]
    return {"id": "chatcmpl-" + uuid.uuid4().hex, "object": "chat.completion", "created": int(time.time()),
           "model": model_id, "choices": [{"index": 0, "message": message, "finish_reason": finish_reason,
                                           "logprobs": None}],
           "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
                     "total_tokens": prompt_tokens + completion_tokens}}


# --------------------------------------------------------------------------------------- validation --

def _require_number(value, name: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ApiError(400, f"{name} must be a number", param=name)
    if minimum is not None and value < minimum:
        raise ApiError(400, f"{name} must be at least {minimum}", param=name)
    return float(value)


def _require_int(value, name: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or \
            (isinstance(value, float) and not value.is_integer()):
        raise ApiError(400, f"{name} must be an integer", param=name)
    value = int(value)
    if minimum is not None and value < minimum:
        raise ApiError(400, f"{name} must be at least {minimum}", param=name)
    return value


# ------------------------------------------------------------------------------------------ the API --

class DawnrAPI:
    """The chat-completions logic, independent of HTTP: one Engine (its model, tokenizer and harness),
    served one request at a time behind `self.lock`. `create` and `create_stream` are the two calls
    the HTTP handler makes; both raise ApiError for anything the request itself got wrong."""

    def __init__(self, engine: Engine, tok, model_id: str, *, max_tokens_cap: int = MAX_TOKENS_CAP,
                default_max_tokens: int = DEFAULT_MAX_TOKENS, default_temperature: float = DEFAULT_TEMPERATURE,
                default_top_k: int | None = DEFAULT_TOP_K, timeout: float = DEFAULT_TIMEOUT,
                lock_timeout: float = DEFAULT_LOCK_TIMEOUT, api_key: str | None = None,
                max_request_bytes: int = MAX_REQUEST_BYTES):
        if not chat.has_chat_tokens(tok):
            raise ValueError("this checkpoint was not trained in the chat format; run chat_train.py first")
        self.engine, self.tok, self.model_id = engine, tok, model_id
        self.max_tokens_cap, self.default_max_tokens = max_tokens_cap, default_max_tokens
        self.default_temperature, self.default_top_k = default_temperature, default_top_k
        self.timeout, self.lock_timeout = timeout, lock_timeout
        self.api_key, self.max_request_bytes = api_key, max_request_bytes
        self.created = int(time.time())
        self.lock = threading.Lock()

    def _model_row(self) -> dict:
        return {"id": self.model_id, "object": "model", "created": self.created, "owned_by": "dawnr"}

    def list_models(self) -> dict:
        return {"object": "list", "data": [self._model_row()]}

    def get_model(self, model_id: str) -> dict:
        if model_id != self.model_id:
            raise ApiError(404, f"model {model_id!r} does not exist; this server serves {self.model_id!r}",
                           code="model_not_found", param="model")
        return self._model_row()

    def _prepare(self, req: dict) -> tuple[list[int], dict, dict[str, Tool]]:
        if not isinstance(req, dict):
            raise ApiError(400, "the request body must be a JSON object")
        model = req.get("model")
        if model is not None and model != self.model_id:
            raise ApiError(404, f"model {model!r} does not exist; this server serves {self.model_id!r}",
                           code="model_not_found", param="model")
        if req.get("n", 1) not in (1, None):
            raise ApiError(400, "n > 1 is not supported; dawnr answers one choice per request", param="n")
        conversation, continuing = to_conversation(req.get("messages"))
        record: list = []
        reserved = set(self.engine.harness.registry.names())
        client_tools = parse_client_tools(req.get("tools"), req.get("tool_choice"), reserved, record)
        if client_tools and not self.engine.harness_tokens:
            raise ApiError(400, "this checkpoint has no harness tokens (chat.with_harness_tokens); it cannot "
                           "be offered tools -- retrain, or send the request without \"tools\"", param="tools")
        if continuing and not self.engine.harness_tokens:
            raise ApiError(400, "this checkpoint has no harness tokens; it cannot mark a tool result "
                           "untrusted -- retrain, or do not resend a \"tool\" message as the last message",
                           param="messages")
        temperature = _require_number(req.get("temperature", self.default_temperature), "temperature", minimum=0)
        top_k_val = req.get("top_k", self.default_top_k)
        top_k = None if top_k_val is None else _require_int(top_k_val, "top_k", minimum=1)
        max_tokens = req.get("max_completion_tokens", req.get("max_tokens"))
        max_tokens = self.default_max_tokens if max_tokens is None else _require_int(max_tokens, "max_tokens",
                                                                                      minimum=1)
        max_tokens = min(max_tokens, self.max_tokens_cap)
        seed_val = req.get("seed")
        seed = secrets.randbelow(2 ** 31) if seed_val is None else _require_int(seed_val, "seed")
        stop = req.get("stop")
        if isinstance(stop, str):
            stop = [stop]
        if stop is not None and (not isinstance(stop, list) or not all(isinstance(s, str) for s in stop)):
            raise ApiError(400, "stop must be a string or an array of strings", param="stop")

        for tool in client_tools.values():
            self.engine.harness.registry.add(tool)
        ok = False
        try:
            first_turn = not any(m["role"] == "assistant" for m in conversation["messages"])
            if first_turn and (client_tools or len(self.engine.harness.registry) > 1):
                first = conversation["messages"][0]
                first["content"] = self.engine.harness.index() + "\n\n" + first["content"]
            try:
                render = render_for_continuation if continuing else chat.render_for_completion
                prompt_ids = render(self.tok, conversation)
            except ValueError as e:
                raise ApiError(400, str(e), param="messages") from None
            if len(prompt_ids) >= self.engine.model.config.block_size:
                raise ApiError(400, f"the conversation is {len(prompt_ids)} tokens; the model's context "
                               f"window is {self.engine.model.config.block_size}", code="context_length_exceeded",
                               param="messages")
            ok = True
        finally:
            if not ok:
                for name in client_tools:
                    self.engine.harness.registry.remove(name)
        kw = dict(max_tokens=max_tokens, temperature=temperature, top_k=top_k, seed=seed, record=record, stop=stop)
        return prompt_ids, kw, client_tools

    def create(self, req: dict) -> dict:
        if not self.lock.acquire(timeout=self.lock_timeout):
            raise ApiError(503, "another generation is already running; try again shortly",
                           type_="server_error", code="server_busy")
        try:
            prompt_ids, kw, client_tools = self._prepare(req)
            try:
                deadline = time.monotonic() + self.timeout
                content, tool_call, finish_reason, completion_tokens = run_sync(
                    self.engine, self.tok, prompt_ids, deadline=deadline, **kw)
            finally:
                for name in client_tools:
                    self.engine.harness.registry.remove(name)
        finally:
            self.lock.release()
        return chat_completion_response(self.model_id, content, tool_call, finish_reason, len(prompt_ids),
                                        completion_tokens)

    def create_stream(self, req: dict) -> Iterator[dict]:
        """A generator: draining it fully (or closing it early) always releases the lock and any
        client tools it registered, whether the caller reads every chunk or stops partway."""
        if not self.lock.acquire(timeout=self.lock_timeout):
            raise ApiError(503, "another generation is already running; try again shortly",
                           type_="server_error", code="server_busy")
        try:
            prompt_ids, kw, client_tools = self._prepare(req)
            try:
                cid, created = "chatcmpl-" + uuid.uuid4().hex, int(time.time())
                deadline = time.monotonic() + self.timeout
                include_usage = bool((req.get("stream_options") or {}).get("include_usage"))
                yield from stream_chat_completion(self.model_id, cid, created, self.engine, self.tok, prompt_ids,
                                                  include_usage=include_usage, deadline=deadline, **kw)
            finally:
                for name in client_tools:
                    self.engine.harness.registry.remove(name)
        finally:
            self.lock.release()


# --------------------------------------------------------------------------------------- the server --

class Handler(BaseHTTPRequestHandler):
    server_version = f"{SERVER_NAME}/1"
    protocol_version = "HTTP/1.1"
    timeout = 30                                     # socket read timeout for a slow or idle client

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"{self.address_string()} - {fmt % args}\n")

    def _api(self) -> DawnrAPI:
        return self.server.api                        # type: ignore[attr-defined]

    def _check_auth(self) -> bool:
        key = self._api().api_key
        if key is None:
            return True
        header = self.headers.get("Authorization", "")
        prefix = "Bearer "
        if header.startswith(prefix) and secrets.compare_digest(header[len(prefix):], key):
            return True
        self._send_error(ApiError(401, "incorrect API key", code="invalid_api_key"))
        return False

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.close_connection = True
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _send_error(self, err: ApiError) -> None:
        self._send_json(err.status, err.body())

    def _read_json_body(self) -> dict:
        length = self.headers.get("Content-Length")
        if length is None:
            raise ApiError(400, "Content-Length is required")
        try:
            n = int(length)
        except ValueError:
            raise ApiError(400, "Content-Length is not an integer") from None
        limit = self._api().max_request_bytes
        if n > limit:
            raise ApiError(413, f"the request body is {n} bytes; the limit is {limit}", code="request_too_large")
        raw = self.rfile.read(n)
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as e:
            raise ApiError(400, f"the request body is not valid JSON: {e}") from None

    def do_GET(self) -> None:
        if not self._check_auth():
            return
        api = self._api()
        path = self.path.split("?", 1)[0]
        if path == "/v1/models":
            self._send_json(200, api.list_models())
        elif path.startswith("/v1/models/"):
            try:
                self._send_json(200, api.get_model(path[len("/v1/models/"):]))
            except ApiError as e:
                self._send_error(e)
        else:
            self._send_error(ApiError(404, f"no such route: GET {path}", code="not_found"))

    def do_POST(self) -> None:
        if not self._check_auth():
            return
        path = self.path.split("?", 1)[0]
        if path != "/v1/chat/completions":
            self._send_error(ApiError(404, f"no such route: POST {path}", code="not_found"))
            return
        try:
            req = self._read_json_body()
        except ApiError as e:
            self._send_error(e)
            return
        api = self._api()
        if not bool(req.get("stream")):
            try:
                self._send_json(200, api.create(req))
            except ApiError as e:
                self._send_error(e)
            except Exception:                                        # noqa: BLE001
                self._log_unexpected()
                self._send_error(ApiError(500, "internal error", type_="server_error"))
            return
        try:
            events = api.create_stream(req)
            first = next(events, None)
        except ApiError as e:
            self._send_error(e)
            return
        except Exception:                                            # noqa: BLE001
            self._log_unexpected()
            self._send_error(ApiError(500, "internal error", type_="server_error"))
            return
        self.close_connection = True
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            if first is not None:
                self._write_event(first)
            for chunk in events:
                self._write_event(chunk)
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            events.close()

    def _write_event(self, chunk: dict) -> None:
        self.wfile.write(("data: " + json.dumps(chunk, ensure_ascii=False) + "\n\n").encode("utf-8"))
        self.wfile.flush()

    def _log_unexpected(self) -> None:
        import traceback
        traceback.print_exc(file=sys.stderr)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], api: DawnrAPI):
        super().__init__(address, Handler)
        self.api = api


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--model", type=Path, required=True, help="a checkpoint directory chat_train.py wrote")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--model-id", default=None,
                    help="the id GET /v1/models reports (default: the checkpoint directory's name)")
    ap.add_argument("--harness", type=Path, default=None,
                    help="dawnr's harness configuration, DAWNR-HARNESS.md (default: the t tool only, offline)")
    ap.add_argument("--api-key", default=os.environ.get("DAWNR_API_KEY"),
                    help="require this bearer token on every request (default: $DAWNR_API_KEY, or none)")
    ap.add_argument("--grammar", dest="grammar", action="store_true", default=True,
                    help="engine.py's chat-token grammar: every call closes (default: on here, unlike the "
                         "engine's own default -- a reply an API client is waiting on must not end mid-call)")
    ap.add_argument("--no-grammar", dest="grammar", action="store_false")
    ap.add_argument("--max-calls", type=int, default=8, help="a budget of tool calls per reply (0: unbounded)")
    ap.add_argument("--max-tokens-cap", type=int, default=MAX_TOKENS_CAP)
    ap.add_argument("--default-max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="wall-clock seconds per reply")
    ap.add_argument("--lock-timeout", type=float, default=DEFAULT_LOCK_TIMEOUT,
                    help="seconds to wait for another request's generation to finish")
    ap.add_argument("--max-request-bytes", type=int, default=MAX_REQUEST_BYTES)
    ap.add_argument("--device", default=None)
    a = ap.parse_args(argv)

    from checkpoint import load_checkpoint
    model, tok, _cfg = load_checkpoint(a.model, a.device)
    if not chat.has_chat_tokens(tok):
        raise SystemExit(f"{a.model} was not trained in the chat format (no chat tokens); run chat_train.py on it")
    harness = None
    if a.harness is not None:
        from dawnr_harness import build_harness
        harness = build_harness(a.harness)              # no approver: an HTTP request has nobody to ask
        for problem in harness.problems:
            print(f"[harness] {problem}", file=sys.stderr)
    max_calls = (a.max_calls or None) if a.grammar else None
    engine = Engine(model, tok, harness=harness, grammar=a.grammar, max_calls=max_calls)
    api = DawnrAPI(engine, tok, a.model_id or a.model.name, max_tokens_cap=a.max_tokens_cap,
                  default_max_tokens=a.default_max_tokens, timeout=a.timeout, lock_timeout=a.lock_timeout,
                  api_key=a.api_key, max_request_bytes=a.max_request_bytes)
    server = Server((a.host, a.port), api)
    print(f"dawnr-api: serving {api.model_id!r} on http://{a.host}:{a.port} (harness tokens: "
         f"{'yes' if engine.harness_tokens else 'no'}; auth: {'on' if a.api_key else 'off'})", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        engine.harness.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
