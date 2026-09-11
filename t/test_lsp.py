#!/usr/bin/env python3
"""test_lsp.py: ROADMAP 15.2's DONE WHEN, "a committed transcript of
request and response pairs replays as a test".

t/lsp-transcript.jsonl is an ordered list of {"dir": "c2s"|"s2c", "msg":
<JSON-RPC message>} records, one recorded session over t/tasks/abs.t and
t/malformed/wf-unbound.t (see t/LSP.md for how it was made and what each
step covers). This test starts t/lsp.py as a real subprocess, replays
every recorded client ("c2s") message in order exactly as recorded, and
after each one reads as many server ("s2c") messages as the transcript
recorded immediately after it, asserting each actual reply equals the
recorded one field for field -- except a "t/verdicts" notification's
`cached` flag per kernel, which depends on whether an earlier run (in
this process or a previous one) already primed t/cache.py and so is
masked out; every other field, including the verdict words (real/twin/
status/provisional) and the kernel name, is compared exactly.

A second check, independent of the transcript: for both documents it
opens, every diagnostic the server published has a range.start that
equals the (line, col) `surface.check_file` reports for that same file,
converted to LSP's 0-based positions -- the DONE WHEN's other half,
"every diagnostic lands on the token 14.2 names".

Run: python3 t/test_lsp.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TRANSCRIPT = HERE / "lsp-transcript.jsonl"


def _env_with_kernel_path():
    env = dict(os.environ)
    extra = [str(Path.home() / ".cargo" / "bin"),
            str(Path.home() / ".opam" / "default" / "bin"),
            str(Path.home() / ".elan" / "bin")]
    env["PATH"] = ":".join(extra) + ":" + env.get("PATH", "")
    return env


def _read_message(stream):
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
    body = stream.read(length)
    return json.loads(body.decode("utf-8"))


def _write_message(stream, msg):
    body = json.dumps(msg).encode("utf-8")
    header = ("Content-Length: %d\r\n\r\n" % len(body)).encode("utf-8")
    stream.write(header)
    stream.write(body)
    stream.flush()


def _mask(msg):
    """A copy of `msg` with the one field a rerun cannot promise to
    reproduce (a verdict's cache hit/miss) removed, so comparison is
    exact on everything else -- the verdict words, the kernel name, the
    outcome strings, the source hash, the kernel version."""
    if not isinstance(msg, dict):
        return msg
    if msg.get("method") != "t/verdicts":
        return msg
    out = json.loads(json.dumps(msg))   # deep copy
    for entry in out.get("params", {}).get("kernels", {}).values():
        entry.pop("cached", None)
    return out


def load_transcript():
    entries = []
    with open(TRANSCRIPT) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def group_turns(entries):
    """[(c2s_msg, [s2c_msg, ...]), ...]: each client message paired with
    the server messages the transcript recorded immediately after it and
    before the next client message."""
    turns = []
    i = 0
    n = len(entries)
    while i < n:
        assert entries[i]["dir"] == "c2s", (
            f"transcript entry {i} is not a client message: {entries[i]}")
        c2s = entries[i]["msg"]
        i += 1
        s2c = []
        while i < n and entries[i]["dir"] == "s2c":
            s2c.append(entries[i]["msg"])
            i += 1
        turns.append((c2s, s2c))
    return turns


def test_transcript_replays():
    entries = load_transcript()
    assert entries, "t/lsp-transcript.jsonl is empty"
    turns = group_turns(entries)

    proc = subprocess.Popen(
        [sys.executable, "lsp.py"], cwd=str(HERE),
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, env=_env_with_kernel_path(),
    )
    try:
        checked = 0
        for c2s, expected_s2c in turns:
            _write_message(proc.stdin, c2s)
            if c2s.get("method") == "exit":
                continue
            for expected in expected_s2c:
                actual = _read_message(proc.stdout)
                assert actual is not None, (
                    f"server closed stdout; expected {expected}")
                assert _mask(actual) == _mask(expected), (
                    f"reply mismatch for {c2s.get('method') or c2s.get('id')}:\n"
                    f"  expected: {json.dumps(expected)}\n"
                    f"  actual:   {json.dumps(actual)}")
                checked += 1
        proc.stdin.close()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            raise AssertionError("server did not exit after 'exit'")
    finally:
        if proc.poll() is None:
            proc.kill()
        err = proc.stderr.read().decode("utf-8", errors="replace")
        if proc.returncode not in (0, None) and err.strip():
            print(err, file=sys.stderr)
    print(f"test_transcript_replays: {len(turns)} client messages, "
         f"{checked} server replies, each matching the recorded transcript")


def test_diagnostics_match_check_file():
    """Independent of the transcript: for every publishDiagnostics message
    it recorded, each diagnostic's range.start equals the (line, col)
    surface.check_file reports for that file, 0-based."""
    sys.path.insert(0, str(HERE))
    import surface

    entries = load_transcript()
    n = 0
    for e in entries:
        msg = e["msg"]
        if e["dir"] != "s2c" or msg.get("method") != "textDocument/publishDiagnostics":
            continue
        params = msg["params"]
        uri = params["uri"]
        path = uri[len("file://"):] if uri.startswith("file://") else uri
        errs = surface.check_file(path)
        want = set()
        for err in errs:
            line = getattr(err, "line", None)
            col = getattr(err, "col", None)
            if line is None:
                continue
            want.add((line - 1, col - 1))
        got = {(d["range"]["start"]["line"], d["range"]["start"]["character"])
              for d in params["diagnostics"]}
        assert got == want, (
            f"{path}: diagnostic starts {sorted(got)} != "
            f"check_file starts {sorted(want)}")
        n += len(params["diagnostics"])
    assert n > 0, "no diagnostics found in the transcript to check"
    print(f"test_diagnostics_match_check_file: {n} diagnostic(s) across "
         f"the transcript, every range.start == check_file's (line, col)")


def test_hover_on_local_declaration():
    """Added 2026-09-11 after the independent check of 15.2: hovering a
    local's own name at its `var` statement answers with its type, and the
    declaration position is the identifier, not the keyword (surface.py
    marks the statement at the name since the same day)."""
    import lsp, surface
    path = HERE / "tasks" / "digit_sum.t"
    text = path.read_text(encoding="utf-8")
    positions = {}
    task = surface.parse(text, positions=positions)
    line_no = next(i for i, l in enumerate(text.splitlines(), 1) if l.strip().startswith("var "))
    line = text.splitlines()[line_no - 1]
    col = line.index("var ") + len("var ") + 1          # 1-based column of the name
    h = lsp._hover_at(task, positions, line_no - 1, col - 1)
    assert h is not None, (line_no, col)
    assert h["kind"] == "local" and h["type"] is not None, h
    assert h["decl"] == {"line": line_no, "col": col}, h
    print("test_hover_on_local_declaration: hover at %d:%d -> %s %s declared at %s" % (line_no, col, h["name"], h["type"], h["decl"]))


def main():
    test_transcript_replays()
    test_diagnostics_match_check_file()
    test_hover_on_local_declaration()
    print("OK")


if __name__ == "__main__":
    main()
