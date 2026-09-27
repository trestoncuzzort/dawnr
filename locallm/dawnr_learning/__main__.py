"""The person's controls over what dawnr keeps and learns about them, from a terminal.

    python3 locallm/dawnr_learning people                         everyone this machine keeps records for
    python3 locallm/dawnr_learning show NAME                      every record: id, session, feedback, prompt
    python3 locallm/dawnr_learning export NAME [--out FILE]       everything kept about NAME, as JSON
    python3 locallm/dawnr_learning forget NAME ID                 erase one record (its adapter goes stale)
    python3 locallm/dawnr_learning forget-all NAME --yes          erase NAME: records, adapters, sleeps
    python3 locallm/dawnr_learning profile NAME [--pin DIM=VALUE] [--unpin DIM]
                                                                  what dawnr believes about NAME's taste
    python3 locallm/dawnr_learning status NAME --model DIR        is there an adapter for this base, fresh?
    python3 locallm/dawnr_learning sleep NAME --model DIR [--replay CONV.jsonl] [--guard-text VALID.txt]
                                          [--mode rebuild|continue] [--lr 3e-4] [--rank 8] [--device cuda]
    python3 locallm/dawnr_learning sleep-all --model DIR [--min-new 5] [the options of sleep]
                                          every person with at least --min-new examples their adapter has
                                          not learned, or a stale adapter: the command for a nightly timer

--root DIR (before the command) or DAWNR_PEOPLE_DIR chooses where the records
live; the default is this machine's per-user data folder (feedback.default_root).
Nothing here reaches the network, and nothing is erased without a command that
says so.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOCALLM = HERE.parent
for p in (str(LOCALLM), str(LOCALLM.parent / "t")):
    if p not in sys.path:
        sys.path.insert(0, p)

from dawnr_learning.feedback import PersonStore, default_root, person_id  # noqa: E402


def _first_line(messages) -> str:
    user = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
    return (user.strip().splitlines() or [""])[0][:70] if isinstance(user, str) else ""


def _sleep_options(sp) -> None:
    sp.add_argument("--model", type=Path, required=True, help="the chat checkpoint the adapters belong to")
    sp.add_argument("--replay", type=Path, default=None, help="the base's chat_data.py conversations")
    sp.add_argument("--guard-text", type=Path, default=None, help="held-out plain source text")
    sp.add_argument("--mode", choices=("rebuild", "continue"), default="rebuild")
    sp.add_argument("--lr", type=float, default=3e-4)
    sp.add_argument("--rank", type=int, default=8)
    sp.add_argument("--replay-frac", type=float, default=0.25)
    sp.add_argument("--ewc-lambda", type=float, default=0.0)
    sp.add_argument("--fisher", action="store_true", help="save the diagonal Fisher for a later continue")
    sp.add_argument("--device", default=None)


def _sleep(store, a) -> dict:
    from dawnr_learning.sleep import SleepConfig, sleep_person
    cfg = SleepConfig(mode=a.mode, lr=a.lr, r=a.rank, replay_frac=a.replay_frac if a.replay else 0.0,
                      ewc_lambda=a.ewc_lambda, fisher=a.fisher)
    record = sleep_person(store, a.model, cfg=cfg, replay=a.replay, guard_text=a.guard_text, device=a.device,
                          log=lambda point: print(json.dumps(point), flush=True))
    keep = ("person", "result", "examples_available", "excluded", "steps", "best_step", "stop", "loss_base",
            "loss_adapter", "guard", "behavior", "seconds")
    print(json.dumps({k: record[k] for k in keep if k in record}, indent=2, default=str))
    return record


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="dawnr_learning", description=__doc__.split("\n")[0])
    ap.add_argument("--root", type=Path, default=None, help="where people's records live (default: per-user data)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("people")
    for name in ("show", "export", "forget", "forget-all", "profile", "status", "sleep"):
        sp = sub.add_parser(name)
        sp.add_argument("name")
        if name == "export":
            sp.add_argument("--out", type=Path, default=None)
        elif name == "forget":
            sp.add_argument("id")
        elif name == "forget-all":
            sp.add_argument("--yes", action="store_true", help="really erase everything kept about this person")
        elif name == "profile":
            sp.add_argument("--pin", action="append", default=[], help="DIM=VALUE, e.g. indent=4 or naming=upper")
            sp.add_argument("--unpin", action="append", default=[])
        elif name == "status":
            sp.add_argument("--model", type=Path, required=True, help="the chat checkpoint the adapter belongs to")
        elif name == "sleep":
            _sleep_options(sp)
    every = sub.add_parser("sleep-all")
    every.add_argument("--min-new", type=int, default=5)
    _sleep_options(every)
    a = ap.parse_args(argv)
    root = a.root or default_root()

    if a.cmd in ("people", "sleep-all"):
        people = sorted(p.name for p in root.iterdir() if p.is_dir()) if root.is_dir() else []
        if a.cmd == "people":
            for name in people:
                try:
                    print(f"{name}: {json.dumps(PersonStore(name, root).summary())}")
                except ValueError as e:
                    print(f"{name}: unreadable: {e}")
            if not people:
                print(f"no one yet ({root})")
            return 0
        from dawnr_learning import adapters
        identity = adapters.base_identity(a.model)
        for name in people:
            try:
                store = PersonStore(name, root)
                st = adapters.status(store, identity)
            except ValueError as e:
                print(f"{name}: skipped: {e}")
                continue
            if st["untrained"] >= a.min_new or (st["exists"] and not st["fresh"]):
                print(f"{name}: sleeping ({st['untrained']} new, {'stale' if st['exists'] and not st['fresh'] else 'fresh'})")
                _sleep(store, a)
            else:
                print(f"{name}: nothing to do ({st['untrained']} new, under --min-new {a.min_new})")
        return 0

    store = PersonStore(person_id(a.name), root)
    if a.cmd == "show":
        for r in store.records():
            print(f"{r['id']}  {r.get('session', '')[:24]:24}  {str(r.get('feedback')):6}  {_first_line(r['messages'])}")
        print(json.dumps(store.summary()))
    elif a.cmd == "export":
        data = json.dumps(store.export(), indent=2, ensure_ascii=False) + "\n"
        if a.out:
            a.out.write_text(data, encoding="utf-8")
            print(f"wrote {a.out}")
        else:
            sys.stdout.write(data)
    elif a.cmd == "forget":
        store.erase(a.id)
        print(f"erased {a.id}; an adapter that learned from it will not be used until the next sleep rebuilds it")
    elif a.cmd == "forget-all":
        if not a.yes:
            print("this erases every record, adapter and sleep kept about this person; add --yes to do it")
            return 2
        print(f"erased {store.erase_all()} file(s) kept about {store.person}")
    elif a.cmd == "profile":
        from dawnr_learning import style_profile as PR
        prof = PR.refresh(store)
        for item in a.pin:
            dim, _, raw = item.partition("=")
            if dim not in PR.DIMENSIONS or not raw:
                print(f"--pin takes DIM=VALUE with DIM one of {', '.join(PR.DIMENSIONS)}")
                return 2
            prof.setdefault("pinned", {})[dim] = json.loads(raw) if raw in ("true", "false") or raw.isdigit() \
                else raw
        for dim in a.unpin:
            prof.get("pinned", {}).pop(dim, None)
        PR.save(store.dir, prof)
        print("\n".join(PR.describe(prof)))
    elif a.cmd == "status":
        from dawnr_learning import adapters
        print(json.dumps(adapters.status(store, adapters.base_identity(a.model)), indent=2))
    elif a.cmd == "sleep":
        _sleep(store, a)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
