#!/usr/bin/env python3
"""lower_verus.py: lower t tasks (v0 and v1) to Verus; the second kernel.

THE SEMANTIC DECISION, made with a witness rather than by silence: t
integers are mathematical integers. Verus's `int` type IS mathematical, but
only in ghost/proof code; executable code uses machine ints with overflow
obligations. So every t task lowers to `proof fn`, which preserves t's
semantics exactly; the exec/i64 arm (with explicit range obligations) is a
later gate, opened when t grows machine-int types. Choosing exec now would
silently change what a t task MEANS between Dafny (int = mathematical) and
Verus, exactly the class of cross-backend semantic drift t exists to
surface, not commit.

v1 additions, and the two decisions they forced (both measured, not guessed):

LOOPS. Verus refuses `while` in proof mode ("cannot use while in proof or
spec mode", measured on 0.2026.08.30). Machine-checked iteration in ghost
code is done by recursion, so each t `while` is lowered to a recursive
helper proof fn, with requires = the invariants and ensures = the invariants over
the returned state plus the negated guard, decreases = the loop's own
measure. That IS t's loop rule (SPEC.md gate 2), enforced modularly: the
caller proves the invariants on entry (call-site requires), the helper
proves one iteration preserves them (recursive call's requires) and that
the measure is nonnegative and strictly decreasing (Verus's decreases
check), and after the loop the caller knows exactly invariants + !guard
(the helper's ensures, since proof fns are opaque) and nothing more. No exec
arm, no machine ints, no semantic drift.

DEFINEDNESS. Verus spec code is total: `Seq::index` out of bounds is an
unspecified value guarded only by `recommends`, which the kernel does not
enforce. A lowering that leaned on that would silently totalize `at`,
which SPEC.md declares wrong. So this lowering computes the definedness
condition D(e) of every expression it emits, the exact left-to-right
short-circuit rules of SPEC.md "Definedness", and makes Verus discharge
it: as an `assert` immediately before each body statement that needs one
(where the kernel has the path facts, guard, and invariants in context),
and as standalone well-formedness lemmas for spec positions (each requires
clause assuming the earlier ones; each ensures clause assuming requires
and earlier ensures; each loop invariant assuming the earlier invariants
in its list; each spec_fun body universally). Trivial conditions simplify
to true and are not emitted, so v0 output is untouched.

Body lowering: v0 tasks keep the original expression-oriented lowering,
byte-identical. v1 tasks lower as statements: returns become
definite-assignment `let mut` locals, the final expression returns the
return name, spec_funs become `spec fn ... decreases`, and a
self-recursive body becomes a recursive proof fn carrying the task's own
decreases measure.

EARLY EXIT (2026-09-08, SPEC.md "Early exit"). `{"return": [ID, Expr]}`
lowers to Verus's own `return Expr;`, which is what the module's exec/proof
split already needed: the recursive loop helper's decreases and invariant
obligations attach to its OWN return, and Verus checks the ensures at
every return with no loop-invariant obligation there, exactly SPEC.md's
rule. Measured with two probes through the verus binary directly: an exec
fn with a native `while` (invariants, named return) accepts a `return`
inside the loop and checks the ensures at that exit only, never asking for
the invariant there (probe_ret_exec.rs); a recursive `proof fn` accepts
the same thing (probe_ret_proof.rs), which is what matters here since v1
loops already lower to recursion, never a native `while` (see LOOPS
above). A `return` directly in the task's own body emits a bare
`return Expr;` (`_V1.stmts`'s `wrap=None` case). A `return` inside a loop
is different: that loop's helper can no longer just return the state
tuple, since one call of it can end the whole task instead of one more
iteration, so `_may_return` flags any loop whose body returns (directly,
through an `if`, or through a nested loop's own already-wrapped result),
and such a helper's result becomes `(bool, return-type, state-tuple)`:
flag, the task's return value if set, the loop state otherwise. Its
ensures splits the same way -- the flagged branch owes the task's own
`ensures`, never the loop's invariants, matching the SPEC.md text above
verbatim -- and its call site propagates a set flag onward as a real
`return`, wrapped again if the call site is itself inside another such
loop (`_V1.loop`'s `wrap` parameter). The returned expression owes the
same `_assert_defined` (definedness asserts, div/mod bridging) as an
assign's right-hand side, added to `_V1.stmts`'s "return" case. `_assigned`
deliberately gets no "return" case (a return's target is not per-iteration
loop state, see its docstring); `_body_calls` and `_twin_loop` do, the
former for self-recursion detection, the latter needing none in practice
since a `return` statement carries no nested body to walk into. `_sym`
gives up (None) on a body containing a return, the same as it already
does for a nested while, so the nonlinear_arith bridge is skipped rather
than built from a post-state that free early exit makes non-equational.
The v0 path never sees a `return` (v1-only per SPEC.md); `body_expr`'s
existing fallback already refuses cleanly for any body it cannot express.

A second, unrelated fix rode in on top of this because is_prime.json's own
`forall d. 2<=d<n ==> n mod d != 0` needed it: unlike every prior committed
task's quantifiers, which index a Seq and so give Verus's automatic
trigger inference something to grab, this one is pure arithmetic and Verus
refused it outright ("Could not automatically infer triggers for this
quantifier"). `expr()`'s forall/exists case now supplies an explicit
`#![trigger n % d]` whenever the body has no indexable (`at`/`call`) term
of its own (`_has_indexable`, `_mod_div_trigger`); every prior task's
quantifiers keep their free automatic inference untouched, so all 13
previously committed tasks (v0 and v1 alike) still lower byte-identically.

SEQUENCES AS VALUES (2026-09-09, SPEC.md "Sequences as values (v1)"),
`update` (`s[i := v]`) and `fill` (`seq(n, v)`). Both are native in Verus's
own vstd, so `expr()` just calls the vstd method: `update` emits
`s.update(i, v)` (vstd::seq::Seq::update, measured, probe_update.rs: 0
errors alongside a bound-checked `requires`), `fill` emits
`Seq::new(n as nat, |_t_fill_i: int| v)` (vstd::seq::Seq::new takes a
`nat` length and a `FnSpec(int) -> A`; measured, probe_fill_int.rs: an
`int`-typed `n` with `n >= 0` in scope casts and verifies with no hint
needed, the same `as nat` cast `at`'s own `len()` already relies on in
the other direction). `TYPES["seq"]` (already `Seq<int>`, added ahead of
this task) needed no change: a `seq` return, local, and loop-state slot
were already generic over Verus type strings via `scope`'s `(type, mut)`
entries, so a `Seq<int>`-typed loop variable is framed by name exactly
like an `int` one, no code path cared which.

DEFINEDNESS. `Seq::index` and `Seq::update` share the same
`recommends`-only bound (measured, probe_update_oob.rs and
probe_update_oob2.rs): out of `[0, len)`, `update`'s own length
postcondition still holds (`s.update(i,v).len() == s.len()` verifies
unconditionally) but the ELEMENT at `i` is left unconstrained -- an
out-of-bound `s.update(i,v)[i] == v` fails to verify, the same
"unspecified, not undefined-in-Rust's-sense" shape `at` already gets in
this file, so `defined()`'s new "update" case owes `at`'s own bound
(`0 <= i < len(s)`) plus definedness of all three sub-expressions,
discharged by the same `_assert_defined` mechanism, no new machinery.
`fill`'s bound is native too but from the other side: `n as nat` for a
negative `n` does not trap, it silently produces length 0 (measured,
probe_fill_neg.rs: `Seq::new(n as nat, ...).len() == n` FAILS to verify
with no `n >= 0` in scope, so an unguarded `fill` would silently
totalize exactly the way SPEC.md forbids), so `defined()`'s "fill" case
owes `n >= 0` explicitly, the same shape as `div`/`mod`'s `y != 0`.

EXTENSIONAL EQUALITY. Costs nothing extra: measured directly
(probe_ext_eq.rs, `a.len()==b.len() && forall k. a[k]==b[k]` in
`requires`, bare `a == b` in `ensures`, 0 errors; probe_ext_eq3.rs, a
harder case with no given index facts at all,
`a.update(i,x).update(i,y) == a.update(i,y)`, also 0 errors unaided) --
Verus's `Seq<int>` compiles to Z3's native sequence sort in spec/proof
mode, where `==` already denotes real extensional equality at the SMT
level, not a derived or definitional one a lowering has to unlock with
`=~=` (Verus's own extensionality macro, probed too: identical results
with or without it, probe_ext_eq2.rs / probe_ext_eq3b.rs). So `BIN_OPS`
needed no seq-specific entry: `"==" -> "=="` and `"!=" -> "!="`, already
generic over int/bool, are exactly as sound for two `Seq<int>` operands
and neither swap nor reverse (v1's two committed seq tasks) even
exercises it directly (both specs compare elementwise via `at`), so this
finding is banked for the next seq task that states `==` between two
whole seqs, not exercised by either committed cell.

THE TWIN PATH surfaced a gap the construct's own witnesses hit
immediately: swap's measured twin (off-by-one on the `at` inside `tmp :=
s[i]`, mutated to `s[i+1]`) is UNDEFINED at its witness (s=[0], i=0,
j=0: index 1 outside [0,1)), the "_kind": "undefined" witness shape
interp.py's `Reference.witness` has always been able to produce (SPEC.md
"The twins": "the twin is undefined where the real body has a value" is
one of the two accepted value-changing witness shapes) but that this
file's certificate builder had never had to certify, since none of the
13 tasks committed before this one ever measured it (checked directly:
every one is "value" or "exit"). Declining to certify it would leave
swap permanently UNPROVED on its twin cell, never REFUTED, so
`_undef_obligation` closes it: re-walk the twin body with `interp.ev`,
in the same left-to-right order interp.py used to raise the Undef that
minted the witness, calling `defined()` (the one function this lowering
already trusts for its own asserts, so no second reading of what
"defined" means) at each statement to find the first ground-false
obligation, then emit its negation, substituted with the witness's
concrete values, as the certificate goal, joined with `parts` exactly
like the "value" and "exit" kinds already are. Measured on swap: the
obligation `0 <= (i+1) && (i+1) < len(s)` is false at the witness, the
certificate carries `assert(!(...)) by (compute_only)`, and
verifiers/verus.py accepted it, minting the REFUTED that made swap COUNT
(`off-by-one twin REFUTED`, witness s=[0], i=0, j=0). reverse needed no
such extension: its measured twin (invariant-drop#1) is an "exit"
witness (s=[], i=0, r=[0]), the same kind seq_max and first_even already
certify, and the ONLY change that mattered there was `_tlit` already
accepting a list of ints as a `{"_seq": [...]}` node (present ahead of
this task) and `expr()`'s existing `"_seq"` case (also already present)
rendering it as `seq![(0int)]`, so a seq-valued witness slots into the
existing "exit" certificate path with no new code.

Regression, measured 2026-09-09: `swap` and `reverse` COUNT (real
VERIFIED, twin REFUTED); all 15 previously committed tasks still read
`verified / refuted` in the verus column exactly as t/AGREEMENT.md
records, and `out/abs.rs`, `out/first_even.rs` and `out/digit_sum.rs`
(one v0, two v1 with a loop, chosen to cover both lowering paths) are
byte-identical before and after this change.

SEQUENCES: LITERALS, CONCATENATION, SLICES (2026-09-09, SPEC.md
"Sequences: literals, concatenation, slices (v1)"). Three new Expr forms,
each mapped straight onto a kernel-native form, measured with a probe file
before touching the lowering: `{"op": "seq", "args": [...]}` (`[e1, ...,
en]`) is vstd's own `seq!` macro, `s + t` on two seqs is Verus's native
`Add` impl for `Seq<int>` (`s.add(t)` under the hood, measured identical
either way, probe_seq_basic.rs), and `{"op": "slice", "args": [s, a, b]}`
(`s[a..b]`) is `s.subrange(a, b)` (vstd::seq::Seq::subrange). None of the
three needed a new BIN_OPS/NARY_OPS entry beyond `expr()`'s own "seq" and
"slice" cases: `+` was ALREADY in BIN_OPS, mapped to Rust's own `+`, and
Verus's operator overloading picks the `Seq<int>` impl or the `int` one by
the same operand types the SOURCE expression already carries, exactly as
SPEC.md states ("one operator name, polymorphic by the types of its
operands exactly as `==` already is") -- no dispatch this file has to do
itself. The empty literal renders as `Seq::<int>::empty()` rather than
`seq![]`, reusing the spelling the certificate builder's private `_seq`
ground node already had (`expr()`'s "_seq" case, present since "Sequences
as values"), so there are now two AST shapes ({"op":"seq","args":[]} from
a t task, {"_seq":[]} from a witness) that render identically rather than
two macros to keep in sync.

DEFINEDNESS. `seq` and `+` cost NOTHING new: both are total per SPEC.md
("a literal is defined iff all its elements are"; "a concatenation is
defined iff both arguments are"), which is exactly the formula `defined()`'s
existing catch-all already computes for every operator not given its own
case (`_conj([defined(a) for a in args])`) -- `+` was already routed
through it for the int/int case, and the seq/seq case asks the identical
question of the identical two arguments, so `defined()` needed no new
branch for either op. `slice` is the one that costs something: Verus's
`subrange` carries a `recommends`, not a `requires` (measured,
probe_subrange2.rs: an unguarded out-of-bound `s.subrange(0, 1)` on an
empty `s` compiles with only a "recommendation not met" NOTE, no error,
and critically does NOT totalize -- the very next line's
`assert(r.len() == 1)` genuinely FAILS to verify, so an unguarded slice is
neither rejected nor silently given the length its caller expects). A
lowering that emitted `subrange` bare would therefore neither catch a bad
slice (no requires to fail) nor prove anything false about it (no
totalized value to exploit): it would just read UNPROVED wherever the
bound actually matters, which is not the same failure as `at`'s but is the
same WRONGNESS SPEC.md's "Definedness" section forbids. So `defined()`
gets a "slice" case emitting the obligation the docstring above already
gives a name to: `0 <= a && a <= b && b <= len(s)`, discharged by the
existing `_assert_defined`/`_wf_lemma` machinery with no new plumbing,
the same shape as `at`'s two-conjunct bound with one more clause.

MEASURED, tasks/tail.json (`r := s[1..]`, loop-free) and
tasks/filter_pos.json (`r := r + [s[i]]` inside a loop, plus `r := []` for
the initial empty literal): both COUNT on first measurement, no lowering
fix needed beyond the `expr()`/`defined()` cases above. tail's twin
(off-by-one, `s[2..len(s)]` on a length-1 `s`) is an "undefined" witness
handled with NO new certificate code: `_undef_obligation` already replays
`defined()` over the twin body, and the new "slice" case is what it finds
false (witness s=[0]: `0 <= 2 && 2 <= 1 && 1 <= 1` fails on its middle
conjunct), so the certificate the existing machinery emits is
`!(0 <= (1+1) && (1+1) <= len(s) && len(s) <= len(s))`, ground, and Verus
accepts it under compute_only. filter_pos's twin is an ordinary
invariant-drop "exit" witness, the kind every loop task already
certifies; its exit state's `r` substitutes a seq literal (`seq![1int]`)
through the same `_tlit`/`expr()` path "Sequences as values" already
built. Neither task exercised `_gint`, `_tlit`, or `_unroll` beyond what
they already handled, so no certificate-builder code changed. swap and
reverse are BYTE-IDENTICAL to their prior `out/` sources (`cmp`, all four
files), confirming the two new `expr()`/`defined()` cases are additive
and untaken by any previously committed task. Cells (out/agent-verus-
seqops/, this run): tail COUNTS (real VERIFIED, twin REFUTED, witness
s=[0] -> slice bounds [2..1] outside 0<=a<=b<=1), filter_pos COUNTS (real
VERIFIED, twin REFUTED, invariant-drop#1, witness s=[], i=1, r=[1]), swap
and reverse unchanged (both COUNT, byte-identical sources). No kernel
trigger-inference gap was hit: tail's and filter_pos's foralls both index
a Seq (`r[k]`, `s[k+1]`) so `_has_indexable` already lets Verus's
automatic inference find them, same as every previously committed seq
task; `slice` itself needed no trigger case in `_has_indexable` or
`_mod_div_trigger` since no committed quantifier body contains one.

GUARD DEFINEDNESS (2026-09-09, the residual t/COVERAGE-lifted-785.md names:
"a `div`/`mod` in a loop guard is a definedness obligation ... verus ...
doesn't lower yet"). `loop()` used to raise NotImplementedError outright
whenever `defined(cond)` or `defined(decreases)` was non-trivial, which is
exactly what the two MBPP-DFY IsPrime tasks hit (`while i <= n / 2`, guard
and decreases both containing `n div 2`; the committed `is_prime` never
showed this because its own guard is `i * i <= n`, no div/mod at all).
Fixed the same way an ordinary statement's obligation is discharged: the
combined obligation `defined(cond) && defined(decreases)`, plus every
div/mod pair's Euclidean-law bridge (`_div_mod_law`, deduplicated across
`cond` and `decreases`), is emitted as the FIRST lines of the recursive
loop helper's own body, before the `if {cond} {...}` that is the only
place `cond` is ever evaluated. This covers every evaluation of the guard,
including the outermost one, since even the initial call from the loop's
own call site runs through this same helper body; no call-site or
`req_clauses` change was needed, since the assert is proved from the
helper's own `requires` (already every invariant in scope), the same
context an ordinary in-body `_assert_defined` already relies on. Trivial
(`_conj([defined(cond), defined(decreases)]) == TRUE`, true for every
previously committed loop task) emits nothing, so `is_prime`, `first_even`
and `tail` are byte-identical before and after this change (checked
directly, `cmp`, real and twin, all six files).

That fix turns the two IsPrime tasks' verdict from ABSTAIN into a real
kernel attempt, and surfaces a SECOND, separate residual: Verus's
automatic termination check for a `proof fn`'s recursive `decreases`
clause cannot discharge one containing `div` or `mod` at all, regardless
of provability. Measured by isolating the two loop clauses on a minimal
probe (`i <= n / 2` as the guard alone, decreases `n - i`: verifies;
decreases `(n / 2) - i` alone, guard linear: "could not prove
termination" at the recursive call; decreases `n % 5 - i` alone: same
failure; decreases `n * 2 - i`, a literal-multiplication analogue: no
termination error). No hint closes it: an explicit local `assert` of the
same nonneg/strict-decrease facts before the call, `#[verifier::nonlinear]`
on the helper, restating the guard or the Euclidean law as an extra
`requires` clause, and wrapping the division in its own non-recursive
`spec fn` (hoping the checker would treat it as an opaque call rather than
expanding it) were all tried and none changes the error. There is no
escape hatch to reach for either: `strings` on the installed
`rust_verify` binary (0.2026.08.30.b432e82) shows `decreases_by` and
`decreases_when` exist as attributes, but both carry the diagnostic "only
spec functions can use decreases_by/recommends_by" / "only spec functions
can use decreases_when" -- neither is available on a `proof fn`, which is
what every t loop helper is (see LOOPS above). Since the task's own
`decreases` is `n div 2 - i` and this lowering owes it verbatim, not a
kernel-friendlier equivalent (SPEC.md: `decreases` is an Expr like any
other, faithfully rendered, not re-derived), there is nothing left for
THIS lowering to do about it: `dafny_synthesis_task_id_3__isNonPrime` and
`dafny_synthesis_task_id_605__isPrime` both read verus unproved/unproved
(real and twin alike, `out/agent-verus-guard/`, PATH including
`~/.cargo/bin` so `rustup` resolves) -- the kernel's own message is
"could not prove termination" at the recursive call, not a fault in
either the real body or the invariant-drop twin, and not a defect in the
task's invariants either (nothing about the INVARIANTS blocks this; the
decreases clause alone does, independent of every other clause on the
loop). Measured (`cmp`, real and twin): `is_prime`, `first_even` and
`tail` are unaffected by either finding, byte-identical to their
committed `out/*.rs`.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import harness                                   # noqa: E402
import interp                                    # noqa: E402
from verifiers import verus as verus_backend     # noqa: E402

# DIVISION AND MODULO (2026-09-08, SPEC.md "Division and modulo (v1)").
# Measured on 0.2026.08.30.b432e82 with a six-fact probe on spec `int`
# (probe_div.rs): `assert(-7 / 2 == -4 && -7 % 2 == 1 && 7 / -2 == -3 &&
# 7 % -2 == 1 && -7 / -2 == 4 && -7 % -2 == 1)` verified with 0 errors, so
# Verus's native `/` and `%` on `int` ARE Euclidean, t's own convention:
# `div`/`mod` emit natively (BIN_OPS below), no kernel-terms redefinition
# needed. y == 0: a second probe (probe_div0.rs) shows `x / 0 == 0` and
# `x % 0 == 0` both FAIL to verify for symbolic x, so Verus's `/`/`%` are
# total in the type system (never a trap) but carry no known value at
# y == 0, the same "unspecified, not undefined-in-Rust's-sense" posture
# SMT-LIB gives division by zero. That is exactly what SPEC.md's
# definedness discipline needs: `defined()` below adds `y != 0` to a
# div/mod's obligation, the same shape as `at`'s bound, and every emission
# site asserts it before the value is used, so the y == 0 case is never
# actually reached by a proof this lowering emits; the operator's own
# totality is not relied on.
#
# The Euclidean defining law `x == (x div y) * y + (x mod y)` is native
# for the RANGE half (`0 <= x%y`, `x%y < y || x%y < -y`: probe_range.rs,
# 0 errors unaided) but NOT for the multiplicative half: Verus's default
# solver profile has nonlinear arithmetic off (see LOOPS in the module
# docstring), and `(x/y)*y` multiplies two non-literal terms, so
# probe_law.rs (`ensures x == (x/y)*y + (x%y)` alone) fails with
# "postcondition not satisfied". `_div_mod_law` below asserts that half
# explicitly via `by (nonlinear_arith) requires y != 0` (probe_law3.rs /
# probe_law4.rs, 0 errors; probe_law5.rs confirms the `requires` is a real
# obligation, not an assumption: drop the ambient `y != 0` and it reads
# "requires not satisfied"), emitted at every statement that introduces a
# div/mod term (`_assert_defined`), which is what makes `remainder`'s
# `ensures x == (x div y) * y + r` provable. `digit_sum` needed no such
# help: its recursive spec_fun never multiplies a div/mod result, so its
# loop-invariant preservation goes through on the native range facts and
# ordinary spec_fun unfolding alone.
BIN_OPS = {"==": "==", "!=": "!=", "<": "<", "<=": "<=", ">": ">", ">=": ">=",
           "+": "+", "-": "-", "*": "*", "implies": "==>",
           "div": "/", "mod": "%"}
NARY_OPS = {"and": "&&", "or": "||"}
TYPES = {"int": "int", "bool": "bool", "seq": "Seq<int>"}


_SUFFIX_INT = False   # v1 only: literals as `(7int)` so ite branches infer
                      # (measured: bare `1` in an ite arm is E0283); v0
                      # output stays byte-identical with bare literals.


def _has_indexable(e: dict) -> bool:
    """True iff e contains a Seq index (`at`) or a `call` anywhere -- the
    shapes Verus's automatic trigger inference picks up on its own for a
    quantifier body. Used only to decide whether a forall/exists needs an
    EXPLICIT trigger (see `_mod_div_trigger` and `expr()`'s forall/exists
    case); every committed task's quantifiers index a Seq, so this is true
    for all of them and none gets an explicit trigger it didn't already
    have (v0 and the pre-2026-09-08 v1 output are unaffected)."""
    if "op" in e:
        if e["op"] == "at":
            return True
        return any(_has_indexable(a) for a in e.get("args", []))
    if "call" in e:
        return True
    if "ite" in e:
        c = e["ite"]
        return any(_has_indexable(c[k]) for k in ("cond", "then", "else"))
    if "forall" in e or "exists" in e:
        q = e.get("forall") or e.get("exists")
        return any(_has_indexable(q[k]) for k in ("lo", "hi", "body"))
    return False


def _mod_div_trigger(e: dict) -> dict | None:
    """First `mod`/`div` application in e, pre-order, or None. is_prime's
    ensures/invariant (SPEC.md "Early exit" corpus, 2026-09-08) is
    `forall d. 2<=d<n ==> n mod d != 0`: pure arithmetic, no Seq index or
    call, so Verus's automatic inference refuses it outright ("Could not
    automatically infer triggers for this quantifier", measured on
    is_prime.rs before this fix). `n mod d` is exactly the term that
    should fire the quantifier, so `expr()` supplies it explicitly via
    `#![trigger ...]` whenever `_has_indexable` says auto-inference has
    nothing else to go on."""
    if "op" in e:
        if e["op"] in ("mod", "div"):
            return e
        for a in e.get("args", []):
            r = _mod_div_trigger(a)
            if r is not None:
                return r
        return None
    if "call" in e:
        for a in e["call"]["args"]:
            r = _mod_div_trigger(a)
            if r is not None:
                return r
        return None
    if "ite" in e:
        c = e["ite"]
        for k in ("cond", "then", "else"):
            r = _mod_div_trigger(c[k])
            if r is not None:
                return r
        return None
    return None


def expr(e: dict) -> str:
    if "_seq" in e:
        # Private ground node, emitted only by the refutation certificate
        # builder below: a concrete Seq<int> literal from a measured witness.
        if not e["_seq"]:
            return "Seq::<int>::empty()"
        return "seq![" + ", ".join(f"({v}int)" for v in e["_seq"]) + "]"
    if "int" in e:
        return f"({e['int']}int)" if _SUFFIX_INT else str(e["int"])
    if "var" in e:
        return e["var"]
    if "bool" in e:
        return "true" if e["bool"] else "false"
    if "ite" in e:
        c = e["ite"]
        return (f"(if {expr(c['cond'])} {{ {expr(c['then'])} }}"
                f" else {{ {expr(c['else'])} }})")
    if "call" in e:
        c = e["call"]
        return f"{c['fun']}(" + ", ".join(expr(a) for a in c["args"]) + ")"
    if "forall" in e or "exists" in e:
        kind = "forall" if "forall" in e else "exists"
        q = e[kind]
        v, lo, hi, body = q["var"], expr(q["lo"]), expr(q["hi"]), expr(q["body"])
        rng = f"({lo} <= {v} && {v} < {hi})"
        trig = ""
        if not _has_indexable(q["body"]):
            t = _mod_div_trigger(q["body"])
            if t is not None:
                trig = f" #![trigger {expr(t)}]"
        if kind == "forall":
            return f"(forall|{v}: int|{trig} {rng} ==> {body})"
        return f"(exists|{v}: int|{trig} {rng} && {body})"
    op, args = e["op"], [expr(a) for a in e.get("args", [])]
    if op == "neg":
        return f"(-{args[0]})"
    if op == "not":
        return f"(!{args[0]})"
    if op == "len":
        return f"({args[0]}.len() as int)"
    if op == "at":
        return f"{args[0]}[{args[1]}]"
    if op == "update":
        return f"{args[0]}.update({args[1]}, {args[2]})"
    if op == "fill":
        return f"Seq::new({args[0]} as nat, |_t_fill_i: int| {args[1]})"
    if op == "seq":
        # SPEC.md "Sequences: literals, concatenation, slices" (2026-09-09):
        # [e1, ..., en], n >= 0. `seq!` is vstd's own literal macro; the
        # empty case renders as `Seq::<int>::empty()` (measured,
        # probe_seq_basic.rs: both forms verify, and `seq![]` is not needed
        # since this file already has the empty-literal spelling from the
        # certificate builder's `_seq` node below). Each element is
        # rendered by `expr()` like any other operand, so a non-literal
        # element (filter_pos's `seq![s[i]]`) picks up the same suffixing
        # and indexing this file already emits everywhere else.
        if not args:
            return "Seq::<int>::empty()"
        return "seq![" + ", ".join(args) + "]"
    if op == "slice":
        # s[a..b]: vstd's own `Seq::subrange`, measured (probe_seq_expr.rs,
        # probe_subrange2.rs). Its own `recommends` is NOT enforced by the
        # kernel (measured: an unguarded out-of-bound `subrange` compiles
        # with only a "recommendation not met" NOTE, and a false claim
        # about its result -- e.g. the length postcondition -- correctly
        # FAILS to verify rather than being handed a totalized value), so
        # this op carries no defaults of its own; `defined()`'s "slice"
        # case below is what actually keeps this lowering honest, exactly
        # as SPEC.md requires ("a definedness obligation ... exactly as
        # `at`").
        return f"{args[0]}.subrange({args[1]}, {args[2]})"
    if op in NARY_OPS:
        return "(" + f" {NARY_OPS[op]} ".join(args) + ")"
    if op in BIN_OPS:
        return f"({args[0]} {BIN_OPS[op]} {args[1]})"
    raise ValueError(f"t has no operator {op!r}")


# ----------------------------------------------------------------- v0 path
# byte-identical to the original lowering for "t": 0 tasks.

def body_expr(body: list, ret: str) -> str:
    """Statement body -> Verus expression, or refuse."""
    if len(body) == 1 and "assign" in body[0]:
        name, e = body[0]["assign"]
        assert name == ret, f"assign to {name}, expected {ret}"
        return expr(e)
    if len(body) == 1 and "if" in body[0]:
        c = body[0]["if"]
        return (f"if {expr(c['cond'])} {{ {body_expr(c['then'], ret)} }}"
                f" else {{ {body_expr(c['else'], ret)} }}")
    raise ValueError("t v0 -> verus: body not expressible as one expression")


def lower_v0(task: dict, body: list, witness: dict | None = None) -> str:
    ps = ", ".join(f"{p['name']}: int" for p in task["params"])
    r = task["returns"][0]["name"]
    ensures = ",\n        ".join(expr(e) for e in task["ensures"])
    requires = ",\n        ".join(expr(e) for e in task.get("requires", []))
    req = f"    requires\n        {requires}\n" if requires else ""
    return (
        "use vstd::prelude::*;\n\nverus! {\n\n"
        f"proof fn {task['name']}({ps}) -> ({r}: int)\n"
        f"{req}    ensures\n        {ensures},\n"
        "{\n"
        f"    {body_expr(body, r)}\n"
        "}\n\n} // verus!\n\nfn main() {}\n")


# -------------------------------------------------- definedness conditions
# D(e) per SPEC.md "Definedness": the exact left-to-right short-circuit
# rules, computed as a t expression so it is lowered by the same expr().

TRUE = {"bool": True}


def _conj(parts: list) -> dict:
    parts = [p for p in parts if p != TRUE]
    if not parts:
        return TRUE
    if len(parts) == 1:
        return parts[0]
    return {"op": "and", "args": parts}


def _guard(p: dict, q: dict) -> dict:
    """q need only be defined when p holds."""
    if q == TRUE:
        return TRUE
    return {"op": "implies", "args": [p, q]}


def defined(e: dict) -> dict:
    if "int" in e or "var" in e or "bool" in e:
        return TRUE
    if "ite" in e:
        c = e["ite"]
        dt, de = defined(c["then"]), defined(c["else"])
        branch = (TRUE if dt == TRUE and de == TRUE
                  else {"ite": {"cond": c["cond"], "then": dt, "else": de}})
        return _conj([defined(c["cond"]), branch])
    if "call" in e:
        return _conj([defined(a) for a in e["call"]["args"]])
    if "forall" in e or "exists" in e:
        q = e.get("forall") or e.get("exists")
        db = defined(q["body"])
        body_ob = (TRUE if db == TRUE else
                   {"forall": {"var": q["var"], "lo": q["lo"], "hi": q["hi"],
                               "body": db}})
        return _conj([defined(q["lo"]), defined(q["hi"]), body_ob])
    op, args = e["op"], e.get("args", [])
    if op == "at":
        s, i = args
        bound = {"op": "and", "args": [
            {"op": "<=", "args": [{"int": 0}, i]},
            {"op": "<", "args": [i, {"op": "len", "args": [s]}]}]}
        return _conj([defined(s), defined(i), bound])
    if op == "update":
        s, i, v = args
        bound = {"op": "and", "args": [
            {"op": "<=", "args": [{"int": 0}, i]},
            {"op": "<", "args": [i, {"op": "len", "args": [s]}]}]}
        return _conj([defined(s), defined(i), defined(v), bound])
    if op == "fill":
        n, v = args
        nonneg = {"op": ">=", "args": [n, {"int": 0}]}
        return _conj([defined(n), defined(v), nonneg])
    if op == "slice":
        # s[a..b]: DEFINED IFF 0 <= a <= b <= len(s) (SPEC.md "Sequences:
        # literals, concatenation, slices", 2026-09-09), a definedness
        # obligation under these rules exactly as `at` outside [0, len) --
        # Verus's own `subrange` only carries a `recommends`, which the
        # kernel does not enforce (measured, see `expr()`'s "slice" case),
        # so this file owes the bound itself or a bad slice would silently
        # totalize. `seq` (the literal) and `+` (concatenation, on two
        # seqs as much as on two ints) need no case here: both are total
        # per SPEC.md ("a literal is defined iff all its elements are";
        # "a concatenation is defined iff both arguments are"), exactly the
        # formula the existing catch-all below already computes for every
        # total operator, `+` included.
        s, a, b = args
        bound = {"op": "and", "args": [
            {"op": "<=", "args": [{"int": 0}, a]},
            {"op": "<=", "args": [a, b]},
            {"op": "<=", "args": [b, {"op": "len", "args": [s]}]}]}
        return _conj([defined(s), defined(a), defined(b), bound])
    if op in ("div", "mod"):
        x, y = args
        nonzero = {"op": "!=", "args": [y, {"int": 0}]}
        return _conj([defined(x), defined(y), nonzero])
    if op == "and":
        res = TRUE
        for a in reversed(args):
            res = _conj([defined(a), _guard(a, res)])
        return res
    if op == "or":
        res = TRUE
        for a in reversed(args):
            res = _conj([defined(a), _guard({"op": "not", "args": [a]}, res)])
        return res
    if op == "implies":
        p, q = args
        return _conj([defined(p), _guard(p, defined(q))])
    # total operators: not neg len + - * == != < <= > >=
    return _conj([defined(a) for a in args])


def subst(e: dict, m: dict) -> dict:
    """Capture-avoiding substitution over a t expression: each mapped name
    is replaced by a new name (str) or a whole t expression (dict)."""
    if "var" in e:
        v = m.get(e["var"])
        if v is None:
            return e
        return {"var": v} if isinstance(v, str) else v
    if "int" in e or "bool" in e or "_seq" in e:
        return e
    if "ite" in e:
        c = e["ite"]
        return {"ite": {"cond": subst(c["cond"], m),
                        "then": subst(c["then"], m),
                        "else": subst(c["else"], m)}}
    if "call" in e:
        c = e["call"]
        return {"call": {"fun": c["fun"],
                         "args": [subst(a, m) for a in c["args"]]}}
    if "forall" in e or "exists" in e:
        kind = "forall" if "forall" in e else "exists"
        q = e[kind]
        inner = {k: v for k, v in m.items() if k != q["var"]}
        return {kind: {"var": q["var"], "lo": subst(q["lo"], m),
                       "hi": subst(q["hi"], m),
                       "body": subst(q["body"], inner)}}
    return {"op": e["op"], "args": [subst(a, m) for a in e.get("args", [])]}


def _calls(e: dict, name: str) -> bool:
    if "call" in e:
        c = e["call"]
        if c["fun"] == name:
            return True
        return any(_calls(a, name) for a in c["args"])
    if "ite" in e:
        c = e["ite"]
        return any(_calls(c[k], name) for k in ("cond", "then", "else"))
    if "forall" in e or "exists" in e:
        q = e.get("forall") or e.get("exists")
        return any(_calls(q[k], name) for k in ("lo", "hi", "body"))
    return any(_calls(a, name) for a in e.get("args", []))


def _body_calls(body: list, name: str) -> bool:
    for s in body:
        if "assign" in s and _calls(s["assign"][1], name):
            return True
        if "return" in s and _calls(s["return"][1], name):
            return True
        if "var" in s and _calls(s["var"]["init"], name):
            return True
        if "if" in s:
            c = s["if"]
            if (_calls(c["cond"], name) or _body_calls(c["then"], name)
                    or _body_calls(c["else"], name)):
                return True
        if "while" in s:
            w = s["while"]
            if (_calls(w["cond"], name) or _calls(w["decreases"], name)
                    or any(_calls(i, name) for i in w.get("invariants", []))
                    or _body_calls(w["body"], name)):
                return True
    return False


def _assigned(body: list) -> set:
    # 2026-09-08 (SPEC.md "Early exit"): deliberately no `return` case. This
    # set feeds `loop()`'s choice of which scope names are ordinary loop
    # STATE, threaded through the recursive helper's arguments every
    # iteration. A `return`'s target is not that: it is produced at most
    # once, on the exit path, and `loop()` carries it through a separate
    # wrapped-result slot (see `_may_return` below), never as per-iteration
    # state. Folding it in here would double up the two mechanisms.
    out = set()
    for s in body:
        if "assign" in s:
            out.add(s["assign"][0])
        elif "if" in s:
            out |= _assigned(s["if"]["then"]) | _assigned(s["if"]["else"])
        elif "while" in s:
            out |= _assigned(s["while"]["body"])
    return out


def _declared(body: list) -> set:
    out = set()
    for s in body:
        if "var" in s:
            out.add(s["var"]["name"])
        elif "if" in s:
            out |= _declared(s["if"]["then"]) | _declared(s["if"]["else"])
        elif "while" in s:
            out |= _declared(s["while"]["body"])
    return out


def _may_return(body: list) -> bool:
    """True iff `body` contains a `return` (SPEC.md "Early exit",
    2026-09-08), directly, inside an `if` branch, or inside a nested
    `while`'s body. The nested-loop case matters: a nested loop that may
    return already wraps ITS OWN result (see `loop()`), so the loop
    enclosing it also needs the wrapped-result treatment purely to
    propagate that outward, even though no `return` sits directly in its
    own body."""
    for s in body:
        if "return" in s:
            return True
        if "if" in s:
            if _may_return(s["if"]["then"]) or _may_return(s["if"].get("else") or []):
                return True
        if "while" in s:
            if _may_return(s["while"]["body"]):
                return True
    return False


# ------------------------------------------------------------------ v1 path

def _has_nonlinear(e: dict) -> bool:
    """True iff e contains a product of two non-literal factors, the shape
    Verus's default solver profile (nonlinear arithmetic off, measured:
    sum_upto's invariant preservation fails without help) cannot decide."""
    if "ite" in e:
        return any(_has_nonlinear(e["ite"][k]) for k in ("cond", "then", "else"))
    if "call" in e:
        return any(_has_nonlinear(a) for a in e["call"]["args"])
    if "forall" in e or "exists" in e:
        q = e.get("forall") or e.get("exists")
        return any(_has_nonlinear(q[k]) for k in ("lo", "hi", "body"))
    if "op" in e:
        if e["op"] == "*":
            a, b = e["args"]
            if "int" not in a and "int" not in b:
                return True
        return any(_has_nonlinear(a) for a in e.get("args", []))
    return False


def _sym(body: list, env: dict) -> dict | None:
    """Equational symbolic execution of a loop body: the effect of one
    iteration as a map from each variable to a t expression over the entry
    values, if-joins merged with ite. None when the body contains a nested
    while (its effect is not equational), or, 2026-09-08 (SPEC.md "Early
    exit"), a `return`: an iteration that can escape the loop entirely has
    no single equational post-state either, so the nonlinear_arith bridge
    in `loop()` is skipped and preservation is left to Verus unaided (an
    UNPROVED cell there is not a failure, just no committed task needs
    both a nonlinear invariant and a `return` in the same loop yet)."""
    env = dict(env)
    for s in body:
        if "assign" in s:
            n, e = s["assign"]
            env[n] = subst(e, env)
        elif "return" in s:
            return None
        elif "var" in s:
            v = s["var"]
            env[v["name"]] = subst(v["init"], env)
        elif "if" in s:
            c = subst(s["if"]["cond"], env)
            e1 = _sym(s["if"]["then"], env)
            e2 = _sym(s["if"]["else"], env)
            if e1 is None or e2 is None:
                return None
            env = {k: (e1[k] if e1[k] == e2[k] else
                       {"ite": {"cond": c, "then": e1[k], "else": e2[k]}})
                   for k in env}
        elif "while" in s:
            return None
    return env


def _prenex(e: dict, fresh) -> tuple[list[str], dict]:
    """Pull the foralls that defined() generated (they sit only in positive
    spine positions: conjuncts, guard consequents, ite branches, forall
    bodies) out to the front, renamed fresh, their [lo,hi) ranges turned
    into guards of the matrix. Sound because the binders are fresh and every
    hoisted forall is in a positive position. The point (measured): a
    definedness forall's body often has no function-application term, so
    Verus cannot infer a trigger for it, so hoisting the binder into the
    enclosing lemma's parameters removes the SMT quantifier entirely."""
    if "forall" in e:
        q = e["forall"]
        v = next(fresh)
        body = subst(q["body"], {q["var"]: v})
        bs, mat = _prenex(body, fresh)
        rng = {"op": "and", "args": [
            {"op": "<=", "args": [q["lo"], {"var": v}]},
            {"op": "<", "args": [{"var": v}, q["hi"]]}]}
        return [v] + bs, {"op": "implies", "args": [rng, mat]}
    if "ite" in e:
        c = e["ite"]
        bt, tm = _prenex(c["then"], fresh)
        be, em = _prenex(c["else"], fresh)
        if not bt and not be:
            return [], e
        return bt + be, {"ite": {"cond": c["cond"], "then": tm, "else": em}}
    if "op" in e and e["op"] == "and":
        bs, mats = [], []
        for a in e["args"]:
            b, m = _prenex(a, fresh)
            bs += b
            mats.append(m)
        return bs, {"op": "and", "args": mats}
    if "op" in e and e["op"] == "implies":
        p, q = e["args"]
        bs, qm = _prenex(q, fresh)
        if not bs:
            return [], e
        return bs, {"op": "implies", "args": [p, qm]}
    return [], e


def _div_mod_pairs(e: dict) -> list[tuple[dict, dict]]:
    """Every distinct (x, y) operand pair fed to a `div` or `mod`
    application anywhere in e, first-seen order, deduplicated by rendered
    Verus text (so `div(m, 10)` and a later `mod(m, 10)` in the same
    statement share one bridging fact, see _div_mod_law)."""
    seen: dict[tuple[str, str], tuple[dict, dict]] = {}

    def walk(n: dict) -> None:
        if "ite" in n:
            c = n["ite"]
            walk(c["cond"]); walk(c["then"]); walk(c["else"])
            return
        if "call" in n:
            for a in n["call"]["args"]:
                walk(a)
            return
        if "forall" in n or "exists" in n:
            q = n.get("forall") or n.get("exists")
            walk(q["lo"]); walk(q["hi"]); walk(q["body"])
            return
        if "op" in n:
            if n["op"] in ("div", "mod"):
                x, y = n["args"]
                seen.setdefault((expr(x), expr(y)), (x, y))
            for a in n.get("args", []):
                walk(a)

    walk(e)
    return list(seen.values())


def _div_mod_law(x: dict, y: dict, ind: str) -> str:
    """The Euclidean defining identity `x == (x div y) * y + (x mod y)`,
    established by nonlinear_arith. Measured 2026-09-08: Verus's default
    solver profile (nonlinear arithmetic off) cannot discharge this
    unaided (probe_law.rs: `ensures x == (x/y)*y + (x%y)` with `requires
    y != 0` alone, postcondition not satisfied) because `(x/y)*y`
    multiplies two non-literal terms, but `by (nonlinear_arith) requires
    y != 0 { }` / `requires y != 0;` both close it (probe_law3.rs,
    probe_law4.rs). The range half of the law, `0 <= x%y` and
    `x%y < y || x%y < -y`, is native (probe_range.rs, 0 errors, no hint
    needed) so only the multiplicative identity is asserted here. Sound
    and task-independent: it is a fact about `/` and `%` themselves, true
    for every y != 0, and the `requires` premise is exactly the
    definedness obligation this div/mod already owes (SPEC.md, `defined()`
    above), so it can never smuggle in a task's own obligation as a
    hypothesis; Verus still has to prove that premise from ambient facts
    (measured, probe_law5.rs: dropping the ambient `y != 0` turns this
    into "requires not satisfied")."""
    ident = {"op": "==", "args": [x, {"op": "+", "args": [
        {"op": "*", "args": [{"op": "div", "args": [x, y]}, y]},
        {"op": "mod", "args": [x, y]}]}]}
    nz = {"op": "!=", "args": [y, {"int": 0}]}
    return (f"{ind}assert({expr(ident)}) by (nonlinear_arith)\n"
            f"{ind}    requires\n{ind}        {expr(nz)},\n"
            f"{ind};")


def _dummy(ty: str) -> str:
    """A throwaway literal of Verus type `ty`, for the slot a wrapped loop
    helper's result (SPEC.md "Early exit", 2026-09-08) leaves unused: the
    return value when the call did not return, or the state tuple when it
    did. Its VALUE is never read (the ensures conditions each slot on the
    same flag that decided which one is meaningful); it only has to
    type-check. Built via `expr()` so it picks up the same `_SUFFIX_INT`
    literal form (`0int`) v1 already emits everywhere else."""
    if ty == "int":
        return expr({"int": 0})
    if ty == "bool":
        return expr({"bool": False})
    if ty == "Seq<int>":
        return expr({"_seq": []})
    raise ValueError(f"verus: no dummy literal for type {ty!r}")


class _V1:
    def __init__(self, task: dict):
        self.task = task
        self.name = task["name"]
        self.helpers: list[str] = []   # loop helper proof fns
        self.wf: list[str] = []        # definedness (well-formedness) lemmas
        self.loop_ix = 0

    # -- well-formedness lemmas ------------------------------------------
    def _wf_lemma(self, lname: str, params: list[tuple[str, str]],
                  context: list[dict], obligation: dict) -> None:
        if obligation == TRUE:
            return
        fresh = (f"t_q{i}" for i in range(1000))
        binders, obligation = _prenex(obligation, fresh)
        params = params + [(b, "int") for b in binders]
        ps = ", ".join(f"{n}: {t}" for n, t in params)
        req = ""
        if context:
            req = ("    requires\n        "
                   + ",\n        ".join(expr(c) for c in context) + ",\n")
        self.wf.append(
            f"proof fn {lname}({ps})\n{req}"
            "{\n"
            f"    assert({expr(obligation)});\n"
            "}\n")

    # -- statements ------------------------------------------------------
    def _assert_defined(self, e: dict, lines: list[str], ind: str) -> None:
        ob = defined(e)
        if ob != TRUE:
            lines.append(f"{ind}assert({expr(ob)});")
        for x, y in _div_mod_pairs(e):
            lines.append(_div_mod_law(x, y, ind))

    def stmts(self, body: list, scope: dict, ind: str,
              wrap: str | None = None) -> list[str]:
        """scope: ordered {name: (verus_type, mutable)}. Returns lines.

        `wrap` (SPEC.md "Early exit", 2026-09-08) is None when `body` runs
        directly in the task's own proof fn: a `return` there is a bare
        Verus `return value;`, ending the task exactly as it ends the
        interpreter's exec_body. Inside a loop helper whose body may
        return (`_may_return`), `wrap` is instead the Verus expression for
        THAT helper's own state tuple, so a `return` there emits
        `return (true, value, wrap);` -- the helper's wrapped result, see
        `loop()` -- and a nested loop's own wrapped result is re-wrapped
        the same way at its call site below."""
        lines: list[str] = []
        for s in body:
            if "assign" in s:
                name, e = s["assign"]
                assert name in scope and scope[name][1], \
                    f"assign to {name}, not a mutable name in scope"
                self._assert_defined(e, lines, ind)
                lines.append(f"{ind}{name} = {expr(e)};")
            elif "return" in s:
                rname, e = s["return"]
                assert rname == self.task["returns"][0]["name"], \
                    f"return names {rname}, expected {self.task['returns'][0]['name']}"
                self._assert_defined(e, lines, ind)
                if wrap is None:
                    lines.append(f"{ind}return {expr(e)};")
                else:
                    lines.append(f"{ind}return (true, {expr(e)}, {wrap});")
            elif "var" in s:
                v = s["var"]
                self._assert_defined(v["init"], lines, ind)
                scope[v["name"]] = (TYPES[v["type"]], True)
                lines.append(f"{ind}let mut {v['name']}: {TYPES[v['type']]}"
                             f" = {expr(v['init'])};")
            elif "if" in s:
                c = s["if"]
                self._assert_defined(c["cond"], lines, ind)
                lines.append(f"{ind}if {expr(c['cond'])} {{")
                lines += self.stmts(c["then"], dict(scope), ind + "    ", wrap)
                if c["else"]:
                    lines.append(f"{ind}}} else {{")
                    lines += self.stmts(c["else"], dict(scope), ind + "    ", wrap)
                lines.append(f"{ind}}}")
            elif "while" in s:
                lines += self.loop(s["while"], scope, ind, wrap)
            else:
                raise ValueError(f"t v1 -> verus: unknown statement {s!r}")
        return lines

    # -- loops: proof mode has no while (measured), so the loop rule is  --
    # -- encoded as a recursive helper lemma; see module docstring.      --
    def loop(self, w: dict, scope: dict, ind: str,
             wrap: str | None = None) -> list[str]:
        k = self.loop_ix
        self.loop_ix += 1
        invs = w.get("invariants", [])
        cond, dec = w["cond"], w["decreases"]

        # GUARD DEFINEDNESS (2026-09-09, the residual COVERAGE-lifted-785.md
        # names: a `div`/`mod` in a loop guard -- `cond` or `decreases` --
        # is a definedness obligation neither of these two shared no-op
        # `TRUE` conditions the check used to require. `cond` and
        # `decreases` are each evaluated once per call of the recursive
        # helper below (`cond` by the `if` at its top, `decreases` by
        # Verus's own termination check over the same call), so their
        # combined obligation is asserted as the FIRST statement of the
        # helper body -- see `guard_pre` near the helper's own text --
        # which covers every evaluation, including the very first, since
        # even the outermost call site runs through this same body. That
        # assert is discharged from the helper's own `requires` (every
        # invariant already in scope there, see `req_clauses` below), the
        # identical mechanism an ordinary statement's `_assert_defined`
        # already uses; no separate wf lemma is needed since this is a
        # statement position, not a declarative one, and no call-site
        # change is needed either, since the assert lives inside the
        # callee. Trivial for every previously committed loop task
        # (`is_prime` included: its guard is `i * i <= n`, no div/mod) so
        # `guard_ob` there stays `TRUE` and nothing is emitted, keeping
        # `is_prime`, `first_even` and `tail` byte-identical.
        guard_ob = _conj([defined(cond), defined(dec)])
        guard_lines: list[str] = []
        if guard_ob != TRUE:
            guard_lines.append(f"    assert({expr(guard_ob)});")
        gd_pairs: dict[tuple[str, str], tuple[dict, dict]] = {}
        for e in (cond, dec):
            for x, y in _div_mod_pairs(e):
                gd_pairs.setdefault((expr(x), expr(y)), (x, y))
        for x, y in gd_pairs.values():
            guard_lines.append(_div_mod_law(x, y, "    "))
        guard_pre = "".join(line + "\n" for line in guard_lines)

        # invariant k may assume invariants 1..k-1 (SPEC.md definedness)
        allvars = [(n, t) for n, (t, _m) in scope.items()]
        for j, iv in enumerate(invs):
            self._wf_lemma(f"t_wf_{self.name}_l{k}_inv{j}", allvars,
                           invs[:j], defined(iv))

        assigned = _assigned(w["body"]) - _declared(w["body"])
        state = [n for n in scope if scope[n][1] and n in assigned]
        ro = [n for n in scope if n not in state]
        assert state, "loop body assigns nothing in scope, not lowerable"

        if len(state) == 1:
            state_ty = scope[state[0]][0]
            res_val = state[0]
        else:
            state_ty = "(" + ", ".join(scope[v][0] for v in state) + ")"
            res_val = "(" + ", ".join(state) + ")"

        # EARLY EXIT (2026-09-08, SPEC.md "Early exit"). A `return` inside
        # this loop's body -- directly, in an `if`, or through a nested
        # loop's already-wrapped result -- means one call of the recursive
        # helper can end the whole TASK instead of one more iteration, so
        # its result can no longer be just the state tuple: it becomes
        # (t_res.0: bool, did this call return?; t_res.1: the task's return
        # value if so; t_res.2: the loop state tuple if not). The ensures
        # splits the same way: on the return branch the task owes its own
        # `ensures` (substituting the return name), never the invariants,
        # exactly as SPEC.md states; on the other branch it owes
        # invariants + negated guard as before. Measured (probe_ret_proof.rs,
        # 2026-09-08): Verus accepts a native `return` inside a recursive
        # `proof fn` and checks the ensures at that exit with no
        # loop-invariant obligation -- the same rule probe_ret_exec.rs shows
        # for a native `while` in an exec fn with a named return.
        may_ret = _may_return(w["body"])
        base = "t_res.2" if may_ret else "t_res"
        if len(state) == 1:
            m = {state[0]: base}
        else:
            m = {v: f"{base}.{j}" for j, v in enumerate(state)}

        if may_ret:
            rname = self.task["returns"][0]["name"]
            rtype = TYPES[self.task["returns"][0]["type"]]
            res_ty = f"(bool, {rtype}, {state_ty})"
            m_ret = {rname: "t_res.1"}
            ens = ([f"t_res.0 ==> {expr(subst(en, m_ret))}"
                    for en in self.task["ensures"]]
                   + [f"(!t_res.0) ==> {expr(subst(iv, m))}" for iv in invs]
                   + [f"(!t_res.0) ==> (!{expr(subst(cond, m))})"])
            base_val = f"(false, {_dummy(rtype)}, {res_val})"
            # The return branch owes the task's OWN `ensures`, which may
            # read the task's `requires` (e.g. a bound on a parameter), so
            # those go into the helper's own requires alongside the
            # invariants; harmless when unused, since they hold at every
            # call site (established once at task entry, never reassigned).
            req_clauses = list(self.task.get("requires", [])) + invs
        else:
            res_ty = state_ty
            ens = ([expr(subst(i, m)) for i in invs]
                   + [f"(!{expr(subst(cond, m))})"])
            base_val = res_val
            req_clauses = invs
        ens_s = ",\n        ".join(ens)

        hname = f"t_lp_{self.name}_{k}"
        ps = ", ".join(f"{n}: {scope[n][0]}" for n in ro + state)
        req = ""
        if req_clauses:
            req = ("    requires\n        "
                   + ",\n        ".join(expr(i) for i in req_clauses) + ",\n")

        # Invariants with nonlinear terms need Verus's sanctioned escape
        # hatch, assert ... by (nonlinear_arith) with explicit premises,
        # because the default solver profile has nonlinear arithmetic off
        # (measured; Dafny's does not). The premises are exactly t's
        # preservation rule: all invariants plus the guard at entry; the
        # conclusion is the invariant over the symbolic post-state. `_sym`
        # gives up (None) when the body may return, same as a nested while,
        # so this is skipped in that case; see `_sym`'s docstring.
        nl = [j for j, iv in enumerate(invs) if _has_nonlinear(iv)]
        old_lets, bridge = "", []
        if nl:
            entry = {v: {"var": f"t_old_{v}"} for v in state}
            env = _sym(w["body"], entry)
            if env is not None:
                old_lets = "".join(f"    let t_old_{v} = {v};\n"
                                   for v in state)
                prem = ",\n                ".join(
                    expr(subst(p, entry)) for p in invs + [cond])
                bridge = [
                    f"        assert({expr(subst(invs[j], env))})"
                    " by (nonlinear_arith)\n"
                    f"            requires\n                {prem},\n"
                    "        ;"
                    for j in nl]

        hscope = {n: (scope[n][0], n in state) for n in ro + state}
        inner = self.stmts(w["body"], hscope, "        ",
                            res_val if may_ret else None) + bridge
        shadows = "".join(f"    let mut {v} = {v};\n" for v in state)
        args = ", ".join(ro + state)
        self.helpers.append(
            f"proof fn {hname}({ps}) -> (t_res: {res_ty})\n"
            f"{req}    ensures\n        {ens_s},\n"
            f"    decreases {expr(dec)},\n"
            "{\n"
            f"{old_lets}{shadows}{guard_pre}"
            f"    if {expr(cond)} {{\n"
            + "\n".join(inner) + "\n"
            f"        {hname}({args})\n"
            "    } else {\n"
            f"        {base_val}\n"
            "    }\n"
            "}\n")

        tmp = f"t_tmp{k}"
        lines = [f"{ind}let {tmp} = {hname}({args});"]
        if may_ret:
            if wrap is None:
                lines.append(f"{ind}if {tmp}.0 {{ return {tmp}.1; }}")
            else:
                lines.append(
                    f"{ind}if {tmp}.0 {{ return (true, {tmp}.1, {wrap}); }}")
            if len(state) == 1:
                lines.append(f"{ind}{state[0]} = {tmp}.2;")
            else:
                lines += [f"{ind}{v} = {tmp}.2.{j};" for j, v in enumerate(state)]
        else:
            if len(state) == 1:
                lines.append(f"{ind}{state[0]} = {tmp};")
            else:
                lines += [f"{ind}{v} = {tmp}.{j};" for j, v in enumerate(state)]
        return lines

    # -- whole task ------------------------------------------------------
    def emit(self, body: list) -> str:
        task = self.task
        params = [(p["name"], TYPES[p["type"]]) for p in task["params"]]
        rname = task["returns"][0]["name"]
        rtype = TYPES[task["returns"][0]["type"]]
        reqs = task.get("requires", [])
        enss = task["ensures"]

        # spec fns and their (universal) definedness lemmas
        spec_blocks = []
        for f in task.get("spec_funs", []):
            fps = ", ".join(f"{p['name']}: {TYPES[p['type']]}"
                            for p in f["params"])
            if defined(f["decreases"]) != TRUE:
                raise NotImplementedError(
                    "verus: definedness obligation on spec_fun decreases "
                    "not implemented")
            spec_blocks.append(
                f"spec fn {f['name']}({fps}) -> {TYPES[f['result']]}\n"
                f"    decreases {expr(f['decreases'])},\n"
                "{\n"
                f"    {expr(f['body'])}\n"
                "}\n")
            self._wf_lemma(f"t_wf_{self.name}_fn_{f['name']}",
                           [(p["name"], TYPES[p["type"]])
                            for p in f["params"]],
                           [], defined(f["body"]))

        # requires clause k assumes clauses 1..k-1; ensures clause k assumes
        # all requires and ensures 1..k-1 (SPEC.md definedness)
        for j, rq in enumerate(reqs):
            self._wf_lemma(f"t_wf_{self.name}_req{j}", params,
                           reqs[:j], defined(rq))
        for j, en in enumerate(enss):
            self._wf_lemma(f"t_wf_{self.name}_ens{j}",
                           params + [(rname, rtype)],
                           reqs + enss[:j], defined(en))

        if _body_calls(body, self.name) and "decreases" not in task:
            raise ValueError(
                "self-recursive body without a task-level decreases "
                "(SPEC.md gate 3 requires one)")
        dec = ""
        if "decreases" in task:
            if defined(task["decreases"]) != TRUE:
                raise NotImplementedError(
                    "verus: definedness obligation on task decreases "
                    "not implemented")
            dec = f"    decreases {expr(task['decreases'])},\n"

        scope = {n: (t, False) for n, t in params}
        scope[rname] = (rtype, True)
        main_lines = self.stmts(body, scope, "    ")

        ps = ", ".join(f"{n}: {t}" for n, t in params)
        req = ""
        if reqs:
            req = ("    requires\n        "
                   + ",\n        ".join(expr(e) for e in reqs) + ",\n")
        ens = ",\n        ".join(expr(e) for e in enss)
        main = (
            f"proof fn {self.name}({ps}) -> ({rname}: {rtype})\n"
            f"{req}    ensures\n        {ens},\n{dec}"
            "{\n"
            f"    let mut {rname}: {rtype};\n"
            + "\n".join(main_lines) + "\n"
            f"    {rname}\n"
            "}\n")

        blocks = spec_blocks + self.wf + self.helpers + [main]
        return ("use vstd::prelude::*;\n\nverus! {\n\n"
                + "\n".join(blocks)
                + "\n} // verus!\n\nfn main() {}\n")




# ------------------------------------------------ the refutation certificate
# Shared certificate protocol (2026-09-02, all columns). Verus surfaces NO
# signal separating a countermodel from incompleteness: Z3 runs with
# smt.mbqi false, so the check-sat for a genuinely false postcondition and
# for true nonlinear distributivity both come back "unknown" (measured, see
# verifiers/verus.py), and no flag prints a model. The adapter therefore
# never mints REFUTED from a bare verification failure. What it can trust
# is a proof it checked itself: when lowering a TWIN whose measured witness
# is expressible as a GROUND formula, this lowering appends one extra goal,
# named exactly t_refutation_certificate, that instantiates the spec at the
# concrete witness and asserts via assert(..) by (compute_only), ground
# kernel evaluation with no SMT fallback, that the obligation fails there.
# verifiers/verus.py mints REFUTED only when the kernel accepts that goal,
# and a file carrying the goal's name can never mint VERIFIED.
#
# What each witness kind certifies:
#   value (_ens True only): requires holds at the witness input and the
#     ensures conjunction is false at (input, r := the twin's measured
#     result). Recursive spec fns evaluate under compute_only with no
#     reveal_with_fuel (measured: fact(2), count over seq literals).
#   exit: the loop rule's post-loop obligation is false at the witness
#     state: requires and the twin's SURVIVING invariants hold, the guard
#     is false, and the ensures conjunction is false. The kept invariants
#     and guard are read off the twin body's own loop, found by diffing the
#     real body against the twin body, so the certificate always speaks
#     about the file it travels in. This is the negation of exactly the
#     obligation the lowered twin asks the kernel to prove: the loop helper
#     ensures only invariants plus the negated guard, and the witness state
#     is one interp._Admissible already screened as unrefusable.
#   preservation: would need one loop iteration replayed inside the
#     certificate; not emitted (no current twin produces this kind), so
#     such a cell honestly reads unproved.
#   undefined (2026-09-09, SPEC.md "Sequences as values"): the twin has no
#     value at the witness because some statement's right-hand side hit a
#     partial operator (`at`, `update`, `fill`, `div`, `mod`) outside its
#     domain before any `ensures` instance could even be stated, so there
#     is nothing to substitute the return name with. What IS ground and
#     checkable is the operator's own definedness obligation, which this
#     lowering's `defined()` already computes for every honest assert it
#     emits: requires holds at the witness, and that same obligation,
#     re-evaluated with interp.ev over the SAME statements in the SAME
#     order interp.py walked to raise the Undef that minted this witness
#     kind, is false. `_undef_obligation` below does the walk and returns
#     the first such false obligation, ground-substituted; None (no
#     certificate, an honest unproved) on an `if`, `while`, or `return`
#     before the failing statement, or if the walk disagrees with the
#     witness and finds nothing false.
# Bounded quantifiers whose bounds are ground after witness substitution
# are unrolled here (finite conjunction/disjunction over the concrete
# range, capped) because compute_only cannot evaluate int quantifiers; the
# formula the kernel checks is fully ground. Anything outside these rules
# returns None and no certificate is emitted: a missing or rejected
# certificate can only cost a flip (UNPROVED), never fake one.

CERT_NAME = "t_refutation_certificate"
_UNROLL_CAP = 64


def _tlit(v):
    """A measured witness value as a t literal expression."""
    if isinstance(v, bool):
        return {"bool": v}
    if isinstance(v, int):
        return {"int": v}
    if isinstance(v, list) and all(
            isinstance(x, int) and not isinstance(x, bool) for x in v):
        return {"_seq": list(v)}
    raise ValueError(f"witness value {v!r} has no t literal")


def _gint(e) -> int:
    """Ground int value of a quantifier bound after witness substitution.
    Deliberately strict: anything unexpected raises, which refuses the
    certificate rather than emitting a wrong one."""
    if isinstance(e, dict) and "int" in e:
        return e["int"]
    op = e.get("op") if isinstance(e, dict) else None
    args = e.get("args", []) if isinstance(e, dict) else []
    if op == "len" and len(args) == 1 and "_seq" in args[0]:
        return len(args[0]["_seq"])
    if op == "neg" and len(args) == 1:
        return -_gint(args[0])
    if op in ("+", "-", "*") and len(args) == 2:
        a, b = _gint(args[0]), _gint(args[1])
        return a + b if op == "+" else (a - b if op == "-" else a * b)
    if op in ("div", "mod") and len(args) == 2:
        # Same Euclidean rule as interp.py's ev() for "div"/"mod": the
        # unique q, r with a == q*b + r and 0 <= r < |b|. b == 0 is
        # undefined (SPEC.md), so it refuses rather than fabricating a
        # bound, the same fail-closed posture as every other case here.
        a, b = _gint(args[0]), _gint(args[1])
        if b == 0:
            raise ValueError("quantifier bound: division by zero")
        r = a % abs(b)
        return r if op == "mod" else (a - r) // b
    raise ValueError(f"quantifier bound not ground: {e!r}")


def _unroll(e: dict, budget: list) -> dict:
    """Replace bounded quantifiers (ground bounds) with finite conjunctions
    or disjunctions so compute_only can evaluate the result. budget is a
    one-element countdown over emitted instances; exhausting it raises and
    the certificate is refused."""
    if "forall" in e or "exists" in e:
        kind = "forall" if "forall" in e else "exists"
        q = e[kind]
        lo, hi = _gint(q["lo"]), _gint(q["hi"])
        insts = []
        for k in range(lo, hi):
            budget[0] -= 1
            if budget[0] < 0:
                raise ValueError("quantifier unroll budget exhausted")
            insts.append(_unroll(subst(q["body"], {q["var"]: {"int": k}}),
                                 budget))
        if not insts:
            return {"bool": kind == "forall"}
        if len(insts) == 1:
            return insts[0]
        return {"op": "and" if kind == "forall" else "or", "args": insts}
    if "ite" in e:
        c = e["ite"]
        return {"ite": {"cond": _unroll(c["cond"], budget),
                        "then": _unroll(c["then"], budget),
                        "else": _unroll(c["else"], budget)}}
    if "call" in e:
        c = e["call"]
        return {"call": {"fun": c["fun"],
                         "args": [_unroll(a, budget) for a in c["args"]]}}
    if "op" in e:
        return {"op": e["op"],
                "args": [_unroll(a, budget) for a in e.get("args", [])]}
    return e


def _twin_loop(real_body: list, twin_body: list) -> dict | None:
    """The single while whose invariant list the twin changed, or None."""
    diffs: list[dict] = []

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


def certificate_formula(task: dict, twin_body: list, w: dict) -> dict | None:
    """The certificate's FORMULA as a t expression, or None when the witness
    is not ground-certificatable under the rules in the section above.

    Factored out of `_certificate` 2026-09-06 so another column can certify
    the SAME formula rather than a second reading of it: lower_fstar.py
    imports this and renders it in F* syntax. Every rule in the section
    comment above therefore has one implementation, and a change to what a
    certificate MEANS lands in one place while each column keeps only its own
    syntax and its own ground-evaluation tactic."""
    return _cert_formula(task, twin_body, w)


def _undef_obligation(task: dict, twin_body: list, m: dict, names: dict
                       ) -> dict | None:
    """The negated definedness obligation of the twin body's first
    statement that has none, ground-substituted at the witness (SPEC.md
    "Sequences as values", 2026-09-09; see the "undefined" entry in the
    section comment above). Re-walks `twin_body` with interp.ev, in the
    SAME left-to-right statement order interp.py's own exec_body used to
    raise the Undef that minted this witness in the first place, so the
    statement this finds is the same one interp.py found; `defined()` is
    the identical function this lowering already trusts for every honest
    assert it emits, so there is no second, independent reading of what
    "defined" means. `m` (var name -> t literal) and `env_py` (var name ->
    Python value, the tuples-for-seqs form interp.ev itself uses) both grow
    as the walk proceeds, so a later statement's own obligation (`swap`'s
    off-by-one twin fails on its very first statement, so no committed task
    yet exercises this, but the mechanism is not special-cased to the
    first) sees the concrete values of every name the twin already bound.
    None on an `if`, `while`, or `return` before the failing statement
    (their own definedness is not walked here, matching every other "not
    emitted" case in this file); None if the walk exhausts the body
    without a false obligation, refusing rather than certifying a formula
    that would disagree with the witness that triggered it."""
    env_py = {n: (tuple(v) if isinstance(v, list) else v)
              for n, v in names.items()}
    m = dict(m)
    funs = interp.funs_of(task, twin_body)
    st = interp.St()
    try:
        for s in twin_body:
            if "var" in s:
                name, e = s["var"]["name"], s["var"]["init"]
            elif "assign" in s:
                name, e = s["assign"]
            else:
                return None
            ob = defined(e)
            if ob != TRUE and not interp.ev(ob, env_py, funs, st):
                return {"op": "not", "args": [subst(ob, m)]}
            val = interp.ev(e, env_py, funs, st)
            env_py[name] = val
            m[name] = _tlit(list(val) if isinstance(val, tuple) else val)
    except (interp.Undef, interp.Budget, RecursionError):
        return None
    return None


def _cert_formula(task: dict, twin_body: list, w: dict) -> dict | None:
    kind = w.get("_kind")
    names = {k: v for k, v in w.items() if not k.startswith("_")}
    try:
        m = {n: _tlit(v) for n, v in names.items()}
        parts = [subst(rq, m) for rq in task.get("requires", [])]
        if kind == "value":
            if w.get("_ens") is not True:
                return None      # a drift a sound kernel may still accept
            tw = w.get("_twin")
            if not isinstance(tw, (bool, int, list)):
                return None
            m2 = dict(m)
            m2[task["returns"][0]["name"]] = _tlit(tw)
            parts = [subst(rq, m2) for rq in task.get("requires", [])]
            parts.append({"op": "not", "args": [
                _conj([subst(en, m2) for en in task["ensures"]])]})
        elif kind == "exit":
            loop = _twin_loop(task["body"], twin_body)
            if loop is None:
                return None
            # The obligation is at the RETURN: the loop-exit state run
            # through whatever follows the loop (interp.exit_env, which is
            # None under an enclosing loop, where the exit re-enters it). A
            # tail loop runs nothing and the formula is what it always was.
            # Measured 2026-09-07 (ROADMAP 12.5): slow_max assigns z after
            # its loop, and a certificate stating not-ensures at the loop's
            # own z minted REFUTED on a twin every kernel proves.
            ret = task["returns"][0]["name"]
            post = interp.exit_env(task, twin_body, loop, names)
            if post is None:
                return None
            m2 = dict(m)
            m2[ret] = _tlit(post[ret])
            parts += [subst(iv, m) for iv in loop.get("invariants", [])]
            parts.append({"op": "not", "args": [subst(loop["cond"], m)]})
            parts.append({"op": "not", "args": [
                _conj([subst(en, m2) for en in task["ensures"]])]})
        elif kind == "undefined":
            ob = _undef_obligation(task, twin_body, m, names)
            if ob is None:
                return None
            parts.append(ob)
        else:
            return None          # preservation: see above
        return _unroll(_conj(parts), [_UNROLL_CAP])
    except (ValueError, KeyError, TypeError, IndexError):
        return None


def _certificate(task: dict, twin_body: list, w: dict) -> str | None:
    """The appended t_refutation_certificate block for a measured twin
    witness, or None when the witness is not expressible as a ground
    certificate under the rules in the section comment above."""
    formula = _cert_formula(task, twin_body, w)
    if formula is None:
        return None
    global _SUFFIX_INT
    saved = _SUFFIX_INT
    _SUFFIX_INT = True
    try:
        body = expr(formula)
    finally:
        _SUFFIX_INT = saved
    return (
        "\nverus!{\n\n"
        "// Ground refutation certificate for the measured twin witness.\n"
        "// The kernel evaluates it with no SMT fallback; verifiers/verus.py\n"
        "// mints REFUTED only if this one goal is accepted, and a file\n"
        "// carrying this name can never mint VERIFIED.\n"
        f"proof fn {CERT_NAME}()\n"
        "{\n"
        f"    assert({body}) by (compute_only);\n"
        "}\n\n"
        "} // verus!\n")


# `witness` is the twin's measured witness (harness.twin_cached). Twin call
# sites pass it; when it is present and ground-certificatable, the lowering
# appends the refutation certificate block (see the section above).
def lower(task: dict, body: list, witness: dict | None = None) -> str:
    global _SUFFIX_INT
    if task.get("t", 0) == 0:
        # v0 used to emit bare literals to keep its output byte-identical to
        # an earlier baseline. That is unsound as an emission rule: Verus
        # types a literal expression by inference, and an expression built
        # only from non-negative literals infers `nat`, which does not match
        # the `int` return. Measured 2026-09-04 on fz_v0if_141, where the
        # branch value `(3 * 1)` is rejected with E0308 expected int found
        # nat, while the metamorphic rewrite of the same value to
        # `((3 - 0) * 1)` introduces a subtraction, infers int, and verifies.
        # A lowering whose well-formedness depends on whether a constant
        # folds to something non-negative is not a lowering. v0 now suffixes
        # exactly as v1 does.
        _SUFFIX_INT = True
        try:
            src = lower_v0(task, body, witness=witness)
        finally:
            _SUFFIX_INT = False
    else:
        _SUFFIX_INT = True
        try:
            src = _V1(task).emit(body)
        finally:
            _SUFFIX_INT = False
    if witness is not None:
        cert = _certificate(task, body, witness)
        if cert:
            src += cert
    return src


if __name__ == "__main__":
    raise SystemExit(harness.run_all(sys.argv[1:], lower, verus_backend, "rs"))
