#!/usr/bin/env python3
"""boundary_probe.py: grade the seven lowerings against SPEC.md's INTEGER
and SEQUENCE models, by construction rather than by consensus.

WHY THIS IS NOT fuzz_lower.py. That file's strongest instrument is
cross-kernel disagreement, which cannot see a bias all seven lowerings
share: seven kernels that mistranslate the same construct the same way agree,
and the table is green. The integer-width unsoundness (SPEC.md: "mathematical
integers, unbounded, no overflow"; WP's default model handed every C `int`
`is_sint32`, so `x <= 2^31-1` was granted for free) surfaced only because
lower_framac.py happened to be the odd one out, and lower_spark.py's
`array (Positive range <>)` gave `len(s) <= 2^31-1` the same way. Both were
repaired 2026-09-01. This file re-checks the repair WITHOUT TRUSTING IT and
looks for the same disease anywhere else.

THE DISCRIMINATION PRINCIPLE. Every task here has a truth value that DIFFERS
between SPEC.md's unbounded integers and a machine-integer model:

  * a KNOWN-FALSE task is true only under a bounded model (`ensures r <=
    2^31-1` over a body that returns its argument). SPEC.md says it is false,
    so every kernel must REFUTE it. A VERIFIED is an UNSOUNDNESS: the kernel
    answered a bounded question t did not ask.
  * a KNOWN-TRUE task is true for every mathematical integer but needs a
    value, an intermediate, or a quantifier range outside a machine word
    (`ensures r == x*x` with `x` up to 2^40). Every kernel must VERIFY it. A
    REFUTED is the same disease from the other side.

HOW EACH LABEL WAS ESTABLISHED, the generator's own soundness and the one
thing that would make every finding below worthless if it were fudged. A
bounded search over a finite domain is a SOUND proof of FALSITY (one
counterexample settles it) and is NOT a sound proof of TRUTH (a property can
hold on [-40, 40] and fail at 2^40). So:

  KNOWN-TRUE is established by CONSTRUCTION ONLY. Each true task's `ensures`
  is read off its own body (`r = x*x` gives `ensures r == x*x`) or is an
  elementary theorem of the integers stated as such in `_basis` (`x*x >= 0`;
  `a - a == 0`; `x <= -2^31` implies `-x >= 2^31`; every `i` in `[lo, hi)`
  satisfies `lo <= i`). `_check_labels` then sweeps interp.py over the
  ladder domain, and that sweep can only REFUTE a true label, never confirm
  one: a violation means the construction is wrong and this file refuses to
  run. It is a guard on the generator, never the basis of a label.

  KNOWN-FALSE is established by an EXHIBITED WITNESS wherever one is
  representable: a concrete input, checked here by interp.py, on which the
  body's own value falsifies `ensures`. Four families cannot exhibit one:
  a seq of length 2^31 does not fit in memory, and a quantifier over
  [0, 2^31+3) exceeds interp.py's step cap. Those carry
  `_basis="construction"` with the falsifying point named in prose, and are
  reported separately from the witnessed ones, never presented as measured.

THE INSTRUMENT HAS MEASURED POWER, which is a separate claim from its
verdicts and is worth more than either. Re-running three of the known-FALSE
probes under Frama-C's DEFAULT arithmetic model, the one lower_framac.py
carried before the 2026-09-01 repair, proves them: bp_f_ub31, bp_f_elem_ub31
and bp_f_len_ub31 each close `Proved goals: 7 / 7` there and `6 / 7` under the
pinned `-wp-model Typed+nat` (measured 2026-09-01, frama-c 33.0 / alt-ergo
2.4.3-free). So this corpus VERIFIES a false theorem against the broken
instrument and REFUTES it against the repaired one: a green column below is
evidence, not the absence of a probe. The `bp_k_*` calibration pairs carry the
same argument into every other column without needing a broken build of it.

CONTROLS ARE PART OF THE INSTRUMENT. A column that refutes everything proves
nothing about bounded models, so each family carries a small-magnitude twin
of its boundary probe: `bp_c_lensmall` (`len(s) <= 4`), `bp_c_elemsmall`
(`s[0] <= 4`), `bp_c_qsmall`, `bp_c_reachsmall`, plus `bp_c_true` and
`bp_c_false`. A kernel that REFUTES the small member and VERIFIES the 2^31
member differs on nothing but the magnitude, which is what "bounded model"
means operationally.

MEASURED 2026-09-01 on the training box, 45 tasks x 7 kernels x flake_check
n=3 (945 kernel runs, ZERO flaked cells), pinned versions in the report's
Backends section:

  * NO UNSOUNDNESS. No kernel VERIFIED any of the 25 known-false tasks. The
    2026-09-01 integer repairs to lower_framac.py (`-wp-model Typed+nat`) and
    lower_spark.py (Infinite_Sequences over Big_Integer) hold against a
    corpus that does not trust them, and no other backend has the disease.
  * The bound is what the verdict turns on, per column. All seven kernels
    VERIFY bp_k_ub31 / bp_k_elem_ub31 / bp_k_len_ub31, the same three claims
    with the machine range written in as `requires`, and six of seven REFUTE
    the unhypothesised partners. Only the hypothesis moved.
  * INCOMPLETENESS, reported as refutation. Eight cells REFUTE a task true by
    construction. `bp_t_sq` (`r == x*x` and `r >= 0`) is refuted by verus,
    lean and rocq, on nonlinear arithmetic rather than a bounded model (verus prints
    "postcondition not satisfied" on the `r >= 0` clause; lean's audit shows
    `sorryAx`, its tactic script having failed). `bp_t_qexists` is refuted by
    dafny, lean, rocq AND fstar and verified by spark and framac: a WRONG
    MAJORITY, which is what a consensus grader would have asserted.
  * spark REFUTES 0 of 25 known-false tasks, including a control as plain as
    `F(X) = X` with `ensures r == x + 1`: gnatprove answers "medium:
    postcondition might fail ... provers gave up before completing the proof",
    status `gave_up`, no countermodel, over every Big_Integer goal. Honest
    (Outcome.UNPROVED, ok=False) and not unsoundness, but it means the
    boundary claim rests on six columns' refutations plus spark's 20/20 on
    the known-true side.
  * Two lowering ceilings, both surfacing as MALFORMED rather than as an
    abstention. lower_framac.py emits a t integer literal >= 2^63 into
    EXECUTABLE C position, where the kernel answers "Cannot represent the
    integer 9223372036854775808" (bp_f_elemreach63, bp_f_lenreach63); spec
    position is unaffected, since ACSL `integer` is unbounded. And a
    quantifier naming no term over its bound variable is inexpressible in two
    kernels: dafny 4.11 warns "Could not find a trigger for this quantifier"
    (fatal under --allow-warnings false), verus 0.2026.08.30 errors "Could not
    automatically infer triggers". The bp_*_qtrig* probes carry the same range
    question with `at(s, i)` as a trigger, and both columns then answer it
    correctly, so the gap is notation, not model.
  * fstar scores bp_c_true MALFORMED: F* closes `= x` against
    `(x >= 0 ==> r == x) /\\ (x < 0 ==> r == x)` by normalization with NO SMT
    query, and verifiers/fstar.py requires `discharged > 0` for VERIFIED. Fail
    closed, so not unsoundness, but an honest proof scored as a non-answer.

Own output directory, never t/out/: the suite's drivers own those filenames
(run_par.py's _live_conflict records the cost of a second writer). Pass --out.

    python3 t/boundary_probe.py --out DIR --jobs 64 --flake 3
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import interp                                          # noqa: E402
from fuzz_lower import check_wf                        # noqa: E402
from verifiers import Outcome, flake_check, mp_context             # noqa: E402

BACKENDS = [
    ("dafny", "lower_dafny", "dfy"),
    ("verus", "lower_verus", "rs"),
    ("spark", "lower_spark", "ads"),
    ("framac", "lower_framac", "c"),
    ("lean", "lower_lean", "lean"),
    ("rocq", "lower_rocq", "v"),
    ("fstar", "lower_fstar", "fst"),
]

# The sweep that guards a KNOWN-TRUE label. interp.ladders puts the task's own
# literals and their neighbours at the front of the domain, so a task whose
# spec names 2^31-1 is swept at 2^31-2, 2^31-1 and 2^31, the points where a
# machine-model confusion would show, inside this cap.
SWEEP_POINTS = 400


# ---------------------------------------------------------------- syntax ---

def I(n):
    return {"int": n}


def V(x):
    return {"var": x}


def OP(o, *a):
    return {"op": o, "args": list(a)}


def IMP(p, q):
    return OP("implies", p, q)


def LEN(s):
    return OP("len", V(s))


def AT(s, i):
    return OP("at", V(s), i)


def FA(v, lo, hi, b):
    return {"forall": {"var": v, "lo": lo, "hi": hi, "body": b}}


def EX(v, lo, hi, b):
    return {"exists": {"var": v, "lo": lo, "hi": hi, "body": b}}


def ASG(x, e):
    return {"assign": [x, e]}


def IFS(c, t, e):
    return {"if": {"cond": c, "then": t, "else": e}}


def LOC(n, ty, init):
    return {"var": {"name": n, "type": ty, "init": init}}


# ------------------------------------------------------------ task shapes ---
# Every shape below keeps BOTH branches of its `if` reachable under SPEC.md
# semantics. A dead branch is reported by WP's smoke tests as VACUOUS rather
# than VERIFIED (measured on the fuzzer's fz_p_bigneg/fz_p_bigwide/fz_p_biglen,
# whose machine-representability question sits inside a branch), which turns a
# soundness question into a refusal and measures nothing.

def _band_hi(name, extra, **meta):
    """`if x >= 0 then r = x else r = 0`, postcondition read off the body plus
    one discriminating clause. Positive extremes reach `r` through `x`."""
    return dict(
        {"t": 0, "name": name,
         "params": [{"name": "x", "type": "int"}],
         "returns": [{"name": "r", "type": "int"}],
         "requires": [],
         "ensures": [IMP(OP(">=", V("x"), I(0)), OP("==", V("r"), V("x"))),
                     IMP(OP("<", V("x"), I(0)), OP("==", V("r"), I(0)))]
                    + extra,
         "body": [IFS(OP(">=", V("x"), I(0)),
                      [ASG("r", V("x"))], [ASG("r", I(0))])]},
        **meta)


def _band_lo(name, extra, **meta):
    """The mirror of _band_hi: negative extremes reach `r` through `x`."""
    return dict(
        {"t": 0, "name": name,
         "params": [{"name": "x", "type": "int"}],
         "returns": [{"name": "r", "type": "int"}],
         "requires": [],
         "ensures": [IMP(OP("<=", V("x"), I(0)), OP("==", V("r"), V("x"))),
                     IMP(OP(">", V("x"), I(0)), OP("==", V("r"), I(0)))]
                    + extra,
         "body": [IFS(OP("<=", V("x"), I(0)),
                      [ASG("r", V("x"))], [ASG("r", I(0))])]},
        **meta)


def _band_id(name, extra, **meta):
    """Identity on both branches: `r` carries `x` at every sign, which is what
    a signedness question needs. The two branches are distinct program points,
    so neither is dead."""
    return dict(
        {"t": 0, "name": name,
         "params": [{"name": "x", "type": "int"}],
         "returns": [{"name": "r", "type": "int"}],
         "requires": [],
         "ensures": [IMP(OP(">=", V("x"), I(0)), OP("==", V("r"), V("x"))),
                     IMP(OP("<", V("x"), I(0)), OP("==", V("r"), V("x")))]
                    + extra,
         "body": [IFS(OP(">=", V("x"), I(0)),
                      [ASG("r", V("x"))], [ASG("r", V("x"))])]},
        **meta)


def _band_seq(name, extra, **meta):
    """`if len(s) > 0 then r = 1 else r = 0`, the empty and non-empty cases
    are both reachable for any seq model, so the discriminating clause is the
    only thing a verdict can turn on."""
    return dict(
        {"t": 1, "name": name, "gate": "quantifiers",
         "params": [{"name": "s", "type": "seq"}],
         "returns": [{"name": "r", "type": "int"}],
         "requires": [],
         "ensures": [IMP(OP(">", LEN("s"), I(0)), OP("==", V("r"), I(1))),
                     IMP(OP("==", LEN("s"), I(0)), OP("==", V("r"), I(0)))]
                    + extra,
         "body": [IFS(OP(">", LEN("s"), I(0)),
                      [ASG("r", I(1))], [ASG("r", I(0))])]},
        **meta)


def _reach(name, cond, requires, **meta):
    """`if cond then r = 1 else r = 0` with `ensures r == 0`: FALSE exactly
    when `cond` is satisfiable, and it states no width literal in the
    postcondition, so a lowering cannot answer it by rejecting a bound. Under
    a bounded model the `then` branch is DEAD, which a smoke-test-carrying
    kernel reports as VACUOUS, a distinct signal from VERIFIED, graded
    separately below."""
    return dict(
        {"t": 1, "name": name, "gate": "quantifiers",
         "params": [{"name": "s", "type": "seq"}],
         "returns": [{"name": "r", "type": "int"}],
         "requires": requires,
         "ensures": [OP("==", V("r"), I(0))],
         "body": [IFS(cond, [ASG("r", I(1))], [ASG("r", I(0))])]},
        **meta)


LEN_POS = [OP(">", LEN("s"), I(0))]


def corpus() -> list[dict]:
    C = []

    def add(task):
        C.append(task)

    # === controls =========================================================
    # Without these a column that refutes everything would read as sound, and
    # a column that verifies everything as unsound. Each family's boundary
    # probe has a small-magnitude twin here; the two differ in NOTHING but the
    # constant, so a split verdict names the bound.
    add(_band_id(
        "bp_c_true", [],
        _truth="true", _family="control", _basis="construction: `ensures` is "
        "the body, clause for clause",
        _why="every kernel must VERIFY; a REFUTED here invalidates the whole "
             "column"))
    add(_band_id(
        "bp_c_false", [OP("==", V("r"), OP("+", V("x"), I(1)))],
        _truth="false", _family="control", _basis="witness",
        _witness={"x": 0},
        _why="x = 0 gives r = 0, and 0 == 1 is false; every kernel must "
             "REFUTE"))
    add(_band_seq(
        "bp_c_seqtrue", [],
        _truth="true", _family="control", _basis="construction: `ensures` is "
        "the body, clause for clause",
        _why="the seq-shaped column control"))
    add(_band_seq(
        "bp_c_lensmall", [OP("<=", LEN("s"), I(4))],
        _truth="false", _family="control", _basis="witness",
        _witness={"s": (0, 0, 0, 0, 0)},
        _why="len(s) = 5 falsifies it; the small-magnitude twin of "
             "bp_f_len_ub31, same clause, constant 4 instead of 2^31-1"))
    add(_band_seq(
        "bp_c_elemsmall", [IMP(OP(">", LEN("s"), I(0)),
                               OP("<=", AT("s", I(0)), I(4)))],
        _truth="false", _family="control", _basis="witness",
        _witness={"s": (5,)},
        _why="s = [5] falsifies it; the small-magnitude twin of "
             "bp_f_elem_ub31"))
    add(_band_seq(
        "bp_c_qsmall", [FA("i", I(0), I(8), OP("<=", V("i"), I(4)))],
        _truth="false", _family="control", _basis="witness",
        _witness={"s": ()},
        _why="i = 5 is in [0, 8) and 5 <= 4 is false; the small-magnitude "
             "twin of bp_f_qrange31, and the only member of that family "
             "interp.py can evaluate"))
    add(_reach(
        "bp_c_reachsmall", OP(">", AT("s", I(0)), I(4)), LEN_POS,
        _truth="false", _family="control", _basis="witness",
        _witness={"s": (5,)},
        _why="s = [5] takes the then-branch, so r = 1 and `r == 0` fails; the "
             "small-magnitude twin of bp_f_elemreach31/63"))

    # === known-FALSE: integer width, positive and negative extremes ========
    # SPEC.md: "Integer semantics in both versions: mathematical integers,
    # unbounded, no overflow." Each clause below is true under exactly one
    # machine width and false over the integers, so VERIFIED names the width.
    for tag, bits, bound, wit in (
            ("bp_f_ub16", 16, 2 ** 15 - 1, 2 ** 15),
            ("bp_f_ub31", 32, 2 ** 31 - 1, 2 ** 31),
            ("bp_f_ub63", 64, 2 ** 63 - 1, 2 ** 63),
            ("bp_f_ub127", 128, 2 ** 127 - 1, 2 ** 127)):
        add(_band_hi(
            tag, [OP("<=", V("r"), I(bound))],
            _truth="false", _family="int-width", _basis="witness",
            _witness={"x": wit},
            _why=f"x = {wit} gives r = {wit} > {bound}; VERIFIED means the "
                 f"lowering constrained a t int to {bits} bits"))
    for tag, bits, bound, wit in (
            ("bp_f_lb31", 32, -2 ** 31, -2 ** 31 - 1),
            ("bp_f_lb63", 64, -2 ** 63, -2 ** 63 - 1)):
        add(_band_lo(
            tag, [OP(">=", V("r"), I(bound))],
            _truth="false", _family="int-width", _basis="witness",
            _witness={"x": wit},
            _why=f"x = {wit} gives r = {wit} < {bound}; VERIFIED means the "
                 f"lowering constrained a t int to {bits} bits, negative "
                 f"end"))
    add(_band_id(
        "bp_f_nonneg", [OP(">=", V("r"), I(0))],
        _truth="false", _family="int-width", _basis="witness",
        _witness={"x": -1},
        _why="x = -1 gives r = -1; VERIFIED means the lowering used an "
             "unsigned or Nat type for a t int"))

    # === known-FALSE: seq ELEMENTS ========================================
    # SPEC.md gate 1: "a seq value s has a length len(s) >= 0 and elements
    # s[0] ... s[len(s)-1], each a mathematical integer." A lowering can bound
    # the elements while leaving the length free, so these are independent of
    # the length family below.
    for tag, bound, wit, note in (
            ("bp_f_elem_ub31", 2 ** 31 - 1, 2 ** 31, "32-bit elements"),
            ("bp_f_elem_ub63", 2 ** 63 - 1, 2 ** 63, "64-bit elements")):
        add(_band_seq(
            tag, [IMP(OP(">", LEN("s"), I(0)),
                      OP("<=", AT("s", I(0)), I(bound)))],
            _truth="false", _family="seq-elem", _basis="witness",
            _witness={"s": (wit,)},
            _why=f"s = [{wit}] falsifies it; VERIFIED means {note}"))
    add(_band_seq(
        "bp_f_elem_lb31", [IMP(OP(">", LEN("s"), I(0)),
                               OP(">=", AT("s", I(0)), I(-2 ** 31)))],
        _truth="false", _family="seq-elem", _basis="witness",
        _witness={"s": (-2 ** 31 - 1,)},
        _why="s = [-2^31-1] falsifies it; VERIFIED means 32-bit elements, "
             "negative end"))
    add(_band_seq(
        "bp_f_elem_nonneg", [IMP(OP(">", LEN("s"), I(0)),
                                 OP(">=", AT("s", I(0)), I(0)))],
        _truth="false", _family="seq-elem", _basis="witness",
        _witness={"s": (-1,)},
        _why="s = [-1] falsifies it; VERIFIED means the element type is "
             "unsigned or Nat"))
    for tag, bound, wit in (("bp_f_elemreach31", 2 ** 31, 2 ** 31 + 1),
                            ("bp_f_elemreach63", 2 ** 63, 2 ** 63 + 1)):
        add(_reach(
            tag, OP(">", AT("s", I(0)), I(bound)), LEN_POS,
            _truth="false", _family="seq-elem", _basis="witness",
            _witness={"s": (wit,)},
            _why=f"s = [{wit}] takes the then-branch, so r = 1 and `r == 0` "
                 f"fails; states no bound in the postcondition, so a lowering "
                 f"cannot answer it by rejecting a width literal"))

    # === known-FALSE: seq LENGTH ==========================================
    # NO EXHIBITED WITNESS EXISTS: the falsifying value is a sequence of
    # 2^31 elements. The label is established by construction from SPEC.md's
    # seq model, which admits every finite length >= 0 and states no upper
    # bound; the clause fails at any such length. Graded and reported apart
    # from the witnessed families, and never called measured.
    for tag, bound, bits in (("bp_f_len_ub31", 2 ** 31 - 1, 32),
                             ("bp_f_len_ub63", 2 ** 63 - 1, 64)):
        add(_band_seq(
            tag, [OP("<=", LEN("s"), I(bound))],
            _truth="false", _family="seq-len", _basis="construction",
            _why=f"SPEC.md gives a seq only len(s) >= 0; any s with "
                 f"len(s) = {bound + 1} falsifies the clause. VERIFIED means "
                 f"the length is a {bits}-bit quantity"))
    for tag, bound, bits in (("bp_f_lenreach31", 2 ** 31, 32),
                             ("bp_f_lenreach63", 2 ** 63, 64)):
        add(_reach(
            tag, OP(">=", LEN("s"), I(bound)), [],
            _truth="false", _family="seq-len", _basis="construction",
            _why=f"any s with len(s) = {bound} takes the then-branch, so "
                 f"r = 1 and `r == 0` fails. Under a {bits}-bit length that "
                 f"branch is DEAD, so VACUOUS here is itself evidence of a "
                 f"bounded length"))

    # === known-FALSE: quantifier range ====================================
    # SPEC.md gate 1: "for every integer i with lo <= i < hi". The range is
    # over mathematical integers; a machine-typed cursor answers a different
    # question. Ranges here hold 2^31+3 points, above interp.py's step cap
    # (MAX_STEPS), so the falsifying index is exhibited in prose only.
    add(_band_seq(
        "bp_f_qrange31", [FA("i", I(0), I(2 ** 31 + 3),
                             OP("<=", V("i"), I(2 ** 31)))],
        _truth="false", _family="quant-range", _basis="construction",
        _why="i = 2^31+1 lies in [0, 2^31+3) and 2^31+1 <= 2^31 is false"))
    add(_band_seq(
        "bp_f_qneg31", [FA("i", I(-2 ** 31 - 3), I(0),
                           OP(">=", V("i"), I(-2 ** 31)))],
        _truth="false", _family="quant-range", _basis="construction",
        _why="i = -2^31-1 lies in [-2^31-3, 0) and -2^31-1 >= -2^31 is "
             "false; the negative end of the same question"))
    # The four ranges above name no term over the bound variable, and two of
    # seven kernels cannot express such a quantifier at all: dafny 4.11 emits
    # "Could not find a trigger for this quantifier" (a warning its adapter
    # takes as MALFORMED under --allow-warnings false) and verus 0.2026.08.30
    # emits "Could not automatically infer triggers" as a hard error (both
    # measured 2026-09-01). `at(s, i)` is a trigger term, so the two probes
    # below put the same range question where those two columns can answer it.
    add(_band_seq(
        "bp_f_qtrig31", [FA("i", I(0), I(2 ** 31 + 3),
                            IMP(OP("<", V("i"), LEN("s")),
                                OP("<=", AT("s", V("i")), I(2 ** 31 - 1))))],
        _truth="false", _family="quant-range", _basis="construction",
        _why="s = [2^31] with i = 0 falsifies it (0 < len(s) and "
             "s[0] > 2^31-1); the range is 2^31+3 points wide, above "
             "interp.py's step cap, so the point is exhibited and not run"))
    add(_band_seq(
        "bp_t_qtrig", [FA("i", I(0), I(3 * 10 ** 9),
                          IMP(OP("<", V("i"), LEN("s")),
                              OP("==", AT("s", V("i")), AT("s", V("i")))))],
        _truth="true", _family="quant-range",
        _basis="construction: the body is reflexivity of == on a term whose "
               "definedness the guard supplies (lo = 0 gives i >= 0, the "
               "antecedent gives i < len(s))",
        _why="a trigger-bearing range 3*10^9 wide; a machine-typed cursor "
             "cannot represent it"))
    add(_band_seq(
        "bp_t_qtrigneg", [FA("i", I(-3 * 10 ** 9), I(1),
                             IMP(OP("and", OP(">=", V("i"), I(0)),
                                    OP("<", V("i"), LEN("s"))),
                                 OP("==", AT("s", V("i")),
                                    AT("s", V("i")))))],
        _truth="true", _family="quant-range",
        _basis="construction: the body is reflexivity of == on a term the "
               "conjunction guards, and `and` short-circuits left to right",
        _why="a trigger-bearing range starting at -3*10^9; an unsigned or Nat "
             "cursor cannot represent its lower end"))

    # === known-TRUE: the CALIBRATION pairs =================================
    # Each is its `bp_f_*` partner with the range hypothesis a 32-bit model
    # would grant for free written out as an explicit `requires`. That makes
    # the pair differ in EXACTLY the hypothesis under test, so a kernel that
    # REFUTES the partner and VERIFIES this one has refused for that reason
    # and no other: the discriminating power of the probe, measured in that
    # column rather than assumed.
    add(_band_hi(
        "bp_k_ub31", [OP("<=", V("r"), I(2 ** 31 - 1))],
        _truth="true", _family="calibration",
        _basis="construction: the body assigns r either x or 0, and the "
               "precondition bounds x by 2^31-1",
        _why="the hypothesis bp_f_ub31 does NOT have; a kernel verifying "
             "this and refuting that turns on the range hypothesis alone"))
    C[-1]["requires"] = [OP(">=", V("x"), I(-2 ** 31)),
                         OP("<=", V("x"), I(2 ** 31 - 1))]
    add(_band_seq(
        "bp_k_elem_ub31", [IMP(OP(">", LEN("s"), I(0)),
                               OP("<=", AT("s", I(0)), I(2 ** 31 - 1)))],
        _truth="true", _family="calibration",
        _basis="construction: the `ensures` clause IS the second disjunct of "
               "the precondition, and the first disjunct falsifies its "
               "antecedent",
        _why="bp_f_elem_ub31 with the element bound assumed instead of "
             "claimed"))
    # `or` evaluates left to right and the second disjunct need only be
    # defined when the first is false (SPEC.md "Definedness"), so `at(s, 0)`
    # here is guarded, not totalized.
    C[-1]["requires"] = [OP("or", OP("==", LEN("s"), I(0)),
                            OP("and", OP(">", LEN("s"), I(0)),
                               OP("<=", AT("s", I(0)), I(2 ** 31 - 1))))]
    add(_band_seq(
        "bp_k_len_ub31", [OP("<=", LEN("s"), I(2 ** 31 - 1))],
        _truth="true", _family="calibration",
        _basis="construction: the `ensures` clause IS the precondition",
        _why="bp_f_len_ub31 with the length bound assumed instead of "
             "claimed"))
    C[-1]["requires"] = [OP("<=", LEN("s"), I(2 ** 31 - 1))]

    # === known-TRUE: values and intermediates outside a machine word =======
    add({"t": 0, "name": "bp_t_sq",
         "params": [{"name": "x", "type": "int"}],
         "returns": [{"name": "r", "type": "int"}],
         "requires": [],
         "ensures": [OP("==", V("r"), OP("*", V("x"), V("x"))),
                     OP(">=", V("r"), I(0))],
         "body": [ASG("r", OP("*", V("x"), V("x")))],
         "_truth": "true", "_family": "int-width",
         "_basis": "construction: clause 1 is the body; clause 2 is x*x >= 0, "
                   "an elementary theorem of the integers",
         "_why": "x = 2^40 gives r = 2^80. REFUTED means a bounded model: "
                 "under two's-complement wrapping x*x is negative at "
                 "x = 2^31-1, and under a checked machine model the "
                 "multiplication has no value at all"})
    add({"t": 0, "name": "bp_t_cube",
         "params": [{"name": "x", "type": "int"}],
         "returns": [{"name": "r", "type": "int"}],
         "requires": [],
         "ensures": [IMP(OP(">=", V("x"), I(0)),
                         OP("==", V("r"),
                            OP("*", OP("*", V("x"), V("x")), V("x")))),
                     IMP(OP("<", V("x"), I(0)),
                         OP("==", V("r"),
                            OP("neg", OP("*", OP("*", V("x"), V("x")),
                                         V("x")))))],
         "body": [IFS(OP(">=", V("x"), I(0)),
                      [ASG("r", OP("*", OP("*", V("x"), V("x")), V("x")))],
                      [ASG("r", OP("neg", OP("*", OP("*", V("x"), V("x")),
                                             V("x"))))])],
         "_truth": "true", "_family": "int-width",
         "_basis": "construction: `ensures` is the body, branch for branch",
         "_why": "x = 3*10^9 gives r = 2.7*10^28, past 2^63 by 12 orders of "
                 "magnitude"})
    add({"t": 0, "name": "bp_t_succ",
         "params": [{"name": "x", "type": "int"}],
         "returns": [{"name": "r", "type": "int"}],
         "requires": [],
         "ensures": [OP("==", V("r"), OP("+", V("x"), I(1))),
                     OP(">", V("r"), V("x"))],
         "body": [ASG("r", OP("+", V("x"), I(1)))],
         "_truth": "true", "_family": "int-width",
         "_basis": "construction: clause 1 is the body; clause 2 is "
                   "x + 1 > x, an elementary theorem of the integers",
         "_why": "false under two's-complement wrapping at every width's "
                 "maximum, true for every mathematical integer"})
    add({"t": 0, "name": "bp_t_3x",
         "params": [{"name": "x", "type": "int"}],
         "returns": [{"name": "r", "type": "int"}],
         "requires": [OP(">=", V("x"), I(-2 * 10 ** 9)),
                      OP("<=", V("x"), I(2 * 10 ** 9))],
         "ensures": [OP("==", V("r"),
                        OP("+", OP("+", V("x"), V("x")), V("x"))),
                     IMP(OP(">=", V("x"), I(10 ** 9)),
                         OP(">=", V("r"), I(3 * 10 ** 9)))],
         "body": [ASG("r", OP("+", OP("+", V("x"), V("x")), V("x")))],
         "_truth": "true", "_family": "int-width",
         "_basis": "construction: clause 1 is the body; clause 2 is "
                   "monotonicity of x -> 3x",
         "_why": "the precondition keeps x inside 32 bits and the result "
                 "outside it, so a 32-bit RETURN type refutes while a 32-bit "
                 "PARAMETER type does not"})
    add({"t": 0, "name": "bp_t_absmin",
         "params": [{"name": "x", "type": "int"}],
         "returns": [{"name": "r", "type": "int"}],
         "requires": [],
         "ensures": [IMP(OP("<", V("x"), I(0)),
                         OP("==", V("r"), OP("neg", V("x")))),
                     IMP(OP(">=", V("x"), I(0)), OP("==", V("r"), V("x"))),
                     IMP(OP("<=", V("x"), I(-2 ** 31)),
                         OP(">=", V("r"), I(2 ** 31)))],
         "body": [IFS(OP("<", V("x"), I(0)),
                      [ASG("r", OP("neg", V("x")))], [ASG("r", V("x"))])],
         "_truth": "true", "_family": "int-width",
         "_basis": "construction: clauses 1-2 are the body; clause 3 is "
                   "x <= -2^31 implies -x >= 2^31",
         "_why": "negation at the 32-bit minimum, the classic abs overflow; "
                 "no dead branch, so a bounded kernel must refute rather "
                 "than report the case away"})
    add({"t": 0, "name": "bp_t_negext",
         "params": [{"name": "x", "type": "int"}],
         "returns": [{"name": "r", "type": "int"}],
         "requires": [],
         "ensures": [OP("==", V("r"), OP("neg", V("x"))),
                     IMP(OP("<=", V("x"), I(-2 ** 63)),
                         OP(">=", V("r"), I(2 ** 63)))],
         "body": [ASG("r", OP("neg", V("x")))],
         "_truth": "true", "_family": "int-width",
         "_basis": "construction: clause 1 is the body; clause 2 is "
                   "x <= -2^63 implies -x >= 2^63",
         "_why": "the same negation question one width up"})
    add({"t": 0, "name": "bp_t_bigmul",
         "params": [{"name": "x", "type": "int"}],
         "returns": [{"name": "r", "type": "int"}],
         "requires": [OP(">=", V("x"), I(0)), OP("<=", V("x"), I(2 ** 40))],
         "ensures": [OP("==", V("r"), OP("*", V("x"), V("x"))),
                     OP(">=", V("r"), I(0))],
         "body": [ASG("r", OP("*", V("x"), V("x")))],
         "_truth": "true", "_family": "int-width",
         "_basis": "construction: clause 1 is the body; clause 2 is "
                   "x*x >= 0",
         "_why": "the precondition is satisfiable and the product reaches "
                 "2^80, so no machine width holds r"})
    add({"t": 1, "name": "bp_t_cancel", "gate": "loops",
         "params": [{"name": "x", "type": "int"}],
         "returns": [{"name": "r", "type": "int"}],
         "requires": [],
         "ensures": [OP("==", V("r"), I(0))],
         "body": [LOC("a", "int", OP("*", OP("*", V("x"), V("x")),
                                     OP("*", V("x"), V("x")))),
                  ASG("r", OP("-", V("a"), V("a")))],
         "_truth": "true", "_family": "int-width",
         "_basis": "construction: a - a == 0 for every integer a, whatever a "
                   "is",
         "_why": "the INTERMEDIATE leaves every machine word (x^4 at x = 2^20 "
                 "is 2^80) while the result is 0; a checked machine model has "
                 "no value for `a` and refutes, a wrapping one still gets 0"})

    # === known-TRUE: quantifier ranges and the seq model ===================
    add(_band_seq(
        "bp_t_qrange", [FA("i", I(2 ** 31), I(2 ** 31 + 5),
                           OP(">=", V("i"), I(2 ** 31)))],
        _truth="true", _family="quant-range",
        _basis="construction: SPEC.md gate 1 defines the range as lo <= i "
               "< hi, so lo <= i holds at every point of [lo, hi)",
        _why="the range sits entirely above 2^31; a machine-typed cursor "
             "cannot represent it"))
    add(_band_seq(
        "bp_t_qneg", [FA("i", I(-3 * 10 ** 9), I(-2 * 10 ** 9),
                         OP("<", V("i"), I(0)))],
        _truth="true", _family="quant-range",
        _basis="construction: every point of [-3*10^9, -2*10^9) is below "
               "-2*10^9 < 0",
        _why="a range wholly negative and below -2^31; an unsigned or Nat "
             "cursor makes it empty or malformed"))
    add(_band_seq(
        "bp_t_qexists", [EX("i", I(0), I(3 * 10 ** 9),
                            OP(">", V("i"), I(2 ** 31)))],
        _truth="true", _family="quant-range",
        _basis="construction: i = 2^31+1 lies in [0, 3*10^9) and satisfies "
               "the body",
        _why="the existential's own witness is above 2^31, so a truncated "
             "range has none"))
    add(_band_seq(
        "bp_t_lenge0", [OP(">=", LEN("s"), I(0))],
        _truth="true", _family="seq-len",
        _basis="construction: SPEC.md gate 1 states len(s) >= 0",
        _why="the ONE thing SPEC.md grants about a seq length; a kernel that "
             "cannot prove it has no seq model at all"))
    add({"t": 1, "name": "bp_t_idx2", "gate": "quantifiers",
         "params": [{"name": "s", "type": "seq"}],
         "returns": [{"name": "r", "type": "int"}],
         "requires": [OP("==", LEN("s"), I(2))],
         "ensures": [IMP(OP("==", AT("s", I(0)), AT("s", I(1))),
                         OP("==", V("r"), I(1))),
                     IMP(OP("!=", AT("s", I(0)), AT("s", I(1))),
                         OP("==", V("r"), I(0)))],
         "body": [IFS(OP("==", AT("s", I(0)), AT("s", I(1))),
                      [ASG("r", I(1))], [ASG("r", I(0))])],
         "_truth": "true", "_family": "seq-index",
         "_basis": "construction: `ensures` is the body, branch for branch",
         "_why": "SPEC.md indexes s[0] .. s[len(s)-1]; a 1-based or "
                 "positive-only index type reads a different element or "
                 "leaves s[0] undefined"})
    return C


# ------------------------------------------------------- label discipline ---

def evaluate(task: dict, env0: dict):
    """SPEC.md semantics at ONE concrete input, via interp.py: (status, value)
    with status in req-fail / undefined / no-value / violated / satisfied."""
    clean = {k: v for k, v in task.items() if not k.startswith("_")}
    funs = interp.funs_of(clean, clean["body"])
    ret = clean["returns"][0]["name"]
    st = interp.St()
    try:
        for c in clean.get("requires", []):
            if not interp.ev(c, env0, funs, st):
                return "req-fail", None
    except (interp.Undef, interp.Budget):
        return "undefined", None
    env = dict(env0)
    env[ret] = None
    try:
        interp.exec_body(clean["body"], env, funs, st)
    except (interp.Undef, interp.Budget, RecursionError):
        return "undefined", None
    v = env[ret]
    if v is None:
        return "no-value", None
    try:
        for c in clean["ensures"]:
            if not interp.ev(c, env, funs, interp.St()):
                return "violated", v
    except interp.Undef:
        return "violated", v
    except (interp.Budget, RecursionError):
        return "undecided", v
    return "satisfied", v


def check_labels(tasks: list[dict]) -> tuple[list[str], dict]:
    """The generator's own soundness gate, and the reason this file may be
    believed at all.

    A KNOWN-FALSE label with `_basis="witness"` is CONFIRMED here: the stated
    input must actually falsify `ensures` under interp.py. One counterexample
    is a sound proof of falsity.

    A KNOWN-TRUE label is NOT confirmed here and cannot be: a bounded sweep
    proves nothing about 2^40. The sweep below can only REFUTE such a label,
    and a refutation is a bug in this file, not a finding about a kernel.

    Also returns, per known-true task, how many domain points the sweep
    actually DECIDED. A quantifier over [0, 3*10^9) exhausts interp.py's step
    cap at every point, so its clause is never exercised: reporting 0 here
    stops a reader from mistaking the guard for coverage it does not have."""
    errs, decided = [], {}
    for t in tasks:
        name = t["name"]
        clean = {k: v for k, v in t.items() if not k.startswith("_")}
        for e in check_wf(clean):
            errs.append(f"{name}: not a well-formed t task, {e}")
        if t["_truth"] == "false" and t["_basis"] == "witness":
            st, val = evaluate(t, dict(t["_witness"]))
            if st != "violated":
                errs.append(f"{name}: claimed FALSE by witness "
                            f"{t['_witness']}, but interp.py says {st} "
                            f"(r = {val}), so the label is unproven")
        if t["_truth"] == "true":
            names = [(p["name"], p["type"]) for p in clean["params"]]
            n = 0
            for env0 in interp.domain(clean, names, SWEEP_POINTS):
                st, val = evaluate(t, env0)
                if st == "satisfied":
                    n += 1
                elif st in ("violated", "no-value"):
                    shown = {k: (list(v) if isinstance(v, tuple) else v)
                             for k, v in env0.items()}
                    errs.append(
                        f"{name}: claimed TRUE by construction, but interp.py "
                        f"falsifies it at {shown} (r = {val}, {st}), so the "
                        f"construction is wrong")
                    break
            decided[name] = n
    return errs, decided


# -------------------------------------------------------------- the runner ---

def _cell(bname: str, src: str, n: int):
    backend = importlib.import_module(f"verifiers.{bname}")
    p = Path(src)
    if n == 1:
        r = backend.verify(p)
        return bname, p.stem, r.outcome, True, r.wall_ms, r.error[:200]
    r, agreed = flake_check(backend.verify, p, n)
    return bname, p.stem, r.outcome, agreed, r.wall_ms, r.error[:200]


def run(tasks, outdir: Path, jobs: int, flake: int, only=None):
    outdir.mkdir(parents=True, exist_ok=True)
    cols, present = [], []
    for bname, lmod, sfx in BACKENDS:
        if only and bname not in only:
            continue
        try:
            be = importlib.import_module(f"verifiers.{bname}")
            cols.append((bname, be.version()))
            present.append((bname, importlib.import_module(lmod).lower, sfx))
        except (Exception, SystemExit) as e:                 # noqa: BLE001
            cols.append((bname, f"ABSENT: {e}"))
    rows = {t["name"]: {} for t in tasks}
    pending = []
    for bname, lower, sfx in present:
        for t in tasks:
            name = t["name"]
            clean = {k: v for k, v in t.items() if not k.startswith("_")}
            try:
                src = lower(clean, clean["body"])
            except NotImplementedError as e:
                rows[name][bname] = ("abstain", True, 0, str(e)[:200])
                continue
            except Exception as e:                           # noqa: BLE001
                rows[name][bname] = ("lower-error", True, 0,
                                     f"{type(e).__name__}: {e}"[:200])
                continue
            p = outdir / f"{name}.{sfx}"
            p.write_text(src, encoding="utf-8")
            pending.append((bname, str(p)))
    t0 = time.time()
    ctx = mp_context()
    done = 0
    with ProcessPoolExecutor(max_workers=jobs, mp_context=ctx) as ex:
        futs = [ex.submit(_cell, b, s, flake) for b, s in pending]
        for fut in as_completed(futs):
            bname, stem, outcome, agreed, ms, err = fut.result()
            rows[stem][bname] = (outcome, agreed, ms, err)
            done += 1
            if done % 25 == 0:
                print(f"  {done}/{len(pending)} cells, "
                      f"{time.time() - t0:.0f}s", flush=True)
    return rows, cols


# ----------------------------------------------------------------- grading ---

# Outcomes that assert something about the theorem. Everything else (TIMEOUT,
# UNPROVED, MALFORMED, abstain, lower-error) is the kernel declining to
# answer, which SPEC.md's taxonomy and ROADMAP.md 10.1 both insist is NOT a
# refutation: "incompleteness must never be reported as refutation".
ASSERTIVE = (Outcome.VERIFIED, Outcome.REFUTED)
SILENT = (Outcome.TIMEOUT, Outcome.UNPROVED, Outcome.MALFORMED,
          Outcome.TOOL_ERROR, "abstain", "lower-error")


def grade(tasks, rows, cols):
    by_name = {t["name"]: t for t in tasks}
    present = [b for b, v in cols if not v.startswith("ABSENT")]
    per = {b: {"unsound": [], "unsound_construction": [], "overrefuted": [],
               "silent": [], "deadbranch": [], "flaked": [], "correct": 0}
           for b in present}
    for name, cells in rows.items():
        t = by_name[name]
        for b in present:
            c = cells.get(b)
            if c is None:
                continue
            outcome, agreed, _ms, err = c
            rec = per[b]
            if not agreed:
                rec["flaked"].append(name)
            if t["_truth"] == "false":
                if outcome == Outcome.VERIFIED:
                    key = ("unsound" if t["_basis"] == "witness"
                           else "unsound_construction")
                    rec[key].append(name)
                elif outcome == Outcome.REFUTED:
                    rec["correct"] += 1
                elif outcome == Outcome.VACUOUS and t["_family"] in (
                        "seq-len", "seq-elem") and name.count("reach"):
                    rec["deadbranch"].append(name)
                elif outcome in SILENT:
                    rec["silent"].append((name, outcome, err))
            else:
                if outcome == Outcome.VERIFIED:
                    rec["correct"] += 1
                elif outcome == Outcome.REFUTED:
                    rec["overrefuted"].append(name)
                elif outcome in SILENT:
                    rec["silent"].append((name, outcome, err))
                elif outcome == Outcome.VACUOUS:
                    rec["silent"].append((name, outcome, err))
    # The failure this wave exists for: a wrong verdict SHARED across kernels
    # is invisible to consensus grading, and a wrong MAJORITY would make a
    # consensus grader positively assert the wrong answer. Both are collected;
    # only the SPEC.md label decides which side is wrong.
    shared, majority = [], []
    for name, cells in rows.items():
        t = by_name[name]
        want = (Outcome.REFUTED if t["_truth"] == "false"
                else Outcome.VERIFIED)
        got = {b: cells[b][0] for b in present if b in cells}
        assertive = {b: o for b, o in got.items() if o in ASSERTIVE}
        if not assertive:
            continue
        wrong = [b for b, o in assertive.items() if o != want]
        if len(wrong) == len(assertive):
            shared.append((name, t["_truth"], got, wrong))
        elif len(wrong) * 2 > len(assertive):
            majority.append((name, t["_truth"], got, wrong))
    return per, shared, majority, present


def report(tasks, rows, cols, per, shared, majority, present, decided):
    by_name = {t["name"]: t for t in tasks}
    n_false = sum(1 for t in tasks if t["_truth"] == "false")
    n_true = len(tasks) - n_false
    out = []
    w = out.append
    w("# t boundary discrimination: unbounded against machine integers")
    w("")
    w("Truth is SPEC.md, not consensus. FALSE tasks are true only under a "
      "bounded model; a VERIFIED is an unsoundness. TRUE tasks need a value, "
      "an intermediate or a range outside a machine word; a REFUTED is the "
      "same disease from the other side.")
    w("")
    header = "| task | truth | basis | " + " | ".join(present) + " |"
    w(header)
    w("|" + "---|" * (len(present) + 3))
    for t in tasks:
        name = t["name"]
        cells = rows.get(name, {})
        row = [name, t["_truth"], t["_basis"].split(":")[0]]
        for b in present:
            c = cells.get(b)
            if c is None:
                row.append("\u2014")
            else:
                row.append(c[0] + ("" if c[1] else " (FLAKED)"))
        w("| " + " | ".join(row) + " |")
    w("")
    w("## Per kernel")
    for b in present:
        rec = per[b]
        ref_on_false = sum(1 for t in tasks
                           if t["_truth"] == "false"
                           and rows[t["name"]].get(b, ("",))[0]
                           == Outcome.REFUTED)
        ver_on_true = sum(1 for t in tasks
                          if t["_truth"] == "true"
                          and rows[t["name"]].get(b, ("",))[0]
                          == Outcome.VERIFIED)
        w("")
        w(f"### {b}")
        w(f"- correct: {rec['correct']} of {len(tasks)}")
        w(f"- discrimination: REFUTED {ref_on_false}/{n_false} known-false, "
          f"VERIFIED {ver_on_true}/{n_true} known-true. A column that "
          f"refutes no known-false task carries no falsity evidence here, "
          f"whatever it verifies.")
        if rec["unsound"]:
            w(f"- **UNSOUND (witnessed false, kernel VERIFIED)**: "
              f"{', '.join(rec['unsound'])}")
        if rec["unsound_construction"]:
            w(f"- **UNSOUND (false by construction, kernel VERIFIED)**: "
              f"{', '.join(rec['unsound_construction'])}")
        if rec["overrefuted"]:
            w(f"- REFUTED a task true by construction: "
              f"{', '.join(rec['overrefuted'])}")
        if rec["deadbranch"]:
            w(f"- VACUOUS on a reachability probe (the branch a bounded model "
              f"kills): {', '.join(rec['deadbranch'])}")
        if rec["silent"]:
            w("- declined to answer (not a refutation): "
              + ", ".join(f"{n} [{o}]" for n, o, _ in rec["silent"]))
        if rec["flaked"]:
            w(f"- FLAKED across runs: {', '.join(rec['flaked'])}")
    w("")
    w("## Shared errors: what consensus grading cannot see")
    if not shared:
        w("None: on every task at least one kernel that answered gave the "
          "SPEC.md answer.")
    for name, truth, got, wrong in shared:
        w(f"- `{name}` (known {truth.upper()}, wrong in {len(wrong)}/"
          f"{len(wrong)} answering kernels): "
          + ", ".join(f"{b}={o}" for b, o in got.items())
          + f": {by_name[name]['_why']}")
    w("")
    w("## Wrong majorities: where a consensus grader would assert the "
      "wrong answer")
    if not majority:
        w("None.")
    for name, truth, got, wrong in majority:
        w(f"- `{name}` (known {truth.upper()}; {', '.join(wrong)} wrong): "
          + ", ".join(f"{b}={o}" for b, o in got.items())
          + f": {by_name[name]['_basis']}")
    w("")
    w("## Coverage of the label guard")
    w("Known-true labels rest on construction alone. The sweep is a guard "
      "that can only refute one; this is how many domain points it actually "
      "decided per task, so 0 is read as 'not exercised', never as 'checked'.")
    for t in tasks:
        if t["_truth"] == "true":
            w(f"- {t['name']}: {decided.get(t['name'], 0)} points decided "
              f"of {SWEEP_POINTS} swept")
    w("")
    w("## Backends")
    for b, v in cols:
        w(f"- {b}: {v}")
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--jobs", type=int, default=None)
    ap.add_argument("--flake", type=int, default=3)
    ap.add_argument("--only", default=None,
                    help="comma-separated backend names")
    ap.add_argument("--tasks", default=None,
                    help="comma-separated task names")
    ap.add_argument("--check-only", action="store_true")
    a = ap.parse_args()

    tasks = corpus()
    errs, decided = check_labels(tasks)
    if errs:
        print("REFUSED: the label discipline failed on this file's own "
              "corpus. Every finding downstream would be worthless.")
        for e in errs:
            print(f"  {e}")
        return 2
    n_wit = sum(1 for t in tasks if t["_basis"] == "witness")
    n_true = sum(1 for t in tasks if t["_truth"] == "true")
    unexercised = [n for n, k in decided.items() if k == 0]
    print(f"{len(tasks)} tasks: {n_wit} known-FALSE labels confirmed by an "
          f"exhibited witness, {len(tasks) - n_wit - n_true} known-FALSE by "
          f"construction (no witness is representable), {n_true} known-TRUE "
          f"by construction.")
    print(f"label guard: {n_true} known-true tasks swept over "
          f"{SWEEP_POINTS} domain points with no violation"
          + (f"; {len(unexercised)} not exercised at all by the sweep "
             f"({', '.join(unexercised)}), their clauses exceed "
             f"interp.py's step cap, so the guard says nothing about them"
             if unexercised else ""))
    if a.check_only:
        return 0
    if a.tasks:
        keep = set(a.tasks.split(","))
        tasks = [t for t in tasks if t["name"] in keep]
    only = set(a.only.split(",")) if a.only else None
    jobs = a.jobs or max(1, os.cpu_count() or 1)
    rows, cols = run(tasks, a.out, jobs, a.flake, only)
    per, shared, majority, present = grade(tasks, rows, cols)
    text = report(tasks, rows, cols, per, shared, majority, present, decided)
    (a.out / "BOUNDARY.md").write_text(text, encoding="utf-8")
    (a.out / "boundary.json").write_text(json.dumps(
        {"flake": a.flake,
         "tasks": [{k: (list(v) if isinstance(v, tuple) else v)
                    for k, v in t.items() if k.startswith("_")}
                   | {"name": t["name"]} for t in tasks],
         "rows": {n: {b: list(c) for b, c in cells.items()}
                  for n, cells in rows.items()},
         "backends": dict(cols)}, indent=1, default=str), encoding="utf-8")
    print(text)
    bad = sum(len(per[b]["unsound"]) + len(per[b]["unsound_construction"])
              for b in present)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
