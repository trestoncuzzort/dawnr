#!/usr/bin/env python3
"""lower_spark.py: lower t v0/v1 tasks to SPARK 2014; the third kernel.

THE SEMANTIC DECISION, same doctrine as the Verus backend: t integers are
mathematical. Ada's Integer is a machine type with overflow, so lowering to it
would make `abs` unprovable at Integer'First and silently change what the
task means. Ada 2022's Big_Integer (Ada.Numerics.Big_Numbers.Big_Integers)
IS mathematical and gnatprove proves over it directly.

SHAPE (v1, measured 2026-08-31 on gnatprove FSF 16.1.0 before this rewrite):
GNAT's naming convention refuses a body in the single .ads file the t.spark
verifier writes (measured: "file can have only one compilation unit", "does
not contain unit (spec)", and pragma Source_File_Name is rejected under a
project). So EVERYTHING is a package spec of expression functions:

  * task body      -> one expression function F (statement lists are compiled
                      to expressions: assignments become substitution, `if`
                      becomes an if-expression merge of the branch outcomes);
  * while loops    -> one recursive helper function per loop, W_k over a
                      record of exactly the loop body's syntactic assigned
                      set (SPEC.md frame rule); in-scope names the body
                      never assigns stay plain parameters the caller keeps
                      its own values for. Loop invariants
                      become W_k's Pre AND Post (plus `not cond` in Post),
                      the loop's decreases becomes W_k's Subprogram_Variant.
                      That is the standard Hoare package, stated to the
                      kernel rather than assumed: invariant-on-entry is the
                      call-site Pre check, preservation is the recursive
                      call's Pre check, exit knowledge is Post.
  * recursion      -> F is a recursive expression function; the task-level
                      decreases becomes F's Subprogram_Variant.
  * spec_funs      -> recursive expression functions with their own
                      Subprogram_Variant.
  * seq            -> SPARK.Containers.Functional.Infinite_Sequences,
                      instantiated over Big_Integer (see THE SEQ MODEL).

VARIANTS: SPARK requires a Big_Integer Subprogram_Variant to be provably
nonnegative; t's decreases obligations only give >= 0 at the recursion/loop
step. Every variant is therefore wrapped (if D >= 0 then D else 0): still
well-founded, decreasing exactly when t's obligations hold, and measured to
prove where Big_Integers.Max blew the 20000-step budget.

THE SEQ MODEL, rewritten 2026-09-01 because the previous one was UNSOUND.
It was `type Seq is array (Positive range <>) of Big_Integer`, and an Ada
array index type is discrete and therefore bounded: S'Length <= Integer'Last
holds by typing, so the kernel was handed `len(s) <= 2^31-1` for free.
SPEC.md gives a seq only `len(s) >= 0`. MEASURED on the fuzzer's fz_p_seqlen
probe (ensures len(s) <= 2^31-1 with both branches live): spark VERIFIED it
while dafny, verus, lean, rocq and fstar REFUTED it, a false theorem, the
same disease as lower_framac.py's C int. The seq is now

    package Seqs is new SPARK.Containers.Functional.Infinite_Sequences
      (Element_Type => Big_Integer);

whose Length returns Big_Natural (no upper bound) and whose Get is indexed
by a Big_Integer position. Its private part is `pragma SPARK_Mode (Off)`, so
the prover sees the public axiomatization and nothing of the bounded
representation underneath: the emitted obligation is about sequences of
arbitrary mathematical length. len(s) >= 0, SPEC.md's one seq assumption,
comes from Length's own Big_Natural result subtype, not from an assumption
this lowering writes.

QUANTIFIERS: SPARK quantified expressions range over a discrete type or over
a type carrying the Iterable aspect, and Ada's discrete types are all
bounded. t quantifies over mathematical [lo, hi), so the range is lowered as
an Iterable record whose CURSOR IS Big_Integer:

    type T_Range is record Lo, Hi : Big_Integer; end record
      with Iterable => (First => R_First, Has_Element => R_Has,
                        Next  => R_Next);
    (for all K in T_Range'(lo, hi) => body)      -- `for some` for exists

gnatprove quantifies over the cursor type under R_Has, so this IS t's
quantifier over [lo, hi) with no machine slice and no bound to hoist.
MEASURED (2026-09-01, gnatprove FSF 16.1.0): `for all K in T_Range'(0, N) =>
K <= Integer'Last` with N unconstrained goes `medium: postcondition might
fail`, because the range is genuinely unbounded, while all_nonneg, contains,
count_matches, linear_search and seq_max still prove. This replaces the
previous `for all K in Integer` encoding and the hoisted `bounds_ok`
obligation it owed, and with them the four ABSTAIN paths that existed only
because a bounds obligation had nowhere sound to sit (quantifier in
requires, in a bound mentioning an enclosing bound variable, under a partial
`at` in a bound, in an executable/definitional position).

DEFINEDNESS: `and`/`or`/`implies` lower to `and then`/`or else`/if-
expressions, so SPEC.md's left-to-right definedness contexts land exactly on
GNATprove's own RTE-checking contexts; `at` lowers to `Elem (S, I)`, whose
own precondition `0 <= I and then I < Len (S)` is exactly t's definedness
side condition and is discharged by the kernel at every use. (Seqs.Get is
total in the shipped non-defensive SPARKlib build, and reading out of range
yields an unconstrained value, so the obligation must be, and is, stated on
the wrapper rather than borrowed from the library.)

DIV/MOD (2026-09-08, SPEC.md "Division and modulo"). MEASURED on this
install (probes p_euclid.ads, p_facts.ads, gnatprove FSF 16.1.0, Big_Integer
throughout): Ada's `/` truncates toward zero (-7/2 = -3, 7/-2 = -3, -7/-2 =
3, all proved), `mod` takes the sign of the divisor, i.e. floor-modulo
(-7 mod 2 = 1, 7 mod -2 = -1, -7 mod -2 = -1, all proved), and `rem` takes
the sign of the dividend (-7 rem 2 = -1, 7 rem -2 = 1, -7 rem -2 = -1, all
proved). None of the three is SPEC.md's Euclidean law (0 <= r < |y|) when
the divisor is negative, so native `/` and `mod` may not be emitted for t's
`div`/`mod`, exactly as the header's SHAPE section already forbids for `at`.
So, beside `Len` and `Elem`, this lowering defines two more expression
functions, `T_Mod` and `T_Div`, both with `Pre => Y /= Big_Integer'(0)`, over
`/` and `rem` rather than `mod`: `X = (X / Y) * Y + (X rem Y)` is a fact
GNATprove proves in one step (MEASURED, probe p_law1.ads), while the same
identity restated with `X mod abs (Y)` and a second division, the reading
that would follow directly from "mod against a positive divisor already IS
the Euclidean remainder", TIMES OUT (MEASURED, probe p_law2.ads, same shape,
only the operators differ) rather than failing to prove; that construction
was not shipped for exactly that reason. `X rem Y` already has magnitude
< |Y|, sign of the dividend; only its sign needs straightening to land in
`[0, |Y|)`, which needs no further division:

    T_Mod (X, Y) = if X rem Y >= 0 then X rem Y else (X rem Y) + abs (Y)
    T_Div (X, Y) = if X rem Y >= 0 then X / Y
                   elsif Y > 0 then (X / Y) - 1 else (X / Y) + 1

a nonnegative remainder is kept (it already satisfies the bound whatever
sign Y has); a negative one gains `abs (Y)` and the truncating quotient
steps by one toward -infinity to compensate, so the whole identity reduces
to linear arithmetic over `/`'s and `rem`'s own defining law and the kernel
proves it directly (MEASURED, probe p_law3.ads: the identity and both
Euclidean bounds verify). Definedness at y = 0 is discharged the same way as
`at`'s: the Pre is checked by the kernel at every call site, and `div`/`mod`
lower to `T_Div (a, b)` / `T_Mod (a, b)`, never to native `/`/`mod`/`rem`.
The counterexample mirror (F_Ce, below) does not cover div/mod: _ce_bound
has no case for them and raises its own `_NoCe`, so a task using div/mod
simply gets no F_Ce instance, the same abstention already applied to seq
ops, calls and quantifiers there; nothing about T_Div/T_Mod needs a
machine-int mirror to be sound, but a mirror was not built, and the
committed `remainder`/`digit_sum` cells are checked through F alone.

THE COUNTEREXAMPLE INSTANCE, added 2026-09-01 because the sound numeric model
above closed gnatprove's refutation channel completely: after the move to
Big_Integer the SPARK flip rate went 91.8% -> 0.0%. REPRODUCED before this
section was written: 0 flips on the 11 committed tasks (11 reals VERIFIED, 9
twins TIMEOUT and 2 UNPROVED, not one twin carrying a counterexample) and 0
flips on the 47 real-VERIFIED cells of a fresh 169-task generated corpus.

The cause is MEASURED, and it is not the budget and not the prover.
verifiers/spark.py rules REFUTED only on gnatprove severity "high", which for
a prover check means the counterexample was generated AND confirmed by
gnatprove's runtime assertion checker. Both halves fail on Big_Integer, for
two different reasons, both read off `gnatprove -d`'s own RAC verdict line:

  * a Big_Integer PARAMETER gets no value in the model,
    "Small-step: RES_INCOMPLETE, Reason: No counterexample value for program
    parameter x", so the abs twin carries no cntexmp field at all;
  * a Big_Integer EXPRESSION cannot be executed by the RAC,
    "Small-step: RES_INCOMPLETE, Reason: expr with private type", so even
    when every free variable is an Integer and the model IS built (probe
    p_ce1: `To_Big_Integer (X) >= 0`, cntexmp X = -1 present), the verdict
    stays NON_CONFORMITY_OR_SUBCONTRACT_WEAKNESS and severity stays "medium".
    The same file with the Big_Integer subexpression left unevaluated by
    short-circuit (probe p_ce2) reaches "VERDICT: NON_CONFORMITY" and "high".

Both are properties of the type being private with a SPARK_Mode (Off)
completion, which is what Big_Integer and the Infinite_Sequences containers
both are; a private type whose completion IS visible to SPARK (probe p_priv,
`type P is new Integer`) confirms normally. Budget and prover were measured
out: abs/max twins stay medium/gave_up at --steps 20000, 200000 and 1000000,
under --prover=z3, cvc5 and all, and at --level 0..4; the seq twins hit the
wall backstop at 1000000 before anything changes.

So the refutation cannot come from the unbounded theorem. It comes from a
SECOND subprogram in the same file: F_Ce, the same task instantiated at
machine-integer inputs with exact arithmetic.

  * SOUNDNESS OF VERIFIED is untouched: F over Big_Integer keeps its Post,
    and verifiers/spark.py refuses VERIFIED while any check is unproved. An
    extra obligation can only make a proof harder, never possible, measured
    on the boundary probes, which still resolve: fz_p_bigrange and
    fz_p_bigwide VERIFIED, fz_p_seqlen / fz_p_elemwidth / fz_p_biglen /
    fz_p_attotal not verified.
  * SOUNDNESS OF REFUTED is the instance being FAITHFUL: a machine integer is
    a t integer, so a counterexample to F_Ce is a counterexample to the task
    That holds provided the instance computed the same value t does. That holds iff no
    operation overflows, which is why the instance is emitted only when this
    file can bound every int-valued node of the task by construction:
    |parameter| <= 2^40 (CE_WINDOW) and every derived magnitude <= 2^100
    (CE_CAP), inside Long_Long_Long_Integer's 2^127. The bound is computed on
    t's own AST, over the SAME substitution walk `compile` performs, and any
    node it cannot bound, whether a loop, a call, recursion, a seq, a quantifier
    or an oversized literal, makes the instance not be emitted at all.
  * THE CHECK MUST ALSO BE CHEAP TO EXECUTE, because severity "high" is the
    RAC actually running it. MEASURED: the same shape with a quantifier over
    the window, `for all K in 0 .. 2**40`, reports
    "Small-step: RES_INCOMPLETE, Reason: out of fuel" and falls back to
    "medium", so a machine-typed quantifier would cost the refutation it was
    emitted to buy. Quantifiers are outside the fragment for that reason as
    much as for the bound.
  * AN UNPROVABLE OVERFLOW CHECK CANNOT BECOME A REFUTATION, which is the
    second line under the bound analysis: severity "high" is the small-step
    RAC having EXECUTED the check and seen it fail ("VERDICT: NON_CONFORMITY"
    above), so a check no concrete input can fail cannot reach it, and a bound
    the prover fails to see costs a proof, not a false countermodel.
    MEASURED both ways: X*X at |X| <= 2^40 proves and the cell VERIFIES;
    X*X*X is over CE_CAP, gets no instance, and the (genuinely false) task
    reports UNPROVED rather than a refutation this file could not stand
    behind.
  * INCOMPLETENESS STAYS INCOMPLETENESS: a task the instance cannot reach, or
    a twin whose only counterexamples lie above 2^40, still reports UNPROVED
    or TIMEOUT. The instance adds refutations; it never converts a failure to
    prove into one.

WHAT IT BOUGHT, MEASURED on one 169-task generated corpus (seed 1) and the 11
committed tasks, spark only, --steps 20000:
  * 64 of the 169 generated tasks are inside the fragment; the other 103
    lower to BYTE-IDENTICAL source with and without this section, so their
    verdicts are unchanged by construction, not by re-measurement. On the
    committed tasks the fragment holds abs and max; the other 9 carry loops,
    recursion or sequences.
  * over the whole corpus the flip rate went 0/116 -> 38/116 real-VERIFIED
    cells (32.8%); over the fragment, 0/47 -> 38/47 (80.9%). The 9 misses are
    twins whose own theorem is still true (a loose ensures), which no kernel
    can refute. Committed tasks: 0/11 -> 2/11, all 11 reals still VERIFIED.
  * NO false refutation appeared. Every real whose verdict changed went
    UNPROVED -> REFUTED, and all 14 are tasks the corpus's ground truth calls
    false: 12 fz_wrong, fz_v0loose_045, and the fz_p_bigneg / fz_p_intwidth
    probes, which spark now refutes alongside the other six kernels.
    fuzz_lower.py's own vs-truth and disagreement counts stay 0, and the new
    verdicts are stable over 3 repeats (verifiers.flake_check).

The instance's Pre is deliberately empty and the task's `requires` is folded
into its Post as an implication: a Pre unsatisfiable inside the 2^40 window
would raise VC_INCONSISTENT_PRE, which verifiers/spark.py rules VACUOUS on
the whole file, a wrong verdict bought from a construct that exists only to
carry a witness. `requires -> ensures` cannot be always-False here, because
the twin operators never touch `ensures` (harness.py) and the real proves it.

Ce_Num / Ce_Int / F_Ce cannot collide with a t identifier: cap() lowercases
everything after the first character, so no t name can reach a name with an
interior capital. (RESERVED clashes are checked case-insensitively since
10.8, because Ada resolves names case-insensitively: a t param named
r_first would capitalize to R_first and silently capture R_First.)

EARLY EXIT (SPEC.md, 2026-09-08, ROADMAP 12.7). `return Expr;` cannot become
an actual Ada `return` statement: everything in this file is an expression
function (SHAPE, above), and a full subprogram body -- statements, a loop,
`return` included -- is not a basic_declarative_item, so it cannot be given
directly in the package spec this file writes. MEASURED: a plain
`function F (...) is R : ...; begin ... return R; end F;` placed where an
expression function sits (probe t_probe1.ads) makes gnatprove refuse Phase 2
with "begin block not allowed in package spec" before a single VC is
generated. So `return` is lowered the same way everything else here is: by
substitution. Lower.compile_r is compile()'s return-aware twin, threading an
`esc`/`val` pair (an Ada boolean and the return name's value at that escape)
alongside the ordinary env; has_return() decides, per statement list,
whether compile() (unchanged) or compile_r runs, so a body without a
`return` anywhere -- every one of the 13 previously committed tasks --
lowers byte-for-byte as before. A loop whose body can return gets two extra
fields on its W_k state record, Esc and Ret, and its Post is weakened to
`(if W_k'Result.Esc then True else (invariants and then not cond))`: SPEC.md
says a return leaves the loop without owing the invariant at that point, and
this is that rule stated to the kernel. The task's `ensures` is still owed
at that exit like any other, but that obligation is F's own Post applied to
F'Result uniformly regardless of path, so it needs no separate restatement.
Definedness is inherited for free: a return's expression goes through the
same self.expr() an assignment's right-hand side does, so Elem/T_Div/T_Mod's
Pre checks land at the same call sites either way.

THE REFUTATION CERTIFICATE (10.8, 2026-09-02). The instance above recovered
abs and max; the other nine committed twins stayed verified/timeout, and
the cause was REPRODUCED before this section was written: every one is a
VC_POSTCONDITION at severity medium, unproved_status "limit", at --steps
20000 under the full counterexample flags, and the bundled portfolio
(--prover=cvc5, altergo, z3,cvc5,altergo) and a tenfold budget (--steps
200000) were measured to change nothing on sum_upto and factorial: no
countermodel is ever BUILT over the private Big_Integer model, whatever the
budget. What the kernel cannot FIND it can still CHECK. The harness already
measured a violating witness (harness.twin_for), and run_task hands it to
this lowering at every twin call; certificate() restates that witness as
one ground goal named T_Refutation_Certificate, and verifiers/spark.py
mints REFUTED exactly when gnatprove discharges every check of that
function (see CERT_ENTITY there for the audit rule and its fail-closed
sides: a rejected certificate is UNPROVED, never REFUTED, and a file
carrying the name can never mint VERIFIED).

Two witness kinds are certificatable here, and the goal is in both cases
the negation of the obligation the witness was measured against:

  * "value": requires at the input, and then not (ensures at F(input)).
    F is the file's own twin F, an expression function, so its defining
    axiom pins F(input) to the twin's computed value and the goal holds
    exactly when that value falsifies the ensures. Emitted only when the
    witness records _ens true: a twin value that merely differs can still
    satisfy a loose ensures, and a goal known false is not an instrument.
  * "exit": requires, and then the surviving invariants at the state, and
    then not cond, and then not ensures, every variable a literal. This is
    the exit-entailment instance interp.invariant_witness measured
    (admissibility included): a state the survivors admit, at the loop's
    exit, where the theorem fails. The survivors come from the twin body's
    own loop, so the certificate weakens nothing itself; it is emitted
    only when the twin body has exactly one loop.

"undefined" and "preservation" witnesses are not certificated (fail
closed; certificate() says why), and neither is any witness the lowering
cannot express: those cells honestly keep the kernel's own verdict.

MEASURED (2026-09-02, gnatprove FSF 16.1.0, --steps 20000, --prover=z3):
all nine certificates discharge in seconds at the standard budget, seq
literals, ground quantifier instances and empty-range cases included, and
the committed column went 2/11 -> 11/11 flips with every real lowering
still VERIFIED, stable over 3 repeats (verifiers.flake_check). Soundness
probes, same day: the certificate name planted in a real program without
goals demotes it to UNPROVED; a false certificate is rejected (UNPROVED,
never REFUTED); a kernel-accepted certificate planted in a real program
demotes it to REFUTED (a demotion is the intended worst case, never a
pass); the name in a comment is inert, exactly like the ban scan.
"""
from __future__ import annotations

import re

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import harness                                   # noqa: E402
import interp                                    # noqa: E402
from verifiers import spark as spark_backend     # noqa: E402

TYPE = {"int": "Big_Integer", "bool": "Boolean", "seq": "Seq"}
CMP = {"==": "=", "!=": "/=", "<": "<", "<=": "<=", ">": ">", ">=": ">="}
ARITH = {"+": "+", "-": "-", "*": "*"}
DIVMOD = {"div": "T_Div", "mod": "T_Mod"}
NARY = {"and": "and then", "or": "or else"}

# Every Ada name this file puts in the emitted package. A t identifier that
# capitalizes onto one of them would be captured silently, so lower() refuses
# instead (the W_k helpers are checked separately, by count).
RESERVED = frozenset((
    "F", "Seq", "Seqs", "Len", "Elem", "T_Range", "R_First", "R_Has",
    "R_Next", "Big_Integer", "Boolean", "T_Refutation_Certificate",
    "T_Div", "T_Mod"))

# The counterexample instance (header). The window is above 2^31 so that a
# lowering which had silently kept a 32-bit model would be caught by the
# instance too (fz_p_intwidth, fz_p_bigneg), and the cap leaves 27 bits of
# headroom under Long_Long_Long_Integer'Last = 2^127 - 1.
CE_WINDOW_BITS = 40
CE_WINDOW = 2 ** CE_WINDOW_BITS
CE_CAP = 2 ** 100
CE_TYPE = {"int": "Ce_Int", "bool": "Boolean"}       # parameter types
CE_RET = {"int": "Ce_Num", "bool": "Boolean"}        # result type: unwindowed
CE_PREAMBLE = f"""\
   --  The task at machine inputs with exact arithmetic: gnatprove's RAC
   --  cannot execute a Big_Integer expression, so F above can never carry a
   --  confirmed counterexample (header). Every magnitude here is bounded by
   --  construction, so a counterexample to F_Ce is a counterexample to the
   --  task itself.
   subtype Ce_Num is Long_Long_Long_Integer;
   subtype Ce_Int is Ce_Num range -2**{CE_WINDOW_BITS} .. 2**{CE_WINDOW_BITS};
"""


class _NoCe(Exception):
    """The task is outside the instance's reach; emit no instance. Never a
    lowering failure; the unbounded theorem is unaffected."""


def _ce_cap(n: int) -> int:
    if n > CE_CAP:
        raise _NoCe(f"magnitude bound 2^{n.bit_length()} exceeds the "
                    f"instance's headroom")
    return n


def _ce_max(a, b):
    """Join two branch bounds. None is a bool-valued branch; a task where one
    branch is bool and the other is not is not well typed, and is refused
    rather than instantiated on a guess."""
    if a is None and b is None:
        return None
    if a is None or b is None:
        raise _NoCe("branches of an `if` disagree on type")
    return max(a, b)


_UNSET = object()


def _ce_bound(e: dict, env: dict):
    """An upper bound on |value| for an int-valued node, None for a
    bool-valued one. Every int-valued subnode is bounded on the way down, so
    an overflowing intermediate refuses the instance even when the node above
    it would have fit."""
    if "int" in e:
        return _ce_cap(abs(int(e["int"])))
    if "bool" in e:
        return None
    if "var" in e:
        b = env.get(e["var"], _UNSET)
        if b is _UNSET:
            raise _NoCe(f"read of unassigned {e['var']!r}")
        return b
    if "forall" in e or "exists" in e:
        raise _NoCe("quantifier: the range is mathematical, not machine")
    if "ite" in e:
        c = e["ite"]
        _ce_bound(c["cond"], env)
        return _ce_max(_ce_bound(c["then"], env), _ce_bound(c["else"], env))
    if "call" in e:
        raise _NoCe("call: a spec fun or recursion has no static bound")
    op = e["op"]
    if op in ("len", "at"):
        raise _NoCe("seq operator")
    if op in ("div", "mod"):
        # No machine mirror (header, DIV/MOD): T_Div/T_Mod are Big_Integer
        # expression functions, so F_Ce (Ce_Num inputs) could not call them
        # even if a bound existed. Abstain, the same fail-closed treatment
        # already given to seq ops, calls and quantifiers here.
        raise _NoCe(f"{op!r}: no machine mirror for T_Div/T_Mod")
    bs = [_ce_bound(a, env) for a in e.get("args", [])]
    if op in ("not", "and", "or", "implies") or op in CMP:
        return None
    if any(b is None for b in bs):
        raise _NoCe(f"{op!r} over a bool-valued operand")
    if op == "neg":
        return bs[0]
    if op in ("+", "-"):
        return _ce_cap(bs[0] + bs[1])
    if op == "*":
        return _ce_cap(bs[0] * bs[1])
    raise _NoCe(f"operator {op!r}")


def _ce_stmts(stmts: list, env: dict) -> dict:
    """The bound walk over statements, mirroring Lower.compile's substitution
    exactly: a branch-local declaration is invisible after the `if`, and the
    join is over the variables that were in scope before it."""
    env = dict(env)
    for s in stmts:
        if "assign" in s:
            v, e = s["assign"]
            if v not in env:
                raise _NoCe(f"assign to undeclared {v!r}")
            env[v] = _ce_bound(e, env)
        elif "var" in s:
            d = s["var"]
            env[d["name"]] = _ce_bound(d["init"], env)
        elif "if" in s:
            c = s["if"]
            _ce_bound(c["cond"], env)
            et = _ce_stmts(c["then"], env)
            ee = _ce_stmts(c["else"], env)
            for v in list(env):
                if et[v] is _UNSET and ee[v] is _UNSET:
                    continue           # still unassigned on both sides
                if et[v] is _UNSET or ee[v] is _UNSET:
                    raise _NoCe(f"{v!r} assigned on only one branch")
                env[v] = _ce_max(et[v], ee[v])
        elif "while" in s:
            raise _NoCe("while loop: no static bound on the accumulated value")
        elif "return" in s:
            # SPEC.md "Early exit" (2026-09-08): no machine mirror. F_Ce is
            # one expression function with no way to stop partway through,
            # so a task that can return early gets no instance, the same
            # fail-closed treatment already given to loops, calls, seq ops
            # and quantifiers above.
            raise _NoCe("return: no machine mirror for early exit")
        else:
            raise _NoCe(f"statement {sorted(s)!r}")
    return env


SEQ_PREAMBLE = """\
   package Seqs is new SPARK.Containers.Functional.Infinite_Sequences
     (Element_Type => Big_Integer);
   subtype Seq is Seqs.Sequence;

   --  len(s): Big_Natural, so `len(s) >= 0` (SPEC.md's one seq assumption)
   --  is the library's result subtype and nothing bounds it above.
   function Len (S : Seq) return Big_Integer is (Seqs.Length (S));

   --  at(s, i): the Pre IS SPEC.md's definedness side condition, discharged
   --  by the kernel at every use. Seqs.Get is total in the shipped
   --  non-defensive SPARKlib build, so it cannot be borrowed from there.
   function Elem (S : Seq; I : Big_Integer) return Big_Integer is
     (Seqs.Get (S, I + Big_Integer'(1)))
   with Pre => I >= Big_Integer'(0) and then I < Len (S);
"""

# A t quantifier ranges over mathematical [lo, hi). Ada's discrete types are
# all bounded, so the range is a cursor-iterable whose cursor is Big_Integer;
# gnatprove quantifies over the cursor type under R_Has. R_Next's V is unused
# (flow reports UNUSED_VARIABLE at severity "warning", which the adapter's
# audit tolerates); writing a V-dependent body to silence it would put an
# arm in the iteration model that nothing measures.
RANGE_PREAMBLE = """\
   type T_Range is record
      Lo : Big_Integer;
      Hi : Big_Integer;
   end record
   with Iterable => (First       => R_First,
                     Has_Element => R_Has,
                     Next        => R_Next);

   function R_First (V : T_Range) return Big_Integer is (V.Lo);
   function R_Has (V : T_Range; C : Big_Integer) return Boolean is
     (C >= V.Lo and then C < V.Hi);
   function R_Next (V : T_Range; C : Big_Integer) return Big_Integer is
     (C + Big_Integer'(1));
"""

# div/mod (see the header's DIV/MOD section). Built on `/` and `rem`, not
# `mod`: `X = (X / Y) * Y + (X rem Y)` is the pair GNATprove proves in one
# step (MEASURED, probe p_law1.ads), while the same fact stated over
# `X mod abs (Y)` and a second division (the naive reading of "mod against a
# positive divisor is the Euclidean remainder") TIMES OUT at the standard
# budget (MEASURED, probe p_law2.ads: VC_POSTCONDITION medium/limit, same
# shape, only the operators differ) rather than failing to prove; a tenfold
# budget was not tried because the fix costs nothing. `X rem Y` already has
# magnitude < |Y|; only its sign needs straightening to land in [0, |Y|):
# nonnegative, keep it (it already satisfies SPEC.md's bound whatever sign Y
# has); negative, add |Y| to the remainder and correspondingly step the
# truncating quotient by one toward -infinity. No further division is ever
# introduced, so the identity is linear arithmetic over `/`'s and `rem`'s own
# defining law, which the prover discharges directly (MEASURED, probe
# p_law3.ads: the identity and both Euclidean bounds verify).
DIVMOD_PREAMBLE = """\
   function T_Mod (X, Y : Big_Integer) return Big_Integer is
     (if (X rem Y) >= Big_Integer'(0)
      then (X rem Y)
      else (X rem Y) + abs (Y))
   with Pre => Y /= Big_Integer'(0);

   function T_Div (X, Y : Big_Integer) return Big_Integer is
     (if (X rem Y) >= Big_Integer'(0)
      then (X / Y)
      elsif Y > Big_Integer'(0)
      then (X / Y) - Big_Integer'(1)
      else (X / Y) + Big_Integer'(1))
   with Pre => Y /= Big_Integer'(0);
"""


def cap(name: str) -> str:
    """The Ada spelling of a t name. Ada identifiers may not carry two
    underscores in a row or end in one, and the lifter's file-qualified task
    names do (clover_abs__abs, measured 2026-09-06: gnatprove refused every
    lifted task at the package name). A run of k >= 2 underscores becomes
    `_` + "x" * (k - 1) + `_`, a trailing underscore gains an `x`, and
    `lower` abstains when two distinct t names meet after this mapping, so
    a rename is never silently a capture. Names without such runs are
    unchanged, so every committed task's Ada text is byte-identical."""
    name = _ADA_RUN.sub(lambda m: "_" + "x" * (len(m.group()) - 1) + "_", name)
    if name.endswith("_"):
        name += "x"
    return name.capitalize()


_ADA_RUN = re.compile(r"_{2,}")


# --- name capture ----------------------------------------------------------

def bound_names(task: dict, body: list) -> set:
    """Every t identifier the emitted package will capitalize into an Ada
    name: params, returns, locals, spec_fun names and their params, and
    quantifier bound variables."""
    out = set()

    def go(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in ("var", "name", "fun") and isinstance(v, str):
                    out.add(v)
                elif k in ("forall", "exists") and isinstance(v, dict):
                    out.add(v.get("var"))
                go(v)
        elif isinstance(x, list):
            for v in x:
                go(v)

    go(task)
    go(body)
    return {n for n in out if isinstance(n, str)}


def loop_assigned(body: list) -> set:
    """Syntactic assigned set of a loop body, SPEC.md's frame rule: a while
    loop havocs exactly the variables assigned in its body. A `return`
    (SPEC.md "Early exit", 2026-09-08) assigns its target exactly like an
    `assign` does before ending the task, and interp.assigned() already
    counts it that way; matched here so the target becomes a field of the
    loop's own state record (see lower_while's body_has_return path)."""
    out: set = set()
    for s in body:
        if "assign" in s:
            out.add(s["assign"][0])
        elif "return" in s:
            out.add(s["return"][0])
        elif "if" in s:
            out |= loop_assigned(s["if"]["then"])
            out |= loop_assigned(s["if"]["else"])
        elif "while" in s:
            out |= loop_assigned(s["while"]["body"])
    return out


def _dead_lit(t: str) -> str:
    """A well-typed placeholder Ada literal for a state var this file lets
    into a loop's call site unassigned (SPEC.md "Early exit": the return
    target, when nothing before the loop ever set it). Never read for its
    value; only its type has to line up."""
    return {"int": "Big_Integer'(0)", "bool": "False",
           "seq": "Seqs.Empty_Sequence"}[t]


def has_return(body: list) -> bool:
    """Whether `body` can reach a `return` statement at any depth (SPEC.md
    "Early exit", 2026-09-08), mirroring the same recursive shape as
    loop_assigned/interp.assigned(). Drives the return-aware statement
    lowering below (Lower.compile_r, lower_while's body_has_return path): a
    body with no `return` anywhere keeps compile()/lower_while() exactly as
    they were before this note, byte-for-byte."""
    for s in body:
        if "return" in s:
            return True
        if "if" in s and (has_return(s["if"]["then"])
                          or has_return(s["if"]["else"])):
            return True
        if "while" in s and has_return(s["while"]["body"]):
            return True
    return False


class Lower:
    def __init__(self, task: dict, ce: bool = False):
        self.task = task
        self.helpers: list[str] = []   # emitted W_k record types + functions
        self.wcount = 0
        self.needs_range = False       # set by the first lowered quantifier
        self.needs_divmod = False      # set by the first lowered div/mod
        self.spec_fun_names = {sf["name"] for sf in task.get("spec_funs", [])}
        # The counterexample instance walks the SAME tree with the SAME
        # operator table; only the numeric type of a literal differs, so a
        # transcription slip cannot make the instance disagree with the
        # theorem it instantiates (header).
        self.num = "Ce_Num" if ce else "Big_Integer"

    # --- expressions -------------------------------------------------------

    def expr(self, e: dict, sub: dict) -> str:
        if "int" in e:
            # Qualified: a bare literal fails resolution where both operands
            # of an operator are literal-bearing (measured: "expected type
            # universal integer" on count_matches), and the qualified form
            # keeps the Big_Integer literal aspect for arbitrary magnitude.
            return f"{self.num}'({e['int']})"
        if "bool" in e:
            return "True" if e["bool"] else "False"
        if "var" in e:
            v = e["var"]
            if v not in sub:
                raise ValueError(f"unbound variable {v!r}")
            if sub[v] is None:
                raise ValueError(f"read of unassigned {v!r}")
            return sub[v]
        if "forall" in e or "exists" in e:
            self.needs_range = True
            q = e["forall"] if "forall" in e else e["exists"]
            v = cap(q["var"])
            lo, hi = self.expr(q["lo"], sub), self.expr(q["hi"], sub)
            # The cursor IS the mathematical bound variable: T_Range's cursor
            # type is Big_Integer, so [lo, hi) is not sliced to a machine type
            # and there is no range obligation to owe (see the header).
            body = self.expr(q["body"], {**sub, q["var"]: v})
            kind = "for all" if "forall" in e else "for some"
            return f"({kind} {v} in T_Range'({lo}, {hi}) => {body})"
        if "ite" in e:
            c = e["ite"]
            return (f"(if {self.expr(c['cond'], sub)} "
                    f"then {self.expr(c['then'], sub)} "
                    f"else {self.expr(c['else'], sub)})")
        if "call" in e:
            c = e["call"]
            fun = "F" if c["fun"] == self.task["name"] else cap(c["fun"])
            if c["fun"] != self.task["name"] \
                    and c["fun"] not in self.spec_fun_names:
                raise ValueError(f"call to unknown function {c['fun']!r}")
            args = [self.expr(a, sub) for a in c["args"]]
            return f"{fun} ({', '.join(args)})" if args else fun
        op = e["op"]
        args = [self.expr(a, sub) for a in e.get("args", [])]
        if op == "len":
            return f"Len ({args[0]})"
        if op == "at":
            s, i = args
            return f"Elem ({s}, {i})"
        if op == "neg":
            return f"(-{args[0]})"
        if op == "not":
            return f"(not {args[0]})"
        if op == "implies":
            return f"(if {args[0]} then {args[1]} else True)"
        if op in NARY:
            return "(" + f" {NARY[op]} ".join(args) + ")"
        if op in CMP:
            return f"({args[0]} {CMP[op]} {args[1]})"
        if op in ARITH:
            return f"({args[0]} {ARITH[op]} {args[1]})"
        if op in DIVMOD:
            # Never native `/`/`mod` (header, DIV/MOD): both are wrong for a
            # negative divisor. T_Div/T_Mod's shared Pre => Y /= 0 is
            # SPEC.md's definedness obligation, checked at this call site
            # exactly as Elem's Pre discharges `at`.
            self.needs_divmod = True
            return f"{DIVMOD[op]} ({args[0]}, {args[1]})"
        raise ValueError(f"t has no operator {op!r}")

    # clause() and req_clause() are gone with the machine-Integer quantifier
    # encoding they served: T_Range carries no bounds obligation to hoist, so
    # every position (requires included) is just expr(). The four ABSTAIN
    # paths that guarded the hoist are gone with it; see the header.

    # --- statements --------------------------------------------------------

    def compile(self, stmts: list, env: dict, types: dict,
                psub: dict) -> dict:
        env, types = dict(env), dict(types)
        for s in stmts:
            if "assign" in s:
                v, e = s["assign"]
                if v not in env:
                    raise ValueError(f"assign to undeclared {v!r}")
                env[v] = self.expr(e, {**psub, **env})
            elif "var" in s:
                d = s["var"]
                env[d["name"]] = self.expr(d["init"], {**psub, **env})
                types[d["name"]] = d["type"]
            elif "if" in s:
                c = s["if"]
                cond = self.expr(c["cond"], {**psub, **env})
                et = self.compile(c["then"], env, types, psub)
                ee = self.compile(c["else"], env, types, psub)
                for v in env:
                    if et[v] == ee[v]:
                        env[v] = et[v]
                    elif et[v] is None or ee[v] is None:
                        raise NotImplementedError(
                            f"spark: {v!r} assigned on only one branch of an "
                            f"`if` and read later; no join value")
                    else:
                        env[v] = f"(if {cond} then {et[v]} else {ee[v]})"
            elif "while" in s:
                env = self.lower_while(s["while"], env, types, psub)
            elif "return" in s:
                # SPEC.md "Early exit" (2026-09-08). compile() is the
                # ORIGINAL, non-return-aware statement compiler: `lower()`
                # and lower_while() route any body has_return() finds a
                # `return` in through compile_r below instead, so a
                # `return` reaching here would be a routing bug, not a
                # task shape compile() should ever try to interpret.
                raise NotImplementedError(
                    "spark: return statement reached compile(); "
                    "has_return()-routing should have used compile_r")
            else:
                raise ValueError(f"unknown statement {sorted(s)!r}")
        return env

    # compile_r() is compile()'s return-aware twin (SPEC.md "Early exit",
    # 2026-09-08, ROADMAP 12.7). Only called on a statement list has_return()
    # finds a `return` in, from lower() at the task's top level and from
    # lower_while() for a loop whose own body can return; every other body
    # keeps compile()/lower_while() exactly as they read before this note,
    # byte-for-byte, since neither is touched by anything below.
    #
    # A `return` cannot become an actual Ada `return` statement: everything
    # this file emits is an expression function (SHAPE, header), and a full
    # subprogram body (statements, a loop, `return`) is not a
    # basic_declarative_item, so it cannot be given directly in the package
    # spec this file writes. MEASURED (2026-09-08, probe t_probe1.ads: a
    # plain `function F (...) is R : ...; begin ... return R; end F;` right
    # where an expression function sits): gnatprove refuses Phase 2 with
    # "begin block not allowed in package spec" before a single VC is even
    # generated. So `return` is lowered the same way everything else here
    # is: by substitution, threading one more pair of facts alongside the
    # ordinary env -- `esc`, an Ada boolean expression (None standing for
    # the literal False) that is true exactly when some execution of the
    # statement list reached a `return`, and `val`, the Ada expression for
    # the return name's value at that escape (defined whenever esc is not
    # None). A `return`'s own target is folded into env exactly like an
    # assign's, so downstream code that is not itself escape-aware (a
    # later `if` merge, a recursive call's arguments) reads an ordinary
    # substitution and stays correct: it is simply describing "the value
    # under the hypothesis nothing escaped", which is exactly what a
    # non-escaping continuation needs, and is discarded wherever an escape
    # is live (lower_while's Esc branch, lower()'s final (if esc then val
    # else env[ret]) merge) in favour of `val`.
    def compile_r(self, stmts: list, env: dict, types: dict, psub: dict,
                  ret_name: str):
        env, types = dict(env), dict(types)
        esc = None
        val = None

        def combine(local_esc, local_val):
            nonlocal esc, val
            if esc is None:
                esc, val = local_esc, local_val
            elif local_esc is not None:
                val = f"(if {esc} then {val} else {local_val})"
                esc = f"({esc} or else {local_esc})"
            # local_esc is None: this statement never escapes, so whatever
            # esc/val already stand (from earlier in the same list) are
            # unaffected.

        for s in stmts:
            if "assign" in s:
                v, e = s["assign"]
                if v not in env:
                    raise ValueError(f"assign to undeclared {v!r}")
                env[v] = self.expr(e, {**psub, **env})
            elif "return" in s:
                name, e = s["return"]
                new_val = self.expr(e, {**psub, **env})
                env[name] = new_val
                combine("True", new_val)
            elif "var" in s:
                d = s["var"]
                env[d["name"]] = self.expr(d["init"], {**psub, **env})
                types[d["name"]] = d["type"]
            elif "if" in s:
                c = s["if"]
                cond = self.expr(c["cond"], {**psub, **env})
                default = env.get(ret_name)
                et, esc_then, val_then = self.compile_r(
                    c["then"], env, types, psub, ret_name)
                ee, esc_else, val_else = self.compile_r(
                    c["else"], env, types, psub, ret_name)
                for v in env:
                    if et[v] == ee[v]:
                        env[v] = et[v]
                    elif et[v] is None or ee[v] is None:
                        raise NotImplementedError(
                            f"spark: {v!r} assigned on only one branch of "
                            f"an `if` and read later; no join value")
                    else:
                        env[v] = f"(if {cond} then {et[v]} else {ee[v]})"
                if esc_then is None and esc_else is None:
                    local_esc, local_val = None, None
                else:
                    then_e = esc_then if esc_then is not None else "False"
                    else_e = esc_else if esc_else is not None else "False"
                    local_esc = f"(if {cond} then {then_e} else {else_e})"
                    then_v = val_then if esc_then is not None else default
                    else_v = val_else if esc_else is not None else default
                    local_val = f"(if {cond} then {then_v} else {else_v})"
                combine(local_esc, local_val)
            elif "while" in s:
                env, wesc, wval = self.lower_while(
                    s["while"], env, types, psub, ret_name)
                combine(wesc, wval)
            else:
                raise ValueError(f"unknown statement {sorted(s)!r}")
        return env, esc, val

    def lower_while(self, w: dict, env: dict, types: dict,
                    psub: dict, ret_name: str | None = None):
        """Lower one while loop to its W_k helper. `ret_name` is None for
        every call site compile() makes (the original, non-return-aware
        shape, returned as a plain env dict, unchanged since before SPEC.md
        "Early exit"); compile_r() always passes the task's return name, and
        gets back (env, esc, val) instead -- esc/val are None/None when
        THIS loop's own body (body_has_return below) has no return in it,
        exactly mirroring compile_r's own convention."""
        if "decreases" not in w:
            raise ValueError("while without a decreases clause")
        self.wcount += 1
        name, tname = f"W_{self.wcount}", f"W_{self.wcount}_State"
        state = list(env.keys())
        body_has_return = ret_name is not None and has_return(w["body"])
        for v in state:
            if env[v] is None:
                if body_has_return and v == ret_name:
                    # The return target may be genuinely unassigned before
                    # the loop (SPEC.md "Early exit": first_even, is_prime
                    # both reach their while with `r` never yet assigned).
                    # No invariant or Pre/Post above ever mentions it here
                    # (a loop's own contract is stated over the state it
                    # HAVOCS, and nothing upstream could have constrained a
                    # name nothing has touched yet), so entry has no fact to
                    # lose by treating it as a normal (if unconstrained)
                    # state field instead of refusing the loop outright.
                    continue
                raise NotImplementedError(
                    f"spark: loop reached with {v!r} unassigned; the state "
                    f"record has no value for it")
        # SPEC.md frame rule: the loop havocs exactly the syntactic assigned
        # set of its body. Only those variables become record fields of the
        # helper's result; every other in-scope name stays a plain parameter
        # the helper passes through unchanged, and the caller keeps its own
        # value for it. (Before 2026-09-02 the record held ALL of env, and
        # the Post said only invariants + not guard about it, the
        # havoc-everything theorem: fr_probe_ret / fr_probe_local went
        # TIMEOUT here while Dafny, Verus and Frama-C proved them.) A
        # `return`'s target counts as assigned here too (loop_assigned,
        # 2026-09-08), so it becomes a state field exactly when the body can
        # actually set it.
        hav = loop_assigned(w["body"])
        mut = [v for v in state if v in hav]
        if not mut:
            raise NotImplementedError(
                "spark: loop body assigns nothing in scope; an empty state "
                "record is not lowerable")
        tparams = self.task["params"]
        plist = [f"{cap(p['name'])} : {TYPE[p['type']]}" for p in tparams] \
            + [f"{cap(v)} : {TYPE[types[v]]}" for v in state]
        entry = {**psub, **{v: cap(v) for v in state}}
        result = {**psub,
                  **{v: (f"{name}'Result.{cap(v)}" if v in mut else cap(v))
                     for v in state}}
        invs = w.get("invariants", [])
        pre = "\n       and then ".join(self.expr(i, entry) for i in invs)
        post_parts = [self.expr(i, result) for i in invs]
        post_parts.append(f"(not {self.expr(w['cond'], result)})")
        post = "\n       and then ".join(post_parts)
        d = self.expr(w["decreases"], entry)
        variant = f"(if {d} >= 0 then {d} else 0)"
        inner = {v: cap(v) for v in state}
        if body_has_return:
            benv, besc, bval = self.compile_r(
                w["body"], inner, types, psub, ret_name)
        else:
            benv = self.compile(w["body"], inner, types, psub)
            besc = bval = None
        cond = self.expr(w["cond"], {**psub, **inner})
        rec_args = [cap(p["name"]) for p in tparams] \
            + [benv[v] for v in state]
        agg = ", ".join(f"{cap(v)} => {cap(v)}" for v in mut)
        sig = f"function {name} ({'; '.join(plist)}) return {tname}"
        aspects = []
        if pre:
            aspects.append(f"Pre  => {pre}")
        if body_has_return:
            # SPEC.md "Early exit": a return inside the loop leaves it
            # without owing the invariant at that point. The task's own
            # `ensures` is still owed at that exit, like any other, but
            # that obligation sits on F's Post (lower(), below), which
            # applies uniformly to F'Result whichever path produced it;
            # nothing here needs to restate it.
            aspects.append(
                f"Post => (if {name}'Result.Esc then True else ({post}))")
        else:
            aspects.append(f"Post => {post}")
        aspects.append(f"Subprogram_Variant => (Decreases => {variant})")
        ret_type = TYPE[self.task["returns"][0]["type"]]
        if body_has_return:
            fields = "\n".join(f"      {cap(v)} : {TYPE[types[v]]};"
                               for v in mut)
            fields += f"\n      Esc : Boolean;\n      Ret : {ret_type};"
            esc_fields = ", ".join(f"{cap(v)} => {benv[v]}" for v in mut)
            base_case = (f"{tname}'({agg}, Esc => False, "
                        f"Ret => {cap(ret_name)})")
            recurse_or_escape = (
                f"(if {besc}\n"
                f"         then {tname}'({esc_fields}, Esc => True, "
                f"Ret => {bval})\n"
                f"         else {name} ({', '.join(rec_args)}))")
            body_expr = (f"(if {cond}\n"
                        f"        then {recurse_or_escape}\n"
                        f"        else {base_case})")
        else:
            fields = "\n".join(f"      {cap(v)} : {TYPE[types[v]]};"
                               for v in mut)
            body_expr = (f"(if {cond}\n"
                        f"        then {name} ({', '.join(rec_args)})\n"
                        f"        else {tname}'({agg}))")
        self.helpers.append(
            f"   type {tname} is record\n{fields}\n   end record;\n"
            f"\n"
            f"   {sig}\n"
            f"   with\n     " + ",\n     ".join(aspects) + ";\n"
            f"\n"
            f"   {sig}\n"
            f"   is ({body_expr});\n")
        # A state var may still be Python None here: the pre-check above lets
        # exactly the unassigned return-target case through (SPEC.md "Early
        # exit"), so it needs a placeholder Ada value for the call site --
        # dead on arrival, since nothing upstream constrains or reads it
        # before the loop assigns (or returns) it for real.
        out_args = [cap(p["name"]) for p in tparams] \
            + [(env[v] if env[v] is not None else _dead_lit(types[v]))
               for v in state]
        call = f"{name} ({', '.join(out_args)})"
        out_env = {v: (f"{call}.{cap(v)}" if v in mut else env[v])
                  for v in state}
        if ret_name is None:
            return out_env
        if body_has_return:
            return out_env, f"{call}.Esc", f"{call}.Ret"
        return out_env, None, None

    # --- spec_funs ---------------------------------------------------------

    def lower_spec_fun(self, sf: dict) -> str:
        sub = {p["name"]: cap(p["name"]) for p in sf["params"]}
        d = self.expr(sf["decreases"], sub)
        plist = "; ".join(f"{cap(p['name'])} : {TYPE[p['type']]}"
                          for p in sf["params"])
        sig = f"function {cap(sf['name'])} ({plist}) return " \
              f"{TYPE[sf['result']]}"
        return (f"   {sig}\n"
                f"   with Subprogram_Variant => "
                f"(Decreases => (if {d} >= 0 then {d} else 0));\n"
                f"\n"
                f"   {sig} is\n"
                f"     ({self.expr(sf['body'], sub)});\n")


CERT_NAME = "T_Refutation_Certificate"


def _cert_lit(v) -> str:
    """One witness value as ground Ada text. Types are read off the JSON
    value itself (bool before int: a Python bool is an int), so the literal
    cannot disagree with what interp.py measured."""
    if isinstance(v, bool):
        return "True" if v else "False"
    if isinstance(v, list):
        out = "Seqs.Empty_Sequence"
        for x in v:
            out = f"Seqs.Add ({out}, Big_Integer'({x}))"
        return out
    return f"Big_Integer'({v})"


def _cert_loops(body: list) -> list:
    """Every while loop in the twin body, pre-order."""
    out = []
    for s in body:
        if "while" in s:
            out.append(s["while"])
            out += _cert_loops(s["while"]["body"])
        elif "if" in s:
            out += _cert_loops(s["if"]["then"]) + _cert_loops(s["if"]["else"])
    return out


def certificate(task: dict, body: list, w: dict | None, L: Lower) -> str:
    """THE REFUTATION CERTIFICATE (10.8). One additional ground goal, named
    exactly T_Refutation_Certificate, that instantiates the harness witness
    so the kernel itself can judge it: verifiers/spark.py mints REFUTED only
    when gnatprove DISCHARGES every check of this function, and a file that
    so much as names it can never mint VERIFIED there.

    Two witness kinds are certificatable in this kernel:

      * "value" (a whole-program input): the goal is requires at the input,
        and then not (ensures at ret := F(input)). F is the file's own twin
        F, so the kernel evaluates the twin body it was handed, not a
        transcription: F's defining axiom (it is an expression function)
        forces F(input) to the twin's computed value, and the goal is
        provable exactly when that value falsifies the ensures. Emitted only
        when the witness records _ens true, because a twin value that merely
        DIFFERS may still satisfy a loose ensures, and a goal known to be
        false is not an instrument.

      * "exit" (a loop state, from INVARIANT-DROP): the goal is the negated
        exit-entailment VC at the state, requires and then the surviving
        invariants and then not cond and then not ensures at the RETURN,
        the state run through the statements after the loop first
        (interp.exit_env; since 2026-09-07), every variable a literal. That is byte-for-byte the statement interp.invariant_witness
        measured (admissibility included), restated to the kernel: a state
        the survivors admit, at the loop's exit, where the theorem fails.
        The twin body's own loop supplies the survivors, so the certificate
        weakens nothing itself. Emitted only when the twin body has exactly
        one loop, the one the witness's state ranges over.

    "undefined" and "preservation" witnesses are NOT certificated: the first
    has no value for the ensures to be evaluated at (the twin's definedness
    failure is its own evidence, but not ground evidence this goal can
    carry), and the second needs one symbolic body step from the state,
    which this file does not yet trust itself to instantiate. Fail closed:
    no certificate, and the cell honestly reads what the kernel could judge.

    Any lowering failure (a name the witness does not value, an operator
    outside t) emits no certificate rather than a wrong one.
    """
    if not w:
        return ""
    kind = w.get("_kind")
    vals = {k: v for k, v in w.items() if not k.startswith("_")}
    sub = {k: _cert_lit(v) for k, v in vals.items()}
    ret = task["returns"][0]["name"]
    try:
        if kind == "value":
            if w.get("_ens") is not True:
                return ""
            if set(vals) != {p["name"] for p in task["params"]}:
                return ""
            args = ", ".join(sub[p["name"]] for p in task["params"])
            call = f"F ({args})" if args else "F"
            parts = [L.expr(e, sub) for e in task.get("requires", [])]
            ens = [L.expr(e, {**sub, ret: call}) for e in task["ensures"]]
        elif kind == "exit":
            loops = _cert_loops(body)
            if len(loops) != 1:
                return ""
            loop = loops[0]
            # The obligation is at the RETURN: the loop-exit state run
            # through whatever follows the loop (interp.exit_env, None under
            # an enclosing loop). A tail loop runs nothing and the goal is
            # unchanged. Measured 2026-09-07 (ROADMAP 12.5): slow_max
            # assigns its result after its loop, and this goal, stating
            # not-ensures at the loop's own state, minted REFUTED on a twin
            # gnatprove proves.
            post = interp.exit_env(task, body, loop, vals)
            if post is None:
                return ""
            parts = [L.expr(e, sub) for e in task.get("requires", [])]
            parts += [L.expr(i, sub) for i in loop.get("invariants", [])]
            parts.append(f"(not {L.expr(loop['cond'], sub)})")
            ens = [L.expr(e, {**sub, ret: _cert_lit(post[ret])})
                   for e in task["ensures"]]
        else:
            return ""
    except (ValueError, KeyError, NotImplementedError):
        return ""
    neg = f"(not {ens[0]})" if len(ens) == 1 \
        else "(not (" + " and then ".join(ens) + "))"
    parts.append(neg)
    conj = "\n      and then ".join(parts)
    sig = f"function {CERT_NAME} return Boolean"
    return (f"   --  Refutation certificate: the measured witness, restated\n"
            f"   --  as one ground goal for the kernel to judge (see the\n"
            f"   --  header). This file can never claim VERIFIED.\n"
            f"   {sig}\n"
            f"   with Post => {CERT_NAME}'Result;\n"
            f"\n"
            f"   {sig} is\n"
            f"     ({conj});\n")


# `witness` is the twin's measured witness (harness.twin_cached). Twin call
# sites pass it; a certificatable witness becomes the certificate goal above.
def lower(task: dict, body: list, witness: dict | None = None) -> str:
    L = Lower(task)
    ret = task["returns"][0]
    psub = {p["name"]: cap(p["name"]) for p in task["params"]}
    needs_seq = any(p["type"] == "seq" for p in task["params"]) or any(
        p["type"] == "seq"
        for sf in task.get("spec_funs", []) for p in sf["params"])

    # The seq and range preambles put fixed Ada names in scope; a t
    # identifier capitalizing onto one of them would be captured silently,
    # which is a wrong answer rather than a missing one.
    # `Esc`/`Ret` (SPEC.md "Early exit", 2026-09-08) only enter the emitted
    # package when a loop actually escapes, so they are only reserved for a
    # task has_return finds a `return` in; the other 13 committed tasks'
    # RESERVED set, and therefore their output, is untouched.
    reserved = RESERVED | ({"Esc", "Ret"} if has_return(body) else set())
    reserved_lc = {r.lower() for r in reserved}
    clash = sorted(n for n in bound_names(task, body)
                   if n.lower() in reserved_lc)
    if clash:
        raise NotImplementedError(
            f"spark: t name(s) {clash} collide with the emitted package's own "
            f"names ({sorted(reserved)})")
    named = sorted(bound_names(task, body) | {task["name"]})
    by_ada = {}
    for n in named:
        by_ada.setdefault(cap(n).lower(), []).append(n)
    merged = sorted(v for v in by_ada.values() if len(v) > 1)
    if merged:
        raise NotImplementedError(
            f"spark: t names {merged} spell the same Ada identifier after the "
            f"underscore rule in cap()")

    spec_funs = [L.lower_spec_fun(sf) for sf in task.get("spec_funs", [])]

    # SPEC.md "Early exit" (2026-09-08): a body that can `return` is lowered
    # through compile_r, which threads the escape alongside the ordinary
    # substitution env; one without it keeps compile() exactly as it read
    # before this note. Either way F's Post (below) is the task's `ensures`
    # applied uniformly to F'Result, so the exit obligation SPEC.md states
    # ("the task owes its ensures there as at every exit") falls out of
    # this merge for free rather than needing its own restatement.
    if has_return(body):
        env, esc, val = L.compile_r(
            body, {ret["name"]: None}, {ret["name"]: ret["type"]}, psub,
            ret["name"])
        if env[ret["name"]] is None:
            raise ValueError(f"body never assigns {ret['name']!r}")
        final = env[ret["name"]] if esc is None \
            else f"(if {esc} then {val} else {env[ret['name']]})"
    else:
        env = L.compile(body, {ret["name"]: None}, {ret["name"]: ret["type"]},
                        psub)
        if env[ret["name"]] is None:
            raise ValueError(f"body never assigns {ret['name']!r}")
        final = env[ret["name"]]

    aspects = []
    reqs = [L.expr(e, psub) for e in task.get("requires", [])]
    if reqs:
        aspects.append("Pre  => " + "\n       and then ".join(reqs))
    post_sub = {**psub, ret["name"]: "F'Result"}
    aspects.append("Post => " + "\n       and then ".join(
        L.expr(e, post_sub) for e in task["ensures"]))
    if "decreases" in task:
        d = L.expr(task["decreases"], psub)
        aspects.append(f"Subprogram_Variant => "
                       f"(Decreases => (if {d} >= 0 then {d} else 0))")

    cert = certificate(task, body, witness, L)

    plist = "; ".join(f"{cap(p['name'])} : {TYPE[p['type']]}"
                      for p in task["params"])
    fsig = f"function F ({plist}) return {TYPE[ret['type']]}" if plist \
        else f"function F return {TYPE[ret['type']]}"
    pkg = f"T_{cap(task['name'])}"
    parts = [
        "pragma Ada_2022;",
        "with Ada.Numerics.Big_Numbers.Big_Integers;",
        "use  Ada.Numerics.Big_Numbers.Big_Integers;",
    ]
    if needs_seq:
        parts += ["with SPARK.Containers.Functional.Infinite_Sequences;"]
    parts += [f"package {pkg} with SPARK_Mode is", ""]
    if needs_seq:
        parts += [SEQ_PREAMBLE]
    if L.needs_range:
        parts += [RANGE_PREAMBLE]
    if L.needs_divmod:
        parts += [DIVMOD_PREAMBLE]
    for sf in spec_funs:
        parts += [sf]
    for h in L.helpers:
        parts += [h]
    parts += [
        f"   {fsig}",
        "   with\n     " + ",\n     ".join(aspects) + ";",
        "",
        f"   {fsig} is",
        f"     ({final});",
        "",
    ]
    inst = ce_instance(task, body)
    if inst:
        parts += [inst]
    if cert:
        parts += [cert]
    parts += [f"end {pkg};"]
    return "\n".join(parts) + "\n"


def ce_instance(task: dict, body: list) -> str:
    """The task at machine inputs, or "" when this file cannot bound it.

    The instance exists only to give gnatprove a domain its counterexample
    generator can build a model in and its RAC can execute; neither is
    possible over Big_Integer (header). It is emitted after F, so the havoc
    oracle's `function F ... is` scan still lands on F: verifiers/spark.py's
    pattern requires whitespace, `(` or `return` after the F, and `F_Ce`
    presents `_`.
    """
    ret = task["returns"][0]
    if ret["type"] not in CE_TYPE \
            or any(p["type"] not in CE_TYPE for p in task["params"]) \
            or task.get("spec_funs") or "decreases" in task:
        return ""
    try:
        env = _ce_stmts(body, {**{p["name"]: (CE_WINDOW
                                              if p["type"] == "int" else None)
                                  for p in task["params"]},
                               ret["name"]: _UNSET})
        pbound = {p["name"]: (CE_WINDOW if p["type"] == "int" else None)
                  for p in task["params"]}
        for e in task.get("requires", []):
            _ce_bound(e, pbound)
        for e in task["ensures"]:
            _ce_bound(e, {**pbound, ret["name"]: env[ret["name"]]})
        L = Lower(task, ce=True)
        psub = {p["name"]: cap(p["name"]) for p in task["params"]}
        cenv = L.compile(body, {ret["name"]: None},
                         {ret["name"]: ret["type"]}, psub)
        final = cenv[ret["name"]]
        post_sub = {**psub, ret["name"]: "F_Ce'Result"}
        ens = [L.expr(e, post_sub) for e in task["ensures"]]
        reqs = [L.expr(e, psub) for e in task.get("requires", [])]
    except (_NoCe, ValueError, NotImplementedError, KeyError):
        # Outside the fragment. The unbounded theorem above is the artifact;
        # the instance is an addition, and its absence costs a refutation,
        # never a proof.
        return ""
    if env[ret["name"]] is _UNSET:
        return ""
    # `requires` becomes a hypothesis of the Post rather than a Pre: a Pre
    # unsatisfiable inside the window is VC_INCONSISTENT_PRE, which
    # verifiers/spark.py rules VACUOUS for the whole file (header).
    if reqs:
        post = ("(if " + "\n                and then ".join(reqs)
                + "\n              then "
                + "\n                and then ".join(ens) + ")")
    else:
        post = "\n       and then ".join(ens)
    plist = "; ".join(f"{cap(p['name'])} : {CE_TYPE[p['type']]}"
                      for p in task["params"])
    sig = (f"function F_Ce ({plist}) return {CE_RET[ret['type']]}" if plist
           else f"function F_Ce return {CE_RET[ret['type']]}")
    return (CE_PREAMBLE + "\n"
            + f"   {sig}\n"
            + f"   with\n     Post => {post};\n"
            + "\n"
            + f"   {sig} is\n"
            + f"     ({final});\n")


if __name__ == "__main__":
    raise SystemExit(harness.run_all(sys.argv[1:], lower, spark_backend, "ads"))
