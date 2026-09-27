"""web.py: the internet as two tools, web_fetch and web_search, behind the permission policy and off by default.

Standard-library `urllib` only. What comes back is untrusted text (OWASP
LLM01:2025: segregate and identify external content), and a fetch is
bounded: http and https only, no credentials in the URL, no loopback,
private, link-local, multicast or reserved address unless the operator allows
private hosts (a model must not be able to probe the machine's own network:
OWASP's server-side request forgery guidance), every redirect re-checked and
at most five, a byte cap, a wall-clock deadline, text types only, HTML
reduced to its text, the characters returned capped.

Search has no default backend and no hard-coded key. A backend is anything
with `search(query, n) -> [{"title", "url", "snippet"}]`: `searxng` (a
self-hosted SearXNG instance's keyless JSON API, docs.searxng.org/dev/search_api.html:
GET /search?q=...&format=json), `command` (an operator program given the
query as its last argument, printing a JSON list), or one added with
register_backend().

DNS pinning. check_url resolves the host once and validates that address;
fetch() then connects to that exact address (_PinnedHTTPConnection,
_PinnedHTTPSConnection), never letting the HTTP client resolve the host a
second time. Without this, a short-TTL DNS server can answer a public
address for check_url's lookup and a private one for urllib's own lookup a
moment later at connect time -- DNS rebinding (en.wikipedia.org/wiki/
DNS_rebinding, "Web Based" protections: "the IP address is locked to the
value received in the first DNS response"). Each redirect hop is resolved,
validated and pinned again by the same rule (_Redirects.redirect_request),
since a redirect can name a different host. The Host header and, for https,
TLS's SNI and certificate hostname verification still use the original
hostname (self.host) throughout; only the socket's destination is pinned.
"""
from __future__ import annotations

import http.client
import ipaddress
import json
import re
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser

from .tools import CallContext, Tool, ToolResult

TEXT_TYPES = ("application/json", "application/xml", "application/xhtml+xml", "application/rss+xml",
              "application/atom+xml", "application/ld+json", "application/javascript")
USER_AGENT = "dawnr-harness/0.1"


class FetchRefused(Exception):
    """A fetch the harness will not make, or could not finish; the message is what the model is told."""


@dataclass
class WebConfig:
    timeout: float = 15.0
    max_bytes: int = 2_000_000
    max_chars: int = 20_000
    max_redirects: int = 5
    allow_private_hosts: bool = False


def check_url(url: str, allow_private: bool) -> tuple[str, str]:
    """(url, the address to connect to), after validating `url` and resolving its host exactly once.

    Unless `allow_private`, every address the host resolves to must be public: not private, loopback,
    link-local, multicast, reserved or unspecified (a model must not be able to probe the machine's own
    network). The first resolved address is returned so the caller can pin its connection to it (DNS
    rebinding: see this module's docstring) instead of resolving the host again later, when a low-TTL DNS
    answer could differ from the one just validated.
    """
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise FetchRefused(f"only http and https URLs are fetched, not {parts.scheme or 'a relative URL'!r}")
    if not parts.hostname:
        raise FetchRefused("the URL has no host")
    if parts.username or parts.password:
        raise FetchRefused("URLs carrying credentials are not fetched")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(parts.hostname, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError) as e:
        raise FetchRefused(f"cannot resolve {parts.hostname}: {e}") from None
    if not infos:
        raise FetchRefused(f"cannot resolve {parts.hostname}: no address")
    if not allow_private:
        for info in infos:
            addr = ipaddress.ip_address(info[4][0].split("%", 1)[0])
            if (addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_multicast
                    or addr.is_reserved or addr.is_unspecified):
                raise FetchRefused(f"{parts.hostname} is a private or local address ({addr}); not fetched")
    return url, infos[0][4][0]


class _Redirects(urllib.request.HTTPRedirectHandler):
    def __init__(self, cfg: WebConfig, allow_private: bool):
        super().__init__()
        self.cfg, self.allow_private, self.count = cfg, allow_private, 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.count += 1
        if self.count > self.cfg.max_redirects:
            raise FetchRefused(f"more than {self.cfg.max_redirects} redirects")
        newurl, address = check_url(newurl, self.allow_private)          # a redirect may name a different host
        new_req = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new_req is not None:
            new_req.pinned_address = address                             # pin this hop too, not just the first
        return new_req


class _PinnedHTTPConnection(http.client.HTTPConnection):
    """http.client.HTTPConnection, but connect() dials `pinned_address` (check_url's own resolution)
    instead of resolving `self.host` again -- the second, independent lookup a DNS-rebinding attack needs
    (this module's docstring). The Host header, built by http.client itself from `self.host`, is
    untouched; only the socket's destination changes."""

    def __init__(self, host, *args, pinned_address: str | None = None, **kwargs):
        super().__init__(host, *args, **kwargs)
        self._pinned_address = pinned_address

    def connect(self):
        if self._pinned_address is None:            # no resolution was done to pin (allow_private, no lookup)
            super().connect()
            return
        self.sock = socket.create_connection((self._pinned_address, self.port), self.timeout, self.source_address)
        if self._tunnel_host:
            self._tunnel()


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """As _PinnedHTTPConnection, then wraps the pinned socket in TLS using `self.host` (never the pinned
    address) for SNI and certificate hostname verification -- exactly what http.client.HTTPSConnection.connect
    does for whatever address it resolves itself, so pinning changes nothing about what the certificate is
    checked against."""

    def __init__(self, host, *args, pinned_address: str | None = None, **kwargs):
        super().__init__(host, *args, **kwargs)
        self._pinned_address = pinned_address

    def connect(self):
        if self._pinned_address is None:
            super().connect()
            return
        sock = socket.create_connection((self._pinned_address, self.port), self.timeout, self.source_address)
        server_hostname = self._tunnel_host or self.host
        if self._tunnel_host:
            self.sock = sock
            self._tunnel()
            sock = self.sock
        self.sock = self._context.wrap_socket(sock, server_hostname=server_hostname)


class _PinnedHTTPHandler(urllib.request.HTTPHandler):
    def http_open(self, req):
        return self.do_open(_PinnedHTTPConnection, req, pinned_address=getattr(req, "pinned_address", None))


class _PinnedHTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, req):
        return self.do_open(_PinnedHTTPSConnection, req, context=self._context,
                            pinned_address=getattr(req, "pinned_address", None))


class _Text(HTMLParser):
    SKIP = {"script", "style", "noscript", "template", "svg", "iframe", "object"}
    BLOCK = {"p", "div", "br", "li", "ul", "ol", "tr", "table", "section", "article", "header", "footer", "h1",
             "h2", "h3", "h4", "h5", "h6", "pre", "blockquote", "title", "dt", "dd", "hr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skipping = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skipping += 1
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skipping = max(0, self.skipping - 1)
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skipping:
            self.out.append(data)


def html_to_text(html: str) -> str:
    p = _Text()
    p.feed(html)
    p.close()
    lines = [" ".join(line.split()) for line in "".join(p.out).splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def fetch(url: str, cfg: WebConfig, *, allow_private: bool | None = None, accept: str | None = None) -> dict:
    """{"url", "status", "content_type", "bytes", "truncated", "text"}; raises FetchRefused."""
    allow_private = cfg.allow_private_hosts if allow_private is None else allow_private
    url, address = check_url(url, allow_private)
    opener = urllib.request.build_opener(_Redirects(cfg, allow_private), _PinnedHTTPHandler(), _PinnedHTTPSHandler())
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept or
                                               "text/html, text/plain;q=0.9, application/json;q=0.8, */*;q=0.1"})
    req.pinned_address = address                # connect to the address just validated, never re-resolve self.host
    deadline = time.monotonic() + cfg.timeout
    try:
        resp = opener.open(req, timeout=cfg.timeout)
    except urllib.error.HTTPError as e:
        if 300 <= e.code < 400:              # urllib refused the redirect itself (to a scheme it will not follow)
            e.close()
            raise FetchRefused(f"a redirect to {e.headers.get('Location', '?')} was not followed") from None
        resp = e
    except urllib.error.URLError as e:
        reason = e.reason if isinstance(e.reason, FetchRefused) else f"could not fetch {url}: {e.reason}"
        raise FetchRefused(str(reason)) from None
    except (TimeoutError, socket.timeout):
        raise FetchRefused(f"no answer from {url} in {cfg.timeout:g}s") from None
    except (OSError, ValueError, http.client.HTTPException) as e:
        raise FetchRefused(f"could not fetch {url}: {e}") from None
    with resp:
        status = getattr(resp, "status", None) or resp.getcode()
        headers = resp.headers
        ctype = headers.get_content_type() if headers else "application/octet-stream"
        if not (ctype.startswith("text/") or ctype in TEXT_TYPES):
            raise FetchRefused(f"{url} is {ctype}, not text; not returned")
        chunks, size, truncated = [], 0, False
        try:
            while True:
                if time.monotonic() > deadline:
                    truncated = True
                    break
                # read1(), not read(): read() loops internally until it has 65536 bytes or hits EOF, so one
                # call can span many underlying socket reads, each with its own fresh cfg.timeout allowance --
                # a server that drips one byte every (cfg.timeout - epsilon) seconds then never reaches this
                # loop's own deadline check at all, and fetch() blocks for as long as the drip continues
                # (docs.python.org/3/library/io.html#io.BufferedIOBase.read1: "at most one call to the
                # underlying raw stream's read"). read1() returns as soon as any data has arrived, so the
                # deadline above is checked once per chunk actually received, not once per 65536 bytes.
                chunk = resp.read1(65536)
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
                if size > cfg.max_bytes:
                    truncated = True
                    break
        except (TimeoutError, socket.timeout, OSError):
            truncated = True
        raw = b"".join(chunks)[:cfg.max_bytes]
        charset = (headers.get_content_charset() if headers else None) or "utf-8"
        try:
            text = raw.decode(charset, errors="replace")
        except LookupError:
            text = raw.decode("utf-8", errors="replace")
        final = resp.geturl() if hasattr(resp, "geturl") else url
    if ctype in ("text/html", "application/xhtml+xml"):
        text = html_to_text(text)
    return {"url": final, "status": status, "content_type": ctype, "bytes": len(raw), "truncated": truncated,
            "text": text}


# ---------------------------------------------------------------- search --

BACKENDS: dict = {}


def register_backend(name: str, factory) -> None:
    """factory(spec: dict, cfg: WebConfig) -> an object with search(query, n)."""
    BACKENDS[name] = factory


class SearxngBackend:
    def __init__(self, spec: dict, cfg: WebConfig):
        if not isinstance(spec.get("url"), str):
            raise ValueError("the searxng backend needs \"url\", the instance's base URL")
        self.url, self.cfg = spec["url"].rstrip("/"), cfg

    def search(self, query: str, n: int) -> list[dict]:
        url = f"{self.url}/search?" + urllib.parse.urlencode({"q": query, "format": "json"})
        # the operator chose this endpoint, so a self-hosted instance on this machine is allowed
        page = fetch(url, self.cfg, allow_private=True, accept="application/json")
        try:
            data = json.loads(page["text"])
        except ValueError:
            raise FetchRefused("the search backend did not answer JSON (is format=json enabled?)") from None
        return [{"title": str(r.get("title", "")), "url": str(r.get("url", "")), "snippet": str(r.get("content", ""))}
                for r in (data.get("results") or [])[:n] if isinstance(r, dict)]


class CommandBackend:
    def __init__(self, spec: dict, cfg: WebConfig):
        argv = spec.get("command")
        if not (isinstance(argv, list) and argv and all(isinstance(a, str) for a in argv)):
            raise ValueError("the command backend needs \"command\": [program, args...]")
        self.argv, self.cfg = argv, cfg

    def search(self, query: str, n: int) -> list[dict]:
        try:
            p = subprocess.run([*self.argv, query], capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=self.cfg.timeout)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise FetchRefused(f"the search command failed: {e}") from None
        if p.returncode != 0:
            raise FetchRefused(f"the search command exited {p.returncode}: {p.stderr.strip()[:200]}")
        try:
            rows = json.loads(p.stdout)
        except ValueError:
            raise FetchRefused("the search command did not print a JSON list") from None
        return [{"title": str(r.get("title", "")), "url": str(r.get("url", "")), "snippet": str(r.get("snippet", ""))}
                for r in (rows if isinstance(rows, list) else [])[:n] if isinstance(r, dict)]


register_backend("searxng", SearxngBackend)
register_backend("command", CommandBackend)


def make_backend(spec: dict | None, cfg: WebConfig):
    if not spec:
        return None
    name = spec.get("backend")
    if name not in BACKENDS:
        raise ValueError(f"no search backend {name!r} (have {', '.join(sorted(BACKENDS))})")
    return BACKENDS[name](spec, cfg)


# ----------------------------------------------------------------- tools --

def web_tools(cfg: WebConfig | None = None, search_spec: dict | None = None, backend=None) -> list[Tool]:
    cfg = cfg or WebConfig()
    backend = backend if backend is not None else make_backend(search_spec, cfg)

    def run_fetch(args: dict, ctx: CallContext) -> ToolResult:
        try:
            page = fetch(args["url"], cfg)
        except FetchRefused as e:
            return ToolResult(str(e), is_error=True)
        limit = min(args.get("max_chars", cfg.max_chars), cfg.max_chars)
        text = page["text"]
        cut = len(text) > limit
        head = (f"fetched {page['url']} ({page['status']}, {page['content_type']}, {page['bytes']} bytes"
                + (", truncated" if page["truncated"] or cut else "") + ")")
        body = text[:limit] + (f"\n[truncated at {limit} characters]" if cut else "")
        return ToolResult(f"{head}\n{body}", is_error=not (200 <= int(page["status"] or 0) < 400),
                          trust="untrusted", data={"url": page["url"], "status": page["status"]})

    def run_search(args: dict, ctx: CallContext) -> ToolResult:
        if backend is None:
            return ToolResult("no search backend is configured (the operator names one under web.search in the "
                              "harness configuration)", is_error=True)
        try:
            rows = backend.search(args["query"], args.get("n", 5))
        except FetchRefused as e:
            return ToolResult(str(e), is_error=True)
        if not rows:
            return ToolResult(f"no results for {args['query']!r}", trust="untrusted")
        lines = []
        for i, r in enumerate(rows, 1):
            lines.append(f"{i}. {' '.join(r['title'].split())} - {r['url']}")
            if r["snippet"].strip():
                lines.append("   " + " ".join(r["snippet"].split())[:400])
        return ToolResult("\n".join(lines), trust="untrusted")

    fetch_schema = {"type": "object",
                    "properties": {"url": {"type": "string", "maxLength": 2048},
                                   "max_chars": {"type": "integer", "minimum": 1, "maximum": cfg.max_chars}},
                    "required": ["url"], "additionalProperties": False}
    search_schema = {"type": "object",
                     "properties": {"query": {"type": "string", "minLength": 1, "maxLength": 500},
                                    "n": {"type": "integer", "minimum": 1, "maximum": 10}},
                     "required": ["query"], "additionalProperties": False}
    return [Tool("web_fetch", "Fetch a web page (http or https) and return its text.", fetch_schema, run_fetch,
                 permission="ask", trust="untrusted", network=True, consequential=True),
            Tool("web_search", "Search the web; answers titles, URLs and snippets.", search_schema, run_search,
                 permission="ask", trust="untrusted", network=True, consequential=True)]
