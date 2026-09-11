#!/usr/bin/env python3
"""t/lsp.py: a language server for t (ROADMAP 15.2, "The language server").

`python3 t/lsp.py` speaks the Language Server Protocol over stdin/stdout:
JSON-RPC 2.0 messages framed with a `Content-Length` header, exactly as
every LSP client (an editor's LSP client library, not the editor itself)
already expects. One server, spoken to by any number of editors that can
launch a subprocess and talk stdio LSP -- nothing here is editor-specific.

Requests handled:
  initialize / initialized / shutdown / exit  -- the LSP lifecycle.
  textDocument/didOpen, didChange (full sync only), didSave
      -- parse the text with positions (surface.parse(text, positions=...)),
      run check_wf.check_wf with them, and publish one
      textDocument/publishDiagnostics notification per document, one
      Diagnostic per WfError or SurfaceError, at the position of the
      offending TOKEN (14.2's own terms): start at the (line, col)
      check_wf/surface.py records (1-based, per t's own convention),
      converted to LSP's 0-based range, running to that token's end
      (start + the token's own text length -- see `_token_span`); `code`
      is the rule key (or the SurfaceError production when parsing itself
      failed), `source` is the literal string "t".
  textDocument/hover
      -- the type and declaration site of the name under the cursor
      (a param, a return, a local, or a spec_fun), from the parsed task
      and its positions map (see `_collect_hovers`).
  textDocument/definition
      -- for a spec_fun call, the location of that spec_fun's own
      declaration (its `spec fun <name>` line). Anything else: null.
  textDocument/formatting
      -- the document's text re-printed through surface.print_task, as one
      TextEdit replacing the whole document. A document that does not
      parse, or does not round-trip through print_task, returns no edits
      (formatting a broken file is a no-op, not a crash).
  t/verify (a custom request), and automatically after every didSave
      -- runs tlib.verify(task, kernels=...) in a worker thread (so the
      server keeps answering RPCs while a kernel runs) and sends the
      result back as a custom notification, "t/verdicts": see VERDICTS
      NOTIFICATION below. `kernels` defaults to ["dafny"] (fast enough for
      a committed transcript test); a client names its own set in
      `initializationOptions.kernels` at initialize time, or per-call in
      the t/verify request's params.

VERDICTS NOTIFICATION. "t/verdicts", params:
    {"uri": <document uri>,
     "kernels": {<kernel>: {"status": "ok" | "absent" | "no_twin",
                             "provisional": bool,
                             "real": <Outcome string> | null,
                             "twin": <Outcome string> | null,
                             "twin_op": <string> | null,
                             "witness": <string>,
                             "source_sha": <string> | null,
                             "kernel_version": <string> | null,
                             "cached": bool}, ...}}
`status` is "absent" exactly when the kernel binary itself is missing
(tlib.kernel_version raised) -- an absent kernel is reported as absent,
never as a verdict of any kind; "no_twin" when the kernel is present but
no rung of the twin ladder produced a witness for this task (`real`/`twin`
are null in both those cases); "ok" otherwise, with `real`/`twin` the
Outcome strings tlib.verify produced. `provisional` (only meaningful when
`status` is "ok") is tlib's own flag: a flake_check that ran but did not
reach n-of-n agreement -- shown as provisional, not asserted as final.

Every kernel invocation needs
`$HOME/.cargo/bin:$HOME/.opam/default/bin:$HOME/.elan/bin` on PATH (the
same rule every other t script follows); this module does not modify
PATH itself, since it may run under a client that already set it up, or
under a test harness (test_lsp.py) that sets it before launching the
subprocess.

Errors: a JSON-RPC request this server cannot service (an unknown method,
a document that is not open) gets a JSON-RPC error response, never a
crash; a notification (no id, so no response is possible) that fails is
swallowed after being written to stderr, since LSP defines no reply for
one.
"""
from __future__ import annotations

import json
import sys
import threading
import traceback
from pathlib import Path

import check_wf
import surface
import tlib

HERE = Path(__file__).resolve().parent


# ===========================================================================
# JSON-RPC framing over stdio.
# ===========================================================================

def read_message(stream) -> dict | None:
    """One JSON-RPC message from `stream` (a buffered binary stream), or
    None at end of input. Reads the Content-Length header block (a blank
    line ends it), then exactly that many bytes of body."""
    length = None
    while True:
        line = stream.readline()
        if line == b"":
            return None
        line = line.rstrip(b"\r\n")
        if line == b"":
            break
        if line.lower().startswith(b"content-length:"):
            length = int(line.split(b":", 1)[1].strip())
    if length is None:
        raise ValueError("message header carried no Content-Length")
    body = stream.read(length)
    return json.loads(body.decode("utf-8"))


def write_message(stream, msg: dict, lock: threading.Lock) -> None:
    """Write one JSON-RPC message, Content-Length framed. `lock` serialises
    writes across threads (the verify worker writes a notification from a
    background thread while the main loop may be writing a response)."""
    body = json.dumps(msg).encode("utf-8")
    header = ("Content-Length: %d\r\n\r\n" % len(body)).encode("utf-8")
    with lock:
        stream.write(header)
        stream.write(body)
        stream.flush()


# ===========================================================================
# Positions: t records (line, col) 1-based, LSP wants 0-based. A "token" in
# 14.2's sense is the offending AST node's own leading text; `_token_span`
# guesses its length from the node's shape so a diagnostic, a hover or a
# definition covers the actual name/literal rather than one bare character.
# ===========================================================================

_OP_TEXT = {"div": "/", "mod": "%"}


def _token_text(node) -> str:
    """A printable guess at the source text the token `node` was marked at
    began with -- long enough for `_token_span` to compute a sane end
    column. Exact for every name (var/call/param/return): those are marked
    at the identifier token itself, so `len(name)` IS the token's length.
    Approximate for compound nodes (an `if`/`while`/`var` statement, an
    `op` node marked at its leading symbol) -- those cover only the
    keyword or operator that starts them, which is what a reader's eye
    lands on for a diagnostic anyway."""
    if not isinstance(node, dict):
        return str(node)
    if "var" in node and isinstance(node["var"], str):
        return node["var"]
    if "call" in node and isinstance(node["call"], dict):
        return node["call"].get("fun", "")
    if "name" in node and isinstance(node.get("name"), str):
        return node["name"]
    if "int" in node:
        return str(node["int"])
    if "bool" in node:
        return "true" if node["bool"] else "false"
    if "op" in node:
        return _OP_TEXT.get(node["op"], node["op"])
    if "assign" in node and isinstance(node["assign"], list):
        return node["assign"][0]
    if "return" in node and isinstance(node["return"], list):
        return "return"
    for kw in ("if", "while", "ite"):
        if kw in node:
            return kw
    if "forall" in node:
        return "forall"
    if "exists" in node:
        return "exists"
    return ""


def _token_span(node, line: int, col: int) -> tuple[int, int, int, int]:
    """(start_line, start_col, end_line, end_col), 0-based LSP positions,
    from a 1-based (line, col) and `node`'s guessed token text. A token
    never spans a line in this grammar (no multi-line identifiers,
    keywords or operators), so end_line == start_line always."""
    text = _token_text(node)
    width = max(len(text), 1)
    return (line - 1, col - 1, line - 1, col - 1 + width)


# ===========================================================================
# Diagnostics.
# ===========================================================================

def _diagnostics_for(text: str, file: str) -> list[dict]:
    """publishDiagnostics-ready diagnostics for `text`: a parse failure is
    one diagnostic at the SurfaceError's own position (code = its
    production); a parse success runs check_wf and yields one diagnostic
    per WfError, at the token check_wf attributed the error to."""
    positions: dict = {}
    try:
        task = surface.parse(text, positions=positions)
    except surface.SurfaceError as exc:
        line = exc.line if exc.line is not None else 1
        col = exc.col if exc.col is not None else 1
        sl, sc, el, ec = (line - 1, col - 1, line - 1, col)
        return [{
            "range": {"start": {"line": sl, "character": sc},
                     "end": {"line": el, "character": ec}},
            "severity": 1,
            "code": exc.production or "SurfaceError",
            "source": "t",
            "message": exc.message,
        }]

    errs = check_wf.check_wf(task, positions=positions, file=file)
    diags = []
    for err in errs:
        if err.line is None:
            continue
        # Find the actual node object for a precise token guess: id()s
        # from `positions` cannot be reversed to an object after the fact,
        # so match by position instead, which is what the diagnostic's
        # range needs anyway.
        node = _node_at(task, err.line, err.col, positions)
        sl, sc, el, ec = _token_span(node, err.line, err.col)
        diags.append({
            "range": {"start": {"line": sl, "character": sc},
                     "end": {"line": el, "character": ec}},
            "severity": 1,
            "code": err.rule,
            "source": "t",
            "message": err.message,
        })
    return diags


def _walk_dicts(obj):
    """Every dict reachable inside `obj` (task JSON is dicts and lists of
    dicts and scalars only), depth-first, `obj` itself first."""
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk_dicts(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_dicts(v)


def _node_at(task, line, col, positions):
    """The first dict node marked at exactly (line, col), or an empty dict
    (falls back to a one-character token) if none is."""
    for node in _walk_dicts(task):
        pos = positions.get(id(node))
        if pos == (line, col):
            return node
    return {}


# ===========================================================================
# Hover: name -> (kind, type, decl_pos), threaded through the same scoping
# check_wf.py's _ty/_check_stmts use, but recording every reference's span
# and its declaration's position instead of type-checking.
# ===========================================================================

def _collect_hovers(task, positions) -> list[dict]:
    """[{line, col, end_col, name, kind, type, decl}], one entry per name
    occurrence (a use or the declaration itself) whose node is in
    `positions`. `decl` is {"line", "col"} (1-based) or None."""
    hovers: list[dict] = []
    funs = {f["name"]: f for f in task.get("spec_funs", [])}
    fun_pos = {name: positions.get(id(f)) for name, f in funs.items()}

    def emit(node, name, kind, typ, decl_pos):
        pos = positions.get(id(node))
        if pos is None:
            return
        line, col = pos
        hovers.append({
            "line": line, "col": col, "end_col": col + max(len(name), 1),
            "name": name, "kind": kind, "type": typ,
            "decl": {"line": decl_pos[0], "col": decl_pos[1]}
                   if decl_pos else None,
        })

    def walk_expr(e, env):
        if not isinstance(e, dict):
            return
        if "var" in e and isinstance(e["var"], str):
            name = e["var"]
            kind, typ, decl_pos = env.get(name, (None, None, None))
            emit(e, name, kind or "unbound", typ, decl_pos)
            return
        if "call" in e:
            c = e["call"]
            fname = c["fun"]
            f = funs.get(fname)
            emit(e, fname, "spec_fun", f["result"] if f else None,
                fun_pos.get(fname))
            for a in c["args"]:
                walk_expr(a, env)
            return
        if "ite" in e:
            c = e["ite"]
            walk_expr(c["cond"], env)
            walk_expr(c["then"], env)
            walk_expr(c["else"], env)
            return
        if "forall" in e or "exists" in e:
            q = e["forall"] if "forall" in e else e["exists"]
            walk_expr(q["lo"], env)
            walk_expr(q["hi"], env)
            qpos = positions.get(id(e))
            sub = dict(env)
            sub[q["var"]] = ("bound", "int", qpos)
            walk_expr(q["body"], sub)
            return
        if "op" in e:
            for a in e.get("args", []):
                walk_expr(a, env)
            return

    def walk_stmts(body, env):
        for s in body:
            if "assign" in s:
                target, e = s["assign"]
                walk_expr(e, env)
                kind, typ, decl_pos = env.get(target, (None, None, None))
                emit(s, target, kind or "unbound", typ, decl_pos)
            elif "var" in s:
                d = s["var"]
                walk_expr(d["init"], env)
                pos = positions.get(id(s))
                env = dict(env)
                env[d["name"]] = ("local", d["type"], pos)
                emit(s, d["name"], "local", d["type"], pos)
            elif "if" in s:
                c = s["if"]
                walk_expr(c["cond"], env)
                walk_stmts(c["then"], dict(env))
                walk_stmts(c["else"], dict(env))
            elif "while" in s:
                w = s["while"]
                walk_expr(w["cond"], env)
                if "decreases" in w:
                    walk_expr(w["decreases"], env)
                for inv in w.get("invariants", []):
                    walk_expr(inv, env)
                walk_stmts(w["body"], dict(env))
            elif "return" in s:
                _, e = s["return"]
                walk_expr(e, env)

    penv = {p["name"]: ("param", p["type"], positions.get(id(p)))
           for p in task["params"]}
    for p in task["params"]:
        emit(p, p["name"], "param", p["type"], positions.get(id(p)))
    for r in task["returns"]:
        emit(r, r["name"], "return", r["type"], positions.get(id(r)))

    for e in task.get("requires", []):
        walk_expr(e, penv)
    ret = task["returns"][0]
    eenv = dict(penv)
    eenv[ret["name"]] = ("return", ret["type"], positions.get(id(ret)))
    for e in task.get("ensures", []):
        walk_expr(e, eenv)

    for f in task.get("spec_funs", []):
        emit(f, f["name"], "spec_fun", f["result"], positions.get(id(f)))
        fenv = {p["name"]: ("param", p["type"], positions.get(id(p)))
               for p in f["params"]}
        for p in f["params"]:
            emit(p, p["name"], "param", p["type"], positions.get(id(p)))
        walk_expr(f["decreases"], fenv)
        walk_expr(f["body"], fenv)

    walk_stmts(task.get("body", []), dict(eenv))
    return hovers


def _hover_at(task, positions, line0: int, col0: int):
    """(hover_entry_or_None) at a 0-based LSP (line, character): the entry
    whose span covers the 1-based (line0+1, col0+1)."""
    line, col = line0 + 1, col0 + 1
    hovers = _collect_hovers(task, positions)
    for h in hovers:
        if h["line"] == line and h["col"] <= col < h["end_col"]:
            return h
    return None


# ===========================================================================
# The server.
# ===========================================================================

class Server:
    def __init__(self, in_stream, out_stream, kernels=None):
        self.in_stream = in_stream
        self.out_stream = out_stream
        self.write_lock = threading.Lock()
        self.docs: dict[str, str] = {}       # uri -> text
        self.kernels = kernels or ["dafny"]
        self.shutdown_requested = False

    # -- message plumbing ---------------------------------------------

    def send(self, msg: dict) -> None:
        write_message(self.out_stream, msg, self.write_lock)

    def respond(self, id_, result=None, error=None) -> None:
        msg = {"jsonrpc": "2.0", "id": id_}
        if error is not None:
            msg["error"] = error
        else:
            msg["result"] = result
        self.send(msg)

    def notify(self, method: str, params: dict) -> None:
        self.send({"jsonrpc": "2.0", "method": method, "params": params})

    # -- lifecycle -------------------------------------------------------

    def handle_initialize(self, msg):
        params = msg.get("params") or {}
        opts = params.get("initializationOptions") or {}
        if "kernels" in opts:
            self.kernels = opts["kernels"]
        self.respond(msg["id"], {
            "capabilities": {
                "textDocumentSync": 1,          # full document sync
                "hoverProvider": True,
                "definitionProvider": True,
                "documentFormattingProvider": True,
            },
            "serverInfo": {"name": "t-lsp", "version": "0.1"},
        })

    def handle_initialized(self, msg):
        pass    # a notification; nothing to acknowledge

    def handle_shutdown(self, msg):
        self.shutdown_requested = True
        self.respond(msg["id"], None)

    # -- documents ---------------------------------------------------------

    def _uri_path(self, uri: str) -> str:
        if uri.startswith("file://"):
            return uri[len("file://"):]
        return uri

    def _publish(self, uri: str) -> None:
        text = self.docs.get(uri, "")
        diags = _diagnostics_for(text, self._uri_path(uri))
        self.notify("textDocument/publishDiagnostics",
                    {"uri": uri, "diagnostics": diags})

    def handle_did_open(self, msg):
        p = msg["params"]["textDocument"]
        self.docs[p["uri"]] = p["text"]
        self._publish(p["uri"])

    def handle_did_change(self, msg):
        p = msg["params"]
        uri = p["textDocument"]["uri"]
        changes = p["contentChanges"]
        # Full sync only (textDocumentSync: 1): each change replaces the
        # whole text; the last one in the list is authoritative.
        if changes:
            self.docs[uri] = changes[-1]["text"]
        self._publish(uri)

    def handle_did_save(self, msg):
        uri = msg["params"]["textDocument"]["uri"]
        if "text" in msg["params"]:
            self.docs[uri] = msg["params"]["text"]
        self._publish(uri)
        self._verify_async(uri)

    # -- hover / definition / formatting ------------------------------

    def _parsed(self, uri: str):
        """(task, positions) for `uri`'s current text, or (None, None) if
        it does not parse."""
        text = self.docs.get(uri, "")
        positions: dict = {}
        try:
            task = surface.parse(text, positions=positions)
        except surface.SurfaceError:
            return None, None
        return task, positions

    def handle_hover(self, msg):
        p = msg["params"]
        uri = p["textDocument"]["uri"]
        pos = p["position"]
        task, positions = self._parsed(uri)
        if task is None:
            self.respond(msg["id"], None)
            return
        h = _hover_at(task, positions, pos["line"], pos["character"])
        if h is None:
            self.respond(msg["id"], None)
            return
        lines = [f"**{h['name']}**: `{_fmt_type(h['type'])}` ({h['kind']})"]
        if h["decl"] is not None:
            lines.append(f"declared at {uri}:{h['decl']['line']}:{h['decl']['col']}")
        sl, sc, el, ec = (h["line"] - 1, h["col"] - 1,
                         h["line"] - 1, h["end_col"] - 1)
        self.respond(msg["id"], {
            "contents": {"kind": "markdown", "value": "\n\n".join(lines)},
            "range": {"start": {"line": sl, "character": sc},
                     "end": {"line": el, "character": ec}},
        })

    def handle_definition(self, msg):
        p = msg["params"]
        uri = p["textDocument"]["uri"]
        pos = p["position"]
        task, positions = self._parsed(uri)
        if task is None:
            self.respond(msg["id"], None)
            return
        h = _hover_at(task, positions, pos["line"], pos["character"])
        if h is None or h["kind"] != "spec_fun" or h["decl"] is None:
            self.respond(msg["id"], None)
            return
        dl, dc = h["decl"]["line"], h["decl"]["col"]
        self.respond(msg["id"], {
            "uri": uri,
            "range": {"start": {"line": dl - 1, "character": dc - 1},
                     "end": {"line": dl - 1, "character": dc - 1}},
        })

    def handle_formatting(self, msg):
        p = msg["params"]
        uri = p["textDocument"]["uri"]
        text = self.docs.get(uri, "")
        try:
            task = surface.parse(text)
            formatted = surface.print_task(task)
        except surface.SurfaceError:
            self.respond(msg["id"], [])
            return
        lines = text.split("\n")
        last_line = max(len(lines) - 1, 0)
        last_col = len(lines[-1])
        self.respond(msg["id"], [{
            "range": {"start": {"line": 0, "character": 0},
                     "end": {"line": last_line, "character": last_col}},
            "newText": formatted,
        }])

    # -- verdicts (15.1 over the wire) ------------------------------------

    def _verify_async(self, uri: str) -> None:
        text = self.docs.get(uri, "")
        try:
            task = surface.parse(text)
        except surface.SurfaceError:
            return   # nothing to verify; diagnostics already say why

        def worker():
            payload = {}
            for kernel in self.kernels:
                try:
                    entry = tlib.verify(task, kernels=[kernel]).get(kernel, {})
                except Exception as exc:                # pragma: no cover
                    payload[kernel] = {"status": "tool_error",
                                       "provisional": False,
                                       "real": None, "twin": None,
                                       "twin_op": None, "witness": "none",
                                       "source_sha": None,
                                       "kernel_version": None,
                                       "cached": False,
                                       "error": str(exc)}
                    continue
                refused = entry.get("refused")
                if refused and refused.startswith("kernel absent"):
                    status = "absent"
                elif refused:
                    status = "no_twin"
                else:
                    status = "ok"
                payload[kernel] = {
                    "status": status,
                    "provisional": entry.get("provisional", False),
                    "real": entry.get("real"),
                    "twin": entry.get("twin"),
                    "twin_op": entry.get("twin_op"),
                    "witness": entry.get("witness", "none"),
                    "source_sha": entry.get("source_sha"),
                    "kernel_version": entry.get("kernel_version"),
                    "cached": entry.get("cached", False),
                }
            self.notify("t/verdicts", {"uri": uri, "kernels": payload})

        threading.Thread(target=worker, daemon=True).start()

    def handle_verify(self, msg):
        uri = msg["params"]["uri"]
        kernels = msg["params"].get("kernels", self.kernels)
        old = self.kernels
        self.kernels = kernels
        try:
            self._verify_async(uri)
        finally:
            self.kernels = old
        self.respond(msg["id"], {"started": True})

    # -- dispatch ----------------------------------------------------------

    HANDLERS_REQ = {
        "initialize": "handle_initialize",
        "shutdown": "handle_shutdown",
        "textDocument/hover": "handle_hover",
        "textDocument/definition": "handle_definition",
        "textDocument/formatting": "handle_formatting",
        "t/verify": "handle_verify",
    }
    HANDLERS_NOTIF = {
        "initialized": "handle_initialized",
        "textDocument/didOpen": "handle_did_open",
        "textDocument/didChange": "handle_did_change",
        "textDocument/didSave": "handle_did_save",
    }

    def dispatch(self, msg: dict) -> bool:
        """Handle one message. Returns False when the server should exit
        (the "exit" notification), True otherwise."""
        method = msg.get("method")
        has_id = "id" in msg
        if method == "exit":
            return False
        try:
            if has_id:
                handler_name = self.HANDLERS_REQ.get(method)
                if handler_name is None:
                    self.respond(msg["id"], error={
                        "code": -32601, "message": f"method not found: {method}"})
                    return True
                getattr(self, handler_name)(msg)
            else:
                handler_name = self.HANDLERS_NOTIF.get(method)
                if handler_name is not None:
                    getattr(self, handler_name)(msg)
                # An unknown notification is silently ignored, per spec.
        except Exception:
            traceback.print_exc(file=sys.stderr)
            if has_id:
                self.respond(msg["id"], error={
                    "code": -32603, "message": "internal error, see stderr"})
        return True

    def serve_forever(self) -> None:
        while True:
            try:
                msg = read_message(self.in_stream)
            except Exception:
                traceback.print_exc(file=sys.stderr)
                break
            if msg is None:
                break
            if not self.dispatch(msg):
                break


def _fmt_type(t) -> str:
    if t is None:
        return "?"
    if isinstance(t, str):
        return t
    if isinstance(t, dict) and "pair" in t:
        return f"({t['pair'][0]}, {t['pair'][1]})"
    if isinstance(t, dict) and t == {"seq": "seq"}:
        return "seq<seq>"
    return str(t)


def main() -> int:
    server = Server(sys.stdin.buffer, sys.stdout.buffer)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
