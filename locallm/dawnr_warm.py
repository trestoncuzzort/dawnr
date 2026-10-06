"""dawnr_warm.py: the assistant's system-and-tools prefix, processed by the model server once and alone.

    python3 locallm/dawnr_warm.py --host 127.0.0.1:8712 [--cwd DIR] [--read-only] [--root DIR ...] [--online] [TASK ...]

Why: the model keeps a recurrent state, so the server can take a conversation up again only from a checkpoint, and it
makes one at the end of each prompt it processes. After a task's first call the checkpoints sit at the prefix plus
that task's text and beyond; the next task shares only the prefix, finds no checkpoint at or before it, and the
server processes the prefix again: 2,220 tokens, 19 s on six CPU cores (measured on 2026-10-06; the server's flags
for checkpoints set how many are kept and how far apart, not where they fall). Processed alone, the prefix leaves a
checkpoint at exactly its end, and the next conversation's first call costs only its own text (25 to 72 tokens,
under a second). The launcher runs this before each conversation; while the checkpoint is still there it costs one
request and no tokens. The options are the assistant's own, so the prefix warmed is the one it sends.

It never fails the assistant: whatever goes wrong is printed and the exit code is 0. The server-side accounts of the
same mechanism are llama.cpp issue 22384 and pull request 24035; the maintainers keep a new conversation's prefix
out of the server's scope, so the client warms it.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent_eval_native import _post  # noqa: E402


def prefix_of(a: str, b: str) -> str:
    """The text two renderings of the same conversation share before their user turns differ, cut back to the start
    of the last special token (`<|...`), so that the tokens of the prefix are the first tokens of either rendering."""
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    shared = a[:n]
    cut = shared.rfind("<|")
    if cut < 0:
        cut = shared.rfind("\n") + 1
    return shared[:cut]


def rendered(host: str, system: str, tools: list, user: str, post=_post) -> str:
    """The server's own rendering of the conversation so far: the prefix the model will see."""
    body = {"messages": [{"role": "system", "content": system}, {"role": "user", "content": user}], "tools": tools}
    return post(f"http://{host}/apply-template", body, 60.0)["prompt"]


def warm(host: str, system: str, tools: list, post=_post) -> dict:
    """The prefix processed alone, no token asked for. {"prefix_chars", "prompt_n", "cache_n", "seconds"}."""
    prefix = prefix_of(rendered(host, system, tools, "a", post), rendered(host, system, tools, "b", post))
    began = time.monotonic()
    reply = post(f"http://{host}/completion", {"prompt": prefix, "n_predict": 0, "cache_prompt": True}, 600.0)
    timings = reply.get("timings") or {}
    return {"prefix_chars": len(prefix), "prompt_n": timings.get("prompt_n"), "cache_n": timings.get("cache_n"),
            "seconds": round(time.monotonic() - began, 2)}


def main(argv=None) -> int:
    import dawnr_cli as cli
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("task", nargs="*", help="ignored: the assistant's own arguments are accepted so the launcher can pass them through")
    ap.add_argument("--host", required=True)
    ap.add_argument("--name", default="base")
    ap.add_argument("--cwd", type=Path, default=Path.cwd())
    ap.add_argument("--read-only", action="store_true")
    ap.add_argument("--root", action="append", default=[])
    ap.add_argument("--online", action="store_true")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--state", type=Path, default=None)
    a = ap.parse_args(argv)
    try:
        config = cli.default_config(a.cwd, read_only=a.read_only, roots=tuple(a.root), online=a.online, state=a.state)
        harness, agent = cli.build_agent(config)
        with harness:
            planner = cli.Planner(harness, agent, a.host, a.name)
            got = warm(a.host, planner.system, planner.tools)
        print(f"warm: {got['prompt_n']} tokens processed, {got['cache_n']} from the cache, {got['seconds']} s", file=sys.stderr)
    except Exception as error:                                  # noqa: BLE001  (a cold start is slower, not wrong)
        print(f"warm: not done ({type(error).__name__}: {str(error)[:120]})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
