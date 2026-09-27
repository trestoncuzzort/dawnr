"""Seeded-fault tests for two seq-building shapes the Frama-C lowering used
to abstain on (framac track, 2026-09-26; lower_framac.py
`_exact_concat_lines`, the `+` cases of `_seq_len_render`/`_seq_at_render`,
and `_ret_capacity`'s LITERAL-ONLY WRITES source):

  * a concatenation of variables, slices and literals assigned to an
    EXACT-length return (replaceLastElement, removeKthElement);
  * a seq return written only by literals under a branch (da0054, da0488);
  * an append-built local folded into the return, whose `:= []` now
    initializes the length local (vt0029 `ones`), and whose executable
    `len` reads that length local rather than the buffer capacity (vt0362
    `spacing`);
  * and, in the twin's certificate, an `ite` or a short-circuit `and`/`or`
    resolved branch-free (clamp, is_equal_to_sum_even), which used to reach
    the certificate as a C conditional whose dead arm doomed a smoke goal.

Lowering-level checks always run. Kernel checks run Frama-C/WP through
verifiers/framac.py when frama-c is installed (printed SKIP otherwise): each
real program verifies, and each seeded fault of the same shape (wrong piece,
swapped pieces, off-by-one slice, swapped branch literals) does not.

Run as: cd <repo>/t && python3 test_framac_seqbuild.py
"""
from __future__ import annotations

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

WORK = HERE / "out" / "test_framac_seqbuild"

REPLACE_LAST = """t 1
task replaceLast(first: seq, second: seq) returns (result: seq)
  requires len(first) > 0
  ensures len(result) == len(first) - 1 + len(second)
  ensures forall i in [0, len(first) - 1) . result[i] == first[i]
  ensures forall j in [len(first) - 1, len(result)) . result[j] == second[j - len(first) + 1]
{
  result := BODY;
}
"""

REMOVE_KTH = """t 1
task removeKth(list: seq, k: int) returns (new_list: seq)
  requires len(list) > 0
  requires 0 < k
  requires k < len(list)
  ensures new_list == list[0..k - 1] + list[k..len(list)]
{
  new_list := BODY;
}
"""

LITERALS = """t 1
task yesNo(d: int, t_v: int) returns (result: seq)
  ensures d <= t_v ==> result == [89, 101, 115]
  ensures not (d <= t_v) ==> result == [78, 111]
{
  if d <= t_v {
    result := YES;
  } else {
    result := NO;
  }
}
"""

# The fold of an append-built local into the return (`_fold_local_append_
# into_ret`) now keeps the local's `:= []` as `result := []`, so the
# capacity length local starts at 0 (vericoding vt0029 `ones`).
ONES = """t 1
task onesT(n: int) returns (result: seq)
  requires n >= 0
  ensures len(result) == n
  ensures forall i in [0, n) . result[i] == 1
{
  var v: seq := [];
  var i: int := 0;
  while i < n
    invariant i <= n
    invariant len(v) == i
    invariant forall k in [0, i) . v[k] == 1
    invariant i >= 0
    decreases n - i
  {
    STEP
    i := i + 1;
  }
  result := v;
}
"""

# Executable `len` of a capacity-tracked return reads its length local, not
# the buffer capacity (`_EXEC_SEQ_LEN`; vericoding vt0362 `spacing`, whose
# guard `len(y) < len(x)` used to lower to `result_n < x_n`).
SPACING = """t 1
task spacingT(x: seq) returns (result: seq)
  ensures len(result) == len(x)
  ensures forall i in [0, len(x)) . result[i] > 0
{
  var y: seq := [];
  while GUARD
    invariant len(y) <= len(x)
    invariant forall i_v in [0, len(y)) . y[i_v] > 0
    decreases len(x) - len(y)
  {
    y := y + [VAL];
  }
  result := y;
}
"""

FAILURES: list = []


def check(name, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + name + ("" if cond else f": {detail}"))
    if not cond:
        FAILURES.append(name)


def _write(src: str, stem: str) -> Path:
    WORK.mkdir(parents=True, exist_ok=True)
    tf = WORK / f"{stem}.t"
    tf.write_text(src, encoding="utf-8")
    task = harness.load(tf)
    cf = WORK / f"{stem}.c"
    cf.write_text(lower_framac.lower(task, task["body"]), encoding="utf-8")
    return cf


def lowering_checks() -> None:
    c = _write(REPLACE_LAST.replace("BODY", "first[0..len(first) - 1] + second"),
               "rl_real").read_text(encoding="utf-8")
    check("exact concat lowers (no abstain)", "_t(" in c, c[:200])
    check("exact concat asserts the pieces fill the buffer",
          "== result_n; */" in c, c)
    check("each piece's loop assigns only its own range",
          c.count("loop assigns __k, result[") == 2, c)
    c = _write(REMOVE_KTH.replace("BODY", "list[0..k - 1] + list[k..len(list)]"),
               "rk_real").read_text(encoding="utf-8")
    check("concat renders in ACSL term position",
          "new_list_n == ((((k - 1)) - (0))) + (((list_n) - (k)))" in
          c.replace("(((((k", "((((k"), c[:600])
    try:
        env = {"s": "seq", "r": "seq"}
        lower_framac._exact_concat_lines(
            "r", {"op": "+", "args": [{"var": "s"}, {"var": "r"}]},
            lower_framac.Ctx(env, {}), "  ", {}, "t")
        check("in-place concat abstains", False, "lowered")
    except NotImplementedError as e:
        check("in-place concat abstains by name", "own target" in str(e), str(e))
    c = _write(LITERALS.replace("YES", "[89, 101, 115]").replace("NO", "[78, 111]"),
               "lit_real").read_text(encoding="utf-8")
    check("literal-only writes get a capacity of the longest literal",
          "requires result_n == 3;" in c, c[:400])
    c = _write(ONES.replace("STEP", "v := v + [1];"), "ones_real").read_text(
        encoding="utf-8")
    check("folded local's `:= []` initializes the length local",
          "result_len = 0;" in c, c)
    c = _write(SPACING.replace("GUARD", "len(y) < len(x)").replace("VAL", "1"),
               "spacing_real").read_text(encoding="utf-8")
    check("executable len of the tracked return reads its length local",
          "while ((result_len < x_n))" in c, c)


def kernel_checks() -> None:
    if not framac.FRAMAC:
        print("SKIP kernel checks: frama-c not installed")
        return
    cases = [
        (REPLACE_LAST, "first[0..len(first) - 1] + second", True, "rl_real"),
        (REPLACE_LAST, "first[0..len(first) - 1] + first", False, "rl_wrongpiece"),
        (REPLACE_LAST, "second + first[0..len(first) - 1]", False, "rl_swapped"),
        (REMOVE_KTH, "list[0..k - 1] + list[k..len(list)]", True, "rk_real"),
        (REMOVE_KTH, "list[0..k] + list[k + 1..len(list)]", False, "rk_offbyone"),
    ]
    for src, body, want, stem in cases:
        r = framac.verify(_write(src.replace("BODY", body), stem))
        ok = (r.outcome == Outcome.VERIFIED) if want else (r.outcome != Outcome.VERIFIED)
        check(f"{stem}: {'verifies' if want else 'is not verified'}", ok, r.outcome)
    for guard, val, want, stem in (("len(y) < len(x)", "1", True, "spacing_real"),
                                   ("len(y) < len(x)", "0", False, "spacing_zero"),
                                   ("len(y) + 1 < len(x)", "1", False,
                                    "spacing_short")):
        r = framac.verify(_write(SPACING.replace("GUARD", guard)
                                 .replace("VAL", val), stem))
        ok = (r.outcome == Outcome.VERIFIED) if want else (r.outcome != Outcome.VERIFIED)
        check(f"{stem}: {'verifies' if want else 'is not verified'}", ok, r.outcome)
    for body, want, stem in (("v := v + [1];", True, "ones_real"),
                             ("v := v + [2];", False, "ones_wrongval"),
                             ("v := v + [1, 1];", False, "ones_twice")):
        r = framac.verify(_write(ONES.replace("STEP", body), stem))
        ok = (r.outcome == Outcome.VERIFIED) if want else (r.outcome != Outcome.VERIFIED)
        check(f"{stem}: {'verifies' if want else 'is not verified'}", ok, r.outcome)
    for yes, no, want, stem in (("[89, 101, 115]", "[78, 111]", True, "lit_real"),
                                ("[78, 111]", "[89, 101, 115]", False, "lit_swapped"),
                                ("[89, 101]", "[78, 111]", False, "lit_short")):
        r = framac.verify(_write(LITERALS.replace("YES", yes).replace("NO", no), stem))
        ok = (r.outcome == Outcome.VERIFIED) if want else (r.outcome != Outcome.VERIFIED)
        check(f"{stem}: {'verifies' if want else 'is not verified'}", ok, r.outcome)


CLAMP = """t 1
task clampT(v: int, lower: int, upper: int) returns (result: int)
  requires lower < upper
  ensures lower <= result
  ensures result <= upper
  ensures v < lower ==> result == lower
  ensures lower <= v and v <= upper ==> result == v
  ensures upper < v ==> result == upper
{
  result := if v < lower then lower else if upper < v then upper else v;
}
"""

EVEN8 = """t 1
task evenAtLeast8(n: int) returns (b: bool)
  ensures b == (n % 2 == 0 and n >= 8)
{
  b := n % 2 == 0 and n >= 8;
}
"""


def _twin(src: str, stem: str) -> Path:
    WORK.mkdir(parents=True, exist_ok=True)
    tf = WORK / f"{stem}.t"
    tf.write_text(src, encoding="utf-8")
    task = harness.load(tf)
    tb, _op, w = harness.twin_cached(task)
    cf = WORK / f"{stem}_twin.c"
    cf.write_text(lower_framac.lower(task, tb, witness=w), encoding="utf-8")
    return cf


def certificate_checks(kernel: bool) -> None:
    """Branch-free `ite` and short-circuit `and`/`or` in the certificate
    replay (`_cert_cexpr`, 2026-09-26): the decision is asserted and only
    the taken arm is rendered, so no C `?:`/`&&` reaches the certificate.
    Kernel: the twin is refuted; the same certificate with one decision
    assert flipped is not."""
    for src, stem in ((CLAMP, "clamp"), (EVEN8, "even8")):
        cf = _twin(src, stem)
        text = cf.read_text(encoding="utf-8")
        cert = text[text.index("void t_certificate"):]
        check(f"{stem}: certificate has no C conditional",
              "?" not in cert and "&&" not in cert.split("t_refutation")[0],
              cert)
        if not kernel:
            continue
        r = framac.verify(cf)
        check(f"{stem}: twin is refuted", r.outcome == Outcome.REFUTED, r.outcome)
        # Flip the LAST decision assert of the certificate (a definedness
        # assert such as `(2) != 0` is not a decision), inside the
        # certificate function only: the twin function has asserts too.
        lines = cert.splitlines()
        k = max(i for i, ln in enumerate(lines)
                if ln.strip().startswith("/*@ assert (")
                and "t_refutation" not in ln and ") != 0; */" not in ln)
        body = lines[k].strip()[len("/*@ assert "):-len("; */")]
        flipped = (body[2:-1] if body.startswith("(!") else f"(!{body})")
        lines[k] = lines[k].replace(body, flipped)
        bad = WORK / f"{stem}_twin_flipped.c"
        bad.write_text(text[:text.index("void t_certificate")] + "\n".join(lines),
                       encoding="utf-8")
        r = framac.verify(bad)
        check(f"{stem}: flipped decision is not a refutation",
              r.outcome != Outcome.REFUTED, r.outcome)


def main() -> int:
    lowering_checks()
    kernel = "--no-kernel" not in sys.argv and bool(framac.FRAMAC)
    certificate_checks(kernel)
    if "--no-kernel" not in sys.argv:
        kernel_checks()
    shutil.rmtree(WORK, ignore_errors=True)
    print(f"{len(FAILURES)} failures")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
