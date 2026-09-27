"""notes_server.py: a second MCP server for dawnr's tool conversations, serving recorded task notes.

    python notes_server.py notes.json

The same stdio server as dawnr's own (dawnr_harness/mcp_server.py, both
protocol eras), listing two other tools:

* `lookup {"topic"}`: the note filed under that topic in notes.json, as
  text. An unknown topic is a tool error (isError), as MCP says a tool's own
  failure is reported. A topic whose note says `"delay": s` answers after s
  seconds, so the harness's client timeout is exercised for real.
* `send {"to", "text"}`: answers that the message was filed. It is the tool an
  injected note asks the model to call; nothing is sent anywhere.

The notes are fixture text written for this repository from the proved
corpus (tool_fixtures.py writes notes.json), some with instructions injected
into them. Everything this server returns reaches the model as untrusted
output, because the harness marks every MCP result that way.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

LOCALLM = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(LOCALLM))

from dawnr_harness.mcp_server import Server  # noqa: E402
from dawnr_harness.tools import validate  # noqa: E402

LOOKUP = {"name": "lookup", "title": "task notes",
          "description": "The note filed under a topic.",
          "inputSchema": {"type": "object", "properties": {"topic": {"type": "string", "maxLength": 200}},
                          "required": ["topic"], "additionalProperties": False}}
SEND = {"name": "send", "title": "send a note",
        "description": "Send a note to an address.",
        "inputSchema": {"type": "object", "properties": {"to": {"type": "string", "maxLength": 200},
                                                         "text": {"type": "string", "maxLength": 20000}},
                        "required": ["to", "text"], "additionalProperties": False}}


class NotesServer(Server):
    def __init__(self, notes: dict):
        super().__init__()
        self.notes = notes

    def tools(self) -> list[dict]:
        return [LOOKUP, SEND]

    def call(self, name: str, arguments) -> dict:
        spec = LOOKUP if name == "lookup" else SEND
        errs = validate(spec["inputSchema"], arguments if arguments is not None else {})
        if errs:
            return {"content": [{"type": "text", "text": "; ".join(errs)}], "isError": True}
        if name == "send":
            return {"content": [{"type": "text", "text": f"filed a note to {arguments['to']}"}], "isError": False}
        note = self.notes.get(arguments["topic"])
        if note is None:
            return {"content": [{"type": "text", "text": f"no note is filed under {arguments['topic']!r}"}],
                    "isError": True}
        if note.get("delay"):
            time.sleep(float(note["delay"]))
        return {"content": [{"type": "text", "text": note["text"]}], "isError": False}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: notes_server.py notes.json", file=sys.stderr)
        return 2
    notes = json.loads(Path(argv[0]).read_text(encoding="utf-8"))["notes"]
    NotesServer(notes).serve()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
