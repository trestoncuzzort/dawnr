"""guard.py: an operator's PreToolUse hook that lets web_fetch reach only the hosts it names.

    {"hooks": {"PreToolUse": [{"matcher": "web_fetch", "hooks": [
        {"type": "command", "command": "${PYTHON}", "args": ["guard.py", "tasks.example.org"]}]}]}}

Claude Code's hook contract (code.claude.com/docs/en/hooks), as
dawnr_harness/hooks.py runs it: the event arrives as JSON on stdin, and a
PreToolUse hook that prints hookSpecificOutput.permissionDecision "deny" with
a reason stops the call before it runs. Used by dawnr's tool conversations for
the "a hook blocked it" answers, which are the harness's real output.
"""
from __future__ import annotations

import json
import sys
import urllib.parse


def main(argv=None) -> int:
    allowed = set(sys.argv[1:] if argv is None else argv)
    event = json.load(sys.stdin)
    url = str((event.get("tool_input") or {}).get("url", ""))
    host = urllib.parse.urlsplit(url).hostname or ""
    if host in allowed:
        print(json.dumps({}))
        return 0
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "deny",
        "permissionDecisionReason": f"{host or 'that host'} is not on the operator's list of hosts"}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
