#!/usr/bin/env python3
"""test_exits_desugar.py: the rewrite of `break` and `continue` away (SPEC.md "Early exits (v1)", PREDICT T44,
`tshape.desugar_exits`), checked against the interpreter: on every input of a small domain, the rewritten body
computes what the original computes (the same return value, or undefined where it is undefined), for the committed
tasks, their twins and programs written to reach each case of the rewrite. Standard library only, no kernel runs."""
from __future__ import annotations

import itertools
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import check_wf  # noqa: E402
import harness  # noqa: E402
import interp  # noqa: E402
import surface  # noqa: E402
import tasks_io  # noqa: E402
import tshape  # noqa: E402

CHECKS = 0


def ok(cond, what):
    global CHECKS
    CHECKS += 1
    if not cond:
        print("FAIL:", what)
        sys.exit(1)


def _exits(x) -> bool:
    if isinstance(x, dict):
        return "break" in x or "continue" in x or any(_exits(v) for v in x.values())
    return isinstance(x, list) and any(_exits(v) for v in x)


SEQS = [tuple(p) for n in range(4) for p in itertools.product((-1, 0, 1, 2), repeat=n)]
INTS = list(range(-2, 4))


def _inputs(task: dict):
    cols = []
    for p in task["params"]:
        cols.append(SEQS if p["type"] == "seq" else INTS if p["type"] == "int" else (False, True))
    for vals in itertools.product(*cols):
        yield {p["name"]: v for p, v in zip(task["params"], vals)}


def _run(task: dict, body: list, env: dict):
    e = dict(env)
    try:
        interp.exec_body(body, e, interp.funs_of(task, body), interp.St())
    except interp.Undef:
        return ("undefined",)
    except interp.Budget:
        return ("budget",)
    ret = task["returns"][0]["name"]
    return ("value", e.get(ret, "unassigned"))


def same_everywhere(task: dict, body: list, what: str) -> list:
    new = tshape.desugar_exits(task, body)[1]
    ok(not _exits(new), f"{what}: no break or continue left")
    ok(check_wf.check_wf({**task, "body": new}) == [], f"{what}: the rewrite is well-formed")
    n = 0
    for env in _inputs(task):
        a, b = _run(task, body, env), _run(task, new, env)
        if a != b:
            ok(False, f"{what}: at {env} the original gives {a}, the rewrite {b}")
        n += 1
    ok(n > 0, f"{what}: compared on {n} inputs")
    return new


def test_committed_tasks_and_twins():
    for name in ("index_of", "find_zero", "count_evens_skip"):
        task = tasks_io.load_task(str(HERE / "tasks" / f"{name}.t"))
        same_everywhere(task, task["body"], name)
        twin, op, _w = harness.twin_for(task)
        ok(twin is not None, f"{name} has a twin")
        same_everywhere(task, twin, f"{name}'s twin ({op})")


def test_shapes():
    new = tshape.desugar_exits(*_parsed(INDEX_OF))[1]
    text = surface.print_task({**_parsed(INDEX_OF)[0], "body": new})
    ok("return i;" in text and "break" not in text, "a break before `r := i` becomes `return i`")
    task, body = _parsed(SKIP)
    text = surface.print_task({**task, "body": tshape.desugar_exits(task, body)[1]})
    ok("continue" not in text and text.count("i := i + 1;") == 2, "a continue's rest moves into the other branch")


INDEX_OF = """t 1
task f(s: seq, x: int) returns (r: int)
  ensures true
{
  var i: int := 0;
  while i < len(s)
    invariant 0 <= i and i <= len(s)
    decreases len(s) - i
  {
    if s[i] == x {
      break;
    }
    i := i + 1;
  }
  r := i;
}
"""

SKIP = """t 1
task f(s: seq) returns (c: int)
  ensures true
{
  c := 0;
  var i: int := 0;
  while i < len(s)
    invariant 0 <= i and i <= len(s)
    decreases len(s) - i
  {
    if s[i] < 0 {
      i := i + 1;
      continue;
    }
    c := c + s[i];
    i := i + 1;
  }
}
"""

PROGRAMS = {
    # a continue under two ifs, a break under an else, both in one loop
    "nested": """t 1
task f(s: seq, x: int) returns (r: int)
  ensures true
{
  r := 0;
  var i: int := 0;
  while i < len(s)
    invariant 0 <= i and i <= len(s)
    decreases len(s) - i
  {
    if s[i] > 0 {
      if s[i] == x {
        i := i + 1;
        continue;
      }
      r := r + s[i];
    } else {
      if s[i] < 0 {
        break;
      }
      r := r - 1;
    }
    i := i + 1;
  }
  r := r * 2;
}
""",
    # two loops in a row, each with a break: the first one's continuation holds the second loop
    "two_loops": """t 1
task f(s: seq, x: int) returns (r: int)
  ensures true
{
  var i: int := 0;
  while i < len(s)
    invariant 0 <= i and i <= len(s)
    decreases len(s) - i
  {
    if s[i] == x {
      break;
    }
    i := i + 1;
  }
  var j: int := i;
  while j < len(s)
    invariant i <= j and j <= len(s)
    decreases len(s) - j
  {
    if s[j] != x {
      break;
    }
    j := j + 1;
  }
  r := j - i;
}
""",
    # a loop inside an if, its break's continuation the rest of the branch and then the rest of the task
    "loop_in_if": """t 1
task f(s: seq, x: int) returns (r: int)
  ensures true
{
  r := -1;
  if x > 0 {
    var i: int := 0;
    while true
      invariant 0 <= i and i <= len(s)
      decreases len(s) - i
    {
      if i == len(s) {
        break;
      }
      if s[i] == x {
        r := i;
        break;
      }
      i := i + 1;
    }
    r := r + 10;
  }
  r := r + 1;
}
""",
    # a nested loop whose break is followed, in the outer body, by a return: its continuation is known
    "inner_then_return": """t 1
task f(s: seq) returns (r: int)
  ensures true
{
  r := 0;
  var i: int := 0;
  while i < len(s)
    invariant 0 <= i and i <= len(s)
    decreases len(s) - i
  {
    if s[i] == 2 {
      var j: int := 0;
      while j < len(s)
        invariant 0 <= j and j <= len(s)
        decreases len(s) - j
      {
        if s[j] == 1 {
          break;
        }
        j := j + 1;
      }
      return j;
    }
    i := i + 1;
  }
}
""",
    # a continue and a return in one loop, and a loop with no exit after it
    "continue_return": """t 1
task f(s: seq) returns (r: int)
  ensures true
{
  r := 0;
  var i: int := 0;
  while i < len(s)
    invariant 0 <= i and i <= len(s)
    decreases len(s) - i
  {
    if s[i] == 0 {
      i := i + 1;
      continue;
    }
    if s[i] == 2 {
      return i;
    }
    r := r + s[i];
    i := i + 1;
  }
  var k: int := 0;
  while k < 2
    invariant 0 <= k and k <= 2
    decreases 2 - k
  {
    r := r + 1;
    k := k + 1;
  }
}
""",
}


def _parsed(src: str):
    task = surface.parse(src)
    ok(check_wf.check_wf(task) == [], f"the program is well-formed: {check_wf.check_wf(task)}")
    return task, task["body"]


def test_programs():
    for name, src in PROGRAMS.items():
        task, body = _parsed(src)
        same_everywhere(task, body, name)


def test_refused_by_name():
    # a break in a loop nested in another loop's body, the rest of that body not ending in return
    src = """t 1
task f(s: seq) returns (r: int)
  ensures true
{
  r := 0;
  var i: int := 0;
  while i < len(s)
    invariant 0 <= i and i <= len(s)
    decreases len(s) - i
  {
    var j: int := 0;
    while j < len(s)
      invariant 0 <= j and j <= len(s)
      decreases len(s) - j
    {
      if s[j] == 1 {
        break;
      }
      j := j + 1;
    }
    r := r + j;
    i := i + 1;
  }
}
"""
    task, body = _parsed(src)
    try:
        tshape.desugar_exits(task, body)
        ok(False, "a nested loop's break refuses")
    except NotImplementedError as e:
        ok("nested in another loop's body" in str(e), f"refused by name: {e}")


def test_untouched_without_exits():
    task = tasks_io.load_task(str(HERE / "tasks" / "first_even.t"))
    t2, b2 = tshape.desugar_exits(task, task["body"])
    ok(t2 is task and b2 is task["body"], "a body without break or continue is returned as is")
    task = tasks_io.load_task(str(HERE / "tasks" / "index_of.t"))
    t2, b2 = tshape.desugar_exits(task, task["body"])
    ok(t2["body"] is b2 and b2 is not task["body"], "the real body stays the task's own body")
    twin = harness.twin_for(task)[0]
    t3, b3 = tshape.desugar_exits(task, twin)
    ok(t3["body"] is not b3 and not _exits(t3["body"]), "a twin's rewrite keeps the real body apart, rewritten too")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: ok")
    print(f"{CHECKS} checks")
