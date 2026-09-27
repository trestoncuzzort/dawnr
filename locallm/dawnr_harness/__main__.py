"""The harness without a model: what a configuration offers, and one call through its policy and hooks.

    python locallm/dawnr_harness [--config my-harness.json] index
    python locallm/dawnr_harness [--config my-harness.json] call t '{"program": "t 1\\n..."}'
    python locallm/dawnr_harness [--config my-harness.json] problems

A call that needs approval asks on this terminal.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __name__ == "__main__" and __package__ in (None, ""):
    # run as `python locallm/dawnr_harness`: import the package's copy of this module and run it
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from dawnr_harness.__main__ import main as _main
    raise SystemExit(_main())

from .runtime import build_harness  # noqa: E402


def terminal_approver(name: str, arguments: dict, why: str) -> bool:
    shown = json.dumps(arguments, ensure_ascii=False)
    print(f"[approval] {name} {shown[:400]}\n  why asked: {why}", file=sys.stderr)
    try:
        return input("  allow? [y/N] ").strip().lower() in ("y", "yes")
    except EOFError:
        return False


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", type=Path, default=None, help="the operator's harness configuration (JSON)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("index", help="print what the model would be offered")
    sub.add_parser("problems", help="print what loading the configuration skipped, and why")
    c = sub.add_parser("call", help="run one call through the policy and hooks")
    c.add_argument("name")
    c.add_argument("arguments", nargs="?", default="{}")
    c.add_argument("--context", default="", help="conversation text (Example lines the t tool runs)")
    a = ap.parse_args(argv)
    with build_harness(a.config, approver=terminal_approver if sys.stdin.isatty() else None) as h:
        if a.cmd == "index":
            print(h.index())
        elif a.cmd == "problems":
            print("\n".join(h.problems) or "none")
        else:
            try:
                args = json.loads(a.arguments)
            except ValueError as e:
                ap.error(f"arguments are not JSON: {e}")
            r = h.call(a.name, args, context=a.context)
            label = "untrusted" if r.trust == "untrusted" else "trusted"
            print(f"[{label}{', error' if r.is_error else ''}]\n{r.text}")
            for note in r.notes:
                print(f"[harness note]\n{note}")
            for m in h.messages:
                print(f"[message] {m}", file=sys.stderr)
            return 1 if r.is_error else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
