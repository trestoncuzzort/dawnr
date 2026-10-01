#!/usr/bin/env python3
"""t/dafny_feedback.py -- what Dafny itself says about a task that passes its tests and has no proof
(2026-10-01).

    python3 t/dafny_feedback.py ROWS.jsonl OUT.jsonl [--jobs 8]     # debugging rows in, the same rows out

SAFE trains self-debugging on triplets of a wrong proof, the VERIFIER'S ERROR and the correct
proof, and at inference hands a failed proof back with that error (arXiv:2410.15756, 3.3; with
it a 1.3B model goes from 21.6 to 27.3 at one answer). This project's debugging rows carried one
generic line a kernel ("could not prove the real program: usually a loop invariant is missing or
too weak..."), which names nothing a student could act on: a second try trained on 788 such rows
repaired 1 answer of 91 (t/PREDICT-2026-10-01-several-answers.md, prediction 22).

Dafny's diagnostics name the clause: which postcondition, which invariant, on entry or
maintained by the loop, which index. `diagnostics(task)` lowers the task with t/lower_dafny.py,
runs `dafny verify` with the adapter's own budget and turns each error into one line quoting the
clause of the lowered program it points at. The clause is quoted in Dafny's spelling (`|s|`,
`&&`); the lowering keeps a task's clauses in order and nearly verbatim, and the student is
trained and asked with the same lines.

Dafny alone, on purpose: it is the kernel closest to `t`, its messages are the most specific of
the seven, and one voice is something to act on where seven verdicts were not
(CORRECTIONS.md: a 14B model handed seven verdicts writes worse proofs more often than better
ones). The other six still judge the repaired answer.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

LOCATED = re.compile(r"^.*?\((?P<line>\d+),(?P<col>\d+)\): (?P<kind>Error|Related location): ?(?P<msg>.*)$")
HEAD = "It passes the tests, but the proof does not go through. Dafny reports:\n"
ASK_AGAIN = "\n\nWrite the corrected task."
MAX_LINES = 6


def parse(output: str, source: str) -> list[str]:
    """Dafny's output over `source`, as at most MAX_LINES lines, one an error, each quoting the
    clause it is about: the related location when Dafny names one, else the line of the error."""
    lines = source.split("\n")
    found, current = [], None
    for raw in output.split("\n"):
        m = LOCATED.match(raw.strip())
        if m is None:
            if "out of resource" in raw or "timed out" in raw:
                found.append("Dafny ran out of its resource limit before it could decide")
            continue
        n = int(m.group("line"))
        text = lines[n - 1].strip() if 0 < n <= len(lines) else ""
        if m.group("kind") == "Error":
            current = {"msg": m.group("msg").strip().rstrip("."), "at": text, "related": None}
            found.append(current)
        elif isinstance(current, dict) and current["related"] is None:
            current["related"] = text
    said: list[str] = []
    for e in found:
        if isinstance(e, str):
            line = e
        else:
            clause = e["related"] or e["at"]
            line = f"{e['msg']}: `{clause}`" if clause and clause not in ("{", "}") else e["msg"]
        if "- " + line not in said:
            said.append("- " + line)
    return said[:MAX_LINES]


def diagnostics(task: dict, wall: int = 150) -> list[str]:
    """parse() of a real Dafny run on the lowered task; [] when the task does not lower or Dafny is absent."""
    import lower_dafny                                          # noqa: E402
    from verifiers import dafny as adapter                      # noqa: E402
    if not adapter.DAFNY:
        return []
    try:
        source = lower_dafny.lower(task, task["body"])
    except Exception:                                           # noqa: BLE001
        return []
    with tempfile.TemporaryDirectory(prefix="dafny-feedback-") as tmp:
        path = Path(tmp) / "task.dfy"
        path.write_text(source, encoding="utf-8")
        try:
            p = subprocess.run([adapter.DAFNY, "verify", "--resource-limit", str(adapter.DEFAULT_RLIMIT),
                                "--warn-contradictory-assumptions", str(path)],
                               capture_output=True, text=True, errors="replace", timeout=wall)
        except subprocess.TimeoutExpired:
            return ["- Dafny did not finish within its time limit"]
    return parse(p.stdout + p.stderr, source)


_TALLY = re.compile(r"finished with (\d+) verified, (\d+) errors?")


def judge(task: dict, wall: int = 150) -> dict:
    """{"verified": bool, "said": [...]} from ONE Dafny run on the lowered task: verified when
    Dafny exits 0 having discharged at least one obligation with no error. This is the in-loop
    verdict a repair step acts on (SAFE repairs against Verus alone); it is weaker than the
    adapter's (no vacuity or certificate checks), and all seven kernels and the twins still judge
    whatever comes out of the loop."""
    import lower_dafny                                          # noqa: E402
    from verifiers import dafny as adapter                      # noqa: E402
    if not adapter.DAFNY:
        return {"verified": False, "said": [], "why": "no dafny"}
    try:
        source = lower_dafny.lower(task, task["body"])
    except Exception as e:                                      # noqa: BLE001
        return {"verified": False, "said": [], "why": f"does not lower: {type(e).__name__}"}
    with tempfile.TemporaryDirectory(prefix="dafny-feedback-") as tmp:
        path = Path(tmp) / "task.dfy"
        path.write_text(source, encoding="utf-8")
        try:
            p = subprocess.run([adapter.DAFNY, "verify", "--resource-limit", str(adapter.DEFAULT_RLIMIT),
                                "--warn-contradictory-assumptions", str(path)],
                               capture_output=True, text=True, errors="replace", timeout=wall)
        except subprocess.TimeoutExpired:
            return {"verified": False, "said": ["- Dafny did not finish within its time limit"]}
    out = p.stdout + p.stderr
    m = _TALLY.search(out)
    verified = p.returncode == 0 and m is not None and int(m.group(1)) >= 1 and int(m.group(2)) == 0
    return {"verified": verified, "said": [] if verified else parse(out, source)}


def judge_file(argv: list[str]) -> int:
    """`--judge TASKS.jsonl OUT.jsonl [--jobs N]`: one task JSON a line in, one verdict a line out."""
    from multiprocessing import Pool
    jobs = int(argv[argv.index("--jobs") + 1]) if "--jobs" in argv else 8
    tasks = [json.loads(l) for l in Path(argv[1]).read_text(encoding="utf-8").splitlines() if l.strip()]
    with Pool(jobs) as pool:
        out = pool.map(judge, tasks, chunksize=2)
    Path(argv[2]).write_text("".join(json.dumps(r) + "\n" for r in out), encoding="utf-8")
    print(json.dumps({"tasks": len(out), "verified": sum(1 for r in out if r["verified"])}))
    return 0


def message(said: list[str]) -> str:
    """The words a student is trained on and asked with (without the closing request)."""
    return HEAD + "\n".join(said)


def with_dafny(row: dict) -> dict:
    """A debugging row of failure `proof` with Dafny's own message in place of the generic one;
    any other row, and a row Dafny says nothing about, is returned as it was."""
    if row.get("failure") != "proof":
        return row
    import spec_experiment as se                                # noqa: E402
    import surface                                              # noqa: E402
    try:
        task = surface.parse(se.find_block(row["prompt"][-2]["content"]))
    except Exception:                                           # noqa: BLE001
        return row
    said = diagnostics(task)
    if not said:
        return row
    out = json.loads(json.dumps(row))
    out["prompt"][-1]["content"] = message(said) + ASK_AGAIN
    out["dafny"] = said
    return out


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) < 2:
        print(__doc__)
        return 2
    if argv[0] == "--judge":
        return judge_file(argv)
    from multiprocessing import Pool
    jobs = int(argv[argv.index("--jobs") + 1]) if "--jobs" in argv else 8
    rows = [json.loads(l) for l in Path(argv[0]).read_text(encoding="utf-8").splitlines() if l.strip()]
    with Pool(jobs) as pool:
        out = pool.map(with_dafny, rows, chunksize=4)
    Path(argv[1]).write_text("".join(json.dumps(r) + "\n" for r in out), encoding="utf-8")
    proof = [r for r in out if r.get("failure") == "proof"]
    print(json.dumps({"rows": len(out), "proof rows": len(proof),
                      "with Dafny's own message": sum(1 for r in proof if "dafny" in r)}))
    return 0


if __name__ == "__main__":                                      # pragma: no cover
    raise SystemExit(main())
