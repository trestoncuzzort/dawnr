#!/usr/bin/env python3
"""t/repair.py -- give a model a second try at the proofs it did not get through (2026-09-17).

    python3 t/repair.py t/out/spec-experiment/<tag> [--model qwen2.5-coder:14b] [--jobs 4]

An answer that passes every test but is not proven in all seven kernels is usually right code with too little
proof in it: a missing loop invariant, a missing decreases, a bound the kernel cannot see. repair.py sends each
such answer back to the model with the kernels' verdicts and asks for the same program with the proof completed.
The replies land in a new tag, <tag>-fix1, in spec_experiment.py's layout, so extract, tests, pool_pick.py,
run_par.py and loop_dataset.py treat it as one more answer set.

Two kinds of repair, chosen from the verdicts, and what each may change is enforced after extraction:
- `proof`: no kernel refuted the program. The signature, every `requires` and every `ensures` stay exactly as
  they were (new `ensures` may be added, none removed or altered); the body, invariants and decreases may change.
  A repair can never make such a task easier to prove by promising less.
- `spec`: some kernel found an input where the program breaks its own `ensures`. The code passes its tests, so the
  `ensures` is what is wrong: it may be rewritten; the signature and every `requires` stay exactly as they were.
  A rewritten `ensures` still has to be proven in all seven with the broken copy caught, so one too weak to tell
  right from wrong is rejected by the kernels, as for any first answer.
A reply that changes more than its kind allows is dropped (extract.json stage `spec-changed`). The tests run again on
every repaired task, and pool_pick.py skips a reply identical to one already graded.

The training prompt stays the original problem: raw/<id>.json's `messages` are the source answer's own, and the
repair conversation is kept beside them as `repair_messages`.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import spec_experiment as se                                    # noqa: E402

KERNEL_NAMES = {"dafny": "Dafny", "verus": "Verus", "spark": "SPARK (GNATprove)", "framac": "Frama-C (WP)",
                "lean": "Lean 4", "rocq": "Rocq", "fstar": "F*"}
MEANING = {
    "unproved": "could not prove the real program: usually a loop invariant is missing or too weak to imply the "
                "ensures, or a decreases is missing",
    "timeout": "ran out of time: give the prover more to go on (stronger invariants, smaller steps)",
    "refuted": "found an input where the program breaks its own ensures",
    "decorative": "proved the program, but also a deliberately broken copy: the ensures are too weak to tell "
                  "right from wrong; add an ensures that pins the result down",
    "unsound": "proved a broken copy that a concrete input shows is wrong: the ensures do not constrain the result",
    "abstain": "cannot express this construct yet; prefer simpler constructs (plain while loops over sequences)",
    "malformed": "rejected the translated program: avoid unusual constructs",
    "no-twin": "no broken copy could be built because no input satisfies the requires: the requires is too strong",
    "tool_error": "failed to run on this program",
}


def cell_words(cell: str) -> tuple[str, str]:
    real, _, twin = cell.partition(" / ")
    return real.strip(), twin.replace("(FLAKED)", "").strip()


def feedback(row: dict, cols: list[str]) -> str:
    lines = []
    for k in cols:
        cell = row.get(k, "")
        real, twin = cell_words(cell)
        if real == "verified" and twin == "refuted":
            lines.append(f"- {KERNEL_NAMES.get(k, k)}: proved it, and caught the broken copy.")
            continue
        if real == "verified" and twin in ("decorative", "unsound", "verified"):
            why = MEANING["decorative"]
        elif real == "verified":
            why = f"proved the program, but the broken copy read `{twin}`"
        else:
            why = MEANING.get(real, f"read `{real}`")
        lines.append(f"- {KERNEL_NAMES.get(k, k)}: {why}.")
    return "\n".join(lines)


def spec_of(task: dict) -> dict:
    return {"params": task["params"], "returns": task["returns"], "requires": task.get("requires", [])}


def kind_of(row: dict, cols: list[str]) -> str:
    return "spec" if any(cell_words(row.get(k, ""))[0] == "refuted" for k in cols) else "proof"


def spec_kept(original: dict, repaired: dict, kind: str = "proof") -> bool:
    if json.dumps(spec_of(original), sort_keys=True) != json.dumps(spec_of(repaired), sort_keys=True):
        return False
    if kind == "spec":
        return True
    new = [json.dumps(e, sort_keys=True) for e in repaired.get("ensures", [])]
    return all(json.dumps(e, sort_keys=True) in new for e in original.get("ensures", []))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("src", type=Path, help="a graded tag directory (grade-in/ and kernels.md present)")
    ap.add_argument("--model", default="qwen2.5-coder:14b")
    ap.add_argument("--host", default="127.0.0.1:11434")
    ap.add_argument("--suffix", default="-fix1")
    ap.add_argument("--pool", default="v3")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--temperature", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--num-ctx", type=int, default=12288)
    ap.add_argument("--num-predict", type=int, default=3072)
    ap.add_argument("--timeout", type=float, default=1800)
    a = ap.parse_args()

    src = a.src
    tag = src.name + a.suffix
    out = se.outdir(tag)
    (out / "raw").mkdir(parents=True, exist_ok=True)
    (out / "tasks").mkdir(parents=True, exist_ok=True)
    cols, cells = se.parse_kernel_table(src / "kernels.md")
    if not cols:
        print(f"repair: {src.name} has no kernels.md yet")
        return 2
    ext = json.loads((src / "extract.json").read_text(encoding="utf-8"))
    by_name = {e["name"]: tid for tid, e in ext.items() if e.get("stage") == "task"}
    todo = []
    for f in sorted((src / "grade-in").glob("*.json")):
        name = f.stem
        row = cells.get(name)
        if row is None or all(cell_words(row.get(k, ""))[0:2] == ("verified", "refuted") for k in cols):
            continue                                   # not graded, or already clean
        tid = by_name.get(name)
        if tid is None or (out / "raw" / f"{tid}.json").exists():
            continue
        todo.append((tid, name, row))
    options = {"temperature": a.temperature, "seed": a.seed, "num_ctx": a.num_ctx, "num_predict": a.num_predict}
    digest = se.model_digest(a.host, a.model)
    print(f"repair: {src.name}: {len(todo)} answers pass their tests but are not clean in all seven", flush=True)
    lock, state, t0 = threading.Lock(), {"n": 0, "failed": 0}, time.monotonic()

    def one(item):
        tid, name, row = item
        raw = json.loads((src / "raw" / f"{tid}.json").read_text(encoding="utf-8"))
        block = se.find_block(raw["reply"]) or ""
        kind = kind_of(row, cols)
        if kind == "proof":
            keep = ("Keep the task name, the parameters, the return type, every `requires` and every `ensures` "
                    "exactly as they are; you may add `ensures` lines, and change the body, the loop invariants and "
                    "the decreases clauses.")
        else:
            keep = ("The code passes the tests, so the `ensures` is what is wrong: rewrite the `ensures` so they "
                    "state exactly what the tests show the result must be, strong enough that a wrong result breaks "
                    "them. Keep the task name, the parameters, the return type and every `requires` exactly as they "
                    "are; fix the loop invariants to match.")
        ask = (f"Your t task passes every test. The seven proof checkers said:\n\n{feedback(row, cols)}\n\n"
               f"Rewrite the task so every checker proves it and catches a broken copy. {keep} Reply with the "
               "complete task in one ```t block.")
        messages = raw["messages"] + [{"role": "assistant", "content": f"```t\n{block}\n```"},
                                      {"role": "user", "content": ask}]
        try:
            resp = se.chat(a.host, a.model, messages, options, a.timeout)
        except OSError as e:
            print(f"repair: {tid}: no answer: {e}", file=sys.stderr)
            with lock:
                state["failed"] += 1
            return
        rec = dict(raw, model=a.model, digest=digest, options=options, repair_of=f"{src.name}/{name}", repair_kind=kind,
                   repair_messages=messages, reply=resp.get("message", {}).get("content", ""),
                   reply_tokens=resp.get("eval_count"), done_reason=resp.get("done_reason"))
        (out / "raw" / f"{tid}.json").write_text(json.dumps(rec, indent=1), encoding="utf-8")
        with lock:
            state["n"] += 1
            if state["n"] % 10 == 0 or state["n"] == 1:
                el = time.monotonic() - t0
                print(f"repair: {state['n']}/{len(todo)} ({el:.0f} s, {el / state['n']:.1f} s each)", flush=True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, a.jobs)) as ex:
        list(ex.map(one, todo))

    # extract and test the repaired set in the usual layout, then drop replies that changed the specification
    py = sys.executable
    subprocess.run([py, str(HERE / "spec_experiment.py"), "extract", "--model", tag, "--pool", a.pool], check=True)
    ext_new = json.loads((out / "extract.json").read_text(encoding="utf-8"))
    dropped = 0
    for tid, e in ext_new.items():
        if e.get("stage") != "task":
            continue
        orig = json.loads((src / "tasks" / f"{e['name']}.json").read_text(encoding="utf-8"))
        path = out / "tasks" / f"{e['name']}.json"
        kind = json.loads((out / "raw" / f"{tid}.json").read_text(encoding="utf-8")).get("repair_kind", "proof")
        if not spec_kept(orig, json.loads(path.read_text(encoding="utf-8")), kind):
            path.unlink()
            e["stage"], e["why"] = "spec-changed", "requires, signature or an original ensures was changed"
            dropped += 1
    (out / "extract.json").write_text(json.dumps(ext_new, indent=1), encoding="utf-8")
    subprocess.run([py, str(HERE / "spec_experiment.py"), "tests", "--model", tag, "--pool", a.pool], check=True)
    subprocess.run([py, str(HERE / "pool_pick.py"), str(out)], check=True)
    print(f"repair: {tag}: {state['n']} replies, {dropped} dropped for changing the specification, "
          f"{len(list((out / 'grade-in').glob('*.json')))} to grade")
    return 1 if state["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
