"""Twins of every family's right work that are wrong one way, and whether the family's judge rejects them.

    python3 locallm/judge_twins.py [--seeds N] [--family NAME ...] [--out rows.jsonl]

A judge that passes its own solution and fails the untouched start (dawnr_factory.selfcheck) can still accept work
that is wrong in a way the request forbids; a row the judge wrongly accepts teaches the wrong thing, and a score it
inflates is not a score. So each family's solution is changed one way at a time and judged again:

    half      one written text file cut to its first half
    digit     the first digit in one written text file changed (outside comment lines when it can be)
    drop      one of several written files left as it was
    swap      two neighbouring lines of one written text file swapped
    junk      a line left at the end of one written text file
    figure    the first digit of the answer changed
    silence   no answer, when the task asks for one
    no_act    the computer not touched, when the task asks for it

A twin the judge accepts is printed with its family; the count of accepted twins per family is the finding. Some
twins are the same work in other words (a digit changed in a comment), so the list is read by hand before a judge
is changed. After SWE-ABS (arXiv:2603.00520) and the program-variant probes of arXiv:2604.01518, which found that
test-based judges accept one in five wrong patches; only their probe step is taken, the judges here stay code.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import dawnr_factory as factory  # noqa: E402
import dawnr_tasks  # noqa: E402

TWINS = ("half", "digit", "drop", "swap", "junk", "figure", "silence", "no_act")
ANSWER_KEYS = ("answer", "any", "says", "truth", "truth_any")


def _text_files(solution: dict) -> list:
    """The written files that are text, in a fixed order."""
    return sorted(rel for rel, text in solution["files"].items() if isinstance(text, str))


def _bump(text: str, skip_comments: bool) -> str | None:
    """The text with its first digit changed, or None when it has none."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if skip_comments and line.lstrip().startswith("#"):
            continue
        m = re.search(r"\d", line)
        if m:
            d = str((int(m.group()) + 1) % 10)
            lines[i] = line[:m.start()] + d + line[m.end():]
            return "\n".join(lines)
    return None


def twins_of(task: dict) -> list:
    """[(name, solution)]: every twin this task's solution admits."""
    sol, out = task["solution"], []
    texts = _text_files(sol)

    def with_file(name, rel, text):
        files = dict(sol["files"])
        files[rel] = text
        out.append((name, {**sol, "files": files}))

    for rel in texts[:1]:
        lines = sol["files"][rel].split("\n")
        if len(lines) >= 4:
            with_file("half", rel, "\n".join(lines[: len(lines) // 2]) + "\n")
        bumped = _bump(sol["files"][rel], True) or _bump(sol["files"][rel], False)
        if bumped is not None:
            with_file("digit", rel, bumped)
        if len(lines) >= 3:
            mid = len(lines) // 2
            swapped = list(lines)
            swapped[mid - 1], swapped[mid] = swapped[mid], swapped[mid - 1]
            if swapped != lines:
                with_file("swap", rel, "\n".join(swapped))
        with_file("junk", rel, sol["files"][rel].rstrip("\n") + "\nzzz left over\n")
    if len(sol["files"]) >= 2:
        files = dict(sol["files"])
        del files[sorted(files)[0]]
        out.append(("drop", {**sol, "files": files}))
    if re.search(r"\d", sol["answer"] or ""):
        out.append(("figure", {**sol, "answer": _bump(sol["answer"], False)}))
    if any(k in task["expect"] for k in ANSWER_KEYS) and (sol["answer"] or "").strip():
        out.append(("silence", {**sol, "answer": "I looked at the folder."}))
    if sol["acted"]:
        out.append(("no_act", {**sol, "acted": []}))
    return out


def judge_solution(task: dict, solution: dict, tmp: Path, shell_for=None) -> dict:
    """The judge's word on `solution` as the end of `task`, built the way selfcheck builds it."""
    work = tmp / "work"
    work.mkdir(parents=True, exist_ok=True)
    for rel, text in task["files"].items():
        (work / rel).parent.mkdir(parents=True, exist_ok=True)
        (work / rel).write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))
    expect = factory.as_tuple(task)[4]
    if expect.get("setup"):
        expect["setup"](work)
    before = dawnr_tasks.snapshot(work)
    shell = shell_for(work) if shell_for is not None else None
    for rel, text in solution["files"].items():
        if text is None:
            if (work / rel).exists():
                (work / rel).unlink()
        else:
            (work / rel).parent.mkdir(parents=True, exist_ok=True)
            (work / rel).write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))
    for folder in sorted((p for p in work.rglob("*") if p.is_dir() and not p.is_symlink()), key=lambda p: -len(p.parts)):
        if not any(folder.iterdir()) and solution.get("prune", True):
            folder.rmdir()
    if shell is not None:
        from dawnr_agent.shell import _force_remove
        for run in list(shell.runs.values()):
            _force_remove(shell.runs.pop(run.id).scratch)
    return dawnr_tasks.judge(work, before, solution["answer"], expect, shell, list(solution["acted"]))


def main(argv=None) -> int:
    import dawnr_families  # noqa: F401  (registers the families)
    import dawnr_cli as cli
    from dawnr_agent.shell import _force_remove
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--family", action="append")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    rows, accepted_total, twins_total = [], 0, 0
    for name in sorted(a.family or factory.FAMILIES):
        accepted = []
        count = 0
        for seed in range(a.seeds):
            task = factory.make(name, seed)
            for twin, solution in twins_of(task):
                base, opened = Path(tempfile.mkdtemp(prefix="dawnr-twins-")), []

                def shell_for(work, base=base, opened=opened):
                    harness, agent = cli.build_agent(cli.default_config(work, state=base / "state"))
                    opened.append(harness)
                    return agent.shell
                try:
                    verdict = judge_solution(task, solution, base, shell_for if "run" in task["expect"] else None)
                finally:
                    for harness in opened:
                        harness.close()
                    _force_remove(str(base))
                count += 1
                ok = verdict["done"] and not verdict["harm"]
                rows.append({"family": name, "seed": seed, "twin": twin, "accepted": ok, "why": verdict["why"][:3], "harm": verdict["harm"][:3]})
                if ok:
                    accepted.append(f"{twin}@{seed}")
        twins_total += count
        accepted_total += len(accepted)
        print(f"{name:28s} {count:3d} twins, {len(accepted):2d} accepted" + (": " + " ".join(accepted) if accepted else ""))
    print(f"{accepted_total} of {twins_total} twins accepted by their judges")
    if a.out:
        with a.out.open("w") as f:
            for row in rows:
                f.write(json.dumps(row) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
