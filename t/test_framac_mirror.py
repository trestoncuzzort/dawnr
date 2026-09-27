"""Kernel-level seeded-fault tests for the spec_fun C mirrors (framac track,
2026-09-26; lower_framac.py `_spec_fun_c`'s RECURSIVE MIRRORS note and
`_place_mirrors`).

The lowering change lets a recursive spec_fun reach executable position
through a recursive C mirror `f_c` whose contract is `\\result == f(args)`
plus the spec_fun's own `decreases`, gives every mirror `assigns \\nothing`,
and emits only the mirrors the file calls. Each test below runs Frama-C/WP
through verifiers/framac.py and checks that the kernel still separates right
from wrong programs of the shape the change admits:

  * the real factorialOfLastDigit program verifies;
  * a wrong caller (`+ 1` on the mirror's result, or the wrong argument)
    does not;
  * a mirror whose recursion does not decrease does not (WP's own variant
    goal fails), so termination is checked, not assumed;
  * a mirror whose body disagrees with the logic function does not;
  * a caller with `assigns \\nothing` that calls a mirror verifies (the
    frame clause the mirror now states), and the same caller computing the
    wrong value does not.

Skips (exit 0, printed) when frama-c is not installed. Run one at a time on
a small machine: cd <repo>/t && python3 test_framac_mirror.py
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import harness                                   # noqa: E402
import lower_framac                              # noqa: E402
from verifiers import Outcome                    # noqa: E402
from verifiers import framac                     # noqa: E402

WORK = HERE / "out" / "test_framac_mirror"

FACT = """t 1
gate recursion
task factLast(n: int) returns (fact: int)
  requires n >= 0
  ensures fact == factorial(n % 10)
spec fun factorial(n_v: int): int
  decreases n_v
= if n_v >= 0 then if n_v == 0 then 1 else n_v * factorial(n_v - 1) else 0
{
  var lastDigit: int := n % 10;
  fact := BODY;
}
"""

DIGITS = """t 1
gate recursion
task lastDigitProduct(a: int, b: int) returns (r: int)
  requires a >= 0 and b >= 0
  ensures r == lastDigit(a) * lastDigit(b)
spec fun lastDigit(x: int): int
  decreases 0
= x % 10
{
  r := BODY;
}
"""


def _lower(src: str, body: str, stem: str) -> Path:
    WORK.mkdir(parents=True, exist_ok=True)
    tf = WORK / f"{stem}.t"
    tf.write_text(src.replace("BODY", body), encoding="utf-8")
    task = harness.load(tf)
    cf = WORK / f"{stem}.c"
    cf.write_text(lower_framac.lower(task, task["body"]), encoding="utf-8")
    return cf


def _verify(cf: Path):
    r = framac.verify(cf)
    return r.outcome, [g for g, _ in (r.extras or {}).get("unproved_goals", [])]


FAILURES: list = []


def check(name, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + name + ("" if cond else f": {detail}"))
    if not cond:
        FAILURES.append(name)


def main() -> int:
    if not framac.FRAMAC:
        print("SKIP: frama-c not installed")
        return 0
    real = _lower(FACT, "factorial(lastDigit)", "fact_real")
    out, _ = _verify(real)
    check("recursive mirror: real program verifies", out == Outcome.VERIFIED, out)

    for stem, body in (("fact_plus1", "factorial(lastDigit) + 1"),
                       ("fact_wrongarg", "factorial(lastDigit + 1)")):
        out, _ = _verify(_lower(FACT, body, stem))
        check(f"recursive mirror: seeded fault {stem} is not verified",
              out != Outcome.VERIFIED, out)

    src = real.read_text(encoding="utf-8")
    nodec = WORK / "fact_nodecrease.c"
    nodec.write_text(src.replace("factorial_c((n_v - 1))", "factorial_c(n_v)"),
                     encoding="utf-8")
    out, goals = _verify(nodec)
    check("non-decreasing mirror is not verified", out != Outcome.VERIFIED, out)
    check("its variant goal is among the unproved",
          any(g.endswith("factorial_c_variant") for g in goals), goals)

    wrongm = WORK / "fact_wrongmirror.c"
    wrongm.write_text(re.sub(r"n_v \* factorial_c", "n_v + factorial_c", src),
                      encoding="utf-8")
    out, _ = _verify(wrongm)
    check("mirror disagreeing with the logic function is not verified",
          out != Outcome.VERIFIED, out)

    out, _ = _verify(_lower(DIGITS, "lastDigit(a) * lastDigit(b)", "digits_real"))
    check("assigns \\nothing caller of a mirror verifies",
          out == Outcome.VERIFIED, out)
    out, _ = _verify(_lower(DIGITS, "lastDigit(a) * lastDigit(a)", "digits_wrong"))
    check("same caller with the wrong value is not verified",
          out != Outcome.VERIFIED, out)

    shutil.rmtree(WORK, ignore_errors=True)
    print(f"{len(FAILURES)} failures")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
