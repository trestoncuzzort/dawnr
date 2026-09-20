#!/usr/bin/env python3
"""The 1,038 stdin-shaped problems `nl_stdin.py` measured, as a usable pool.

`t/nl_stdin.py` built the signature extractor and measured the result:
**3,058 of 20,509 stdin-shaped problems accepted, 1,038 of them in the pool**
(APPS 480, CodeContests 558, `t/COVERAGE-nl-stdin.md:19-21`). Nothing ever
imported it. `spec_experiment.pool()` never called it, so those 1,038 existed as
a measurement and nothing else, while `LIMITS.md` said the corpus was exhausted.

**Wiring alone is not enough, and that is what this module is for.** A pool entry
needs a *callable* reference solution: `spec_check.reference()` execs the record's
code and looks up `entry["fn"]`, and `check_task` returns `no reference` when it
is not callable. `loop_dataset.positive_rejection` then returns
`spec-not-agrees`, so a problem with no callable reference **can never become a
training positive** no matter how well a model answers it. A stdin solution is a
script, not a function: it reads `input()` and prints. `nl_stdin.in_pool` means
"the first Python solution's constructs are inside t's fragment", which is a
different claim.

So this module does the missing half: it renders a t-typed argument list back
into the exact stdin text the problem's own grammar rule describes, runs the
solution against it with stdin and stdout redirected, and reads the single
integer back. That is the inverse of `nl_stdin.classify_lines` +
`nl_stdin.build_args`, and the round-trip is tested both ways in
`t/test_nl_stdin_pool.py`.

    python3 t/nl_stdin_pool.py --limit 50      # report what would be admitted
"""
from __future__ import annotations

import argparse
import functools
import hashlib
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import nl_stdin                                                 # noqa: E402

# Clear of MBPP (< 100000), HumanEval (100000+) and APPS (200000+), and split so
# the two sources cannot collide with each other either.
STDIN_APPS_BASE = 300000
STDIN_CC_BASE = 1000000
# CodeContests names its problems ("1575_A. Another Sorting Problem"), so there
# is no own-id integer to add to the base the way APPS has. The id is therefore
# derived from that name by hash, over a span wide enough that a collision is
# rare, and a collision REFUSES both problems rather than moving one:
#
#   an id must be a function of the problem and nothing else. `positive_rejection`
#   rejects a sample whose recorded `task_id` does not match the pool's, so an id
#   that depends on which problems were walked, or in what order, silently
#   invalidates every result measured under an earlier run. That is what an
#   incrementing counter does, and it is why the pool-mismatch gate then looks
#   like the thing in the way.
#
# 558 admissible CodeContests problems over this span put the chance of any
# collision at about 1.5%, and it is reported rather than resolved.
STDIN_CC_SPAN = 10_000_000
POINTS_PER_PROBLEM = 8


def render_stdin(rule: str, args: list) -> str:
    """A t-typed args list back into the stdin text its grammar rule describes.

    The exact inverse of `nl_stdin.build_args`, and it needs the RULE LABEL
    because `b` and `c` produce identical args (`[int, seq]`) from different
    layouts: `b` puts the sequence on one line, `c` puts one element per line.
    Reading the args alone cannot tell them apart, which is why the label is
    carried through the pool entry rather than recomputed.
    """
    if rule.startswith("e:"):                    # a one-test-case wrapper
        return "1\n" + render_stdin(rule[2:], args)
    if re.fullmatch(r"a\(k=\d+\)", rule):        # k integers on one line
        return " ".join(str(v) for _kind, v in args) + "\n"
    if rule == "b":                              # n, then n integers on one line
        return f"{args[0][1]}\n" + " ".join(str(v) for v in args[1][1]) + "\n"
    if rule == "c":                              # n, then one integer per line
        return f"{args[0][1]}\n" + "".join(f"{v}\n" for v in args[1][1])
    if rule == "d":                              # "n m", then n integers
        return (f"{args[0][1]} {args[1][1]}\n"
                + " ".join(str(v) for v in args[2][1]) + "\n")
    raise ValueError(f"no renderer for grammar rule {rule!r}")


def callable_source(code: str, rule: str, fn: str) -> str:
    """Solution script -> source text defining `fn(*args)`.

    Written as source rather than a closure because `spec_check.reference()`
    execs the record's `code` string and looks the name up in the resulting
    globals; a function object has no way into that path.

    The solution runs with a fresh `__main__`-shaped global namespace every
    call, so a script guarded by `if __name__ == "__main__":` still executes and
    module-level state cannot leak between draws. `spec_check` already wraps the
    call in a 5-second SIGALRM, so a solution that loops forever is that
    caller's problem, not this one's.
    """
    return (
        f"_T_SOLUTION = {code!r}\n"
        f"_T_RULE = {rule!r}\n"
        "def " + fn + "(*_t_args):\n"
        "    import io as _io, sys as _sys\n"
        "    import nl_stdin_pool as _p\n"
        "    _kinds = []\n"
        "    for _a in _t_args:\n"
        "        _kinds.append(['seq', list(_a)] if isinstance(_a, (list, tuple))\n"
        "                      else ['int', _a])\n"
        "    _text = _p.render_stdin(_T_RULE, _kinds)\n"
        "    _si, _so = _sys.stdin, _sys.stdout\n"
        "    _sys.stdin, _sys.stdout = _io.StringIO(_text), _io.StringIO()\n"
        "    try:\n"
        "        try:\n"
        "            exec(compile(_T_SOLUTION, '<stdin-solution>', 'exec'),\n"
        "                 {'__name__': '__main__'})\n"
        "        except SystemExit:\n"
        "            pass\n"
        "        _out = _sys.stdout.getvalue()\n"
        "    finally:\n"
        "        _sys.stdin, _sys.stdout = _si, _so\n"
        "    _toks = _out.split()\n"
        "    if len(_toks) != 1:\n"
        "        raise ValueError('solution printed %d tokens, not 1' % len(_toks))\n"
        "    return int(_toks[0])\n"
    )


def _fn_name(source: str, pid: str) -> str:
    """A stable identifier-shaped name. The problem has none; stdin scripts are anonymous."""
    tail = re.sub(r"\W", "_", pid.split(":")[-1])
    return f"{source.lower()}_stdin_{tail}"


def _why_refused(source: str, ex: dict) -> str:
    """Why a problem nl_stdin admitted did not become a pool entry."""
    raw = ex["id"].split(":")[-1]
    if stable_id(source, 0, raw) is None:
        return "no usable id"
    try:
        render_stdin(ex["grammar_rule"], ex["points"][0]["args"])
    except (ValueError, IndexError, KeyError):
        return f"no renderer for rule {ex.get('grammar_rule')!r}"
    return "other"


def stable_id(source: str, base: int, raw_id: str) -> int | None:
    """base + the problem's OWN id, or a hash of its name when it has no number."""
    try:
        return base + int(raw_id)
    except (TypeError, ValueError):
        pass
    if source != "CC" or not raw_id:
        return None
    digest = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()[:12]
    return base + int(digest, 16) % STDIN_CC_SPAN


def _entry(source: str, pid: str, base: int, raw_id: str, result: dict,
           code: str, text: str) -> tuple[int, dict] | None:
    tid = stable_id(source, base, raw_id)
    if tid is None:
        return None
    fn = _fn_name(source, pid)
    rule = result["grammar_rule"]
    try:                          # refuse now rather than at grading time
        render_stdin(rule, result["points"][0]["args"])
    except (ValueError, IndexError, KeyError):
        return None
    # Capped at 8 the way `spec_experiment.apps_pool` caps its own points
    # (`list(zip(ins, outs))[:8]`), and for the same reason: the points are
    # evidence for spec_check to draw from, not the corpus itself. CodeContests
    # ships `generated_tests` in the hundreds -- measured median 87 per problem,
    # max 339, 76,177 across the pool -- and carrying them all makes every
    # consumer pay for evidence the eighth draw already gave. The ACCEPTANCE
    # decision still reads every sample the problem has, in nl_stdin, so this
    # narrows what is stored and not what was checked.
    points = [{"ok": True, "fn": fn, "args": p["args"], "expected": p["expected"]}
              for p in result["points"][:POINTS_PER_PROBLEM]]
    tests = [f"assert {fn}({', '.join(repr(v) for _k, v in p['args'])}) == {p['expected'][1]}"
             for p in points[:3]]
    return tid, {"rec": {"task_id": tid, "text": text.strip(),
                         "code": callable_source(code, rule, fn),
                         "test_list": tests, "source": f"{source}-stdin/{raw_id}",
                         "grammar_rule": rule},
                 "points": points, "fn": fn}


@functools.lru_cache(maxsize=4)
def stdin_pool(limit: int = 0) -> dict[int, dict]:
    """Every stdin-shaped problem nl_stdin admits, as pool entries with a callable.

    **This walk costs about 2.5 minutes**, against 0.6 s for all of pool v5,
    because acceptance requires classifying every sample of every one of the
    20,509 stdin-shaped problems. It is memoised for the process and no
    further.

    There is deliberately no disk cache. Hugging Face `datasets` is the closest
    prior art -- it fingerprints a derived dataset by hashing the source files
    and each transform (https://huggingface.co/docs/datasets/en/about_cache),
    and its own documentation warns that an input whose order is not
    deterministic across sessions produces a fingerprint that is not either.
    Two things make that shape wrong here: `nl/data` is rsynced between the
    desktop and the lab, so mtimes move while content does not, and a pool that
    is silently one corpus behind is exactly the failure this repository is
    built to prevent -- every number downstream would still be printed, just
    about a different pool. A cache that cannot outlive the process cannot go
    stale, so that is the one taken."""
    out: dict[int, dict] = {}
    collisions: list[tuple[str, str]] = []
    refused: dict[str, int] = {}
    for source, base, walk in (("APPS", STDIN_APPS_BASE, nl_stdin.process_apps),
                               ("CC", STDIN_CC_BASE, nl_stdin.process_codecontests)):
        try:
            _records, examples = walk(limit or None)
        except Exception:                                       # noqa: BLE001
            continue                    # a corpus that is not on disk is not an error
        for ex in examples:
            raw = ex["id"].split(":")[-1]
            made = _entry(source, ex["id"], base, raw, ex,
                          ex.get("solution") or "", ex.get("text") or "")
            if not made:
                refused[_why_refused(source, ex)] = refused.get(_why_refused(source, ex), 0) + 1
                continue
            tid, entry = made
            if tid in out:
                # Two problems, one id. Taking either one means a result recorded
                # against it can mean the other, so both go.
                if out[tid]["rec"]["source"] != entry["rec"]["source"]:
                    collisions.append((out[tid]["rec"]["source"], entry["rec"]["source"]))
                    del out[tid]
                continue
            out[tid] = entry
            if limit and len(out) >= limit:
                break
    stdin_pool.refused = dict(refused)          # for the report; nl_stdin admitted these
    if collisions:
        print(f"stdin pool: {len(collisions)} id collision(s), both sides dropped: "
              + ", ".join(f"{a} / {b}" for a, b in collisions[:5]), file=sys.stderr)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    pool = stdin_pool(a.limit)
    print(f"stdin pool: {len(pool)} entries")
    by_source: dict[str, int] = {}
    points = [len(e["points"]) for e in pool.values()]
    for e in pool.values():
        src = e["rec"]["source"].split("-")[0]
        by_source[src] = by_source.get(src, 0) + 1
    for src, n in sorted(by_source.items()):
        print(f"  from {src}: {n}")
    for why, n in sorted(getattr(stdin_pool, "refused", {}).items(), key=lambda kv: -kv[1]):
        print(f"  refused: {why}: {n}")
    if points:
        points.sort()
        print(f"  points per problem: min {points[0]}, median {points[len(points)//2]}, "
              f"max {points[-1]}, total {sum(points)}")
    rules: dict[str, int] = {}
    for e in pool.values():
        r = e["rec"]["grammar_rule"]
        rules[r] = rules.get(r, 0) + 1
    for r, n in sorted(rules.items(), key=lambda kv: -kv[1]):
        print(f"  {r:16} {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
