"""The person's controls over what dawnr remembers of them.

    python locallm/dawnr_memory [--person NAME] [--root DIR] list [--kind fact]
    python locallm/dawnr_memory --person ann show f-0123456789abcdef
    python locallm/dawnr_memory --person ann recall "what should I work on today?"
    python locallm/dawnr_memory --person ann pin "Answer in short sentences."
    python locallm/dawnr_memory --person ann correct f-0123456789abcdef "lives in Porto"
    python locallm/dawnr_memory --person ann forget f-0123456789abcdef [more ids]
    python locallm/dawnr_memory --person ann forget-session 3f2a9c1b7d4e
    python locallm/dawnr_memory --person ann export [--out ann.json]
    python locallm/dawnr_memory --person ann forget-everything --yes
    python locallm/dawnr_memory --person ann settings [--remember off] [--recall off]

Everything runs on this machine and reads or writes only the named person's folder.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __name__ == "__main__" and __package__ in (None, ""):
    # run as `python locallm/dawnr_memory`: import the package's copy of this module and run it
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from dawnr_memory.__main__ import main as _main
    raise SystemExit(_main())

from .retrieval import recall  # noqa: E402
from .store import KINDS, MemoryStore, StoreError, memory_root, write_owner_only  # noqa: E402

DEFAULT_BUDGET = 256


def _switch(value: str) -> bool:
    if value.lower() in ("on", "yes", "true", "1"):
        return True
    if value.lower() in ("off", "no", "false", "0"):
        return False
    raise argparse.ArgumentTypeError("on or off")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="dawnr_memory", description=__doc__.split("\n")[0])
    ap.add_argument("--person", default="default", help="whose memory (default: default)")
    ap.add_argument("--root", type=Path, default=None, help="the memory folder (default: the app's data folder)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list", help="every record, newest first")
    p.add_argument("--kind", choices=KINDS, default=None)
    p = sub.add_parser("show", help="one record, every field")
    p.add_argument("id")
    p = sub.add_parser("recall", help="what dawnr would be told at the start of a session opening with MESSAGE")
    p.add_argument("message", nargs="?", default="")
    p.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    p = sub.add_parser("pin", help="a note you write: recalled first, never changed by extraction")
    p.add_argument("text")
    p = sub.add_parser("correct", help="replace a record's words with yours")
    p.add_argument("id")
    p.add_argument("text")
    p = sub.add_parser("forget", help="delete records (their files are removed)")
    p.add_argument("ids", nargs="+")
    p = sub.add_parser("forget-session", help="delete what one session added")
    p.add_argument("session", help="the session's episode id (e-...) or its session id")
    p = sub.add_parser("export", help="everything, as JSON")
    p.add_argument("--out", type=Path, default=None, help="write to this file (only you can read it) instead")
    p = sub.add_parser("forget-everything", help="delete this person's whole memory")
    p.add_argument("--yes", action="store_true", help="really: nothing asks again and nothing can undo it")
    p = sub.add_parser("settings", help="show or change whether dawnr remembers and recalls")
    p.add_argument("--remember", type=_switch, default=None, metavar="on|off")
    p.add_argument("--recall", type=_switch, default=None, metavar="on|off")
    a = ap.parse_args(argv)

    try:
        store = MemoryStore(a.root or memory_root(), a.person)
    except (StoreError, ValueError, OSError) as e:
        print(f"dawnr_memory: {e}", file=sys.stderr)
        return 2
    if a.cmd == "list":
        records = store.records((a.kind,) if a.kind else KINDS)
        for r in records:
            print(f"{r['id']}  {r['kind']:<10}  {str(r.get('updated', ''))[:10]}  {r['text']}")
        print(f"{len(records)} record(s) for {store.person} in {store.dir}")
    elif a.cmd == "show":
        record = store.get(a.id)
        if record is None:
            print(f"no record {a.id} for {store.person}", file=sys.stderr)
            return 1
        print(json.dumps(record, ensure_ascii=False, indent=1, sort_keys=True))
    elif a.cmd == "recall":
        result = recall(store, a.message, budget=a.budget)
        print(result.text or "(nothing would be recalled)")
        print(f"[{len(result.ids)} of {result.considered} record(s); at most {result.cost} of {a.budget} tokens]")
    elif a.cmd == "pin":
        record = store.pin(a.text)
        print(f"pinned {record['id']}: {record['text']}")
    elif a.cmd == "correct":
        try:
            record = store.correct(a.id, a.text)
        except KeyError as e:
            print(e.args[0], file=sys.stderr)
            return 1
        print(f"corrected {record['id']}: {record['text']}")
    elif a.cmd == "forget":
        missing = [i for i in a.ids if not store.forget(i)]
        print(f"forgot {len(a.ids) - len(missing)} record(s)"
              + (f"; not found: {', '.join(missing)}" if missing else ""))
        return 1 if missing else 0
    elif a.cmd == "forget-session":
        session = a.session
        episode = store.get(session) if session.startswith("e-") else None
        if episode is not None:                    # an episode's id names its session, as `list` shows it
            session = str(episode.get("session") or "")
        gone = store.forget_session(session) if session else []
        print(f"forgot {len(gone)} record(s) from session {session or a.session}: {', '.join(gone) or 'none'}")
    elif a.cmd == "export":
        text = json.dumps(store.export(), ensure_ascii=False, indent=1, sort_keys=True) + "\n"
        if a.out is None:
            sys.stdout.write(text)
        else:
            a.out.parent.mkdir(parents=True, exist_ok=True)
            write_owner_only(a.out.resolve(), text.encode("utf-8"), "export")
            print(f"exported {store.person}'s memory to {a.out}")
    elif a.cmd == "forget-everything":
        if not a.yes:
            print("this deletes every record of this person's memory and cannot be undone; add --yes", file=sys.stderr)
            return 1
        print(f"forgot everything for {store.person}: {store.forget_everything()} file(s) removed")
    elif a.cmd == "settings":
        changes = {k: v for k, v in (("remember", a.remember), ("recall", a.recall)) if v is not None}
        settings = store.set_settings(**changes) if changes else store.settings()
        print(json.dumps(settings, sort_keys=True))
    for problem in store.problems:
        print(f"[skipped] {problem}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
