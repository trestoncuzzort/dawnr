#!/usr/bin/env python3
"""t/ship.py: prove the C at the width that ships (programme R4b, internal/RESEARCH-2026-10-07-zoom-out.md section 8).

The matrix proves the Frama-C lowering with WP's Typed+nat model: C's `int` read as a mathematical integer, pinned
because t's integers are unbounded. T62 compiled that C and found every disagreement with the interpreter to be
integer width: the shipped `int` is 32 bits. This module proves the same C file at machine width. It uses WP's
`Typed` model with `-wp-rte`, so every signed operation owes a proof that it does not overflow (WP manual, section
1.5, receipt 3fe411d90de6). Each routine reads one of:

- **ships for every int32 input:** every goal, the contract and every overflow guard, is proved;
- **ships within ±2^k:** an overflow guard is open for the full range; the largest power-of-two bound on every int
  input (and on every element of a sequence input, with lengths at most 1000) under which every goal proves is
  searched, k from 4 to 30, and stated as the routine's proved operating envelope;
- **no envelope found:** open even at ±16;
- **not shipped:** the lowering refuses the task, or its contract is open at machine width for another reason.

  python3 t/ship.py t/autonomy --jobs 4 --table SHIP.md
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import tasks_io  # noqa: E402
import tlib  # noqa: E402
from verifiers import framac  # noqa: E402

LEN_BOUND = 1000
_GOAL = re.compile(r"^\[wp\] \[(Timeout|Stepout|Unknown|Failed)\] (\S+)", re.M)
_PROVED = re.compile(r"Proved goals:\s+(\d+)\s*/\s*(\d+)")


def _wp(src: str, work: Path) -> tuple[int, int, list]:
    f = work / "ship.c"
    f.write_text(src, encoding="utf-8")
    steps = framac.FLOAT_STEPS if re.search(r"\bdouble\b", src) else framac.DEFAULT_STEPS
    p = subprocess.run([framac.FRAMAC, "-wp", "-wp-rte", "-wp-model", "Typed", "-wp-prover", "alt-ergo",
                        "-wp-steps", str(steps), "-wp-timeout", str(framac._goal_timeout(steps)), "-wp-cache", "none",
                        "-wp-par", "2", str(f)], capture_output=True, text=True, timeout=600, cwd=str(work))
    out = p.stdout + p.stderr
    m = _PROVED.findall(out)
    if not m:
        raise RuntimeError("no WP summary: " + (out.strip().splitlines() or ["?"])[-1][:200])
    done, total = map(int, m[-1])
    return done, total, sorted({g for _s, g in _GOAL.findall(out)})   # provers finish in any order


def _with_envelope(src: str, task: dict, k: int) -> str:
    """The C file with the routine's contract opened by input bounds: |x| <= 2^k for every int input, every element
    of every sequence input likewise, and sequence lengths at most LEN_BOUND."""
    fn = re.search(r"^(?:int|double|_Bool)\s+\w+_t\(([^)]*)\)\s*\{", src, re.M)
    c_names = {x.strip().rsplit(None, 1)[-1].lstrip("*") for x in fn.group(1).split(",") if x.strip()}
    b = 2 ** k
    reqs = []
    for p in task["params"]:
        n = p["name"]
        if n not in c_names:
            continue
        if p["type"] == "int":
            reqs.append(f"requires -{b} <= {n} <= {b};")
        elif p["type"] in ("seq", "array"):
            reqs.append(f"requires {n}_n <= {LEN_BOUND};")
            reqs.append(f"requires \\forall integer t_sk; 0 <= t_sk < {n}_n ==> -{b} <= {n}[t_sk] <= {b};")
    head = src[:fn.start()]
    i = head.rfind("/*@")
    if i < 0 or not reqs:
        return src
    return src[:i + 3] + "\n  " + "\n  ".join(reqs) + src[i + 3:]


def _bound_candidates(task: dict) -> dict:
    """R4c: for each top-level loop (by its index among the task's top-level `while`s), the ACSL text of every bound
    `v <= w`, `w <= v` or `v <= w + 1` between an int the loop assigns and another int in scope (a parameter, a local,
    a sequence's length, 0) that holds at every loop-head state the interpreter observes (repair.py's R1b states)."""
    import harness
    import interp
    import contract_repair as repair
    harness._set_ctx(task)
    ref = interp.Reference(task)
    states = repair._loop_states(task, ref)
    seqs = [p["name"] for p in task["params"] if p["type"] in ("seq", "array")]
    out = {}
    order = [k for k, st in enumerate(task["body"]) if isinstance(st, dict) and "while" in st]
    for li, k in enumerate(order):
        sts = states.get(k, [])
        if not sts:
            continue
        scope = set(sts[0])
        for st in sts[1:]:
            scope &= set(st)
        ints = [n for n in sorted(scope) if all(isinstance(st[n], int) and not isinstance(st[n], bool) for st in sts)]
        moved = repair._assigned(task["body"][k]["while"]["body"])
        terms = [(n, (lambda st, n=n: st[n])) for n in ints]
        terms += [(f"{s}_n", (lambda st, s=s: len(st[s]))) for s in seqs if s in scope]
        terms.append(("0", lambda st: 0))
        cands = []
        for v in [n for n in ints if n in moved]:
            for w, fw in terms:
                if w == v:
                    continue
                le = all(st[v] <= fw(st) for st in sts)
                if le:
                    cands.append(f"{v} <= {w}")
                elif all(st[v] <= fw(st) + 1 for st in sts):
                    cands.append(f"{v} <= {w} + 1")      # only when the tighter bound does not hold
                if all(fw(st) <= st[v] for st in sts):
                    cands.append(f"{w} <= {v}")
        out[li] = sorted(set(cands))
        out[("acc", li)] = [(v, w) for v in ints if v in moved for w, _f in terms if w not in (v, "0")]
    return out


def _scaled(cands: dict, k: int) -> dict:
    """The candidates with, for the envelope ±2^k, every accumulator bounded by a counter times the bound:
    `-(w * 2^k) <= v <= w * 2^k` (a sum of w terms each within the envelope)."""
    out = {li: list(t) for li, t in cands.items() if not isinstance(li, tuple)}
    b = 2 ** k
    for key, pairs in cands.items():
        if isinstance(key, tuple):
            li = key[1]
            out.setdefault(li, [])
            out[li] += [f"{v} <= {w} * {b}" for v, w in pairs] + [f"-({w} * {b}) <= {v}" for v, w in pairs]
    return out


_LOOP = re.compile(r"/\*@((?:(?!\*/).)*?\bloop\b(?:(?!\*/).)*?)\*/\s*(while|for)\s*\(", re.S)


def _with_invariants(src: str, cands: dict) -> tuple[str, dict]:
    """The C file with each candidate inserted as a named loop invariant `t_bJ` into the annotation of the C loop
    matching its t loop (the lowering's own helper loops, over `__` variables, skipped); and J -> its text."""
    loops = [m for m in _LOOP.finditer(src) if "__" not in m.group(1)]
    named, edits, j = {}, [], 0
    for li, texts in cands.items():
        if li >= len(loops) or not texts:
            continue
        lines = []
        for t in texts:
            j += 1
            named[j] = t
            lines.append(f"loop invariant t_b{j}: {t};")
        edits.append((loops[li].start() + 3, "\n    " + "\n    ".join(lines)))
    for pos, ins in sorted(edits, reverse=True):
        src = src[:pos] + ins + src[pos:]
    return src, named


def _houdini(src: str, cands: dict, work: Path, task: dict | None = None, k: int | None = None):
    """Drop every inferred invariant whose own goal fails, until the rest are proved together (at most six rounds):
    (C text with the survivors, the survivors, the last WP result)."""
    live = {li: list(t) for li, t in cands.items()}
    for _round in range(6):
        text, named = _with_invariants(src, live)
        if k is not None:
            text = _with_envelope(text, task, k)
        done, total, open_goals = _wp(text, work)
        bad = {int(m.group(1)) for g in open_goals for m in [re.search(r"loop_invariant_t_b(\d+)_", g)] if m}
        if not bad:
            return text, named, (done, total, open_goals)
        drop = {named[j] for j in bad}
        live = {li: [t for t in ts if t not in drop] for li, ts in live.items()}
    text, named = _with_invariants(src, live)
    if k is not None:
        text = _with_envelope(text, task, k)
    return text, named, _wp(text, work)


def ship_file(path: str) -> dict:
    res = {"file": path}
    try:
        task = tasks_io.load_task(path)
    except Exception as e:                              # noqa: BLE001
        res.update(name=Path(path).stem, status=f"load-error: {type(e).__name__}")
        return res
    res["name"] = task.get("name", Path(path).stem)
    try:
        src = tlib.lower(task, "framac")
    except NotImplementedError:
        res["status"] = "not shipped: the C lowering refuses it"
        return res
    except Exception as e:                              # noqa: BLE001
        res["status"] = f"not shipped: {type(e).__name__}"
        return res
    with tempfile.TemporaryDirectory(prefix="t-ship-") as d:
        work = Path(d)
        try:
            done, total, open_goals = _wp(src, work)
        except Exception as e:                          # noqa: BLE001
            res["status"] = f"error: {e}"[:200]
            return res
        res["goals"] = f"{done}/{total}"
        if done == total:
            res["status"] = "ships for every int32 input"
            return res
        rte = [g for g in open_goals if "_rte_" in g]
        res["open"] = open_goals[:6]
        if not rte:
            res["status"] = "not shipped: the contract is open at machine width"
            return res
        # R4c: bounds inferred from the observed loop states, kept by Houdini, may close the overflow guards
        try:
            cands = _bound_candidates(task)
        except Exception:                               # noqa: BLE001
            cands = {}
        base = {li: t for li, t in cands.items() if not isinstance(li, tuple)}
        if any(base.values()):
            try:
                text, named, (d1, t1, _o1) = _houdini(src, base, work)
            except Exception:                           # noqa: BLE001
                named, d1, t1 = {}, 0, 1
            if named and d1 == t1:
                res["status"] = "ships for every int32 input"
                res["invariants"] = sorted(named.values())
                return res
            if named:
                res["invariants"] = sorted(named.values())
        lo, hi, best = 4, 30, None
        while lo <= hi:                                 # the largest k whose envelope proves every goal
            mid = (lo + hi) // 2
            try:
                if any(v for v in cands.values()):
                    _txt, named2, (d2, t2, _o) = _houdini(src, _scaled(cands, mid), work, task, mid)
                else:
                    d2, t2, _o = _wp(_with_envelope(src, task, mid), work)
                    named2 = {}
            except Exception:                           # noqa: BLE001
                d2, t2, named2 = 0, 1, {}
            if d2 == t2 and named2:
                res["invariants"] = sorted(named2.values())
            if d2 == t2:
                best, lo = mid, mid + 1
            else:
                hi = mid - 1
        if best is None:
            res["status"] = "no envelope found (open even at ±2^4)"
        else:
            res["status"] = f"ships within ±2^{best}"
            res["envelope"] = best
    return res


def table(results: list) -> str:
    def count(pred):
        return sum(1 for r in results if pred(r.get("status", "")))
    lines = ["# Shipped at machine width", "",
             "Each routine's C lowering proved with WP's machine-integer model and `-wp-rte`, so every signed operation "
             "owes a no-overflow proof (t/ship.py). Where an overflow guard is open for the full range, the largest "
             f"bound ±2^k on every int input and sequence element (lengths at most {LEN_BOUND}) under which every goal "
             "proves is the routine's proved operating envelope.", "",
             f"- ships for every int32 input: {count(lambda s: s.startswith('ships for every'))}",
             f"- ships within an envelope: {count(lambda s: s.startswith('ships within'))}",
             f"- no envelope found: {count(lambda s: s.startswith('no envelope'))}",
             f"- contract open at machine width: {count(lambda s: 'contract is open' in s)}",
             f"- not shipped (the C lowering refuses it): {count(lambda s: 'refuses' in s)}", "",
             "| task | status | goals at full width (before inference) | bounds inferred and proved (R4c) | open goals at full width |",
             "|---|---|---|---|---|"]
    for r in sorted(results, key=lambda r: r["name"]):
        inv = "; ".join(r.get("invariants", []))
        lines.append(f"| {r['name']} | {r['status']} | {r.get('goals', '')} | {inv} | {', '.join(r.get('open', []))} |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="ship.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("target", metavar="FILE|DIR")
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--table", metavar="PATH")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    t = Path(args.target)
    files = [str(p) for p in sorted(t.iterdir()) if p.suffix in (".t", ".json")] if t.is_dir() else [str(t)]
    if args.jobs > 1:
        with ProcessPoolExecutor(max_workers=args.jobs) as ex:
            results = list(ex.map(ship_file, files))
    else:
        results = [ship_file(f) for f in files]
    for r in results:
        print(json.dumps(r, sort_keys=True) if args.json else f"{r['name']}: {r['status']}")
    if args.table:
        Path(args.table).write_text(table(results), encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
