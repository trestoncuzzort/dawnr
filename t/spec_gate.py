#!/usr/bin/env python3
"""t/spec_gate.py -- the gate's specification stage when there is no reference solution (2026-10-01).

    python3 t/spec_gate.py --python PYTHON.jsonl [--pool v5] [--ids-file IDS] [--json OUT] TAG [TAG ...]

The provers say a program meets its specification. They do not say the specification is what the
question asked. In evaluation t/spec_check.py asks the problem's reference solution; a person
asking a question has none. Measured on the fine-tuned 4B's dev answers (2026-10-01): of 10
problems that pass their tests and a proof, 4 carry a specification that is right and complete,
4 a weak one, and 2 a different function that happens to fit the three tests.

Clover (arXiv:2310.17807) accepts generated code only when independently produced artifacts are
consistent, and compares code with code by their OUTPUTS ON A SET OF INPUTS (its doc2code and
anno-complete edges); it reports 87% of correct instances accepted and no adversarial incorrect
one. CodeT (arXiv:2207.10397) trusts a sample by its agreement with independent samples. The
second artifact here is a Python solution the model writes for the same question, kept only if
it passes the question's own tests in the sandbox (t/py_sandbox.py). Python is the language the
base model knows best, and it shares no text with the `t` answer.

The stage is the reference check itself with that Python in the reference's place
(spec_check.check_task(oracle=...)): on inputs drawn in the shapes of the question's own
examples, the specification must hold at the Python's output (at least MIN_DRAWS draws inside
the `requires`, which must admit at least MIN_DOMAIN of the drawn inputs the Python answers),
and it must reject at least MIN_COMPLETENESS of the mutated outputs (SAFE's floor for a usable
specification, arXiv:2410.15756 3.2). An answer with no test-passing Python
beside it is refused: nothing independent says its specification is the question's.

What differs from Clover: inputs are drawn, not shipped; no language model judges anything;
there is one second artifact, not five. Its stated limit holds here too: an edge case the
Python, the tests and the specification all miss is not detected.

Also reported, never deciding: SAFE's two scores on the question's own tests
(t/spec_quality.py) and the lazy-program exploit (AlphaVerus, arXiv:2412.06176;
spec_check.exploit).
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import harness                                                  # noqa: E402
import py_sandbox                                               # noqa: E402
import spec_check                                               # noqa: E402
import spec_experiment as se                                    # noqa: E402
import spec_quality                                             # noqa: E402

MIN_DRAWS = 10
MIN_COMPLETENESS = 0.6
# INVENTED: no published number for this one. A task may state a real precondition (n >= 0, a
# non-empty list) that excludes some drawn inputs the Python happens to answer, so the floor
# cannot be 1; a `requires` that admits little more than the question's own examples must not
# pass on the few draws that land inside it. Half is the floor; what it costs in right answers
# is measured (t/PREDICT-2026-10-01-gate-without-reference.md).
MIN_DOMAIN = 0.5
DRAWS = 100


def python_oracle(session: py_sandbox.Session):
    """The sandboxed function as spec_check.check_task calls a reference: a value, an exception
    for an input it refuses, spec_check.Timeout when it does not finish, and a value `to_t`
    rejects (so the draw is skipped, as for a reference returning a set) when the result has no
    JSON form."""
    def call(*args):
        try:
            return session.call(list(args))
        except py_sandbox.CallTimeout:
            raise spec_check.Timeout() from None
        except py_sandbox.Unrepresentable:
            return {}                                           # to_t raises TypeError: "no t value"
    return call


def domain(result: dict) -> float | None:
    """Of the drawn inputs the Python answered with a value t can hold, the share the task's
    `requires` admits."""
    inside, outside = result.get("draws", 0), result.get("outside_requires", 0)
    return inside / (inside + outside) if inside + outside else None


def passes(result: dict) -> bool:
    """The rule: agrees on at least MIN_DRAWS draws; the `requires` admits at least MIN_DOMAIN of
    the drawn inputs the Python answers; and of the mutants judged at least MIN_COMPLETENESS are
    rejected (no mutant judged is not a failure: every mutant was undefined)."""
    if result.get("status") != "agrees" or result.get("draws", 0) < MIN_DRAWS:
        return False
    if domain(result) < MIN_DOMAIN:
        return False
    share = result.get("completeness")
    return not isinstance(share, (int, float)) or share >= MIN_COMPLETENESS


def reason(result: dict) -> str:
    if passes(result):
        return "passes"
    if result.get("status") == "agrees":
        if result.get("draws", 0) < MIN_DRAWS:
            return "too few draws inside the requires"
        if domain(result) < MIN_DOMAIN:
            return "the requires excludes most drawn inputs"
        return "weak specification"
    if result.get("status") == "disagrees":
        return "the specification is false at the Python's answer"
    return str(result.get("status") or "not checked")


def judge(task: dict, entry: dict, code: str | None, seed: int = 1, n: int = DRAWS) -> dict:
    """One answer: {"passes", "why", the check's result, the reported scores}. `code` is the
    model's own Python for the question, already known to pass the question's tests, or None."""
    out = {"tests": spec_quality.scores(task, entry), "exploit": spec_check.exploit(task, entry).get("exploited_by")}
    if code is None:
        return dict(out, passes=False, why="no test-passing Python beside it")
    try:
        with py_sandbox.Session(code, entry["fn"]) as session:
            result = spec_check.check_task(task, entry, n, random.Random(seed), oracle=python_oracle(session))
    except py_sandbox.LoadError as e:
        return dict(out, passes=False, why=f"the Python does not load: {e}"[:160])
    except Exception as e:                                      # noqa: BLE001
        return dict(out, passes=False, why=f"the check raised {type(e).__name__}: {e}"[:160])
    keep = {k: result[k] for k in ("status", "draws", "outside_requires", "completeness", "mutants_rejected",
                                   "mutants_accepted", "skipped", "args", "reference_said", "ensures",
                                   "weak_witness") if k in result}
    return dict(out, passes=passes(result), why=reason(result), agreement=keep)


def load_python(path: Path) -> dict[str, str]:
    """problem id -> the Python kept for it (rows {"task_id", "code"}; the last row for an id wins)."""
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            if row.get("code"):
                out[str(row["task_id"])] = row["code"]
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tags", nargs="+")
    ap.add_argument("--python", type=Path, required=True, help="JSONL of {task_id, code}: the model's own tested Python")
    ap.add_argument("--pool", choices=se.POOL_VERSIONS, default="v5")
    ap.add_argument("--ids-file", type=Path)
    ap.add_argument("--only", choices=("tests-pass", "all"), default="tests-pass",
                    help="judge only answers that pass their problem's tests (default), or every task-stage answer")
    ap.add_argument("--json", type=Path)
    a = ap.parse_args(argv)
    pool = {str(k): v for k, v in se.pool(a.pool).items()}
    python = load_python(a.python)
    ids = {x for x in a.ids_file.read_text(encoding="utf-8").split()} if a.ids_file else None
    out, tally = {}, Counter()
    for tag in a.tags:
        d = se.OUT_ROOT / se.model_tag(tag)
        try:
            tests = json.loads((d / "tests.json").read_text(encoding="utf-8"))
        except OSError:
            continue
        for tid, t in sorted(tests.items(), key=lambda kv: int(kv[0])):
            if tid not in pool or (ids is not None and tid not in ids):
                continue
            if a.only == "tests-pass" and t.get("overall") != "pass":
                continue
            path = d / "tasks" / f"{t['name']}.json"
            if not path.exists():
                continue
            task = harness.load(path)
            v = judge(task, pool[tid], python.get(tid))
            v["task_sha256"] = spec_check.task_sha256(task)
            out[f"{tag}/{t['name']}"] = v
            tally[v["why"] if not v["passes"] else "passes"] += 1
    print(f"spec_gate: {sum(tally.values())} answers judged: " + ", ".join(f"{v} {k}" for k, v in tally.most_common()))
    if a.json:
        a.json.write_text(json.dumps({"results": out}, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":                                      # pragma: no cover
    raise SystemExit(main())
