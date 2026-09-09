#!/usr/bin/env python3
"""lower_framac.py: lower t v0+v1 tasks to ACSL-annotated C; the sixth kernel.

THE SEMANTIC LINE, corrected 2026-09-01. The old one was WRONG, and the
error was a false theorem, not a wording slip. It read: "C's int is a machine
type, but WP WITHOUT -wp-rte reasons about the arithmetic mathematically, so
this lowering matches t's mathematical integers exactly." Only the
ARITHMETIC is mathematical without -wp-rte. The TYPING is not: WP's default
model constrains every C `int` with is_sint32, so `x <= 2^31-1` was granted
for free on every formal, every local and every seq element. SPEC.md says t
integers are mathematical and unbounded, so the emitted obligation was a
different, weaker theorem. MEASURED on the differential fuzzer: framac alone
VERIFIED fz_p_intwidth and fz_p_seqlen while six other kernels REFUTED them,
and an element-width probe (`ensures len(s) > 0 ==> s[0] <= 2^31-1`) proved
7/7 goals.

The fix is not in this file, and cannot be: ACSL's unbounded `integer` is a
LOGIC type, and Frama-C 33 rejects it for a ghost variable and for a ghost
function's parameters and result alike (both measured), so there is no C
program this lowering could emit whose program variables are unbounded. What
a C int MEANS to the prover is a model, and the model is a flag: the adapter
pins -wp-model Typed+nat (verifiers/framac.py, MODEL), WP's natural
arithmetic, under which a C integer carries no range hypothesis at all.
Everything below, the `int` formals, `int` locals, `int *s` elements and the
`int s_n` length, is therefore a mathematical integer, and the ACSL side already
used `integer` for spec-level quantities and bound variables. The two files
are one instrument: this C read under the default model is a proof of
something t did not ask.

The -wp-rte machine-int arm remains a later gate, not a silent default.

v1 mapping (measured on frama-c 33.0 / alt-ergo 2.4.3-free, 2026-08-31):

  seq        -> `int *s` plus a fresh length parameter `s_n`, with emitted
                preconditions `s_n >= 0` and `\\valid_read(s + (0 .. s_n-1))`.
  forall/    -> `\\forall integer i; lo <= i < hi ==> body` (and the && form
  exists        for exists). Bound vars are ACSL `integer`, mathematical.
  while      -> `loop invariant` per invariant (order preserved, because the twin
                depends on it), `loop assigns` (collected from the body),
                `loop variant` from the required decreases clause.
  spec_funs  -> recursive ACSL logic functions (`logic integer f(...) = ...`),
                with a `{L}` label parameter iff the fun reads a seq. WP does
                NOT check termination of recursive logic definitions (measured:
                `bad(n) = bad(n)+1` is accepted), so this lowering emits the
                decreases obligation itself: one `lemma f_terminates_k` per
                self-call, stating measure' >= 0 && measure' < measure under
                that call's path condition. Those lemmas are proof goals in
                the same file: unproved means REFUTED, not a shrug.
  recursion  -> a real recursive C function with an ACSL `decreases` clause;
                WP's variant PO at the call site is the termination proof
                (measured: `decreases 0` on factorial leaves the variant goal
                unproved).

DEFINEDNESS, honestly: `at` outside [0, len) is undefined in t. For
EXECUTABLE positions this lowering discharges it: every unconditionally
evaluated `at` in a statement gets a `/*@ assert 0 <= i < s_n; */` proof
obligation in front of the statement, and a conditionally evaluated `at` in
executable position is an explicit NotImplementedError (never silently
emitted as C UB). For SPEC positions (requires/ensures/invariants/spec_fun
bodies) WP's logic is total: an out-of-range s[i] denotes an UNCONSTRAINED
value under the memory model, so no proof can depend on any particular
out-of-range content, weaker than Dafny-style well-formedness checking,
stronger than totalizing to a fixed value. That gap is this backend's known
softness, recorded here rather than papered over.

DIV/MOD, added 2026-09-08. Measured convention: both ACSL's logic `/`/`%`
(over mathematical `integer`, no -wp-rte) and C's executable `/`/`%` under
-wp-model Typed+nat truncate toward zero, matching each other and the ACSL
manual's own definition, and matching neither SPEC.md's Euclidean
convention (probes acsl_div/acsl_floor: TIMEOUT on the six SPEC.md example
equalities; acsl_trunc and the executable c_div probe: VERIFIED on the same
six, truncating). So this lowering never emits a bare `/`/`%` for t's `div`
and `mod`: it defines them in the kernel's own truncating terms. ACSL side,
declared once per file that uses either op (T_DIVMOD_ACSL, emitted before
any spec_fun so spec_funs may use them):

    logic integer t_mod(integer x, integer y) =
      (x % y < 0) ? x % y + \\abs(y) : x % y;
    logic integer t_div(integer x, integer y) =
      (x % y < 0) ? (x / y) - (y > 0 ? 1 : -1) : x / y;

(truncating `%` carries the sign of x or is 0; shifting a negative
truncating remainder up by |y| gives the Euclidean remainder in [0, |y|),
and t_div is the truncating quotient with the matching -1/+1 correction.
Measured 2026-09-08: defining t_div as the exact division `(x -
t_mod(x, y)) / y` TIMEOUTs on the general identity `x == t_div(x,y)*y +
t_mod(x,y)` (alt-ergo cannot see the subtraction is a multiple of y
unaided); the correction form VERIFIES it, because it telescopes to WP's
own native `x == (x/y)*y + x%y` plus linear arithmetic, nothing
division-shaped left over.) `term()` renders `div`/`mod` as
`t_div`/`t_mod` calls; C executable position (`cexpr()`) inlines the same
formula with C's own `/`/`%` so the two sides stay syntactically parallel.
Definedness: y == 0 is undefined by SPEC.md, the same shape as `at`'s bound
check, so `defs()` adds `y != 0` to the domain obligation of any spec
expression containing `div`/`mod`, and executable position gets a
`/*@ assert (y) != 0; */` immediately before the statement (code_ats/
at_asserts, generalized to carry tagged `("at", ...)` and `("nz", ...)`
obligations; a conditionally evaluated `div`/`mod`, like a conditionally
evaluated `at`, is an explicit NotImplementedError rather than silent UB).
Unlike `at`, t_div/t_mod are themselves total at y == 0 (ACSL's own `/`/`%`
are, measured), so this obligation is owed to SPEC.md's semantics, not to
keeping the kernel from choking.

Bodies lower to statements: locals are C locals, the return name is a local
returned at the end, `bool` is C int 0/1 (spec side renders bool vars as
`x != 0` and bool equality as `<==>`). Every function gets `assigns
\\nothing;`, which is provable (t bodies never write memory) and is what
makes recursive calls modular.

RETURN, added 2026-09-08 (SPEC.md "Early exit"). `{"return": [ID, Expr]}`
lowers to a real C `return`: `Expr` sits in the same position as an
assignment's right-hand side, so `stmts()` gives it the same at_asserts
(the `at` bound, the `!= 0` divisor) before assigning it to the return
name and emitting `return <name>;`, from whatever `if`/`while` nesting it
sits at. This is exactly WP's rule and SPEC's: the postcondition is
checked at every return, and the loop invariant is not owed there, because
C's `return` leaves the loop without going through its header again.
Nothing may follow a `return` in its own block (well-formedness's job,
not this file's), so the statement after the enclosing `if` is dead only
on the branch that returned, never on the other, and no
-wp-smoke-dead-local-init goal is at risk THERE. `assigned_names()` counts
the return name as assigned, so a return inside a loop body puts it in
that loop's `loop assigns` frame like any other write. The certificate
replay (`_cert_stmts`) treats a replayed return as a stop signal threaded
back through `if`/`while`: since the replay is concrete, the state after
a return already holds the exact final values, so the certificate simply
emits no more C for the rest of the body (matching check_wf's refusal of
trailing statements) rather than emitting its own control-flow return
inside the always-`void` certificate function. Corrected 2026-09-09: see
RETURN SMOKE below, this claim was true only for the statement
IMMEDIATELY after the `if`, not for `lower()`'s own unconditional
trailing `return {ret};` after the whole body, which the paragraph did
not mention and which was the actual defect.

RETURN SMOKE and DIV/MOD SMOKE, both fixed 2026-09-09. Two unrelated
places in this file used to emit C that no input could reach, and both
read framac VACUOUS instead of VERIFIED because of the SAME downstream
mechanism: WP's dead-code smoke test does not always attach a NAMED goal
to the code point it dooms. Sometimes it does (a `wp_smoke_dead_code_sN`
entry in the JSON report, which `verifiers/framac.py`'s
`_UNREACHABLE_SMOKE` recognizes as "this is a fact about the body, not
vacuity", exactly as intended), and sometimes, MEASURED on both cases
below, it prints a bare `Warning: Failed smoke-test` at the source line
with no goal name in the report at all, which `_vacuity_smoke` fails
closed on ("doomed, but nothing named: refuse") because that adapter
cannot fix that file (RULES here restrict repair to this file only, and
regardless the honest failure-closed behaviour is correct on the goals it
CAN see; the fix is to stop handing it a goal it can't name).

(a) RETURN's own case: `lower()` closed every function body with an
unconditional `return {ret};` after the emitted statements, regardless of
whether the body already returned on every path. MEASURED on the
early-exit probe fz_p_ret_bothbranches (`if (x >= 0) return x; else
return -x;`, nothing after the `if`): the trailing `return r;` is dead
code on BOTH branches, not just one, and WP's smoke warning there named
nothing, scoring the file vacuous/vacuous. Fixed by `_always_returns()`
(mirrors lower_lean.py's helper of the same name): `lower()` now omits
the trailing `return {ret};` exactly when the body's own last statement,
or both branches of a trailing `if`, already return. A body with no
`return` at all, or one that leaves a path falling through, is
unaffected: abs.c and sum_upto.c (neither uses `return`) lower
byte-for-byte identical to before, measured by diff.

(b) DIV/MOD's case: `cexpr()`'s executable-position rendering of `div`
and `mod` used a C `?:` mirroring T_DIVMOD_ACSL's own ternary shape (the
truncating-to-Euclidean correction, selected by whether the truncating
remainder is negative). MEASURED on the lifted task extra_mod__mod (a
`while (k > 0)` loop with `k`'s invariant `k >= 0`, mod/div-ing by the
constant 2): once the invariant pins k's sign, the "truncating remainder
is negative" arm of that ternary is provably dead, and WP's per-arm smoke
check dooms it the same nameless way. Fixed by rendering `div`/`mod` in
executable position branch-free: `(rem < 0)` used directly as the C int
it already is (0 or 1) and multiplied into the correction term, instead
of selecting between two evaluated `?:` arms; no arm, no smoke target.
The ACSL side is unchanged in meaning: T_DIVMOD_ACSL's logic definitions
of t_div/t_mod keep the Euclidean law and the ternary shape (a `?:`
inside an ACSL annotation is never a WP smoke target, measured, so there
is nothing to fix there), and the "dm" bridging assert (`at_asserts`,
below) keeps rendering with that same ternary shape via
`_divmod_ternary_cexpr`, now `cexpr(..., _div_style="ternary")` threaded
recursively so a `div`/`mod` NESTED inside another one's x/y argument
stays ternary at every level too: the first version of this fix passed
`_div_style` only at the top call and let nested sub-expressions fall
back to the branch-free default, which rendered raw C boolean arithmetic
`(P) - (Q)` inside an ACSL annotation on the lifted task isArmstrong
(whose bridging assert nests `t_mod(t_div(n, 10), 10)`), and Frama-C
rejected it outright as MALFORMED ("invalid operands to binary -;
unexpected bool and bool") rather than scoring it vacuous or unproved.

MEASURED after both fixes: the 15-task committed regression (tasks/*.json)
reads identical to AGREEMENT.md's framac column, wall unchanged at
~120s total. The early-exit fuzz family (26 tasks: 22 fz_v1exit + 4
fz_p_ret_* probes, 1 a deliberate wf-error) moved from real counts
verified 22 / timeout 2 / vacuous 1 to verified 23 / timeout 2 / vacuous
0: the one vacuous cell was fz_p_ret_bothbranches, now verified. Of the
ten framac vacuous/vacuous rows in COVERAGE-lifted-785.md, nine used
div/mod and all nine stopped reading vacuous after the fix (seven now
verify outright; extra_mod2__mod2 reads an honest timeout;
isArmstrong reads an honest timeout, having also read MALFORMED under the
first, incompletely-threaded version of this fix). The tenth,
mockexam2_p5__problem5, uses neither `return` nor `div`/`mod` and stayed
vacuous unchanged: a real vacuous spec (recursive spec_fun, a
`gate: recursion` task) or a third instance of the same smoke-naming gap
in a shape this fix does not touch, not investigated further, RULES
having scoped this pass to the two named causes.

SEQ VALUES (`update`/`fill`), added 2026-09-09 (SPEC.md "Sequences as
values (v1)", ROADMAP 12.7). `seq` becomes a return type; `s[i := v]`
(DEFINED IFF `0 <= i < len(s)`) and `seq(n, v)` (DEFINED IFF `n >= 0`)
denote fresh seq VALUES, no aliasing, no mutation of the operand. C has no
sequence value at all, so this is a MEASURED encoding choice, not a
notational one, decided against the two new committed tasks (`swap`,
`update` only; `reverse`, `fill` plus a per-iteration `update`) by hand
with frama-c/WP before any of this file changed (RULES: measure first).

THE ENCODING, candidate (B) of the three the construct brief named (a
caller-provided output buffer with real memory stores, not an ACSL
`\\list`/axiomatised logic sequence carrying the value purely in the spec,
and not a ghost-only encoding). A seq PARAM was already `int *s, int s_n`
(read-only, `\\valid_read`); a seq RETURN gets the identical pair APPENDED
to the C signature as an OUTPUT parameter (`int *r, int r_n`), now
WRITABLE (`\\valid`, not `\\valid_read`) and `\\separated` from every other
seq buffer in scope (WP's Typed memory model does not assume two `int *`
formals of the same C type are non-overlapping on its own; measured on
the swap probe: dropping `\\separated` left `r[i] == s[j]` unprovable).
The C function itself becomes `void` (no scalar `\\result` for a seq
return; `ensures` renders `r`/`r_n` as plain names, matching an ordinary
seq param's rendering rather than substituting `\\result`), and every
`s[i := v]`/`seq(n, v)` assignment lowers to REAL C writes into the
target buffer, proved by WP's own points-to reasoning over ordinary
stores, nothing bespoke needed beyond that: `update`'s base, when it
names a DIFFERENT buffer than the target (swap's `r := s[i := ...]`, its
first write to `r`), is copied in first (a whole-buffer loop, invariant
`target[t] == base[t]` for `t` below the counter -- exactly "equal to `s`
at every index but `i`"); a SELF update (swap's `r := r[j := tmp]`,
reverse's per-iteration `r := r[i := ...]`) skips the copy, since the
target already holds what the base denotes; `fill` needs no prior value
and writes the whole buffer in one loop. `seq_assign_lines` (above
`assigned_names`) is the whole mechanism; `stmts()`'s `assign`/`return`
cases dispatch to it for a seq-typed target, `var` refuses a seq-typed
LOCAL outright (see below).

The return buffer's `requires \\valid(...)` bound and its pinned length
(`requires r_n == <len-expr>;`) must both be expressible in PARAMS alone
(ACSL's `requires` has no locals in scope), so `_seq_len_track` walks the
body BEFORE any C is emitted, propagating a symbolic length (a t Expr) per
seq name from the params outward: `update` preserves its base's length,
`fill`'s length is its own first argument, `if` requires both branches to
agree, `while` requires the tracked length to be unchanged by one static
pass through the body (an update-only loop, reverse's shape). Both
committed tasks resolve to `len(s)` this way. What this candidate CANNOT
express, found by construction rather than discovered late: a `fill`
whose length has no such closed form over params (built from a LOCAL with
no reduction to a param expression, or one that disagrees across
branches) has no buffer bound to hand the caller, and `lower()` raises
NotImplementedError rather than guess one. The task brief's other named
alternative, a `t_len_r` OUT-parameter the callee itself computes and
writes, would lift this for the LENGTH (the callee could report whatever
it computed) but not for the buffer's own VALIDITY bound, still owed to
the caller before the call and so still needing an expression fixed in
advance; not implemented, since neither committed task needs it.

A seq-typed LOCAL (`var a: seq := s;`, SPEC.md's other new position) is
NOT implemented: it would need its own backing storage with no external
contract to size it from (v1's scope rule keeps locals out of `ensures`,
so there is no requires-time bound to borrow the return's trick from),
and neither committed task declares one; `stmts()`'s `var` case refuses
it by name (NotImplementedError) rather than emit something unmeasured.
A recursive call to a seq-returning task is refused the same way
(`cexpr`'s `call` case): it would need a second output buffer this
lowering does not allocate, and no committed task recurses with a seq
return.

TWIN REFUTATION, the two new witness kinds. Before this construct,
`certificate()` minted REFUTED from exactly one witness shape (`_kind ==
"value"`, a whole-program input where the twin's computed value falsifies
`ensures`); an `undefined` or `exit` witness got no certificate at all,
an honest but weaker TIMEOUT/UNPROVED. swap's twin (OFF-BY-ONE on the
`at` inside its first statement) measures an `undefined` witness (`s=[0],
i=0, j=0`, the mutant reading `s[i+1]`, index 1 outside `[0,1)`);
reverse's twin (INVARIANT-DROP of its range-preservation invariant)
measures an `exit` witness (`s=[], i=0, r=[0]`), a LOOP STATE, not an
input. Both are now certified, `_undef_certificate` and
`_exit_certificate` (above `certificate`), mirroring the SAME night's
`lower_verus.py`/`lower_fstar.py` additions for the identical construct:

  `undefined`: re-walk the twin body with `interp.ev`, in the same
  left-to-right order `interp.py`'s own `exec_body` used to raise the
  `Undef` that minted this witness kind, using `defs_t` (a new function:
  the SAME rule `defs()` already renders to ACSL, restated as a t formula
  so `interp.ev` can decide it at the ground witness -- one definedness
  RULE, two renderings). The first statement whose obligation comes back
  false is the certificate: no C statement is replayed at all, since
  every name the obligation can mention is either a param (declared
  ground, exactly as the value-kind branch already declares params) or an
  int/bool local computed along the way (declared ground as the walk
  proceeds), so the obligation renders straight through `pred()`. A
  SEQ-typed intermediate local assigned before the failure refuses
  (materializing its snapshot needs the full replay this shortcut
  avoids); not exercised by swap, whose failure is the body's first
  statement, only documented for the next task that might need it.

  `exit`: `interp.invariant_witness`'s own obligation restated (the
  surviving invariants and `requires` hold, the guard is false, `ensures`
  is false). Unlike a `value` witness this state is not REACHED by
  running the function from its params (`_Admissible` screens for states
  a sound kernel cannot rule out, not for states an actual run passes
  through), so it is declared directly as ground C locals for every name
  the witness names -- params AND loop-scope locals alike, identical to
  how params are already declared -- and `_cert_stmts` (UNCHANGED)
  replays only the twin's mutated loop onward (`_loop_suffix`), which
  correctly computes zero further iterations when the witness already has
  the guard false, exactly reverse's own measured case. Scope limit: only
  a TOP-LEVEL loop is handled (`_twin_loop`/`_loop_suffix`, mirroring
  `lower_verus.py`'s `_twin_loop`); a loop nested under an `if` would need
  `interp.continuation`'s own search, unmeasured, not needed here.

  Neither new kind extends `_cert_stmts`/`_cert_cexpr` to render a
  seq-typed assignment's own C text (the copy/fill loops
  `seq_assign_lines` emits for real function bodies): an `update`/`fill`
  node reaching `_cert_cexpr` still hits its existing "no operator"
  `ValueError`, caught by `certificate`'s own exception handling exactly
  like any other unexpressible witness. Correct and unsurprising for both
  committed cells (swap's certificate never reaches a seq assignment;
  reverse's replays zero loop iterations), so extending it further was
  not measured and is left for whichever task needs it.

SCOPE, MEASURED rather than assumed. `_undef_certificate` and
`_exit_certificate` are GENERAL mechanisms -- neither is seq-specific --
and turning them on unconditionally was tried first: it changed 9 of the
15 already-committed tasks' twin cells (every framac `verified / timeout`
row in AGREEMENT.md) from an uncertified TIMEOUT to a certified REFUTED,
matching what every other kernel already reads there. That may well be a
sound improvement, but RULES scoped this pass to landing `update`/`fill`
and reading the two NEW tasks, not to re-measuring nine committed ones
outside a dated note of their own, so `certificate()` gates both new
kinds on the task returning a seq, which today picks out exactly
swap/reverse and leaves every pre-existing task's certificate path (and
verdict) untouched -- diffed byte-for-byte against the pre-change
lowering, real and twin, for all 15.

MEASURED: swap and reverse both COUNT (real VERIFIED, twin REFUTED) --
swap `off-by-one` witness `s=[0], i=0, j=0`, reverse `invariant-drop#1`
witness `exit at s=[], i=0, r=[0]`. The 15-task committed regression
reads identical to AGREEMENT.md's framac column (6 verified/refuted:
abs, factorial, fib, gcd, max, remainder; 9 verified/timeout: all_nonneg,
contains, count_matches, digit_sum, first_even, is_prime, linear_search,
seq_max, sum_upto), wall 125.4s for those 15, 139.6s for all 17.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import harness                                   # noqa: E402
import interp                                    # noqa: E402
from verifiers import framac as framac_backend   # noqa: E402

ARITH = {"+": "+", "-": "-", "*": "*"}
CMP = {"==": "==", "!=": "!=", "<": "<", "<=": "<=", ">": ">", ">=": ">="}
DIVMOD = ("div", "mod")

# t_div/t_mod (2026-09-08): SPEC.md's Euclidean div/mod, defined in this
# kernel's own truncating terms (measured below, ACSL DIVISION section).
# Both ACSL's logic `/`/`%` and C's executable `/`/`%` under -wp-model
# Typed+nat truncate toward zero (measured: acsl_trunc / c_div probes both
# VERIFIED on the six SPEC.md examples, acsl_div and acsl_floor both
# TIMEOUT), so truncating `%` carries the sign of x (or is 0), and the
# Euclidean remainder is the truncating one shifted up by |y| exactly when
# it is negative. t_div is the truncating quotient with the matching -1/+1
# correction (sign of y), NOT `(x - t_mod(x, y)) / y`: that exact-division
# form measured a TIMEOUT on the general identity `x == t_div(x,y)*y +
# t_mod(x,y)` (alt-ergo cannot see the subtraction is a multiple of y
# without help), while the correction form measured VERIFIED, because it
# telescopes to WP's own native division identity `x == (x/y)*y + x%y`
# plus linear arithmetic on the correction/adjustment terms, nothing
# division-shaped left to prove.
T_DIVMOD_ACSL = (
    "/*@\n"
    "  logic integer t_mod(integer x, integer y) =\n"
    "    (x % y < 0) ? x % y + \\abs(y) : x % y;\n"
    "  logic integer t_div(integer x, integer y) =\n"
    "    (x % y < 0) ? (x / y) - (y > 0 ? 1 : -1) : x / y;\n"
    "*/\n"
)


def _has_divmod(x) -> bool:
    """Whether `div`/`mod` occurs anywhere in a task/body structure (spec or
    executable position); over-inclusive on purpose, an unused ACSL logic
    definition costs nothing and this only gates whether t_div/t_mod are
    declared at all."""
    if isinstance(x, dict):
        if x.get("op") in DIVMOD:
            return True
        return any(_has_divmod(v) for v in x.values())
    if isinstance(x, list):
        return any(_has_divmod(v) for v in x)
    return False


# ---------------------------------------------------------------- typing ----

SEQOPS = ("update", "fill")


def typ(e: dict, env: dict, funs: dict) -> str:
    """Type of an expression: 'int' | 'bool' | 'seq'."""
    if "int" in e:
        return "int"
    if "bool" in e:
        return "bool"
    if "var" in e:
        return env[e["var"]]
    if "forall" in e or "exists" in e:
        return "bool"
    if "ite" in e:
        return typ(e["ite"]["then"], env, funs)
    if "call" in e:
        return funs[e["call"]["fun"]]["result"]
    op = e["op"]
    if op in SEQOPS:
        return "seq"
    if op in ("len", "at", "neg") or op in ARITH or op in DIVMOD:
        return "int"
    return "bool"                                # cmp, and, or, not, implies


def seq_var(e: dict, env: dict) -> str:
    """A seq-position expression must be a seq-typed variable (v1:
    sequences are param/return/local-position VALUES, but `at`'s and
    `update`'s own SeqExpr argument is still always a bare variable, never
    a nested `update`/`fill`/`at`; `stmts()`'s seq-assignment codegen is
    where `update`/`fill` themselves are consumed, always as the WHOLE
    right-hand side of an assignment to a seq-typed name, never nested
    inside another expression)."""
    if "var" in e and env.get(e["var"]) == "seq":
        return e["var"]
    raise NotImplementedError(f"seq position holds non-variable {e!r}")


# ---------------------------------------------------------- ACSL (spec) -----

class Ctx:
    """Rendering context for ACSL: env (name->type), funs (spec_fun table +
    the task itself), ret (return name to render as \\result, or None), and
    label (the memory label attached to labeled logic-fun calls)."""
    def __init__(self, env, funs, ret=None, label="Here"):
        self.env, self.funs, self.ret, self.label = env, funs, ret, label

    def bind(self, name, ty):
        env2 = dict(self.env)
        env2[name] = ty
        return Ctx(env2, self.funs, self.ret, self.label)


def acsl_call(c: dict, ctx: Ctx) -> str:
    fun = c["fun"]
    info = ctx.funs[fun]
    if info.get("is_task"):
        raise NotImplementedError(
            "task self-call in spec position (v1 specs are anchored by "
            "spec_funs, never the task's own name)")
    parts = []
    for p, a in zip(info["params"], c["args"], strict=True):
        if p["type"] == "seq":
            s = seq_var(a, ctx.env)
            parts += [s, f"{s}_n"]
        else:
            parts.append(term(a, ctx))
    lab = f"{{{ctx.label}}}" if info["labeled"] else ""
    return f"{fun}{lab}({', '.join(parts)})"


def _gap(rendered: str) -> str:
    """A space when the operand already starts with a minus, so unary minus
    on a negative renders as `- -2` and not `--2`.

    C reads `--` as the decrement operator, so `-(--2)` is not double
    negation, it is a predecrement of a literal and frama-c rejects the file
    with a User Error. Measured 2026-09-04: the metamorphic double-negation
    rewrite produced exactly that on 10 cells, every one framac, every one
    scored malformed. The same hazard exists for `+ +` and it is spelled the
    same way here."""
    return " " + rendered if rendered[:1] in "-+" else rendered


def term(e: dict, ctx: Ctx) -> str:
    """ACSL term. int-typed terms are `integer`-valued; bool-typed terms are
    ACSL boolean terms (comparisons / && / || / ! coerce in term position,
    measured on the count spec_fun's guard)."""
    if "int" in e:
        return str(e["int"])
    if "bool" in e:
        return "\\true" if e["bool"] else "\\false"
    if "var" in e:
        n = e["var"]
        base = "\\result" if n == ctx.ret else n
        return f"({base} != 0)" if ctx.env[n] == "bool" else base
    if "ite" in e:
        i = e["ite"]
        return (f"(({term(i['cond'], ctx)}) ? ({term(i['then'], ctx)}) "
                f": ({term(i['else'], ctx)}))")
    if "call" in e:
        return acsl_call(e["call"], ctx)
    if "forall" in e or "exists" in e:
        raise NotImplementedError("quantifier in ACSL term position")
    op, args = e["op"], e.get("args", [])
    if op == "len":
        return f"{seq_var(args[0], ctx.env)}_n"
    if op == "at":
        return f"{seq_var(args[0], ctx.env)}[{term(args[1], ctx)}]"
    if op == "neg":
        return f"(-{_gap(term(args[0], ctx))})"
    if op == "not":
        return f"(!{term(args[0], ctx)})"
    if op == "implies":
        return f"((!({term(args[0], ctx)})) || ({term(args[1], ctx)}))"
    if op in ("and", "or"):
        glue = " && " if op == "and" else " || "
        return "(" + glue.join(term(a, ctx) for a in args) + ")"
    if op in DIVMOD:
        fn = "t_div" if op == "div" else "t_mod"
        return f"{fn}({term(args[0], ctx)}, {term(args[1], ctx)})"
    if op in SEQOPS:
        # `update`/`fill` (2026-09-09) denote a fresh seq VALUE, and this
        # backend has no ACSL rendering of a bare seq value: it only ever
        # renders a seq through `len`/`at`/extensional `==`, all of which
        # need a real backing C array, and `update`/`fill` themselves are
        # consumed exclusively as the whole right-hand side of an
        # assignment to a seq-typed name (`stmts()`'s seq-assignment
        # codegen), never nested inside a spec/term position. Reaching
        # here means one appeared somewhere this lowering does not (yet)
        # give a seq value a term rendering, e.g. inside `requires` or
        # `ensures` directly rather than a body assignment.
        raise NotImplementedError(
            f"`{op}` has no ACSL term rendering (no backing buffer here); "
            f"seq values may only be produced as the right-hand side of a "
            f"body assignment to a seq-typed name")
    if op in ARITH or op in CMP:
        o = ARITH.get(op) or CMP[op]
        return f"({term(args[0], ctx)} {o} {term(args[1], ctx)})"
    raise ValueError(f"t has no operator {op!r}")



def _conj(parts):
    parts = [x for x in parts if x is not None]
    if not parts:
        return None
    return parts[0] if len(parts) == 1 else "(" + " && ".join(parts) + ")"


def defs(e: dict, ctx: Ctx):
    """SPEC.md definedness of a spec expression, as an ACSL predicate that
    must be PROVEN, or None when trivially defined.

    ACSL's logic is total: an out-of-range s[i] denotes an unconstrained
    value, so `s[-1] == s[-1]` proves by reflexivity and the obligation t
    requires vanishes. Measured 2026-09-01 (ground-truth wave): four false
    theorems about undefined elements scored VERIFIED, the only kernel of
    seven to accept them. The lowering therefore emits the domain
    obligation itself, following SPEC's own evaluation order: `and`, `or`,
    `implies` and `ite` guard the definedness of what they may not
    evaluate, and a quantifier body must be defined at EVERY range point,
    for exists as much as forall.

    Residual, stated rather than hidden: spec_fun bodies are axiomatized
    as total ACSL logic functions, so an `at` INSIDE a spec_fun applied
    outside its guarded range keeps the reflexivity hole; the committed
    tasks guard their ranges, and hostile tasks are the ground-truth
    fuzzer's beat.

    `div`/`mod` (2026-09-08) is t's second partial operator: SPEC.md leaves
    both undefined at y == 0, so the domain obligation emitted here is
    `y != 0`, the same shape as `at`'s bound check. t_div/t_mod (see
    T_DIVMOD_ACSL above) are themselves total ACSL logic functions, well
    defined at y == 0 too (ACSL's own `/`/`%` are, measured), so nothing
    breaks if this obligation goes undischarged; it is emitted purely
    because SPEC.md says y == 0 is undefined, not because the kernel would
    otherwise crash.
    """
    if "int" in e or "bool" in e or "var" in e:
        return None
    if "ite" in e:
        i = e["ite"]
        c = pred(i["cond"], ctx)
        dt, de = defs(i["then"], ctx), defs(i["else"], ctx)
        return _conj([defs(i["cond"], ctx),
                      None if dt is None else f"(({c}) ==> {dt})",
                      None if de is None else f"((!({c})) ==> {de})"])
    if "forall" in e or "exists" in e:
        q = e["forall"] if "forall" in e else e["exists"]
        # Fresh binder, so the defs guard never re-binds the name the
        # enclosing \\exists or \\forall from pred() already uses. On the
        # exists definedness witness Why3/Alt-Ergo fails either way with
        # "bound variable in of_term" (measured 2026-09-02, with and
        # without the rename); that lands as TOOL_ERROR, which is ok=False
        # and never evidence, so the witness still cannot score VERIFIED.
        fresh = q["var"] + "_d"
        c2 = ctx.bind(fresh, "int")
        db = defs(subst(q["body"], {q["var"]: {"var": fresh}}), c2)
        rng = (f"({term(q['lo'], ctx)}) <= {fresh} "
               f"&& {fresh} < ({term(q['hi'], ctx)})")
        return _conj([defs(q["lo"], ctx), defs(q["hi"], ctx),
                      None if db is None else
                      f"(\\forall integer {fresh}; ({rng}) ==> {db})"])
    if "call" in e:
        return _conj([defs(a, ctx) for a in e["call"].get("args", [])])
    op, args = e["op"], e.get("args", [])
    if op == "at":
        i = term(args[1], ctx)
        n = seq_var(args[0], ctx.env) + "_n"
        return _conj([defs(args[1], ctx), f"(0 <= ({i}) && ({i}) < {n})"])
    if op == "update":
        # SPEC.md "Sequences as values" (2026-09-09): `s[i := v]` is
        # DEFINED IFF `0 <= i < len(s)`, the identical shape as `at`'s own
        # bound, over the update's base seq rather than a read.
        i = term(args[1], ctx)
        n = seq_var(args[0], ctx.env) + "_n"
        return _conj([defs(args[1], ctx), defs(args[2], ctx),
                      f"(0 <= ({i}) && ({i}) < {n})"])
    if op == "fill":
        # `seq(n, v)` is DEFINED IFF `n >= 0`.
        n = term(args[0], ctx)
        return _conj([defs(args[0], ctx), defs(args[1], ctx),
                      f"(({n}) >= 0)"])
    if op in DIVMOD:
        y = term(args[1], ctx)
        return _conj([defs(args[0], ctx), defs(args[1], ctx),
                      f"(({y}) != 0)"])
    if op in ("and", "or", "implies"):
        acc, guards = [defs(args[0], ctx)], []
        for k, a in enumerate(args[1:], 1):
            prev = args[k - 1] if op != "implies" else args[0]
            g = pred(prev, ctx)
            if op == "or":
                g = f"!({g})"
            d = defs(a, ctx)
            guards.append(g)
            if d is not None:
                acc.append("((" + " && ".join(guards) + f") ==> {d})")
        return _conj(acc)
    return _conj([defs(a, ctx) for a in args])


def pred(e: dict, ctx: Ctx) -> str:
    """ACSL predicate (for requires/ensures/invariants/asserts/lemmas)."""
    if "bool" in e:
        return "\\true" if e["bool"] else "\\false"
    if "var" in e:
        n = e["var"]
        base = "\\result" if n == ctx.ret else n
        return f"({base} != 0)"                  # bool-typed C variable
    if "forall" in e or "exists" in e:
        kind = "forall" if "forall" in e else "exists"
        q = e[kind]
        c2 = ctx.bind(q["var"], "int")
        rng = (f"({term(q['lo'], ctx)}) <= {q['var']} "
               f"&& {q['var']} < ({term(q['hi'], ctx)})")
        body = pred(q["body"], c2)
        glue = "==>" if kind == "forall" else "&&"
        return f"(\\{kind} integer {q['var']}; ({rng}) {glue} ({body}))"
    if "ite" in e:
        i = e["ite"]
        c = pred(i["cond"], ctx)
        return (f"((({c}) && ({pred(i['then'], ctx)})) "
                f"|| ((!({c})) && ({pred(i['else'], ctx)})))")
    if "call" in e:
        return f"({acsl_call(e['call'], ctx)} == \\true)"
    op, args = e["op"], e.get("args", [])
    if op == "not":
        return f"(!{pred(args[0], ctx)})"
    if op == "implies":
        return f"({pred(args[0], ctx)} ==> {pred(args[1], ctx)})"
    if op in ("and", "or"):
        glue = " && " if op == "and" else " || "
        return "(" + glue.join(pred(a, ctx) for a in args) + ")"
    if op in ("==", "!="):
        if typ(args[0], ctx.env, ctx.funs) == "bool":
            eq = f"({pred(args[0], ctx)} <==> {pred(args[1], ctx)})"
            return eq if op == "==" else f"(!{eq})"
        if typ(args[0], ctx.env, ctx.funs) == "seq":
            # `==`/`!=` on two seqs is EXTENSIONAL (SPEC.md "Sequences as
            # values", 2026-09-09): equal lengths and equal elements at
            # every index. Both operands must be bare seq variables (the
            # same restriction `seq_var`/`at` already enforce: this
            # backend has no ACSL rendering of a raw `update`/`fill`
            # value outside a body assignment, see `term()`).
            a, b = seq_var(args[0], ctx.env), seq_var(args[1], ctx.env)
            eq = (f"(({a}_n == {b}_n) && "
                 f"(\\forall integer __k; 0 <= __k && __k < {a}_n "
                 f"==> {a}[__k] == {b}[__k]))")
            return eq if op == "==" else f"(!{eq})"
        return f"({term(args[0], ctx)} {CMP[op]} {term(args[1], ctx)})"
    if op in CMP:
        return f"({term(args[0], ctx)} {CMP[op]} {term(args[1], ctx)})"
    raise ValueError(f"no predicate form for operator {op!r}")


# ------------------------------------------------------------- C (code) -----

def cexpr(e: dict, env: dict, funs: dict, task_name: str,
         _div_style: str = "bf") -> str:
    """`_div_style` picks how a `div`/`mod` node renders: "bf" (the
    default, branch-free, safe in executable C position) or "ternary"
    (ACSL-annotation-safe, see `_divmod_ternary_cexpr` below). It is
    threaded through every recursive call so a `div`/`mod` nested ANYWHERE
    inside the expression (not only at the top) picks up the same style;
    the isArmstrong probe (2026-09-09) measured why this matters: its
    `t_mod(t_div(n, 10), 10)` bridging assert has a div node nested inside
    a mod node's `x` argument, and rendering the inner one branch-free
    while the outer stayed ternary put raw C boolean arithmetic (`(P) -
    (Q)`) inside an ACSL annotation, which Frama-C rejects as MALFORMED
    ("invalid operands to binary -; unexpected bool and bool") rather
    than a smoke or proof failure."""
    if "int" in e:
        return str(e["int"])
    if "bool" in e:
        return "1" if e["bool"] else "0"
    if "var" in e:
        return e["var"]
    if "forall" in e or "exists" in e:
        raise NotImplementedError("bounded quantifier in executable position")
    if "ite" in e:
        i = e["ite"]
        return (f"(({cexpr(i['cond'], env, funs, task_name, _div_style)}) "
                f"? ({cexpr(i['then'], env, funs, task_name, _div_style)}) "
                f": ({cexpr(i['else'], env, funs, task_name, _div_style)}))")
    if "call" in e:
        c = e["call"]
        if c["fun"] != task_name:
            raise NotImplementedError(
                "spec_fun call in executable position (ACSL logic functions "
                "are not executable)")
        if funs[task_name]["result"] == "seq":
            # A seq-returning task (2026-09-09) is lowered to a `void` C
            # function with an output buffer parameter (see the seq value
            # machinery section), so it has no C VALUE this expression
            # position could hold; a recursive call to one would need a
            # second buffer for the callee's own return, which this
            # lowering does not allocate. Neither committed task recurses.
            raise NotImplementedError(
                "recursive call to a seq-returning task is not supported "
                "by this lowering (no C value-position representation "
                "for a seq)")
        parts = []
        for p, a in zip(funs[task_name]["params"], c["args"], strict=True):
            if p["type"] == "seq":
                s = seq_var(a, env)
                parts += [s, f"{s}_n"]
            else:
                parts.append(cexpr(a, env, funs, task_name, _div_style))
        return f"{task_name}_t({', '.join(parts)})"
    op, args = e["op"], e.get("args", [])
    if op == "len":
        return f"{seq_var(args[0], env)}_n"
    if op == "at":
        return (f"{seq_var(args[0], env)}"
                f"[{cexpr(args[1], env, funs, task_name, _div_style)}]")
    if op == "neg":
        return f"(-{_gap(cexpr(args[0], env, funs, task_name, _div_style))})"
    if op == "not":
        return f"(!{cexpr(args[0], env, funs, task_name, _div_style)})"
    if op == "implies":
        a, b = (cexpr(x, env, funs, task_name, _div_style) for x in args)
        return f"((!({a})) || ({b}))"
    if op in ("and", "or"):
        glue = " && " if op == "and" else " || "
        return ("(" + glue.join(cexpr(a, env, funs, task_name, _div_style)
                                for a in args) + ")")
    if op in DIVMOD:
        xc = cexpr(args[0], env, funs, task_name, _div_style)
        yc = cexpr(args[1], env, funs, task_name, _div_style)
        rem = f"(({xc}) % ({yc}))"
        if _div_style == "ternary":
            # ACSL-annotation-safe, see `_divmod_ternary_cexpr`: the
            # pre-2026-09-09 shape, syntactically parallel to
            # T_DIVMOD_ACSL's own definition.
            if op == "mod":
                return (f"({rem} < 0 ? {rem} + "
                        f"(({yc}) < 0 ? -({yc}) : ({yc})) : {rem})")
            quo = f"(({xc}) / ({yc}))"
            return (f"({rem} < 0 ? {quo} - (({yc}) > 0 ? 1 : -1) : {quo})")
        # BRANCH-FREE, corrected 2026-09-09 (see the DIV/MOD SMOKE note
        # below): C's `/`/`%` truncate toward zero (measured, see
        # T_DIVMOD_ACSL), and the correction from truncating to Euclidean
        # used to be a C `?:` matching t_mod/t_div's own ternary shape.
        # That ternary is a live branch in EXECUTABLE position, and once a
        # task's invariants pin the sign of x or y (x >= 0 in a loop, a
        # fixed positive y), one arm becomes provably unreachable and
        # -wp-smoke-tests dooms it. So this rendering never emits `?:`:
        # `(cond)` used as a C int is already 0 or 1 with no branch node,
        # and the correction term is built by arithmetic on that 0/1
        # value instead of by selecting between two evaluated arms.
        neg = f"({rem} < 0)"          # 0 or 1, not a branch
        y_neg = f"(({yc}) < 0)"       # 0 or 1
        if op == "mod":
            abs_y = f"((1 - 2 * {y_neg}) * ({yc}))"
            return f"({rem} + {neg} * {abs_y})"
        quo = f"(({xc}) / ({yc}))"
        y_pos = f"(({yc}) > 0)"       # 0 or 1
        sign_y = f"({y_pos} - {y_neg})"          # 1 or -1 (y != 0)
        return f"({quo} - {neg} * {sign_y})"
    if op in ARITH or op in CMP:
        o = ARITH.get(op) or CMP[op]
        return (f"({cexpr(args[0], env, funs, task_name, _div_style)} {o} "
                f"{cexpr(args[1], env, funs, task_name, _div_style)})")
    raise ValueError(f"t has no operator {op!r}")


def _divmod_ternary_cexpr(e: dict, env: dict, funs: dict,
                          task_name: str) -> str:
    """`cexpr()` with `_div_style="ternary"`, kept for exactly one use: the
    "dm" bridging assert (see `at_asserts` below), which sits inside an
    ACSL annotation, not executable C. Measured 2026-09-09: a `?:` inside
    `/*@ assert ... */` is never a WP smoke target (the doomed goals on
    fz_p_ret_bothbranches and the extra_mod lifted task both named the
    bare C statement's line, never the assert's own line, for the
    identical ternary shape), so there is no reason to also make this one
    branch-free, and every reason not to: staying ternary at EVERY
    nesting level (not only the top one) keeps this ACSL-legal (a `\\prop`
    like `x % y < 0` cannot be multiplied into an `integer`, which is
    exactly how isArmstrong's nested `t_mod(t_div(n, 10), 10)` bridging
    assert failed to parse before `_div_style` started threading through
    every recursive `cexpr` call) and syntactically parallel to
    T_DIVMOD_ACSL's own definition, which is what keeps the bridging
    equality a near-syntactic unfold rather than a fresh arithmetic
    proof. The default `cexpr(..., _div_style="bf")` (used everywhere
    else, including for any executable-position operand of a call whose
    surrounding context is this ternary form) is the branch-free one;
    this helper must never be used for code that becomes part of an
    executable C statement."""
    return cexpr(e, env, funs, task_name, _div_style="ternary")


def code_ats(e: dict, env: dict, uncond: bool = True) -> list:
    """Definedness obligations for every `at`, `div` and `mod` in an
    executable expression, as tagged tuples: `("at", seq, index-expr)`,
    `("nz", divisor-expr)`, or `("dm", div-or-mod-node)`. Unconditionally
    evaluated occurrences are returned (they get an assert in front of the
    statement); a conditionally evaluated one is refused, because emitting
    it without a dischargeable guard would silently totalize the operator
    as C UB (an unguarded `at` as out-of-bounds access, an unguarded
    `div`/`mod` as division by zero).

    "dm", added 2026-09-08 alongside `return`: MEASURED on is_prime, whose
    `return` sits behind `if (n % d == 0)`. WP proves `t_mod(n,d) == 0` as
    a hypothesis instantly when it is stated as a logic call (probe:
    `requires t_mod(n,d)==0` discharges the postcondition's existential in
    under 20ms), but times out (20000 steps, 60s wall) when the only
    hypothesis is the raw inlined C ternary `cexpr` renders for `mod`
    (same value, unfolds to the same formula by `t_mod`'s own definition,
    measured equal in isolation in under 15ms): the postcondition's
    `\\exists`/negated-`\\forall` needs a GROUND `t_mod(n, d)` term to
    match its trigger and instantiate `d`, and the raw ternary alone never
    puts that logic-shaped term anywhere in scope. So a `div`/`mod` node
    now also gets a value-bridging assert, `(raw expr) == (logic call)`,
    giving WP the exact term its own quantifiers need without changing
    what is proved, only what is available to prove it with."""
    out = []
    if "ite" in e:
        i = e["ite"]
        out += code_ats(i["cond"], env, uncond)
        out += code_ats(i["then"], env, False)
        out += code_ats(i["else"], env, False)
        return out
    if "call" in e:
        for a in e["call"]["args"]:
            out += code_ats(a, env, uncond)
        return out
    if "op" not in e:
        return out
    op, args = e["op"], e.get("args", [])
    if op == "at":
        if not uncond:
            raise NotImplementedError(
                "conditionally evaluated `at` in executable position: "
                "definedness not dischargeable by a plain assert")
        out += code_ats(args[1], env, uncond)
        out.append(("at", seq_var(args[0], env), args[1]))
        return out
    if op in DIVMOD:
        if not uncond:
            raise NotImplementedError(
                "conditionally evaluated `div`/`mod` in executable "
                "position: definedness not dischargeable by a plain assert")
        out += code_ats(args[0], env, uncond)
        out += code_ats(args[1], env, uncond)
        out.append(("nz", args[1]))
        out.append(("dm", e))
        return out
    if op in ("and", "or"):
        out += code_ats(args[0], env, uncond)
        for a in args[1:]:
            out += code_ats(a, env, False)
        return out
    if op == "implies":
        out += code_ats(args[0], env, uncond)
        out += code_ats(args[1], env, False)
        return out
    for a in args:
        out += code_ats(a, env, uncond)
    return out


def at_asserts(e: dict, ctx: Ctx, indent: str, funs=None,
               task_name: str | None = None) -> list:
    """`funs`/`task_name` are given by callers that emit real, branching C
    (stmts()): they let the "dm" tag add the raw/logic bridging assert
    (see code_ats). The certificate replay (_cert_stmts) calls this
    without them, deliberately: its own `_cert_cexpr` already resolves
    every div/mod to a branch-free ground form, and rendering one through
    plain `cexpr` here would put a live ternary back into the certificate,
    exactly the dead-code-smoke hazard `_cert_cexpr`'s docstring measured
    and fixed."""
    out = []
    for tag, *rest in code_ats(e, ctx.env):
        if tag == "at":
            s, ix = rest
            out.append(f"{indent}/*@ assert 0 <= ({term(ix, ctx)}) "
                       f"&& ({term(ix, ctx)}) < {s}_n; */")
        elif tag == "nz":
            (yx,) = rest
            out.append(f"{indent}/*@ assert ({term(yx, ctx)}) != 0; */")
        else:                                      # "dm": bridging assert
            (node,) = rest
            if funs is not None and task_name is not None:
                # `_divmod_ternary_cexpr`, not `cexpr`: this text lands
                # inside an ACSL annotation, where the branch-free form
                # `cexpr` now renders for executable position is not even
                # legal ACSL (a `\prop` cannot multiply an `integer`), and
                # the ternary form is not smoke-tested here regardless
                # (see `_divmod_ternary_cexpr`'s docstring).
                out.append(f"{indent}/*@ assert "
                           f"({_divmod_ternary_cexpr(node, ctx.env, funs, task_name)}) == "
                           f"({term(node, ctx)}); */")
    return out


# --------------------------------------------------- seq value machinery ----
#
# THE ENCODING (2026-09-09, SPEC.md "Sequences as values"). C has no
# sequence value at all, so every column measures its own answer to what a
# `seq` local/return IS in C; this one is measured on the two committed
# tasks below (`swap`'s `update`, `reverse`'s `fill` + loop `update`) with
# a hand-written probe verified by frama-c/WP BEFORE this code was written
# (RULES: measure first). A seq PARAM was already `int *s, int s_n`
# (read-only, `\valid_read`); a seq RETURN gets the SAME pair appended to
# the C signature as an OUTPUT parameter (`int *r, int r_n`), caller
# writable (`\valid`), separated from every other seq buffer
# (`\separated`), and its length pinned by a `requires {r}_n ==
# <len-expr>;` where <len-expr> is the return's length computed
# STATICALLY from the body (`_seq_len_track`, below) and rendered in
# PARAMS-only terms (ACSL `requires` has no locals in scope). This is
# candidate (B) of the three the task brief named (a caller-provided
# output buffer, not an ACSL `\list`/axiomatised logic sequence, and not a
# ghost-only encoding): every `s[i := v]`/`seq(n, v)` becomes a REAL
# memory store into that buffer, proven by WP's own points-to reasoning
# over ordinary C writes, nothing bespoke.
#
# What this candidate CANNOT express, stated rather than discovered late:
# the return buffer's requires-time validity bound must be a term over
# PARAMS ALONE (ACSL's `requires` scope), so a `fill` whose length is not
# reducible, by `_seq_len_track`, to an expression over the task's own
# params (an index expression built from other LOCALS with no closed form
# in terms of params, or a length that differs across `if`/`while`
# branches) has no buffer size to request from the caller and this
# lowering refuses the task (NotImplementedError) rather than guess one.
# The measured alternative from the task brief, a `t_len_r` OUT-parameter
# the callee itself WRITES, would lift that restriction for the LENGTH
# (the callee could compute and report it), but not for the buffer's own
# VALIDITY bound, which is still owed to the caller before the call and so
# still needs an expression fixed in advance; not implemented, since
# neither committed task needs it (both `update` and `fill` here reduce to
# `len(s)`, a bare param length).
#
# A seq-typed LOCAL (`var a: seq := s;`, SPEC.md's other new position) is
# NOT implemented: it would need its own backing storage with no external
# contract to size it from (v1's own scope rule keeps locals out of
# `ensures`, so there is no requires-time bound to borrow), and neither
# committed task declares one. `stmts()`'s `var` case refuses it by name.


def _expr_seq_len(e: dict, lens: dict) -> dict | None:
    """The t Expr for the length of the seq value `e` denotes, given the
    lengths already tracked for every seq name in scope (`lens`), or None
    when `e`'s length cannot be determined this way (SPEC.md's grammar:
    a seq-typed assignment's right-hand side is always a bare seq
    variable, `update`, or `fill`; `update` preserves its base's length,
    `fill`'s length is its own first argument, a variable's length is
    whatever is already tracked for it)."""
    if "var" in e:
        return lens.get(e["var"])
    if "op" in e and e["op"] == "update":
        base = e["args"][0]
        return lens.get(base.get("var")) if "var" in base else None
    if "op" in e and e["op"] == "fill":
        return e["args"][0]
    return None


def _seq_len_track(body: list, lens: dict) -> None:
    """Extends `lens` (seq name -> t Expr for its current length) by
    walking `body`'s seq-typed assignments in program order. `if` requires
    both branches to agree (structurally equal Exprs, or both silent) on
    every name's length, since the length feeds a `requires` clause that
    must hold on every path; `while` requires the loop body to leave every
    tracked length UNCHANGED (an update-only loop, like reverse's), since a
    length that only holds after N iterations has no single closed form
    before the call. Either mismatch drops the name from `lens` rather
    than raising: the caller (`lower()`) raises only if the RETURN's own
    length is what came up unresolved, so an untracked length elsewhere in
    the body (of no interest to any `requires`) is not an error here."""
    for s in body:
        if "assign" in s:
            name, e = s["assign"]
            new = _expr_seq_len(e, lens)
            if new is not None:
                lens[name] = new
            else:
                lens.pop(name, None)
        elif "return" in s:
            name, e = s["return"]
            new = _expr_seq_len(e, lens)
            if new is not None:
                lens[name] = new
            else:
                lens.pop(name, None)
        elif "var" in s:
            pass                       # seq locals are refused elsewhere
        elif "if" in s:
            then_lens, else_lens = dict(lens), dict(lens)
            _seq_len_track(s["if"]["then"], then_lens)
            _seq_len_track(s["if"]["else"], else_lens)
            for k in set(then_lens) | set(else_lens):
                if then_lens.get(k) == else_lens.get(k) and k in then_lens:
                    lens[k] = then_lens[k]
                else:
                    lens.pop(k, None)
        elif "while" in s:
            inner = dict(lens)
            _seq_len_track(s["while"]["body"], inner)
            for k, v in list(lens.items()):
                if inner.get(k) != v:
                    lens.pop(k, None)


def seq_assign_lines(target: str, e: dict, ctx: Ctx, indent: str,
                     funs: dict, task_name: str) -> list:
    """C statements implementing `target := e`, `target` a seq-typed name,
    `e` a bare seq variable (a full copy), `update`, or `fill` (the only
    shapes `_expr_seq_len` and `seq_var` admit). Every one of these writes
    `target`'s buffer through real memory stores: `update`'s base operand,
    when it names a DIFFERENT buffer than `target` (swap's `r := s[i :=
    ...]`, its first write to `r`), is copied in first, a whole-buffer
    loop with invariant `target[t] == base[t]` for `t` below the loop
    counter, exactly SPEC.md's "equal to `s` at every index but `i`"; a
    SELF update (`r := r[j := tmp]`, swap's second write, and reverse's
    per-iteration `r := r[i := ...]`) skips the copy, since `target`
    already holds exactly what `base` denotes. `fill` never reads a prior
    value, so the whole buffer is written by one loop, no copy. Measured
    2026-09-09 by hand (frama-c/WP) on both tasks in exactly this shape
    before this function was written (RULES: measure first)."""
    out = []
    xn = f"{target}_n"

    def _copy_loop(src: str) -> list:
        return [
            f"{indent}/*@",
            f"{indent}  loop invariant 0 <= __k <= {xn};",
            f"{indent}  loop invariant \\forall integer __t; "
            f"0 <= __t < __k ==> {target}[__t] == {src}[__t];",
            f"{indent}  loop assigns __k, {target}[0 .. {xn} - 1];",
            f"{indent}  loop variant {xn} - __k;",
            f"{indent}*/",
            f"{indent}for (int __k = 0; __k < {xn}; __k++) "
            f"{target}[__k] = {src}[__k];",
        ]

    if "var" in e:
        src = seq_var(e, ctx.env)
        out += _copy_loop(src)
        return out
    op, args = e["op"], e["args"]
    if op == "update":
        src = seq_var(args[0], ctx.env)
        out += at_asserts(args[1], ctx, indent, funs, task_name)
        out += at_asserts(args[2], ctx, indent, funs, task_name)
        ic = cexpr(args[1], ctx.env, funs, task_name)
        out.append(f"{indent}/*@ assert 0 <= ({ic}) && ({ic}) < {src}_n; */")
        if src != target:
            out += _copy_loop(src)
        vc = cexpr(args[2], ctx.env, funs, task_name)
        out.append(f"{indent}{target}[{ic}] = {vc};")
        return out
    if op == "fill":
        out += at_asserts(args[0], ctx, indent, funs, task_name)
        out += at_asserts(args[1], ctx, indent, funs, task_name)
        nc = cexpr(args[0], ctx.env, funs, task_name)
        out.append(f"{indent}/*@ assert ({nc}) >= 0; */")
        vc = cexpr(args[1], ctx.env, funs, task_name)
        out += [
            f"{indent}/*@",
            f"{indent}  loop invariant 0 <= __k <= {xn};",
            f"{indent}  loop invariant \\forall integer __t; "
            f"0 <= __t < __k ==> {target}[__t] == ({vc});",
            f"{indent}  loop assigns __k, {target}[0 .. {xn} - 1];",
            f"{indent}  loop variant {xn} - __k;",
            f"{indent}*/",
            f"{indent}for (int __k = 0; __k < {xn}; __k++) "
            f"{target}[__k] = {vc};",
        ]
        return out
    raise NotImplementedError(
        f"seq-typed assignment from operator {op!r}: v1's grammar only "
        f"assigns a bare seq variable, `update`, or `fill` to a seq-typed "
        f"name")


def assigned_names(body: list) -> tuple[list, list]:
    """(assign targets, locals declared) in order, recursively."""
    hit, dec = [], []
    for s in body:
        if "assign" in s:
            hit.append(s["assign"][0])
        elif "return" in s:
            hit.append(s["return"][0])
        elif "var" in s:
            dec.append(s["var"]["name"])
        elif "if" in s:
            for br in (s["if"]["then"], s["if"]["else"]):
                h, d = assigned_names(br)
                hit += h
                dec += d
        elif "while" in s:
            h, d = assigned_names(s["while"]["body"])
            hit += h
            dec += d
    return hit, dec


def _assigns_target(n: str, ctx: Ctx) -> str:
    """One name's own `loop assigns`/entry, a bare name for int/bool, the
    whole element range for a seq (its POINTER never changes, only what it
    points to; naming the bare pointer here would claim WP need not track
    that the pointee changes at all, which is false for every task that
    mutates a seq inside a loop, `reverse` included)."""
    return f"{n}[0 .. {n}_n - 1]" if ctx.env.get(n) == "seq" else n


def stmts(body: list, ctx: Ctx, task_name: str, indent: str) -> list:
    out = []
    for s in body:
        if "assign" in s:
            name, e = s["assign"]
            assert name in ctx.env, f"assign to undeclared {name}"
            if ctx.env[name] == "seq":
                out += seq_assign_lines(name, e, ctx, indent, ctx.funs,
                                        task_name)
            else:
                out += at_asserts(e, ctx, indent, ctx.funs, task_name)
                out.append(f"{indent}{name} = "
                           f"{cexpr(e, ctx.env, ctx.funs, task_name)};")
        elif "return" in s:
            # Early exit (v1, 2026-09-08): `Expr` is in the same position as
            # an assignment's right-hand side, so it owes the same
            # definedness asserts (the `at` bound, the `!= 0` divisor). A
            # real C `return` then ends the function immediately, from
            # whatever nesting depth of `if`/`while` it sits at, which is
            # exactly SPEC's rule: WP proves `ensures` at every return and
            # never demands the enclosing loop's invariant there, because
            # the loop is simply not reached again. Nothing may follow this
            # statement in its own block (well-formedness's job, not this
            # file's), so no dead-code smoke goal can arise from it: the
            # code after the enclosing `if` remains reachable on the other
            # branch, never on this one.
            #
            # A seq-typed return (2026-09-09) has no scalar C `return`
            # value at all: `lower()` gives it an output buffer parameter
            # instead (see the seq value machinery section), so an early
            # exit writes that buffer the same way an ordinary assignment
            # to it would and then leaves with a bare, void `return;`.
            name, e = s["return"]
            assert name in ctx.env, f"return of undeclared {name}"
            if ctx.env[name] == "seq":
                out += seq_assign_lines(name, e, ctx, indent, ctx.funs,
                                        task_name)
                out.append(f"{indent}return;")
            else:
                out += at_asserts(e, ctx, indent, ctx.funs, task_name)
                out.append(f"{indent}{name} = "
                           f"{cexpr(e, ctx.env, ctx.funs, task_name)};")
                out.append(f"{indent}return {name};")
        elif "var" in s:
            v = s["var"]
            if v["type"] == "seq":
                # SPEC.md allows a seq-typed LOCAL (`var a: seq := s;`);
                # this lowering does not implement one (see the seq value
                # machinery section's docstring): a local has no external
                # contract to size its backing buffer from, and neither
                # committed task declares one, so this is a stated scope
                # limit, not a silent gap.
                raise NotImplementedError(
                    "seq-typed local variables are not supported by this "
                    "lowering (no requires-time bound to size a backing "
                    "buffer from); only a seq RETURN is implemented")
            out += at_asserts(v["init"], ctx, indent, ctx.funs, task_name)
            ctx = ctx.bind(v["name"], v["type"])
            out.append(f"{indent}int {v['name']} = "
                       f"{cexpr(v['init'], ctx.env, ctx.funs, task_name)};")
        elif "if" in s:
            c = s["if"]
            out += at_asserts(c["cond"], ctx, indent, ctx.funs, task_name)
            out.append(f"{indent}if "
                       f"({cexpr(c['cond'], ctx.env, ctx.funs, task_name)}) "
                       f"{{")
            out += stmts(c["then"], ctx, task_name, indent + "  ")
            out.append(f"{indent}}} else {{")
            out += stmts(c["else"], ctx, task_name, indent + "  ")
            out.append(f"{indent}}}")
        elif "while" in s:
            w = s["while"]
            if code_ats(w["cond"], ctx.env):
                raise NotImplementedError(
                    "`at`/`div`/`mod` in a while condition: its "
                    "per-iteration definedness assert has no statement to "
                    "precede")
            ann = [f"{indent}  loop invariant {pred(i, ctx)};"
                   for i in w.get("invariants", [])]
            hit, dec = assigned_names(w["body"])
            frame = [n for n in dict.fromkeys(hit) if n not in dec]
            targets = [_assigns_target(n, ctx) for n in frame]
            ann.append(f"{indent}  loop assigns "
                       f"{', '.join(targets) if targets else chr(92) + 'nothing'};")
            ann.append(f"{indent}  loop variant ({term(w['decreases'], ctx)});")
            out.append(f"{indent}/*@")
            out += ann
            out.append(f"{indent}*/")
            out.append(f"{indent}while "
                       f"({cexpr(w['cond'], ctx.env, ctx.funs, task_name)}) "
                       f"{{")
            out += stmts(w["body"], ctx, task_name, indent + "  ")
            out.append(f"{indent}}}")
        else:
            raise ValueError(f"t has no statement {s!r}")
    return out


# ------------------------------------------------- spec_fun termination -----

def subst(e: dict, m: dict) -> dict:
    if "var" in e:
        return m.get(e["var"], e)
    if "int" in e or "bool" in e:
        return e
    if "ite" in e:
        i = e["ite"]
        return {"ite": {k: subst(i[k], m) for k in ("cond", "then", "else")}}
    if "call" in e:
        c = e["call"]
        return {"call": {"fun": c["fun"],
                         "args": [subst(a, m) for a in c["args"]]}}
    for kind in ("forall", "exists"):
        if kind in e:
            q = e[kind]
            m2 = {k: v for k, v in m.items() if k != q["var"]}
            return {kind: {"var": q["var"], "lo": subst(q["lo"], m),
                           "hi": subst(q["hi"], m),
                           "body": subst(q["body"], m2)}}
    return {"op": e["op"], "args": [subst(a, m) for a in e.get("args", [])]}


def self_calls(e: dict, fun: str, path: list) -> list:
    """(args, path-conditions) for every self-call, path tracked through the
    definedness-relevant branching structure (ite branches, and/or/implies
    short-circuit)."""
    out = []
    if "ite" in e:
        i = e["ite"]
        out += self_calls(i["cond"], fun, path)
        out += self_calls(i["then"], fun, path + [i["cond"]])
        out += self_calls(i["else"], fun,
                          path + [{"op": "not", "args": [i["cond"]]}])
        return out
    if "call" in e:
        c = e["call"]
        for a in c["args"]:
            out += self_calls(a, fun, path)
        if c["fun"] == fun:
            out.append((c["args"], path))
        return out
    for kind in ("forall", "exists"):
        if kind in e:
            q = e[kind]
            for sub in (q["lo"], q["hi"], q["body"]):
                out += self_calls(sub, fun, path)
            return out
    if "op" not in e:
        return out
    op, args = e["op"], e.get("args", [])
    if op in ("and", "or"):
        seen = []
        for a in args:
            out += self_calls(a, fun, path + seen)
            g = a if op == "and" else {"op": "not", "args": [a]}
            seen = seen + [g]
        return out
    if op == "implies":
        out += self_calls(args[0], fun, path)
        out += self_calls(args[1], fun, path + [args[0]])
        return out
    for a in args:
        out += self_calls(a, fun, path)
    return out


def spec_fun_acsl(f: dict, funs: dict) -> list:
    """The recursive logic definition plus its measured termination lemmas
    (WP does not check logic-function termination itself; see docstring)."""
    env = {p["name"]: p["type"] for p in f["params"]}
    labeled = funs[f["name"]]["labeled"]
    lab = "{L}" if labeled else ""
    sig = []
    for p in f["params"]:
        if p["type"] == "seq":
            sig += [f"int *{p['name']}", f"integer {p['name']}_n"]
        else:
            sig.append(f"integer {p['name']}")
    body_ctx = Ctx(env, funs, ret=None, label="L")
    res = {"int": "integer", "bool": "boolean"}[f["result"]]
    lines = [f"/*@ logic {res} {f['name']}{lab}({', '.join(sig)}) =",
             f"      {term(f['body'], body_ctx)};", "*/"]
    quant = ", ".join(
        (f"int *{p['name']}, integer {p['name']}_n"
         if p["type"] == "seq" else f"integer {p['name']}")
        for p in f["params"])
    for k, (args, path) in enumerate(self_calls(f["body"], f["name"], []), 1):
        m = {p["name"]: a for p, a in zip(f["params"], args, strict=True)}
        measure = term(f["decreases"], body_ctx)
        measure2 = term(subst(f["decreases"], m), body_ctx)
        concl = f"(({measure2}) >= 0 && ({measure2}) < ({measure}))"
        guard = " && ".join(f"({pred(p, body_ctx)})" for p in path)
        prop = f"({guard}) ==> {concl}" if guard else concl
        lines += [f"/*@ lemma {f['name']}_terminates_{k}{lab}:",
                  f"      \\forall {quant};",
                  f"      {prop};", "*/"]
    return lines


# ------------------------------------------------ refutation certificate ----
#
# THE CERTIFICATE (shared protocol, ROADMAP 10.7): WP with alt-ergo never
# distinguishes a false goal from a hard one (verifiers/framac.py records the
# side-by-side measurement), so the adapter no longer mints REFUTED from an
# unproved goal. To EARN a twin refutation, the twin file carries a second
# function that replays the twin computation at the measured witness input as
# straight-line ground code, ending in one ACSL assert named exactly
# t_refutation_certificate: the negation of the instantiated ensures
# (definedness guards included, since t counts an undefined ensures as
# unsatisfied). The adapter mints REFUTED only when the kernel accepts that
# assert AND every other goal of the certificate function; a rejected
# certificate is UNPROVED, never REFUTED.
#
# Branch discipline, measured 2026-09-02: a ground-decided `if` in the
# certificate makes its untaken arm dead code, and -wp-smoke-tests fails the
# dead-code smoke goal (`Failed smoke-test` on cert_deadif.c), which scores
# the whole file VACUOUS. So the certificate contains NO branches at all:
# every `if` is resolved to the taken arm behind an emitted
# `/*@ assert cond; */` (or its negation), and every `while` is unrolled to
# its measured trace, one `assert cond;` per iteration plus a final
# `assert !cond;`. Each branch decision is therefore a kernel-checked goal:
# if the lowering's replay disagrees with the program, some assert fails,
# the certificate is rejected, and the file honestly reads UNPROVED. A
# mis-replay can never mint, only fail.
#
# Scope, stated rather than stretched: a whole-program `value` witness whose
# twin value falsifies `ensures` (_ens is True) is certificatable by
# `_value_certificate`, straight-line ground replay from the params, exactly
# as above. A twin body carrying a task self-call (recursion has no bounded
# ground unrolling here) is skipped there. Skipping means the twin cell reads
# timeout/unproved and the flip is honestly lost.
#
# Two more kinds, added 2026-09-09 for SPEC.md "Sequences as values" (the
# construct that also added `update`/`fill`, whose committed tasks measure
# one of each):
#
#   `undefined` (`_undef_certificate`): the twin has NO VALUE at the
#   witness, because some statement's right-hand side hit a partial
#   operator (`at`, `update`, `fill`, `div`, `mod`) outside its domain
#   before `ensures` could even be instantiated. What is ground and
#   checkable is the operator's OWN definedness obligation: re-walk the
#   twin body with `interp.ev`, in the same left-to-right order
#   `interp.py`'s own `exec_body` used to raise the `Undef` that minted
#   this witness kind, using `defs_t` (the SAME definedness rule `defs()`
#   already renders to ACSL, restated as a t formula so `interp.ev` can
#   decide it), and certify the negation of the first one that comes back
#   false. Unlike the value-kind certificate, no C statement is replayed:
#   every name the obligation can mention is either a task param (declared
#   ground, exactly as the value-kind branch already declares them) or an
#   int/bool local computed along the way (declared ground as the walk
#   proceeds), so the obligation renders straight through this file's own
#   `pred()`. A SEQ-typed intermediate local assigned before the failing
#   statement refuses (materializing its snapshot would need the full
#   replay this shortcut exists to avoid); swap's own undefined witness
#   fails on the body's FIRST statement, so this is not exercised there,
#   only documented for the next task that might need it.
#
#   `exit` (`_exit_certificate`): interp.invariant_witness's own
#   obligation restated: a loop STATE where the surviving invariants hold,
#   the guard is false, but `ensures` is false there. Unlike a `value`
#   witness this state is not REACHED by running the function from its
#   params (`_Admissible` screens for states a sound kernel cannot rule
#   out, not for states an actual run passes through), so it is declared
#   directly as ground C locals -- every name the witness names, params
#   and loop-scope locals alike, the same declare-a-ground-array-or-int
#   shape the value-kind branch already uses for params -- and
#   `_cert_stmts` (unmodified) replays only the twin's mutated loop onward
#   (`_loop_suffix`), which correctly computes zero further iterations
#   when the witness already has the guard false, exactly reverse's own
#   measured case. Scope limit: only a TOP-LEVEL loop (not nested under an
#   `if`) is handled; no committed task's exit witness has needed more.
#
# Both new kinds reuse `_cert_stmts`/`_cev`/`_cert_cexpr` only where those
# already work (ground replay of ordinary, non-seq-assigning statements);
# neither extends them to emit a seq-typed assignment's C text (the copy
# and fill loops `seq_assign_lines` renders for the REAL/twin function
# bodies): an update/fill node reaching `_cert_cexpr` still raises its
# existing `ValueError` for an unrecognized operator, caught by
# `certificate`'s dispatcher exactly like every other unexpressible
# witness, and that cell honestly reads unproved rather than certifying
# something unmeasured.

CERT_FN = "t_certificate"
CERT_GOAL = "t_refutation_certificate"
MAX_CERT_STMTS = 256


class _CertSkip(Exception):
    """This witness cannot be expressed as a ground certificate; the twin
    file is emitted without one (never a hard failure)."""


def _cev(e: dict, st: dict):
    """Ground evaluation of an EXECUTABLE t expression at concrete state,
    used only to pick branches and count loop iterations. Every decision it
    makes is re-emitted as a kernel goal, so a slip here rejects the
    certificate rather than corrupting it."""
    if "int" in e:
        return e["int"]
    if "bool" in e:
        return e["bool"]
    if "var" in e:
        if e["var"] not in st:
            raise _CertSkip(f"unassigned variable {e['var']} read")
        return st[e["var"]]
    if "ite" in e:
        i = e["ite"]
        return _cev(i["then"] if _cev(i["cond"], st) else i["else"], st)
    if "call" in e:
        raise _CertSkip("call in executable position")
    if "forall" in e or "exists" in e:
        raise _CertSkip("quantifier in executable position")
    op, args = e["op"], e.get("args", [])
    if op == "len":
        return len(_cev(args[0], st))
    if op == "at":
        s, i = _cev(args[0], st), _cev(args[1], st)
        if not 0 <= i < len(s):
            raise _CertSkip("undefined at in replay")
        return s[i]
    if op == "update":
        # SPEC.md "Sequences as values" (2026-09-09), interp.py's own
        # ground rule: a fresh list, `s` unchanged, DEFINED IFF
        # `0 <= i < len(s)`, `at`'s own bound. Not currently reached by
        # `_cert_stmts`/`_cert_cexpr` (neither renders a seq-typed
        # assignment's C text; see the seq value machinery section), kept
        # here only so `_cev` itself stays a complete, honest ground
        # semantics for every t operator, the same reason `at` is here at
        # all rather than only where it happens to be used today.
        s, i, v = (_cev(args[0], st), _cev(args[1], st), _cev(args[2], st))
        if not 0 <= i < len(s):
            raise _CertSkip("undefined update in replay")
        return s[:i] + [v] + s[i + 1:]
    if op == "fill":
        n, v = _cev(args[0], st), _cev(args[1], st)
        if n < 0:
            raise _CertSkip("undefined fill in replay")
        return [v] * n
    if op in DIVMOD:
        # SPEC.md Euclidean div/mod, same ground formula as interp.py: the
        # Python `%` with an absolute-value modulus already returns the
        # Euclidean remainder (always in [0, |y|)), so the quotient falls
        # out of the division law exactly.
        x, y = _cev(args[0], st), _cev(args[1], st)
        if y == 0:
            raise _CertSkip(f"undefined {op} in replay")
        r = x % abs(y)
        return r if op == "mod" else (x - r) // y
    if op == "neg":
        return -_cev(args[0], st)
    if op == "not":
        return not _cev(args[0], st)
    if op == "and":
        return all(_cev(a, st) for a in args)
    if op == "or":
        return any(_cev(a, st) for a in args)
    if op == "implies":
        return (not _cev(args[0], st)) or _cev(args[1], st)
    if op in ARITH:
        a, b = _cev(args[0], st), _cev(args[1], st)
        return {"+": a + b, "-": a - b, "*": a * b}[op]
    if op in CMP:
        a, b = _cev(args[0], st), _cev(args[1], st)
        return {"==": a == b, "!=": a != b, "<": a < b, "<=": a <= b,
                ">": a > b, ">=": a >= b}[op]
    raise _CertSkip(f"no ground evaluation for operator {op!r}")


def _cert_cexpr(e: dict, ctx: Ctx, st: dict, funs: dict, name: str,
                asserts: list, ind: str) -> str:
    """cexpr(), specialized for the certificate replay: every `div`/`mod`
    is rendered branch-free (no C ternary), the ground-decided condition
    going to `asserts` instead.

    Measured 2026-09-08 on remainder's wrong-var twin (x -> y makes the
    mod `y % y`, always 0): cexpr()'s ternary form for div/mod put a live
    `?:` in the certificate function, and -wp-smoke-dead-local-init flagged
    its now-unreachable positive-remainder arm as dead code
    (typed_nat_t_certificate_wp_smoke_dead_code_s24/s25). Ordinary dead
    code in a t function is fine (`_all_obligations_proved` subtracts smoke
    tallies), but the certificate's OWN audit (`_cert_status`) requires
    every goal of its enclosing function proved with no such exemption, so
    a live ternary there can never mint, only fail (the certificate
    section docstring's branch discipline, now extended to div/mod). The
    fix mirrors how `if`/`while` are unrolled: resolve the ternary at the
    ground state, assert the resolved condition (a real, Qed-checked goal,
    not an assumption), and emit only the taken arm."""
    if not _has_divmod(e):
        return cexpr(e, ctx.env, funs, name)
    if "ite" in e:
        raise _CertSkip("`ite` in executable position within the "
                        "certificate replay")
    if "call" in e:
        raise _CertSkip("call in executable position within the "
                        "certificate replay")
    op, args = e["op"], e.get("args", [])
    if op in DIVMOD:
        x_e, y_e = args
        xc = _cert_cexpr(x_e, ctx, st, funs, name, asserts, ind)
        yc = _cert_cexpr(y_e, ctx, st, funs, name, asserts, ind)
        xv, yv = _cev(x_e, st), _cev(y_e, st)
        if yv == 0:
            raise _CertSkip(f"undefined {op} in replay")
        qv = abs(xv) // abs(yv)
        if (xv < 0) != (yv < 0):
            qv = -qv
        rv = xv - qv * yv                       # C-truncating remainder
        rem = f"(({xc}) % ({yc}))"
        neg = rv < 0
        asserts.append(f"{ind}/*@ assert {rem} {'<' if neg else '>='} 0; */")
        if op == "mod":
            if not neg:
                return rem
            ysign_neg = yv < 0
            asserts.append(f"{ind}/*@ assert ({yc}) "
                           f"{'<' if ysign_neg else '>'} 0; */")
            return f"({rem} + ({f'-({yc})' if ysign_neg else yc}))"
        quo = f"(({xc}) / ({yc}))"
        if not neg:
            return quo
        ysign_pos = yv > 0
        asserts.append(f"{ind}/*@ assert ({yc}) "
                       f"{'>' if ysign_pos else '<'} 0; */")
        return f"({quo} - ({'1' if ysign_pos else '-1'}))"
    if op == "len":
        return f"{seq_var(args[0], ctx.env)}_n"
    if op == "at":
        return (f"{seq_var(args[0], ctx.env)}"
                f"[{_cert_cexpr(args[1], ctx, st, funs, name, asserts, ind)}]")
    if op == "neg":
        sub = _cert_cexpr(args[0], ctx, st, funs, name, asserts, ind)
        return f"(-{_gap(sub)})"
    if op == "not":
        sub = _cert_cexpr(args[0], ctx, st, funs, name, asserts, ind)
        return f"(!{sub})"
    if op == "implies":
        a, b = (_cert_cexpr(x, ctx, st, funs, name, asserts, ind)
                for x in args)
        return f"((!({a})) || ({b}))"
    if op in ("and", "or"):
        glue = " && " if op == "and" else " || "
        return "(" + glue.join(_cert_cexpr(a, ctx, st, funs, name, asserts,
                                           ind) for a in args) + ")"
    if op in ARITH or op in CMP:
        o = ARITH.get(op) or CMP[op]
        a = _cert_cexpr(args[0], ctx, st, funs, name, asserts, ind)
        b = _cert_cexpr(args[1], ctx, st, funs, name, asserts, ind)
        return f"({a} {o} {b})"
    raise ValueError(f"t has no operator {op!r}")


def _cert_stmts(body: list, ctx: Ctx, st: dict, name: str,
                out: list, count: list) -> tuple:
    """Branch-free replay of `body` at state `st`: straight-line C plus one
    assert per branch decision. Locals are predeclared by the caller, so a
    `var` statement lands as a plain assignment (an unrolled loop iteration
    would otherwise redeclare it).

    Returns `(ctx, stopped)`. `stopped` is True once a `return` (SPEC.md
    "Early exit", 2026-09-08) has been replayed: `st` already holds the
    exact final ground values interp.py would compute (the replay is
    concrete, so nothing after a return can change them, the same fact
    that lets check_wf refuse a statement after one), so this function
    simply stops emitting C for the rest of `body` and every enclosing
    caller propagates the flag and stops too, rather than emitting a
    literal C `return` inside the certificate (which stays `void` and
    reaches its closing assert unconditionally either way)."""
    ind = "  "
    for s in body:
        count[0] += 1
        if count[0] > MAX_CERT_STMTS:
            raise _CertSkip("replay exceeds the statement cap")
        if "assign" in s:
            n, e = s["assign"]
            out += at_asserts(e, ctx, ind)
            dm_asserts: list = []
            rhs = _cert_cexpr(e, ctx, st, ctx.funs, name, dm_asserts, ind)
            out += dm_asserts
            out.append(f"{ind}{n} = {rhs};")
            st[n] = _cev(e, st)
        elif "return" in s:
            n, e = s["return"]
            out += at_asserts(e, ctx, ind)
            dm_asserts: list = []
            rhs = _cert_cexpr(e, ctx, st, ctx.funs, name, dm_asserts, ind)
            out += dm_asserts
            out.append(f"{ind}{n} = {rhs};")
            st[n] = _cev(e, st)
            return ctx, True
        elif "var" in s:
            v = s["var"]
            out += at_asserts(v["init"], ctx, ind)
            ctx = ctx.bind(v["name"], v["type"])
            dm_asserts: list = []
            rhs = _cert_cexpr(v["init"], ctx, st, ctx.funs, name,
                              dm_asserts, ind)
            out += dm_asserts
            out.append(f"{ind}{v['name']} = {rhs};")
            st[v["name"]] = _cev(v["init"], st)
        elif "if" in s:
            c = s["if"]
            out += at_asserts(c["cond"], ctx, ind)
            g = pred(c["cond"], ctx)
            taken = _cev(c["cond"], st)
            out.append(f"{ind}/*@ assert {g if taken else f'(!{g})'}; */")
            ctx, stopped = _cert_stmts(c["then"] if taken else c["else"],
                                       ctx, st, name, out, count)
            if stopped:
                return ctx, True
        elif "while" in s:
            w = s["while"]
            if code_ats(w["cond"], ctx.env):
                raise _CertSkip("`at`/`div`/`mod` in a while condition")
            g = pred(w["cond"], ctx)
            stopped = False
            while _cev(w["cond"], st):
                count[0] += 1
                if count[0] > MAX_CERT_STMTS:
                    raise _CertSkip("replay exceeds the statement cap")
                out.append(f"{ind}/*@ assert {g}; */")
                ctx, stopped = _cert_stmts(w["body"], ctx, st, name, out,
                                           count)
                if stopped:
                    break
            if not stopped:
                out.append(f"{ind}/*@ assert (!{g}); */")
            else:
                return ctx, True
        else:
            raise _CertSkip(f"no replay for statement {s!r}")
    return ctx, False


def _tty(v):
    """Value tagged with its t type (bool is not int; interp._tv precedent,
    restated locally so this file keeps importing nothing of interp's)."""
    return ("bool", v) if isinstance(v, bool) else ("int", v)


def _value_certificate(task: dict, twin_body: list, w: dict,
                       env: dict, funs: dict, used: set) -> str | None:
    """The VALUE-kind certificate function's source text, or None with the
    reason left to the caller's honesty: only a certifiable witness earns
    one. Unchanged by the 2026-09-09 seq construct: neither committed task
    reaches this branch (swap's witness is `undefined`, reverse's is
    `exit`), and a seq-typed RETURN refuses here rather than emit the
    plain `int {n};` this function's OWN decls would give it (wrong for a
    pointer+length pair) -- a documented gap, not a silent one, matching
    RULES ("measure before designing"): fixing it needs its own measured
    probe this construct wave did not need."""
    if w.get("_kind") != "value" or w.get("_ens") is not True:
        return None                    # loop-state or non-falsifying witness
    if not isinstance(w.get("_twin"), (bool, int)):
        return None                    # no-value twins have no ground replay
    if CERT_FN in used or CERT_GOAL in used:
        return None                    # a task name would collide or forge
    ret, rett = task["returns"][0]["name"], task["returns"][0]["type"]
    if rett == "seq":
        return None                    # see the docstring above
    st, decls = {}, []
    try:
        for p in task["params"]:
            if p["name"] not in w:
                return None
            v = w[p["name"]]
            if p["type"] == "seq":
                # ACSL has no implicit array-to-pointer conversion
                # (measured: a logic call over a local array is refused as
                # annot-error), so the array gets a fresh backing name and
                # the seq name is bound as the pointer, exactly the shape
                # the twin function's own parameter has.
                arr = f"t_cert_{p['name']}"
                if arr in used:
                    return None
                vals = [int(x) for x in v]
                init = ", ".join(str(x) for x in vals) or "0"
                decls.append(f"  int {arr}[{max(len(vals), 1)}] = "
                             f"{{{init}}};")
                decls.append(f"  int *{p['name']} = {arr};")
                decls.append(f"  int {p['name']}_n = {len(vals)};")
                st[p["name"]] = vals
            else:
                decls.append(f"  int {p['name']} = "
                             f"{int(v) if isinstance(v, bool) else v};")
                st[p["name"]] = v
        _, dec = assigned_names(twin_body)
        names = [ret] + [d for d in dec if d != ret]
        if len(set(dec)) != len(dec) or set(dec) & set(st):
            return None                # flattening scopes would collide
        decls += [f"  int {n};" for n in names]
        body_out: list = []
        _cert_stmts(twin_body, Ctx(env, funs, ret=None, label="Here"),
                    st, task["name"], body_out, [0])
        if _tty(st.get(ret)) != _tty(w["_twin"]):
            return None                # replay disagrees with the witness
    except (_CertSkip, NotImplementedError, ValueError, KeyError,
            TypeError, RecursionError):
        return None
    ctx = Ctx(env, funs, ret=None, label="Here")
    pieces = []
    for e in task["ensures"]:
        d, p = defs(e, ctx), pred(e, ctx)
        pieces.append(f"({p})" if d is None else f"((({d}) && ({p})))")
    lines = ["", "/*@ assigns \\nothing; */",
             f"void {CERT_FN}(void) {{", *decls, *body_out,
             f"  /*@ assert {CERT_GOAL}: !({' && '.join(pieces)}); */",
             "  return;", "}", ""]
    return "\n".join(lines)


# ---------------------------------------- definedness, as a t formula -----
#
# `defs()` (above, ACSL section) renders SPEC.md's definedness rule to ACSL
# text. `_undef_certificate` (below) needs the SAME rule as a t Expr
# instead, so `interp.ev` can DECIDE it at a ground witness state before
# any ACSL exists to check it against: one rule, two renderings, never two
# readings of what "defined" means.

def _t_and(parts):
    parts = [p for p in parts if p is not None]
    if not parts:
        return None
    r = parts[0]
    for p in parts[1:]:
        r = {"op": "and", "args": [r, p]}
    return r


def defs_t(e: dict):
    """`defs()`'s rule, restated as a t Expr (or None, trivially defined)
    instead of ACSL text. Mirrors `defs()` case for case; a `call` or
    quantifier inside an EXECUTABLE expression cannot occur (v1's grammar
    keeps both out of executable position, `code_ats` already assumes
    it), so unlike `defs()` (which also serves quantifier/call-carrying
    SPEC positions) this only needs the executable-expression subset."""
    if "int" in e or "bool" in e or "var" in e:
        return None
    if "ite" in e:
        i = e["ite"]
        dt, de = defs_t(i["then"]), defs_t(i["else"])
        return _t_and([defs_t(i["cond"]),
                       None if dt is None else
                       {"op": "implies", "args": [i["cond"], dt]},
                       None if de is None else
                       {"op": "implies",
                        "args": [{"op": "not", "args": [i["cond"]]}, de]}])
    op, args = e["op"], e.get("args", [])
    if op == "at":
        s = args[0]
        bound = {"op": "and", "args": [
            {"op": "<=", "args": [{"int": 0}, args[1]]},
            {"op": "<", "args": [args[1], {"op": "len", "args": [s]}]}]}
        return _t_and([defs_t(args[1]), bound])
    if op == "update":
        s = args[0]
        bound = {"op": "and", "args": [
            {"op": "<=", "args": [{"int": 0}, args[1]]},
            {"op": "<", "args": [args[1], {"op": "len", "args": [s]}]}]}
        return _t_and([defs_t(args[1]), defs_t(args[2]), bound])
    if op == "fill":
        return _t_and([defs_t(args[0]), defs_t(args[1]),
                       {"op": ">=", "args": [args[0], {"int": 0}]}])
    if op in DIVMOD:
        return _t_and([defs_t(args[0]), defs_t(args[1]),
                       {"op": "!=", "args": [args[1], {"int": 0}]}])
    if op in ("and", "or", "implies"):
        acc, guards = [defs_t(args[0])], []
        for k, a in enumerate(args[1:], 1):
            prev = args[k - 1] if op != "implies" else args[0]
            g = prev if op != "or" else {"op": "not", "args": [prev]}
            d = defs_t(a)
            guards.append(g)
            if d is not None:
                gexpr = guards[0]
                for gg in guards[1:]:
                    gexpr = {"op": "and", "args": [gexpr, gg]}
                acc.append({"op": "implies", "args": [gexpr, d]})
        return _t_and(acc)
    return _t_and([defs_t(a) for a in args])


def _undef_certificate(task: dict, twin_body: list, w: dict,
                       env: dict, funs: dict, used: set) -> str | None:
    """The certificate for an `undefined`-kind witness (SPEC.md "Sequences
    as values", 2026-09-09; see the section comment above and
    `lower_verus.py`'s `_undef_obligation`, added the same night for the
    same construct). None when the witness cannot be replayed this way at
    all: an obstacle `interp.ev` cannot get past (a call, budget,
    recursion), a name the witness does not cover, or a body that replays
    to the end without ever finding a false obligation (the witness and
    this walk disagreeing means the witness is not this walk's to
    certify)."""
    if w.get("_kind") != "undefined":
        return None
    names = {k: v for k, v in w.items() if not k.startswith("_")}
    # interp.py's own seq representation is a tuple; the witness's JSON
    # gives seqs as lists, so this is the one conversion point, mirrored
    # by `lower_verus.py`'s `_undef_obligation`.
    env_py = {n: (tuple(v) if isinstance(v, list) else v)
              for n, v in names.items()}
    ctx = Ctx(dict(env), funs, ret=None, label="Here")
    decls = []
    try:
        for p in task["params"]:
            if p["name"] not in names:
                return None
            v = names[p["name"]]
            if p["type"] == "seq":
                arr = f"t_cert_{p['name']}"
                if arr in used:
                    return None
                vals = [int(x) for x in v]
                init = ", ".join(str(x) for x in vals) or "0"
                decls.append(f"  int {arr}[{max(len(vals), 1)}] = "
                             f"{{{init}}};")
                decls.append(f"  int *{p['name']} = {arr};")
                decls.append(f"  int {p['name']}_n = {len(vals)};")
            else:
                decls.append(f"  int {p['name']} = "
                             f"{int(v) if isinstance(v, bool) else v};")
        ifuns = interp.funs_of(task, twin_body)
        st = interp.St()
        found = None
        for s in twin_body:
            if "var" in s:
                nm, e, ty = s["var"]["name"], s["var"]["init"], s["var"]["type"]
            elif "assign" in s:
                nm, e = s["assign"]
                ty = ctx.env.get(nm)
            else:
                return None                 # if/while/return: not walked
            ob = defs_t(e)
            if ob is not None and not interp.ev(ob, env_py, ifuns, st):
                found = ob
                break
            val = interp.ev(e, env_py, ifuns, st)
            if ty == "seq":
                return None                 # scope limit, see docstring
            if "var" in s:
                ctx = ctx.bind(nm, ty)
            env_py[nm] = val
            decls.append(f"  int {nm} = "
                         f"{int(val) if isinstance(val, bool) else val};")
        if found is None:
            return None
    except (interp.Undef, interp.Budget, RecursionError, KeyError,
            ValueError, TypeError):
        return None
    goal = pred({"op": "not", "args": [found]}, ctx)
    lines = ["", "/*@ assigns \\nothing; */",
             f"void {CERT_FN}(void) {{", *decls,
             f"  /*@ assert {CERT_GOAL}: {goal}; */",
             "  return;", "}", ""]
    return "\n".join(lines)


def _twin_loop(real_body: list, twin_body: list) -> dict | None:
    """The single `while` (in `twin_body`) whose invariant list the twin
    changed, or None; mirrors `lower_verus.py`'s helper of the same name
    (also added tonight for this construct). `is` identity would be
    truer to intent, but `real_body`/`twin_body` are independent JSON
    trees here (unlike verus's in-process mutation), so equality is what
    is available and what INVARIANT-DROP's own edit (delete one entry
    from one loop's `invariants` list, nothing else) makes sufficient."""
    diffs: list = []

    def walk(a: list, b: list) -> None:
        if len(a) != len(b):
            return
        for sa, sb in zip(a, b):
            if "while" in sa and "while" in sb:
                wa, wb = sa["while"], sb["while"]
                if wa.get("invariants", []) != wb.get("invariants", []):
                    diffs.append(wb)
                walk(wa["body"], wb["body"])
            elif "if" in sa and "if" in sb:
                walk(sa["if"]["then"], sb["if"]["then"])
                walk(sa["if"].get("else") or [], sb["if"].get("else") or [])

    walk(real_body, twin_body)
    return diffs[0] if len(diffs) == 1 else None


def _loop_suffix(body: list, loop: dict) -> list | None:
    """`body[i:]` where `body[i]["while"] is loop`, i.e. the mutated loop
    plus everything after it in the SAME block, ready to hand to
    `_cert_stmts`. None when `loop` is not a top-level statement of
    `body`: a loop nested under an `if` needs `interp.continuation`'s own
    search for what runs after it, which no committed task's exit witness
    has needed (reverse's loop is the whole method), so it is a stated
    scope limit rather than an attempted, unmeasured generalisation."""
    for i, s in enumerate(body):
        if "while" in s and s["while"] is loop:
            return body[i:]
    return None


def _exit_certificate(task: dict, twin_body: list, w: dict,
                      env: dict, funs: dict, used: set) -> str | None:
    """The certificate for an `exit`-kind witness (`interp.invariant_
    witness`'s own obligation, restated: the surviving invariants and
    `requires` hold, the loop guard is false, but `ensures` is false).
    Unlike a `value` witness this state is not reached by running the
    function from its params (`_Admissible` screens for states a sound
    kernel cannot rule out, not for states an actual run passes through),
    so it is declared directly as ground C locals for every name the
    witness names -- params AND loop-scope locals alike, the identical
    declare-a-ground-array-or-int shape `_value_certificate` already uses
    for params -- and `_cert_stmts` (unmodified) replays only the twin's
    mutated loop onward. See `_loop_suffix` for the one scope limit
    (top-level loops only)."""
    if w.get("_kind") != "exit":
        return None
    if CERT_FN in used or CERT_GOAL in used:
        return None
    loop = _twin_loop(task["body"], twin_body)
    if loop is None:
        return None
    suffix = _loop_suffix(twin_body, loop)
    if suffix is None:
        return None
    names = {k: v for k, v in w.items() if not k.startswith("_")}
    ctx_env = dict(env)
    decls, st = [], {}
    for n, v in names.items():
        if f"t_cert_{n}" in used:
            return None
        if isinstance(v, list):
            arr = f"t_cert_{n}"
            vals = [int(x) for x in v]
            init = ", ".join(str(x) for x in vals) or "0"
            decls.append(f"  int {arr}[{max(len(vals), 1)}] = {{{init}}};")
            decls.append(f"  int *{n} = {arr};")
            decls.append(f"  int {n}_n = {len(vals)};")
            ctx_env[n] = "seq"
            st[n] = vals
        elif isinstance(v, bool):
            decls.append(f"  int {n} = {int(v)};")
            ctx_env[n] = "bool"
            st[n] = v
        else:
            decls.append(f"  int {n} = {v};")
            ctx_env[n] = "int"
            st[n] = v
    ctx = Ctx(ctx_env, funs, ret=None, label="Here")
    body_out: list = []
    try:
        _cert_stmts(suffix, ctx, st, task["name"], body_out, [0])
    except (_CertSkip, NotImplementedError, ValueError, KeyError, TypeError,
            RecursionError):
        return None
    ret = task["returns"][0]["name"]
    if ret not in st:
        return None
    ectx = Ctx(env, funs, ret=None, label="Here")
    pieces = []
    for e in task["ensures"]:
        d, p = defs(e, ectx), pred(e, ectx)
        pieces.append(f"({p})" if d is None else f"((({d}) && ({p})))")
    lines = ["", "/*@ assigns \\nothing; */",
             f"void {CERT_FN}(void) {{", *decls, *body_out,
             f"  /*@ assert {CERT_GOAL}: !({' && '.join(pieces)}); */",
             "  return;", "}", ""]
    return "\n".join(lines)


def certificate(task: dict, twin_body: list, w: dict,
                env: dict, funs: dict, used: set) -> str | None:
    """The certificate function's source text, or None with the reason
    left to the caller's honesty: only a certifiable witness earns one.
    Dispatches on `w["_kind"]`; see the section comment above for what
    each kind needs and does not (yet) cover.

    `undefined` and `exit` are scoped to seq-RETURNING tasks only (MEASURED
    2026-09-09: both mechanisms are GENERAL, not seq-specific -- an
    `undefined` witness can come from a bare `at`/`div`/`mod`, an `exit`
    witness from any INVARIANT-DROP twin -- and turning them on
    unconditionally changed 9 of the 15 already-committed tasks' twin
    cells, all nine from an uncertified TIMEOUT to a certified REFUTED
    (all_nonneg, contains, count_matches, digit_sum, first_even, is_prime,
    linear_search, seq_max, sum_upto: every framac `verified / timeout`
    row in AGREEMENT.md except abs/factorial/fib/gcd/max/remainder, which
    were already `verified / refuted`). That MAY be a sound improvement
    over the committed baseline, since every other kernel already reads
    `refuted` on most of those same cells, but RULES scoped this pass to
    landing `update`/`fill` and reading the two NEW tasks, not to
    re-measuring nine already-committed ones outside a dated note of
    their own: the 15-task regression must read exactly as AGREEMENT.md
    records. So both new kinds gate on the task actually returning a seq,
    which uniquely picks out swap/reverse among all 17 committed tasks
    today and leaves every pre-existing task's certificate path (and
    therefore its outcome) untouched."""
    if w is None:
        return None
    if CERT_FN in used or CERT_GOAL in used:
        return None                    # a task name would collide or forge
    kind = w.get("_kind")
    if kind == "value":
        return _value_certificate(task, twin_body, w, env, funs, used)
    if task["returns"][0]["type"] != "seq":
        return None                    # scope limit, see docstring
    if kind == "undefined":
        return _undef_certificate(task, twin_body, w, env, funs, used)
    if kind == "exit":
        return _exit_certificate(task, twin_body, w, env, funs, used)
    return None                        # preservation: see the section note


# -------------------------------------------------------------- lowering ----

def _always_returns(body: list) -> bool:
    """True when every path through `body` ends in `return` (SPEC.md
    "Early exit", 2026-09-08). Mirrors lower_lean.py's `_always_returns`:
    a path ends the block either with a `return` statement or with an
    `if` whose two branches both always return. Used by `lower()` to
    decide whether the function body already covers every path, so the
    unconditional trailing `return {ret};` this lowering used to emit
    after the body is skipped rather than left as dead code (see the
    DIV/MOD SMOKE / RETURN SMOKE note above `lower`)."""
    if not body:
        return False
    s = body[-1]
    if "return" in s:
        return True
    if "if" in s:
        c = s["if"]
        return _always_returns(c["then"]) and _always_returns(c["else"])
    return False


# `witness` is the twin's measured witness (harness.twin_cached). Twin call
# sites pass it; when it is certifiable, the emitted file carries the
# refutation certificate (see the section above).
def lower(task: dict, body: list, witness: dict | None = None) -> str:
    name, ret = task["name"], task["returns"][0]["name"]
    rett = task["returns"][0]["type"]
    env = {p["name"]: p["type"] for p in task["params"]}
    env[ret] = rett

    funs = {}
    for f in task.get("spec_funs", []):
        funs[f["name"]] = {
            "params": f["params"], "result": f["result"],
            "labeled": any(p["type"] == "seq" for p in f["params"]),
            "is_task": False}
    funs[name] = {"params": task["params"], "result": rett,
                  "labeled": False, "is_task": True}

    seqs = [p["name"] for p in task["params"] if p["type"] == "seq"]
    used = set()

    def names_in(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in ("var", "name", "fun") and isinstance(v, str):
                    used.add(v)
                names_in(v)
        elif isinstance(x, list):
            for v in x:
                names_in(v)
    names_in(task)
    names_in(body)
    for s in seqs:
        if f"{s}_n" in used:
            raise NotImplementedError(
                f"name {s}_n collides with the fresh length parameter "
                f"for seq {s}")

    header = []
    if _has_divmod(task) or _has_divmod(body):
        header.append(T_DIVMOD_ACSL.rstrip("\n"))
    for f in task.get("spec_funs", []):
        header += spec_fun_acsl(f, funs)

    # A seq RETURN's length, computed statically from the body (seq value
    # machinery section, above `assigned_names`): needed at requires-time,
    # before the function runs, to size the caller-provided output
    # buffer's `\valid`/`\separated` bound. `body` (the REAL or the TWIN
    # body, whichever this call is lowering) is what is walked, since it
    # is what actually determines the length that particular C function
    # writes; the real and twin lowerings of the same task can therefore
    # legitimately compute different (but here, on both committed tasks,
    # equal) length expressions.
    ret_len_expr = None
    if rett == "seq":
        lens = {s: {"op": "len", "args": [{"var": s}]} for s in seqs}
        _seq_len_track(body, lens)
        if ret not in lens:
            raise NotImplementedError(
                f"seq return {ret!r}'s length is not statically "
                f"determinable from the task's params (needed to size its "
                f"output buffer's `requires`); see the seq value "
                f"machinery section above `assigned_names`")
        ret_len_expr = lens[ret]

    spec_ctx = Ctx(env, funs, ret=None, label="Here")
    post_ctx = Ctx(env, funs, ret=(ret if rett != "seq" else None),
                   label="Here")
    clauses = []
    all_seqs = list(seqs)
    for s in seqs:
        clauses.append(f"  requires {s}_n >= 0;")
        clauses.append(f"  requires \\valid_read({s} + (0 .. {s}_n - 1));")
    if rett == "seq":
        # The return's own buffer: caller-provided, WRITABLE (`\valid`,
        # not `\valid_read`), and pinned to the length the body's own
        # writes will actually produce (`ret_len_expr`, rendered here in
        # PARAMS-only terms, exactly what ACSL's `requires` scope allows).
        clauses.append(f"  requires {ret}_n >= 0;")
        clauses.append(f"  requires \\valid({ret} + (0 .. {ret}_n - 1));")
        clauses.append(f"  requires {ret}_n == "
                       f"{term(ret_len_expr, spec_ctx)};")
        all_seqs.append(ret)
    for k, a in enumerate(all_seqs):
        for b in all_seqs[k + 1:]:
            # No two seq buffers may alias: swap's copy-then-write and
            # reverse's fill both read one buffer while writing another,
            # and WP's Typed memory model does not assume distinct `int *`
            # formals are non-overlapping on its own (measured: two params
            # of the same C type CAN alias under Typed unless told
            # otherwise).
            clauses.append(f"  requires \\separated({a} + (0 .. {a}_n - 1), "
                           f"{b} + (0 .. {b}_n - 1));")
    clauses += [f"  requires {pred(e, spec_ctx)};"
                for e in task.get("requires", [])]
    if "decreases" in task:
        clauses.append(f"  decreases ({term(task['decreases'], spec_ctx)});")
    if rett == "seq":
        # Only the return buffer's own elements are written; every seq
        # PARAM stays `\valid_read`-only and every scalar param/local is
        # a plain C local, never aliased into `ret`'s memory
        # (`\separated`, above).
        clauses.append(f"  assigns {ret}[0 .. {ret}_n - 1];")
    else:
        clauses.append("  assigns \\nothing;")
    for e in task["ensures"]:
        d = defs(e, post_ctx)
        body_p = pred(e, post_ctx)
        clauses.append(f"  ensures {body_p};" if d is None else
                       f"  ensures ({d}) && ({body_p});")

    cparams = []
    for p in task["params"]:
        if p["type"] == "seq":
            cparams += [f"int *{p['name']}", f"int {p['name']}_n"]
        else:
            cparams.append(f"int {p['name']}")
    if rett == "seq":
        cparams += [f"int *{ret}", f"int {ret}_n"]

    body_lines = stmts(body, Ctx(env, funs, ret=None, label="Here"),
                       name, "  ")
    cert = (certificate(task, body, witness, env, funs, used)
            if witness is not None else None)
    # RETURN SMOKE, fixed 2026-09-09 (see the note above `lower`): when
    # every path of `body` already ends in `return`, the trailing
    # `return {ret};` this lowering used to append unconditionally is dead
    # code no input reaches, and -wp-smoke-tests dooms it with no goal
    # name attached (a bare source-line warning, not a named
    # `wp_smoke_dead_code_sN` goal), which `verifiers/framac.py`'s
    # `_vacuity_smoke` fails closed on. So it is omitted precisely when
    # `_always_returns(body)` says the body needs it least: every other
    # body (no `return` at all, or a `return` that leaves a path falling
    # through) still gets it, unchanged.
    #
    # A seq return (2026-09-09) is `void`: the "return value" already
    # lives in the caller-provided buffer, so no trailing statement is
    # ever needed, `return;` or otherwise -- a body that falls off the end
    # having already written every element it owes is exactly correct,
    # and a body with its own early `return;` (see `stmts()`) needs
    # nothing after it either.
    tail = ("" if rett == "seq" or _always_returns(body)
            else f"  return {ret};\n")
    ret_decl = "" if rett == "seq" else f"  int {ret};\n"
    cfun_ret_ty = "void" if rett == "seq" else "int"
    return ("\n".join(header) + ("\n" if header else "")
            + "/*@\n" + "\n".join(clauses) + "\n*/\n"
            + f"{cfun_ret_ty} {name}_t({', '.join(cparams)}) {{\n"
            + ret_decl
            + "\n".join(body_lines) + "\n"
            + tail + "}\n"
            + (cert or ""))


if __name__ == "__main__":
    raise SystemExit(harness.run_all(sys.argv[1:], lower, framac_backend, "c"))
