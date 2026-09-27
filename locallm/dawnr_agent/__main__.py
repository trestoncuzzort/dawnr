"""The agent without a model: its roots and rules, a dry run of a plan, running a plan, the change journal, undo.

    python locallm/dawnr_agent --config my-harness.json roots
    python locallm/dawnr_agent --config my-harness.json dry-run plan.json
    python locallm/dawnr_agent --config my-harness.json run plan.json [--approve DIGEST]
    python locallm/dawnr_agent --config my-harness.json journal
    python locallm/dawnr_agent --config my-harness.json undo c-0123456789

A plan file is {"goal": "...", "steps": [{"tool": "fs_read", "arguments": {"path": "project/a.t"}}, ...]}.
`dry-run` shows exactly what would run and runs nothing. `run` shows the same and asks on this terminal
whether to run it; `--approve DIGEST` approves ahead of time, and only a plan whose dry run has exactly that
digest (the person saw it in an earlier dry run and nothing has changed since). Without a terminal and
without --approve nobody approves: steps the policy allows run, steps that ask are refused.
`undo` is the person's own command: it reverts one journaled change without the model.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __name__ == "__main__" and __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from dawnr_agent.__main__ import main as _main
    raise SystemExit(_main())

from dawnr_harness.__main__ import terminal_approver  # noqa: E402

from .config import build_agent  # noqa: E402
from .paths import PathRefused  # noqa: E402
from .plan import Plan, PlanError, execute, preview_plan  # noqa: E402


def terminal_plan_approver(dry) -> bool:
    """Show a plan's dry run on this terminal and ask once for the whole plan (a front end's plan_approver)."""
    print(dry.render(for_person=True), file=sys.stderr)
    try:
        return input(f"  run plan {dry.digest}? [y/N] ").strip().lower() in ("y", "yes")
    except EOFError:
        return False


def _print_result(r, label: str = "") -> None:
    tag = "untrusted" if r.trust == "untrusted" else "trusted"
    print(f"[{label}{tag}{', error' if r.is_error else ''}]\n{r.text}")
    for n in r.notes:
        print(f"[harness note]\n{n}")
    for n in r.untrusted_notes:
        print(f"[untrusted]\n{n}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", type=Path, required=True, help="the harness configuration with an \"agent\" section")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("roots", help="the roots, protections, command rules and sandbox, and what loading skipped")
    d = sub.add_parser("dry-run", help="show exactly what a plan would do; run nothing")
    d.add_argument("plan", type=Path)
    r = sub.add_parser("run", help="show a plan, ask, run it")
    r.add_argument("plan", type=Path)
    r.add_argument("--approve", default=None, help="approve ahead of time: the digest a dry run showed")
    j = sub.add_parser("journal", help="the changes the agent made, newest last")
    j.add_argument("-n", type=int, default=20)
    u = sub.add_parser("undo", help="revert one journaled change (the person's command)")
    u.add_argument("change")
    a = ap.parse_args(argv)

    interactive = sys.stdin.isatty()
    harness, agent = build_agent(a.config, approver=terminal_approver if interactive else None)
    with harness:
        if a.cmd == "roots":
            for root in agent.space.roots:
                print(f"root {root.name}: {root.path} ({root.mode})")
            print("secret names: " + ", ".join(agent.space.secret_names))
            print("protected names: " + ", ".join(agent.space.protect_names)
                  + f"; plus {len(agent.space.protected_ids)} files and directories by identity")
            if agent.commands is not None:
                for rule in agent.commands.rules:
                    print(f"command rule {rule.index}: {rule.shape} -> {rule.program} ({rule.permission}, "
                          f"{'network' if rule.network else 'no network'}, {'writes' if rule.writes else 'reads'})")
                print("sandbox: " + ("bubblewrap" if agent.commands.sandbox and not agent.commands.sandbox_problem
                                     else agent.commands.sandbox_problem or "none"))
            print("offline: " + ("yes" if harness.policy.offline else "no"))
            for p in harness.problems:
                print(f"[problem] {p}")
            return 0
        if a.cmd == "journal":
            rows = agent.ops.journal.entries() if agent.ops else []
            for row in rows[-a.n:]:
                print(f"{row['id']} {row.get('action')} {row.get('path')} "
                      f"{(row.get('before') or '-')[:12]} -> {(row.get('after') or '-')[:12]}"
                      + (f" (undoes {row['undoes']})" if row.get("undoes") else ""))
            return 0
        if a.cmd == "undo":
            if agent.files is None:
                print("no roots are configured", file=sys.stderr)
                return 1
            try:
                print(agent.files.undo(a.change, session="person"))
            except PathRefused as e:
                print(f"not undone: {e}", file=sys.stderr)
                return 1
            return 0
        try:
            plan = Plan.from_json(json.loads(a.plan.read_text(encoding="utf-8")))
        except (OSError, ValueError, PlanError) as e:
            print(f"cannot read the plan: {e}", file=sys.stderr)
            return 2
        session = harness.session()
        dry = preview_plan(agent, harness, plan, session)
        print(dry.render(for_person=True))
        if a.cmd == "dry-run":
            return 1 if dry.refused else 0
        approved = None
        if a.approve is not None:
            approved = a.approve == dry.digest
            if not approved:
                print(f"--approve {a.approve} is not this plan's digest ({dry.digest}): something changed since that "
                      "dry run; nothing runs", file=sys.stderr)
                return 1
        elif interactive and not dry.refused:
            try:
                approved = input(f"run plan {dry.digest}? [y/N] ").strip().lower() in ("y", "yes")
            except EOFError:
                approved = False
        outcome = execute(harness, dry, approved=approved, session=session, steps_left=agent.budget.max_steps)
        agent.record_plan(dry, outcome, session)
        print(outcome.summary())
        for o in outcome.outcomes:
            if o.result is not None:
                _print_result(o.result, f"step {o.index} {o.step.tool}: ")
        for m in harness.messages:
            print(f"[message] {m}", file=sys.stderr)
        return 1 if outcome.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
