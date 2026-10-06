#!/usr/bin/env python3
"""lower_dafny.py: lower t tasks (v0 and v1) to Dafny, verify both the task
and its broken twin, and refuse anything that does not flip.

    python3 t/lower_dafny.py            # all of t/tasks/*.json
    python3 t/lower_dafny.py abs        # one task

The verdict is Dafny's, never this file's. Exit codes are the measured ones
from dafny_verify.py (dafny 4.11.0): 0 verified, 2 parse/resolution, 4
verification failed. A task COUNTS only when the real cell is VERIFIED and
the twin cell is REFUTED, and since 2026-09-02 REFUTED is no longer read off
exit 4 (could-not-prove, not a countermodel): it is minted only when dafny
itself accepts the refutation certificate this file appends to the twin
(see the certificate section below and verifiers/dafny.py). Everything else
is refused with the reason printed: twin-verifies means the spec is vacuous;
real-fails means the task is wrong; twin-malformed means the mutation broke
syntax rather than meaning and the witness would be about parsing, not
proof; twin-unproved means the kernel could neither prove the twin nor
accept the certificate, which is not knowledge either way.

2026-09-14 (ROADMAP 16.2, dafny-closure): `expr`'s `exists` branch special-
cases the one shape the lifter's `in` rewrite always produces (`_seq_
membership`, defined just above `expr`): a bare `exists k :: 0<=k<len(seq)
&& seq[k]==elem` now lowers to Dafny's own `elem in seq`, which carries a
built-in axiom a generic quantifier does not get for free. Measured on
dafny-synthesis 412/426/436/554/629 (each a closure predicate -- isEven,
isOdd, isNegative -- called in executable position inside a loop that
appends to its accumulator): the generic exists lowering failed loop-
invariant MAINTENANCE ("this invariant could not be proved to be
maintained by the loop") because dafny cannot automatically re-derive,
across `evenList := evenList + [x]`, that an old membership witness index
still works after the length changes; native `in` does. The closure
predicate itself was a correlate, not the cause: the same failure
reproduces with the predicate call replaced by its raw arithmetic body.
`dafny-synthesis_task_id_433__isGreater` and `_567__isSorted` read
"vacuous" on the real (Outcome.VACUOUS, dafny's own `--warn-contradictory-
assumptions` firing "proved using contradictory assumptions: index in
range") both before and after this fix, and the SAME warning fires on
DafnyBench's own untouched hand-written source for both tasks -- this is
not a lowering defect, named and left open (see verifiers/dafny.py and
t/test_lower_dafny_closure.py).

v1 mapping, gate by gate (SPEC.md):
  quantifiers: t's bounded forall/exists over [lo,hi) lower to Dafny's native
    bounded quantifiers; `seq` is Dafny's seq<int>, `len` is |s|, `at` is s[i].
    Dafny's well-formedness checking discharges t's definedness obligations
    natively: `at` outside [0,len) is a verification error unless guarded, and
    &&/||/==>/ite/quantifier bodies are checked left-to-right / under-guard,
    exactly t's rules. Nothing is totalized.
  loops: t `while` lowers to Dafny while with invariant/decreases clauses;
    Dafny checks decreases >= 0 and strictly decreasing, t's obligation.
  recursion: spec_funs lower to Dafny `function` (pure, with decreases);
    a task self-call lowers to a call of the lowered METHOD, hoisted out of
    expression position into `var tmp := M(...);` statements (SPEC.md allows
    the hoist; evaluation is call-by-value left-to-right). Hoisting is refused
    (NotImplementedError, an ABSTAIN) when a self-call sits under a lazily
    evaluated position (quantifier body, ite branch, non-first and/or/implies
    argument) because unconditional evaluation there could smuggle in a
    precondition the taken path never owed. No task should put one there
    (SPEC: self-calls appear only where evaluation order is unobservable).
  div/mod (added 2026-09-08): measured on dafny 4.11.0, `-7 / 2 == -4`,
    `-7 % 2 == 1`, `7 / -2 == -3`, `7 % -2 == 1`, `-7 / -2 == 4` and
    `-7 % -2 == 1` all verify, so Dafny's native `/` and `%` are the same
    Euclidean operators SPEC.md's "Division and modulo (v1)" states, and t's
    `div`/`mod` lower straight to them, same precedence as `*`, same
    parenthesization discipline as every other binop here. The divisor-
    nonzero obligation is discharged the same way `at`'s range check is:
    Dafny's own well-formedness checking rejects `/` or `%` by a possibly-
    zero divisor unless guarded, nothing here totalizes it.
  early exit (added 2026-09-09, SPEC.md "Early exit (v1)"): `return Expr;`
    lowers to `r := Expr; return;` (Dafny takes no expression on `return`
    once the method has an out-parameter). Dafny checks the method's
    `ensures` at every `return`, and does not ask for the loop's invariant
    there, which is exactly the rule SPEC.md states, so `stmts` needs
    nothing beyond the two-line form: no separate exit-path bookkeeping,
    no invariant re-check to suppress. Nothing else in this file walks
    statement kinds exhaustively (`_twin_loop` and interp.py's `exit_env`
    helper only look for `while`/`if`), so `return` needed no other case.
  sequences as values (added 2026-09-09, SPEC.md "Sequences as values
    (v1)"): the kernel's native sequence type is `seq<int>` (already in
    TYPES from Gate 1's `len`/`at`), and it already has a functional update
    and a constructor: `s[i := v]` denotes the sequence equal to `s` except
    at `i`, and `seq(n, f)` denotes the length-`n` sequence built from a
    function `int -> int`, so `seq(n, v)` (v1's `fill`, a CONSTANT sequence)
    lowers to `seq(n, _ => v)`, an unused-argument lambda, measured to
    verify on 4.11.0. Both are DEFINED IFF the same bound `at` already
    owes (`update`: `0 <= i < |s|`; `fill`: `n >= 0`), and Dafny's own
    well-formedness checking discharges both natively and unconditionally,
    exactly like `at`'s and `div`/`mod`'s: measured on a probe file, an
    unguarded `s[i := v]` and `seq(n, _ => v)` each reject with "index out
    of range" / "sequence size might be negative" at exit 4, and guarded
    ones verify. Nothing here totalizes either op. `==`/`!=` needed no new
    case: Dafny's `seq<int>` equality is already extensional (measured:
    `[1,2,3] == [1,2,3]` and `[1,2,3] != [1,2,4]` both verify as lemmas),
    and BIN_OPS's `==`/`!=` already emit Dafny's own `==`/`!=`, so v1's
    "extensional equality" is the kernel's native equality, at no cost this
    file has to pay. The type mapping (return, local, out-parameter, loop
    state) needed no new code either: TYPES["seq"] = "seq<int>" already
    covered every declaration site (`var d: TYPES[d['type']] := ...`, the
    method's `returns (r: TYPES[...])`, params), because Gate 1 already
    made `seq` a declarable type for `len`/`at`'s sake.
      What DID need work is the twin path. swap's canonical twin (no `if`,
    so COLLAPSE-IF/NEGATE-COND/COMPARE-FLIP/BOUNDARY-SWAP all abstain; the
    first OFF-BY-ONE candidate is the `at(s, i)` in `tmp := s[i]`, mutated
    to `s[i+1]`) is `_kind == "undefined"`: on the smallest admissible input
    (s=[0], i=0, j=0) the real body has a value ([0]) and the twin's does
    not (`s[1]` is out of range), which is a witness kind the certificate
    protocol never covered before (the section comment above `_certificate`
    said so explicitly: "preservation, undefined: not emitted; such a cell
    honestly reads unproved"), because nothing upstream records WHICH node
    failed, only interp.Undef's message string. Measured first, on swap
    unchanged: REFUSED, "real verified, off-by-one twin unproved", exit 4
    with no certificate to accept (the same could-not-prove/definitely-
    false confusion "EXIT 4 IS NOT A REFUTATION" already names, just now
    reachable through a seq index instead of a loop). `_ev_undef` and
    `_exec_undef` close it: a small mirror of interp.ev/exec_body that
    replays the twin's straight-line statements under the witness's
    concrete values and, at the exact `at`/`update`/`fill`/`div`/`mod` node
    that goes out of domain, raises `_DefViol` carrying the failing bound
    as a ground guard (built from values already in hand, so no unrolling
    is needed, unlike the quantifier case). Its negation is the certified
    fact, composed with the substituted `requires` exactly like the value
    and exit kinds. Measured after: swap COUNTS (witness s=[0], i=0, j=0 ->
    real [0], twin "at index 1 outside [0,1)"), and the certificate lemma
    Dafny accepts is `!((0 <= 1) && (1 < 1))`, a ground fact with no
    seq-typed operand at all (the guard is stated in terms of the index and
    the CONCRETE length, not the sequence value), so the existing seq-
    naming machinery (`_name_seqs`, `used`, `_seq_lit`) was exercised only
    by `requires`' own `len(s)`, not by anything this addition introduced.
    Scope is deliberately narrow: a `while` reached before the violation,
    or a quantifier or spec_fun call in the replay, aborts with ValueError
    (caught by `_certificate`'s existing broad except) rather than guessing,
    so a loop-carried undefined witness still honestly reads unproved,
    unchanged from before.
      reverse's canonical twin is ordinary INVARIANT-DROP (`_kind ==
    "exit"`, the same path all the loop tasks already use), needing no new
    machinery: the exit witness (s=[], i=0, r=[0]) substitutes a seq
    literal for `r`, and the existing `_tlit`/`_name_seqs`/`_seq_lit` chain
    (already built for `at`/`len` witnesses) named and let-bound it exactly
    as it does every other seq witness, with `fill`'s own definedness
    (`seq(len(s), 0)`, `len(s) >= 0` always true) needing no certificate
    attention since the real program's `fill` call is never the twin's
    broken statement here.
      Regression, all 15 pre-existing tasks: lowered output (`out/*.dfy`,
    real and twin, `lower()`'s return value byte for byte) is IDENTICAL
    before and after this change (diffed against a HEAD worktree), and all
    15 read `verified / refuted` through the real dafny kernel, unchanged
    from AGREEMENT.md's dafny column. All 17 tasks in `tasks/*.json` COUNT.

  sequence literals, concatenation, slices (added 2026-09-09, SPEC.md
    "Sequences: literals, concatenation, slices (v1)"): all three of the
    kernel's own forms, no totalizing needed. `{"op": "seq", "args":
    [e1, ..., en]}` is Dafny's own sequence display, `[e1, ..., en]`, `[]`
    for n == 0. `{"op": "+", "args": [s, t]}` with both operands seqs needed
    NO new codegen at all: BIN_OPS already maps t's `+` straight to Dafny's
    `+`, and Dafny's `+` is itself overloaded over `seq<int>` as
    concatenation exactly as t's is, measured on a probe (`s + [9]` next to
    plain int `+` in the same method, one verified obligation, 0 errors) as
    the SPEC.md text predicts ("one operator name, polymorphic ... exactly
    as `==`"): the kernel's own overload resolution IS the type dispatch the
    task brief asked this file to make, so there is nothing to write.
    `{"op": "slice", "args": [s, a, b]}` is Dafny's own `s[a..b]`. The
    slice's definedness obligation, `0 <= a <= b <= len(s)`, is discharged
    the same way `at`'s and `update`'s are: Dafny's own well-formedness
    checking, nothing here totalizes it. Measured on a probe: `s[1..5]`
    with no bound on `|s|` rejects at exit 4 with two errors ("lower bound
    out of range", "upper bound below lower bound or above length of
    sequence") on the same line; the identical call guarded by
    `requires |s| >= 5` verifies clean. Two committed tasks carry the
    construct: `tail` (loop-free, `r := s[1..len(s)]`) and `filter_pos` (a
    loop appending `r := r + [s[i]]`).
      What DID need work, same as the update/fill wave: the twin path for a
    witness `_kind == "undefined"` reached through a slice. `tail`'s
    canonical twin is OFF-BY-ONE on the slice's lower bound (`s[1..len(s)]`
    -> `s[(1+1)..len(s)]`); on the smallest admissible input (s=[0]) the
    real body has a value (`[]`) and the twin's does not (`[2..1]` fails
    `a <= b`), the same shape swap's `at`-index twin had. `_ev_undef` and
    `_DefViol` gained two cases: `"seq"` is trivial (every element already
    evaluated by the generic arg loop above it, so `list(a)` is the value,
    always defined once its elements are, matching interp.ev's own `"seq"`
    case); `"slice"` builds a THREE-part ground guard, `0 <= a`, `a <= b`,
    `b <= len(s)`, conjoined, where `at`'s and `update`'s guard is two-part
    (a single index bound) because a slice's obligation is a range, not a
    point. `"+"` needed nothing in `_ev_undef` either: it already read
    `a[0] + a[1]`, and Python's `+` on two lists concatenates exactly as
    interp.ev's own `"+"` case does, so the mirror was already correct for
    the seq case without anyone having written it for that purpose.
    `_ev` (the general evaluator the "value"/"exit"-kind certificates
    unroll and prune through) got NO new cases: neither task's `requires`,
    `ensures`, nor surviving `invariants` mention `seq`, `+`, or `slice`
    directly, only `at`/`len`/comparisons, so nothing in the certificate
    formula for either task's witness ever reaches those ops. A future task
    whose spec itself states a seq literal, concatenation, or slice (not
    just its body) would need that gap closed then, not before; nothing
    here claims it is closed now.
      Measured, own column, on `tasks/tail.json` and `tasks/filter_pos.json`
    (`harness.run_task`, this file's `lower`, the real dafny kernel):
    `tail` COUNTS, real VERIFIED, off-by-one twin REFUTED via the new
    undefined-kind slice certificate (witness s=[0] -> real [], twin slice
    bounds [2..1] outside 0 <= a <= b <= 1). `filter_pos` COUNTS, real
    VERIFIED, invariant-drop twin REFUTED via the unchanged exit-kind
    certificate (witness exit at s=[], i=1, r=[1]): the loop's own `seq`
    literal (`r := []`) and append (`r := r + [s[i]]`) needed no new
    certificate machinery because the twin here breaks on the dropped
    invariant, not on a seq op, and the existing `_name_seqs`/`_tlit`/
    `_seq_lit` chain already names seq witness values regardless of which
    op produced them. `swap` and `reverse` (no new ops in either) are
    UNCHANGED: `harness.run_task` still COUNTS both, and their lowered
    sources, real and twin, are byte-identical (`cmp`) to the committed
    `out/swap.dfy`, `out/swap_twin.dfy`, `out/reverse.dfy`,
    `out/reverse_twin.dfy`.

  pairs (added 2026-09-10, SPEC.md "Pairs (v1)"): Dafny's own product, no
    totalizing needed, same as every other v1 wave. A pair type
    {"pair": [T1, T2]} is Dafny's built-in tuple type (T1, T2), written
    exactly that way for a param, a `returns (r: ...)`, or a `var` local
    (`dafny_type()`, a small wrapper around TYPES that recurses one level
    for a pair and replaces every direct TYPES[p['type']]/TYPES[d['type']]
    lookup at the three declaration sites; spec_fun params/result are left
    on bare TYPES[...], since SPEC.md never allows a pair there). The `pair`
    op is Dafny's own tuple display (a, b); `fst`/`snd` are `.0`/`.1`.
    `==`/`!=` needed no new case at all: Dafny's tuple equality is already
    componentwise/structural (measured: a lemma stating (1, 2) == (1, 2)
    and (1, 2) != (1, 3) both verify), and BIN_OPS's `==`/`!=` already emit
    Dafny's own operator, exactly the seqops precedent ("the kernel's own
    overload resolution IS the type dispatch"). The loop frame rule needed
    no code either: a pair local or return is havocked by name like any
    other variable, and nothing in `stmts` singles out a type when deciding
    what a loop threads.
      What DID need work is the certificate path, for a reason with no seq
    analogue: interp._j renders a Pair as a plain 2-list ([a, b]), which for
    a pair of two ints is byte-for-byte the same shape _j gives a length-2
    seq of ints. `_tlit`, which had built every witness literal by guessing
    its t type from the Python value's shape, could not tell divmod_pair's
    twin value [0, 1] (a pair) from a 2-element seq, and would have named it
    seq<int> in the emitted lemma: a silently WRONG certificate, not a
    refusal (the ambiguity the task brief named explicitly). Fixed by making
    `_tlit(v, ty)` type-directed: given a pair type it recurses
    component-wise into {"op": "pair", "args": [...]}; every other type is
    still inferred from shape, unchanged, so every existing call site
    (`_gint`, `_unroll`'s bound literals, `_ev_undef`'s ground guards) that
    never passes `ty` keeps its old behavior exactly. The type has to come
    from somewhere, though, and the first attempt (a params-only map)
    REGRESSED `reverse` and `filter_pos`: both narrowly lost their working
    invariant-drop certificate (`harness.run_task` read UNPROVED where it
    had read REFUTED, caught immediately by this file's own
    byte-identity/COUNT check against out/) because an "exit"-kind witness
    ranges over "everything in scope at the loop, plus the return"
    (harness.py's `_invariant_candidates`), not params, and both tasks'
    loop-carried `r` IS the return, a seq the params-only map could not see
    was a seq. `_scope_types(task)` replaces it: params, the return, and
    every body local, so every name a witness of either kind can carry has
    a known type. The same ambiguity, and the same fix, applies to
    `_certificate`'s seq-naming step (`seq_names`): gated on
    `scope_types.get(n) == "seq"` now, not `isinstance(v, list)`, so a
    pair-typed name whose value happens to look like a seq is never
    let-bound as one. `_ev`, which evaluates the ground certificate formula
    itself, gained `pair`/`fst`/`snd` cases (interp.Pair(vs[0], vs[1]),
    vs[0].a, vs[0].b); `_unroll` and `_name_seqs` needed nothing, their
    generic "op"-recursion already walks into a pair's args.
      Two named refusals, neither exercised by either committed task, both
    left as honest gaps rather than guessed at: (1) an "undefined"-kind
    witness reached through a `pair`/`fst`/`snd` node would refuse the
    certificate (`_ev_undef`/`_exec_undef` have no case for them, so the
    replay raises ValueError, caught by `_certificate`'s existing broad
    except); both committed twins are "value"-kind, so this never fires
    here, and closing it is the same shape of work `_DefViol` already did
    for `at`/`update`/`fill`/`div`/`mod`, not attempted now. (2) a pair with
    a SEQ component appearing in a witness value would also refuse: only a
    top-level seq-typed name gets let-bound (`seq_names`/`used`), a seq
    nested inside a pair's component has no name to bind to and
    `_name_seqs` raises KeyError on it. SPEC.md's own text anticipates
    exactly this ("dafny ... or a named refusal where ... a seq component
    costs the certificate"); neither divmod_pair (int, int) nor min_max
    (int, int; the seq is the plain param `s`, not a pair component) reaches
    it, so it is recorded here, not fixed blind.
      Measured, own column, on tasks/divmod_pair.json and tasks/min_max.json
    (`harness.run_task`, this file's `lower`, the real dafny kernel,
    flake-checked twice): `divmod_pair` COUNTS, real VERIFIED, wrong-var
    twin REFUTED, witness x=1, y=1 -> real [1, 0], twin [0, 1] (the
    certificate states !(((0*1)+1==1) && (0<=1) && (1<1)), ground and
    dafny-accepted). `min_max` COUNTS, real VERIFIED, collapse-if twin
    REFUTED, witness s=[0, 1] -> real [0, 1], twin [1, 1] (the twin's first
    `if` collapsed makes `lo := s[i]` unconditional; the accepted
    certificate states the twin's r.0 = 1 violates r.0 <= s[0] = 1 <= 0 at
    the let-bound s := [0, 1]); harness never reached invariant-drop for
    either task (COLLAPSE-IF and WRONG-VAR both had witnesses first in
    pre-order). Regression, all 15 pre-existing tasks: `abs`, `swap`,
    `reverse`, `tail`, `filter_pos` were re-lowered and re-verified as a
    directly measured sample (the other ten were not re-run, having no path
    through any changed code: no pair type, no witness naming a return or a
    body local) and all five still COUNT, unchanged from AGREEMENT.md's
    dafny column, with lowered output (`lower()`'s return value, real and
    twin) byte-identical (`cmp`) to the committed `out/abs.dfy`,
    `out/abs_twin.dfy`, `out/swap.dfy`, `out/swap_twin.dfy`,
    `out/reverse.dfy`, `out/reverse_twin.dfy`, `out/tail.dfy`,
    `out/tail_twin.dfy`, `out/filter_pos.dfy`, `out/filter_pos_twin.dfy`.

  nested sequences (added 2026-09-10, SPEC.md "Nested sequences (v1)"):
    Dafny's own `seq<seq<int>>`, no new Expr forms, same as SPEC.md states
    and the same shape as the seqops wave: `{"seq": "seq"}` is `seq<{TYPES
    ["seq"]}>` (`dafny_type()`, one more branch alongside the pair one,
    gated on which key the type dict carries rather than unpacking
    `t["pair"]` unconditionally); the literal, `len`, `at`, `+`, `slice`,
    `update`, `fill` and `==`/`!=` needed NOT ONE new codegen case, because
    `expr()` already lowers every one of them generically off Dafny's own
    overload resolution (measured directly: `at(at(m, i), j)` was already
    lowering to `m[i][j]`, the chained postfix SPEC.md asks for, before
    this wave touched the file, since `at`'s codegen is `f"{args[0]}
    [{args[1]}]"` and a nested `at` is just another `args[0]`). `dafny_type
    ()` is the only change the MAIN lowering (params, returns, `var`
    locals) needed.
      What DID need work, same shape as the pairs wave one level down: the
    certificate path, for the SAME reason pairs needed `_tlit(v, ty)`
    type-directed rather than shape-guessed. An empty nested seq (zero
    rows) and an empty flat seq are both the Python value `[]`; swap_rows's
    own witness carries `m = [[]]` (ONE empty row, not zero rows), so `_tlit`
    gained a `ty`-directed branch, gated on the type dict's key (`"pair"`
    vs the nested `"seq"`) rather than assuming pair, tagging a nested
    value `_seq2` (a tuple of tuples) rather than reusing `_seq` (a flat
    tuple), so a same-shaped flat and nested empty seq are never conflated
    by `_name_seqs`. `_name_seqs` and the naming step in `_certificate`
    (`seq_names`) each gained a SECOND table (`nseq_names`, keyed by
    tuple-of-tuples) rather than sharing one, for the identical reason: one
    dict keyed only by value would let a flat witness's name answer for a
    nested literal of the same shape. `_seq_lit` gained a sibling,
    `_nseq_lit`, one row-print per element (`_seq_lit` again) rather than
    `str(x)` on each element directly. Measured, and NOT assumed: `_ev`'s
    operator dispatch (`at`/`update`/`fill`/`slice`/`+`/`==`), `_ev_undef`/
    `_DefViol`'s mirror of it, and `_scope_types` needed NO changes at all,
    the first two because Python's own list operations are already
    agnostic to whether an element is an int or a row (an out-of-range
    `at`/`update` on `m` raises the same two-part index guard regardless of
    what `m`'s elements are, and a CHAINED `at(at(m,i),j)` failing on the
    inner index already builds its guard from the ROW's own length, no
    seq-typed literal in the guard at all, so an inner-row definedness
    violation was never a gap to begin with), the third because it already
    stored each name's raw JSON type dict verbatim, seq or otherwise,
    unlike `_scope_types` itself, which the pairs wave had to ADD.
      One real bug surfaced, not introduced by nesting itself but only
    reachable through it: `subst()`'s leaf check, `"int" in e or "bool" in
    e or "_seq" in e: return e`, had no case for the new `_seq2` tag, so
    the first substitution of a nested-seq witness into `loop["cond"]`/
    `invariants` (row_max_len's exit-kind path, which calls `subst`
    directly, unlike the value-kind path this file's `_unroll` also
    reaches) fell through to `subst`'s final line, `{"op": e["op"], ...}`,
    and raised `KeyError: 'op'` on a tag dict with no `"op"` key. Measured
    before the fix: row_max_len read REFUSED, "real verified, invariant-
    drop twin unproved" (the KeyError caught by `_certificate`'s broad
    except, same as any other refusal). Fixed by adding `_seq2` to the
    same leaf line; `_unroll`'s own tree-walk needed nothing, its default
    (`return e` when no `forall`/`exists`/`ite`/`call`/`op` key is present)
    already passed an unrecognized tag through unchanged, which is how the
    existing `_seq` tag survived it too. swap_rows's own certificate never
    reached `subst` with a nested tag before `_unroll` (its witness is
    "undefined"-kind, substituted once via `m` alone, no invariant list),
    so the bug was invisible until the second task exercised the exit-kind
    path, exactly the order (swap_rows first, row_max_len second) this
    file measured them in, not designed to expose it.
      Two named refusals, neither exercised by either committed task, both
    verified directly rather than guessed: (1) a pair with a nested-seq
    component, or a nested seq three deep, both illegal in SPEC.md's own
    grammar (a pair's T1/T2 are `"int"`/`"bool"`/`"seq"` only; a nested
    seq's row is always the elementary `"seq"`), fail immediately and
    loudly in `dafny_type()`: `TYPES[t]` on a dict key raises `TypeError:
    unhashable type: 'dict'` at the type-declaration site, before any
    certificate work, measured directly on both shapes. (2) a spec_fun
    called with a nested-seq argument would cost the certificate: `_key()`
    tags every list `("seq", tuple(v))` regardless of depth, and `tuple(v)`
    over a nested value is a tuple of LISTS, unhashable, so `_ev`'s "call"
    case raises `TypeError` building the `facts` dict key, caught by
    `_certificate`'s existing broad except, a refusal, not a crash and not
    a wrong lowering; measured directly (`_key([[1],[2]])` composed into a
    dict key raises `TypeError: unhashable type: 'list'`). Neither
    committed task has a spec_fun, so this path is not reached by either.
      Measured, own column, on tasks/swap_rows.json and
    tasks/row_max_len.json (`harness.run_task`, this file's `lower`, the
    real dafny kernel, into `out/agent-dafny-nested/`): `swap_rows` COUNTS,
    real VERIFIED, off-by-one twin REFUTED, witness m=[[]], i=0, j=0 (real
    r=[[]], the twin's second `update` shifted to index `j+1=1`, outside
    `[0,1)` for `|m|=1`, "the shifted index running off the single row"
    SPEC.md names); the accepted certificate states `!((0<=1)&&(1<1))`,
    ground, no seq-typed operand at all, the same shape swap's own
    off-by-one certificate has one level down. `row_max_len` COUNTS, real
    VERIFIED, invariant-drop twin REFUTED, witness exit at m=[[], [0]],
    i=2, r=0 (the dropped upper-bound invariant lets the loop exit at i=2
    with r stuck at 0, violating `|m[1]| <= r`); the accepted certificate
    is the exit-entailment conjunction over the let-bound `m: seq<seq<int>>
    := [[], [0]];`, the same `_twin_loop`/`interp.exit_env` path
    filter_pos's own invariant-drop certificate already uses, needing no
    new machinery of its own once `_tlit`/`_name_seqs`/`subst` could carry
    a nested value. Regression, six pre-existing tasks sampled directly
    (`abs`, `swap`, `tail`, `filter_pos`, `divmod_pair`, `min_max`, one
    from each earlier wave this file has a certificate path for): all six
    still COUNT, and their lowered output, real and twin, is byte-
    identical (`cmp`) to the committed `out/abs.dfy`, `out/abs_twin.dfy`,
    `out/swap.dfy`, `out/swap_twin.dfy`, `out/tail.dfy`,
    `out/tail_twin.dfy`, `out/filter_pos.dfy`, `out/filter_pos_twin.dfy`,
    `out/divmod_pair.dfy`, `out/divmod_pair_twin.dfy`, `out/min_max.dfy`,
    `out/min_max_twin.dfy`.

  nested sequences, fuzz residual (added 2026-09-10): the v1nested fuzz
    family (18 generated tasks, scratchpad fuzz-nested/corpus.json) read
    dafny verified/refuted on 12 of 18. Two causes accounted for all four
    verified/unproved misses, neither task-specific, both in the
    certificate path only, never in the main lowering:
      (1) fz_v1nested_069 (build_matrix, compare-flip) and
    fz_v1nested_150 (row_sum, compare-flip) are "undefined"-kind witnesses
    whose definedness violation (an out-of-range row/element read the
    compare-flip twin's shifted loop bound reaches) sits INSIDE the twin's
    own `while`, and `_exec_undef`'s old scope refused any witness that
    reached a `while` at all (see the section comment above `_DefViol`,
    now updated). The witness is fully ground, so a `while` is exactly as
    replayable as `interp.exec_body`'s own: fixed by having `_exec_undef`
    step the loop itself (`_ev_undef` on the condition, `_exec_undef` on
    the body, repeat), capped at `interp.MAX_LOOP` the same way
    `interp.exec_body` caps it (`interp.Budget`, an existing member of
    `_certificate`'s catch), and by having both `_exec_undef`'s `if` and
    its new `while` propagate a `return`'s early exit (the bool it now
    returns, mirroring `interp.exec_body`'s own flag) so a violation past
    an early return is never replayed. (2) fz_v1nested_078/fz_v1nested_606
    (nested_lit, off-by-one) and fz_v1nested_115 (concat_nested, wrong-var)
    are "value"-kind witnesses whose RETURN type is seq or nested-seq: the
    twin's own computed return value is substituted straight into the
    certificate formula as a `_seq`/`_seq2` literal, but `_name_seqs`
    requires every such literal to already own a name in `seq_names`/
    `nseq_names`, and those tables were built only from the witness's
    PARAM values (`interp.Reference.witness` never carries the return
    itself for a "value"-kind witness, `_scope_types`'s own docstring
    says so), so the return's literal had no name to bind to and
    `_name_seqs` raised KeyError, a refusal rather than a wrong lowering.
    Fixed by also naming the substituted return value, under the return's
    own name, whenever that name is not already a witness name (true of
    every "value"-kind witness; false of every "exit"-kind one, since
    `_invariant_candidates` always puts the return in scope there, so this
    leaves the exit-kind path, and every task using it, untouched and
    unmeasured-for-regression by construction, not by luck).
      fz_v1nested_150's REAL cell stayed unproved/unproved, not a lowering
    bug: dafny's own error is `index out of range` inside the generated
    spec_fun's body, `rowsum(row, k) := if k <= 0 then 0 else rowsum(row,
    k-1) + row[k-1]`, which is genuinely partial (well-defined only for
    `0 <= k <= |row|`) where a Dafny `function` must be total over its
    whole declared domain (unconstrained `k: int`); for `k > |row|` the
    recursion walks `row[k-1]` out of bounds on the way down to the base
    case. This is a fuzz-corpus generation defect in `f_v1nested`'s
    row_sum shape (fuzz_lower.py, a file this task does not own), not
    something `lower_dafny.py`'s emitter can fix without inventing a
    bound this task's JSON never states; refused by name, left as is.
    fz_p_nest_empty stayed no-twin/no-twin, expected by the corpus's own
    `_why`: its body (`r := []`) has no `if`, comparison, second variable
    or int literal for any ladder rung to perturb, so no twin exists to
    miss.
      Measured, own column, after the fix (fuzz_lower.py --seed 1 --n 400
    --flake 3 --only dafny, on exactly these six tasks): fz_v1nested_069,
    fz_v1nested_078, fz_v1nested_115 and fz_v1nested_606 now COUNT,
    verified/refuted (previously verified/unproved); fz_v1nested_150 is
    unchanged, unproved/unproved; fz_p_nest_empty is unchanged, no-twin/
    no-twin. Regression, all 23 committed tasks (not a sample this time):
    every one re-lowered via `lower(task, task["body"])` for the real body
    and `lower(task, twin_body, witness=w)` (`harness.twin_cached`'s twin
    and witness) for the twin is byte-identical (Python `==`, not `cmp`)
    to the committed `out/<name>.dfy` and `out/<name>_twin.dfy`.

THE STRING LIBRARY (added 2026-09-11, SPEC.md "The string library (v1)"):
  the 17 members (split x2 arities, join, tostr, count, find, strip,
  lstrip, rstrip, replace, lower, upper, isdigit, isalpha, isupper,
  islower, startswith, endswith) as the kernel's own recursive Dafny
  functions in `STRLIB_PRELUDE` (a module-level string near `dafny_type`,
  emitted only when `_uses_strlib` finds an `{"op": M, ...}` node for a
  member name M -- an op-value AST walk, not a raw string search over the
  JSON: count_matches.json names its own int-counting spec_fun "count"
  too, and `_collect_names`-style string matching misfires on it, pulling
  the prelude into a task gate (c) needs unchanged). `split`/`count` are
  the two ops needing argument-shape dispatch (`_strlib_lower`, beside
  `dafny_type`): `split(s)`/`split(s,c)` on arity, `count` on whether its
  first argument is syntactically `slice(X, 0, HI)` -- see below. Every
  other member is a flat name -> Dafny-function-name table (`STRLIB_OPS`).
  Encoding, each a straight port of interp.py's own `_str_*` semantics
  into a Dafny `function` over `seq<int>` (`seq<seq<int>>` for split's
  result and join's rows): SplitWs/TokLen skip whitespace runs (`IsWs`,
  the ten SPEC.md code points) then take maximal non-whitespace tokens;
  SplitSep keeps every row, prepending onto the recursive tail's own
  first row; Join concatenates with the separator between rows, empty on
  no rows, no separator on one; Count/FindFrom scan the front
  non-overlapping/leftmost, `|t|==0` totalized per SPEC.md
  (`len(s)+1`/`0`); Strip/LStrip/RStrip peel from the front/back/both;
  Replace inserts `u` before-and-after every code point when `t==[]`,
  else substitutes every non-overlapping front match; Lower/Upper map the
  two ASCII letter ranges, `IsUpperLetter`/`IsLowerLetter` the shared
  tables `LowerC`/`UpperC`/`IsDigitC`/case-predicates build on; the four
  predicates follow interp.py's exact empty/mixed rules (`IsDigit`/
  `IsAlpha`: non-empty and every code point of the class; `IsUpperStr`/
  `IsLowerStr`: `HasLetter` (some letter) and no letter of the OTHER
  case, so a non-letter never counts against either); ToStr/DigitsOf
  build decimal digits from the low end up (`n / 10`, `n % 10`), signing
  with a leading 45 for `n < 0`; StartsWith/EndsWith compare a boundary
  slice.

  THE LEMMAS. SPEC.md names three: the split length law, the
  join-of-split law, count against a loop. All three are stated as
  function-level `ensures` (never a separate lemma needing a call this
  file cannot insert into an unedited task body): a Dafny `function`'s
  own postconditions are proved once, at its declaration, and then
  assumed for free at every call site, so the design throughout is
  finding a postcondition whose OWN induction aligns with the function's
  recursion (front-peel matching front-peel) closely enough for Dafny's
  automatic per-function induction to close it, reaching for a
  hand-written `lemma` only where measurement showed the automatic path
  did not converge, and then reaching it FROM INSIDE the function's own
  body (Dafny functions may sequence ghost `assert P by { lemma(...); }`
  statements before their final expression, which still counts as
  "automatic": the fact is proved once, at the declaration, never at a
  task's own call site):
    - split length law and join-of-split law: both live on SplitSep
      itself (`ensures |SplitSep(s,c)| == Count(s,[c]) + 1` and
      `ensures Join(SplitSep(s,c),[c]) == s`), and both verify with NO
      hand-written lemma: SplitSep peels `s[0]`/recurses on `s[1..]`, and
      so does the induction each postcondition needs, so Dafny's default
      per-function induction closes both directly (measured: dropping
      either `ensures` and re-adding it alone still verifies stand-alone,
      so neither is riding on the other's proof).
    - count against a loop: count_vowels.json's invariant reads
      `count(slice(s,0,i),[c])` -- a Dafny slice `s[0..i]` fed straight to
      the general `Count`, which recurses front-to-back, but the loop's
      OWN induction needs a back-to-front, prefix-GROWING step
      (`Count(s[0..i+1],[c])` from `Count(s[0..i],[c])`), and the two
      directions do not align: attaching that step directly to `Count`
      as a function `ensures` (both as `Count`'s own postcondition and
      on a dedicated `CountChar1` helper) TIMED OUT at 30s twice, measured
      directly (`strlib_test3.dfy`/`strlib_test4.dfy` in this wave's
      scratch, not committed). Fixed with CountCharPrefix(s, n, c), a
      SEPARATE prefix-by-INDEX accumulator (`decreases` `n` itself, no
      slicing in its own body at all) whose postcondition
      (`CountCharPrefix(s,n,c) == Count(s[0..n],[c])`, guarded
      `0 <= n <= |s|`) is proved via one embedded
      `assert ... by { CountAppend1(s[0..n-1], s[n-1], c); }`, where
      CountAppend1 is the one hand-written lemma this wave needed (an
      append-one-char step for `Count`, proved by ordinary induction on
      `s`, front-peeling exactly like `Count` itself: MEASURED to verify
      in under a second once its recursive calls mirror `Count`'s own).
      `_strlib_lower`'s `count` dispatch recognizes exactly the
      `count(slice(s,0,i), [c])` shape (a single-code-point pattern,
      `_is_singleton_seq`) and rewrites it to `CountCharPrefix(s, i, c)`;
      every OTHER `count(s, t)` shape, sliced or not, single-point or
      not, lowers to the general `Count(s, t)`, and a second
      CountCharPrefix postcondition
      (`n == |s| ==> CountCharPrefix(s,n,c) == Count(s,[c])`) connects
      the two automatically at a loop's exit, with no lemma call and no
      body edit anywhere.
      CountCharPrefix is deliberately TOTAL (clamped to 0 outside
      `[0,|s|]`, no `requires`), not merely for convenience: SPEC.md
      "Invariants are checked in order" (2026-09-09) means an invariant's
      own definedness may assume only EARLIER invariants in the task's
      list, and count_vowels.json states its value invariant BEFORE the
      bounds invariants (`0 <= i`, `i <= len(s)`) that would justify
      `CountCharPrefix`'s domain -- measured directly, a `requires
      0 <= n <= |s|` version of CountCharPrefix fails Dafny's own
      well-formedness check on exactly the FIRST invariant ("function
      precondition could not be proved", the bounds not yet in scope);
      a task body is never reordered to fix this, so the function was
      made total instead, which needs no reordering at all.

  A THIRD SITE NEEDED A NON-LEMMA FIX. word_count.json copies `s` via a
  full-length slice (`t2 := s[0..len(s)]`) before calling `split`, and
  Dafny's seq theory does not fold that slice to `s` on its own where the
  fact is actually needed: a stand-alone `lemma ... ensures s[0..|s|]==s
  {}` verifies trivially (it IS the Z3 goal), but using it via congruence
  to justify `SplitWs(t2) == SplitWs(s)` needs an explicit `assert t2 ==
  s;` in between (measured on a probe file, `wc_min2.dfy`), which is
  again a task-body edit this file does not make. `_full_self_slice`
  (beside `_strlib_lower`) folds `slice(X, 0, len(X))` to `X` at LOWERING
  time instead -- true for any seq, not a string-library fact, but this
  is the task that needed it: `t2 := s[0..len(s)]` now lowers straight to
  `t2 := s`, so `SplitWs(t2)` and `SplitWs(s)` are literally the same
  term and the congruence step is never needed.

  ADDITIONAL ENSURES, found by the fuzz family (below), not by the three
  committed tasks: `Count(s,t) >= 0`; `ToStr`'s `|ToStr(n)| >= 1` and its
  leading-45 sign fact; `Lower`/`Upper`'s `|Lower(s)| == |s|` (length
  preservation) and, guarded on `AllAlpha(s) && |s| > 0`, that the result
  is all-lower/all-upper (this one DOES need its own induction to align:
  `AllAlpha`/`HasLetter`/`NoLowerLetter` all peel `s[0]` the same way
  `Lower` does, so it closes with no hand-written lemma either);
  `LStrip`/`RStrip`/`Strip`'s `|result| <= |s|` and the empty-input case;
  and a `Replace`-`Count` interaction
  (`|t|==|u|==1 && t[0]!=u[0] ==> Count(Replace(s,t,u),u) ==
  Count(s,u) + Count(s,t)`, one non-lemma-count-of-a-replaced-string
  fact), proved with one more hand-written lemma, CountConcat1
  (`Count(x+y,[c]) == Count(x,[c]) + Count(y,[c])`, the same
  front-peeling style as CountAppend1), embedded the same way inside
  Replace's own two recursive branches.

  MEASURED. (a) the three committed tasks, `python3 lower_dafny.py
  word_count split_join count_vowels` (flake 3, harness's default): all
  three COUNT -- word_count (off-by-one twin REFUTED, witness `s=[]`,
  real 0, twin an out-of-range slice `[1..0]`), split_join (wrong-var
  twin REFUTED, witness `s=[32]`(one space)/`c=0`, real `[32]`, twin
  `[]`), count_vowels (invariant-drop twin REFUTED, witness exit at
  `s=[]`, `i=0`, `r=1`). (b) the family: `fuzz_lower.py --only dafny --n
  400 --seed 1 --flake 3 --jobs 8` (the `--tasks` name list this wave was
  given, `fuzz-strlib-names.txt`, matched only 2 of its 17 names against
  this exact corpus -- unwitnessed why, since `--n`/`--seed` alone should
  be deterministic against the CURRENT `fuzz_lower.py`, which this file
  does not own or edit; both matched tasks read as expected,
  fz_v1strlib_007 COUNTS and fz_v1strlib_031 is the known nonrefuting
  off-by-one below). Re-run WITHOUT `--tasks` for the family's real
  weight in this exact `--n 400 --seed 1` corpus: 17 v1strlib tasks, 15
  COUNT. The two that do not: fz_v1strlib_031 (`tostr_len`, real
  VERIFIED, twin genuinely nonrefuting by the corpus's OWN
  `_twin_op: "off-by-one+nonrefuting"`/`_twin_differs: null` labels --
  not a lowering gap, the SPEC.md-measured ~9.2% no-witness rate showing
  up here) and fz_v1strlib_094 (`find_case`, real UNPROVED -- see OPEN,
  below). Zero disagreements, zero vs-truth misses, on this run or the
  one before the ADDITIONAL ENSURES pass (which moved 8 shapes from
  real-unproved to COUNTS: count_one, count_two, case_map_lower,
  case_map_upper, strip_len_lstrip/rstrip/strip, replace_count). (c) the
  committed matrix: every task in `t/tasks/*.json` (26, all of them, not
  a sample) re-lowered via `lower(task, task["body"])` on both this file
  and the pre-wave `git show HEAD:t/lower_dafny.py`; the 23 that mention
  no member (an `_uses_strlib`-equivalent AST check, not a name search)
  are BYTE-IDENTICAL, Python `==`; the 3 that do (count_vowels,
  split_join, word_count) differ, as expected -- they did not exist
  before this wave. `t/AGREEMENT.md` (2026-09-10, pre-wave) lists only
  the 23; its dafny column is unchanged by construction, since the
  source feeding it is unchanged.

  OPEN, BY NAME: `find`'s full characterization (`find(s,t) == -1` iff no
  occurrence; otherwise the FIRST occurrence, no earlier one) is NOT a
  prelude `ensures` -- fz_v1strlib_094's shape (`r := idx+1` on a
  found index, `0` on `-1`, then asserting both a no-match-before and a
  found-here-first fact as a `forall`) needs it and reads real UNPROVED.
  Measured: `FindFrom`'s own value (`-1` or the least matching index) is
  never in question -- `find_case`'s OTHER two members (the twin still
  REFUTES) and every use of `find` elsewhere are unaffected -- what is
  missing is the EXISTENTIAL/no-earlier-occurrence characterization as a
  reusable fact. A hand-written lemma with explicit `forall k | ...
  ensures ...` proof blocks (this wave's scratch, `find_test3.dfy`) got
  partway (the "no match before" quantifier trips on the boundary case
  `k == i` inside the recursive step, losing the `s[i..i+|t|] != t` fact
  the enclosing `if`/`else` already established, once inside the
  `forall`'s own proof scope) and was not finished inside this wave's
  time budget; left as an honest residual rather than forced. `split(s,
  t)` on a multi-code-point separator, `format`, f-strings, `int(x,
  base)`, `splitlines`, the padding members, `title`/`capitalize`/
  `swapcase`, `partition`, `encode` stay OUT of v1 by SPEC.md's own name,
  unaffected by this wave.

Stdlib only, same reason as dataset_gate.py.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import interp                                       # noqa: E402
import names                                        # noqa: E402
from verifiers import Outcome, flake_check          # noqa: E402
from verifiers import dafny as dafny_backend        # noqa: E402

OUT = HERE / "out"

BIN_OPS = {"==": "==", "!=": "!=", "<": "<", "<=": "<=", ">": ">", ">=": ">=",
           "+": "+", "-": "-", "*": "*", "div": "/", "mod": "%",
           "implies": "==>"}

# The string library (v1) prelude (SPEC.md "The string library (v1)", 2026-09-11):
# each of the 17 members as the kernel's own recursive Dafny function over
# seq<int> (and seq<seq<int>> for split/join), plus the lemmas the three
# committed tasks' ensures need, stated as function-level `ensures` so Dafny
# applies them automatically at every call site (no task body is ever edited
# to insert a lemma call): SplitSep carries the split length law
# (`|SplitSep(s,c)| == Count(s,[c]) + 1`) and the join-of-split law
# (`Join(SplitSep(s,c),[c]) == s`) as its own postconditions, proved by
# Dafny's automatic induction because they align with SplitSep's own
# front-recursion (peels s[0], recurses on s[1..]); CountCharPrefix is the
# "count against a loop" lemma, a prefix-by-index accumulator (decreases
# |n| via `n`'s own clamped measure, not |s|) whose own postcondition
# proves it equal to Count(s[0..n],[c]) via an embedded
# `assert ... by { CountAppend1(...); }` (Dafny functions may sequence
# ghost asserts before their final expression; CountAppend1 is a
# hand-written lemma because Dafny's automatic per-function induction alone
# timed out at 30s on the append-style step, measured directly: Count
# recurses front-to-back but the loop invariant needs a back-to-front
# (prefix-growing) step, and the two inductions do not align without help).
# CountCharPrefix is deliberately TOTAL (no `requires`, clamped to 0
# outside [0,|s|]): count_vowels.json's own invariant list states the
# value invariant BEFORE the bounds invariants that would justify
# `0 <= i <= |s|` (SPEC.md "Invariants are checked in order", 2026-09-09),
# so a `requires 0 <= n <= |s|` version fails Dafny's well-formedness
# check on exactly that invariant (measured directly: "function
# precondition could not be proved" at the first invariant, the bounds
# not yet in scope); a task body is never edited to reorder its own
# invariants, so the function is made total instead, which sidesteps the
# gap entirely. `_full_self_slice` (below `_strlib_lower`) folds
# `slice(X, 0, len(X))` to `X` at lowering time for the same reason:
# word_count.json copies `s` via a full-length slice before calling
# `split`, and Dafny's seq theory does not fold that slice to `s` on its
# own where it is needed (a standalone `ensures s[0..|s|] == s` lemma
# proves trivially, being the direct goal, but using it via congruence
# needs an `assert` this file cannot insert into the task's body).
#
# The prelude is emitted only when the task (or the body actually being
# lowered -- a twin's mutated body, when `witness` is set) mentions a
# member (`_uses_strlib`, an op-name AST walk, never a raw string search:
# count_matches.json names its own int-counting spec_fun "count" too, and
# a string search misfires on it), so gate (c)'s byte-identical-source
# check holds for every task that does not call a member, not merely for
# their method text.
STRLIB_PRELUDE = """
function IsWs(c: int): bool { (9 <= c && c <= 13) || (28 <= c && c <= 32) }

function TokLen(s: seq<int>): int
  requires |s| > 0 && !IsWs(s[0])
  ensures 1 <= TokLen(s) <= |s|
  decreases |s|
{
  if |s| == 1 then 1
  else if IsWs(s[1]) then 1
  else 1 + TokLen(s[1..])
}

function SplitWs(s: seq<int>): seq<seq<int>>
  decreases |s|
{
  if |s| == 0 then []
  else if IsWs(s[0]) then SplitWs(s[1..])
  else
    var i := TokLen(s);
    [s[0..i]] + SplitWs(s[i..])
}

function Join(rows: seq<seq<int>>, sep: seq<int>): seq<int>
  decreases |rows|
{
  if |rows| == 0 then []
  else if |rows| == 1 then rows[0]
  else rows[0] + sep + Join(rows[1..], sep)
}

function SplitSep(s: seq<int>, c: int): seq<seq<int>>
  decreases |s|
  ensures |SplitSep(s, c)| >= 1
  ensures Join(SplitSep(s, c), [c]) == s
  ensures |SplitSep(s, c)| == Count(s, [c]) + 1
{
  if |s| == 0 then [[]]
  else if s[0] == c then [[]] + SplitSep(s[1..], c)
  else
    var rest := SplitSep(s[1..], c);
    [[s[0]] + rest[0]] + rest[1..]
}

function Count(s: seq<int>, t: seq<int>): int
  decreases |s|
  ensures Count(s, t) >= 0
{
  if |t| == 0 then |s| + 1
  else if |s| < |t| then 0
  else if s[0..|t|] == t then 1 + Count(s[|t|..], t)
  else Count(s[1..], t)
}

lemma CountAppend1(s: seq<int>, x: int, c: int)
  ensures Count(s + [x], [c]) == Count(s, [c]) + (if x == c then 1 else 0)
  decreases |s|
{
  if |s| == 0 {
    assert [x] == [c] <==> x == c;
  } else {
    CountAppend1(s[1..], x, c);
    assert (s + [x])[1..] == s[1..] + [x];
  }
}

lemma CountConcat1(x: seq<int>, y: seq<int>, c: int)
  ensures Count(x + y, [c]) == Count(x, [c]) + Count(y, [c])
  decreases |x|
{
  if |x| == 0 {
    assert x + y == y;
  } else {
    CountConcat1(x[1..], y, c);
    assert (x + y)[1..] == x[1..] + y;
  }
}

function CountCharPrefix(s: seq<int>, n: int, c: int): int
  decreases if 0 <= n then n else 0
  ensures 0 <= n <= |s| ==> CountCharPrefix(s, n, c) == Count(s[0..n], [c])
  ensures 0 <= n <= |s| && n == |s| ==>
      CountCharPrefix(s, n, c) == Count(s, [c])
{
  if 0 <= n <= |s| then
    (if n == 0 then Count(s[0..0], [c])
     else
       assert s[0..n] == s[0..n-1] + [s[n-1]] by {}
       assert Count(s[0..n], [c]) ==
              Count(s[0..n-1], [c]) + (if s[n-1] == c then 1 else 0) by {
         CountAppend1(s[0..n-1], s[n-1], c);
       }
       assert n == |s| ==> s[0..n] == s by {}
       CountCharPrefix(s, n-1, c) + (if s[n-1] == c then 1 else 0))
  else 0
}

function DigitChar(d: int): int
  requires 0 <= d <= 9
{ 48 + d }

function DigitsOf(n: int): seq<int>
  requires n >= 0
  ensures |DigitsOf(n)| >= 1
  decreases n
{
  if n < 10 then [DigitChar(n)]
  else DigitsOf(n / 10) + [DigitChar(n % 10)]
}

function ToStr(n: int): seq<int>
  ensures |ToStr(n)| >= 1
  ensures n < 0 ==> ToStr(n)[0] == 45
{
  if n < 0 then [45] + DigitsOf(-n) else DigitsOf(n)
}

function FindFrom(s: seq<int>, t: seq<int>, i: int): int
  requires 0 <= i <= |s|
  decreases |s| - i
{
  if |t| == 0 then i
  else if i + |t| > |s| then -1
  else if s[i..i+|t|] == t then i
  else FindFrom(s, t, i+1)
}

function Find(s: seq<int>, t: seq<int>): int
{ FindFrom(s, t, 0) }

function LStrip(s: seq<int>): seq<int>
  decreases |s|
  ensures |LStrip(s)| <= |s|
  ensures |s| == 0 ==> |LStrip(s)| == 0
{
  if |s| == 0 then []
  else if IsWs(s[0]) then LStrip(s[1..])
  else s
}

function RStrip(s: seq<int>): seq<int>
  decreases |s|
  ensures |RStrip(s)| <= |s|
  ensures |s| == 0 ==> |RStrip(s)| == 0
{
  if |s| == 0 then []
  else if IsWs(s[|s|-1]) then RStrip(s[0..|s|-1])
  else s
}

function Strip(s: seq<int>): seq<int>
  ensures |Strip(s)| <= |s|
  ensures |s| == 0 ==> |Strip(s)| == 0
{
  assert |s| == 0 ==> |LStrip(s)| == 0 by {}
  RStrip(LStrip(s))
}

function Replace(s: seq<int>, t: seq<int>, u: seq<int>): seq<int>
  decreases |s|
  ensures (|t| == 1 && |u| == 1 && t[0] != u[0]) ==>
      Count(Replace(s, t, u), u) == Count(s, u) + Count(s, t)
{
  if |t| == 0 then
    (if |s| == 0 then u else u + [s[0]] + Replace(s[1..], t, u))
  else if |s| < |t| then s
  else if s[0..|t|] == t then
    (assert (|t| == 1 && |u| == 1 && t[0] != u[0]) ==>
        Count(u + Replace(s[|t|..], t, u), u) ==
        Count(u, u) + Count(Replace(s[|t|..], t, u), u) by {
      if |t| == 1 && |u| == 1 && t[0] != u[0] {
        CountConcat1(u, Replace(s[|t|..], t, u), u[0]);
      }
    }
     u + Replace(s[|t|..], t, u))
  else
    (assert (|t| == 1 && |u| == 1 && t[0] != u[0]) ==>
        Count([s[0]] + Replace(s[1..], t, u), u) ==
        Count([s[0]], u) + Count(Replace(s[1..], t, u), u) by {
      if |t| == 1 && |u| == 1 && t[0] != u[0] {
        CountConcat1([s[0]], Replace(s[1..], t, u), u[0]);
      }
    }
     [s[0]] + Replace(s[1..], t, u))
}

function IsUpperLetter(c: int): bool { 65 <= c <= 90 }
function IsLowerLetter(c: int): bool { 97 <= c <= 122 }

function LowerC(c: int): int { if IsUpperLetter(c) then c + 32 else c }
function UpperC(c: int): int { if IsLowerLetter(c) then c - 32 else c }

function Lower(s: seq<int>): seq<int>
  decreases |s|
  ensures |Lower(s)| == |s|
  ensures AllAlpha(s) && |s| > 0 ==> IsLowerStr(Lower(s))
{ if |s| == 0 then [] else [LowerC(s[0])] + Lower(s[1..]) }

function Upper(s: seq<int>): seq<int>
  decreases |s|
  ensures |Upper(s)| == |s|
  ensures AllAlpha(s) && |s| > 0 ==> IsUpperStr(Upper(s))
{ if |s| == 0 then [] else [UpperC(s[0])] + Upper(s[1..]) }

function IsDigitC(c: int): bool { 48 <= c <= 57 }

function AllDigits(s: seq<int>): bool
  decreases |s|
{ |s| == 0 || (IsDigitC(s[0]) && AllDigits(s[1..])) }

function IsDigit(s: seq<int>): bool { |s| > 0 && AllDigits(s) }

function AllAlpha(s: seq<int>): bool
  decreases |s|
{ |s| == 0 || ((IsUpperLetter(s[0]) || IsLowerLetter(s[0])) && AllAlpha(s[1..])) }

function IsAlpha(s: seq<int>): bool { |s| > 0 && AllAlpha(s) }

function HasLetter(s: seq<int>): bool
  decreases |s|
{ if |s| == 0 then false else (IsUpperLetter(s[0]) || IsLowerLetter(s[0]) || HasLetter(s[1..])) }

function NoLowerLetter(s: seq<int>): bool
  decreases |s|
{ if |s| == 0 then true else (!IsLowerLetter(s[0]) && NoLowerLetter(s[1..])) }

function NoUpperLetter(s: seq<int>): bool
  decreases |s|
{ if |s| == 0 then true else (!IsUpperLetter(s[0]) && NoUpperLetter(s[1..])) }

function IsUpperStr(s: seq<int>): bool { HasLetter(s) && NoLowerLetter(s) }
function IsLowerStr(s: seq<int>): bool { HasLetter(s) && NoUpperLetter(s) }

function StartsWith(s: seq<int>, t: seq<int>): bool
{ |t| <= |s| && s[0..|t|] == t }

function EndsWith(s: seq<int>, t: seq<int>): bool
{ |t| <= |s| && s[|s|-|t|..] == t }
"""

NARY_OPS = {"and": "&&", "or": "||"}
TYPES = {"int": "int", "bool": "bool", "seq": "seq<int>",
         "real": "real",           # SPEC.md "Exact rationals (v1)" (2026-10-06): Dafny's own real

         # SPEC.md "Finite sets" (2026-09-27): Dafny's own finite set of
         # ints; display `{..}`, `in`, `|s|`, `+` (union), `*` (intersection),
         # `-` (difference) are all native and total, exactly t's six.
         "set": "set<int>"}


# SPEC.md "The string library (v1)" (2026-09-11): the 17 members, each the
# member's own notation name mapped to its prelude function. `split` and
# `count` are handled by name in `_strlib_lower` below (split for its two
# arities, count for the slice-prefix special case); everything else is a
# uniform name -> Dafny-function-name mapping with no argument reshaping.
STRLIB_OPS = {
    "join": "Join", "tostr": "ToStr", "find": "Find", "strip": "Strip",
    "lstrip": "LStrip", "rstrip": "RStrip", "replace": "Replace",
    "lower": "Lower", "upper": "Upper", "isdigit": "IsDigit",
    "isalpha": "IsAlpha", "isupper": "IsUpperStr", "islower": "IsLowerStr",
    "startswith": "StartsWith", "endswith": "EndsWith",
}
STRLIB_MEMBERS = frozenset(STRLIB_OPS) | {"split", "count"}


def _uses_strlib(obj) -> bool:
    """True iff some `{"op": M, ...}` node with M a string-library member
    name (never a raw string match: count_matches.json names its OWN
    int-counting spec_fun "count", called as `{"call": {"fun": "count",
    ...}}`, a `_collect_names`-style scan over every string in the JSON
    would misfire on that name and pull the string-library prelude into a
    task gate (c) needs byte-identical -- measured directly, that cruder
    check DOES misfire on count_matches.json)."""
    if isinstance(obj, dict):
        if obj.get("op") in STRLIB_MEMBERS:
            return True
        return any(_uses_strlib(v) for v in obj.values())
    if isinstance(obj, list):
        return any(_uses_strlib(v) for v in obj)
    return False


def _is_zero_slice(a) -> bool:
    """True for the JSON shape `slice(X, 0, HI)` (a prefix slice), the shape
    the "count against a loop" special case below looks for."""
    return (isinstance(a, dict) and a.get("op") == "slice"
            and isinstance(a.get("args"), list) and len(a["args"]) == 3
            and a["args"][1] == {"int": 0})


def _is_singleton_seq(a) -> bool:
    """True for the JSON shape `seq(X)`, a one-code-point pattern literal
    (`[c]` in the notation) -- the shape every count/split(s,c) single-point
    pattern in the three committed tasks and SPEC.md's notation takes."""
    return (isinstance(a, dict) and a.get("op") == "seq"
            and isinstance(a.get("args"), list) and len(a["args"]) == 1)


def _is_empty_seq_lit(a) -> bool:
    """True for the JSON shape `seq()`, the empty literal `[]` (fuzz_lower's
    `SEQ()`, no args). Lowered bare, `[]` types to Dafny's own bracket
    syntax with nothing to pin its element type; in a context that gives it
    no other type peg (`|[]| == 0` on its own, no sibling seq expression to
    unify against) dafny 4.11.0 rejects it: "the type of this expression is
    underspecified" (measured on fz_p_lit_empty, 2026-09-11, SPEC.md
    "Sequences: literals, concatenation, slices (v1)"). `len` is the one
    op where the fix needs no type at all: SPEC.md states len([]) == 0
    outright, for every element type, so `len` folds an empty-literal
    argument to the literal `0` rather than emitting `|[]|` -- sound by
    the spec's own definition, and it sidesteps the inference gap instead
    of working around it with an ascription Dafny's grammar has no syntax
    for (`[] : seq<int>` and `[] as seq<int>` were both tried and both
    rejected by the parser/resolver, measured the same day)."""
    return (isinstance(a, dict) and a.get("op") == "seq"
            and isinstance(a.get("args"), list) and len(a["args"]) == 0)


def _full_self_slice(op: str, raw_args: list, lower_fn) -> str | None:
    """`slice(X, 0, len(X))` (the same X, structurally) denotes X itself --
    true for any seq, not a string-library fact, but word_count.json (SPEC.md
    "The string library (v1)", 2026-09-11) is the task that needs it proved:
    its body copies `s` via `t2 := s[0..len(s)]` before calling `split`, "a
    full-length slice standing in for the loop-free body's own copy of `s`"
    (SPEC.md), and measured directly, Dafny's seq theory does NOT fold
    `s[0..|s|]` to `s` on its own here: a standalone lemma
    `ensures s[0..|s|] == s {}` verifies trivially (it IS the goal), but
    using that fact to justify `SplitWs(t2) == SplitWs(s)` from `t2 ==
    s[0..|s|]` needs an explicit `assert t2 == s;` in between (measured on a
    probe file) -- exactly the kind of body edit SPEC.md rules out. Folding
    the JSON shape at lowering time sidesteps the gap the same way a
    compiler constant-folds `x + 0`: `t2 := s[0..len(s)]` lowers straight to
    `t2 := s`, so `SplitWs(t2)` and `SplitWs(s)` are the SAME term and need
    no congruence step at all. Sound for any `slice(X, 0, len(X))`, string
    library or not; kept beside `_strlib_lower` because that is the gap it
    was found closing."""
    if op != "slice" or len(raw_args) != 3:
        return None
    base, lo, hi = raw_args
    if lo == {"int": 0} and hi == {"op": "len", "args": [base]}:
        return lower_fn(base)
    return None


def _strlib_lower(op: str, raw_args: list, lower_fn) -> str | None:
    """Lower a v1 string-library op to a call of its prelude function, or
    None for a non-string-library op. `lower_fn` lowers one sub-expression
    (expr's own recursive call in spec position, body_expr's in body
    position), so this one function serves both dispatch tables.

    `count` gets a special case (SPEC.md's "count against a loop" lemma,
    2026-09-11): `count(slice(s, 0, i), [c])`, exactly the shape
    count_vowels.json's invariant takes, lowers to CountCharPrefix(s, i, c)
    -- the prelude function whose own postcondition carries the
    index-incremental step (`CountCharPrefix(s,n,c) ==
    CountCharPrefix(s,n-1,c) + (s[n-1]==c ? 1 : 0)`) the loop's invariant
    preservation needs and Dafny cannot re-derive from the general `Count`
    alone (measured: attaching that step directly to `Count` as a function
    postcondition times out at 30s, front-recursion vs. the prefix-growing
    direction the loop needs do not align without help -- see the prelude's
    docstring). Every other `count(s, t)` shape, including the un-sliced
    `count(s, [c])` in count_vowels.json's own `ensures`, lowers to the
    general `Count(s, t)`; CountCharPrefix carries its own second
    postcondition (`n == |s| ==> CountCharPrefix(s,n,c) == Count(s,[c])`)
    so the two connect automatically at the loop's exit, with no lemma
    call inserted into the (unedited) task body."""
    if op == "split":
        if len(raw_args) == 1:
            return f"SplitWs({lower_fn(raw_args[0])})"
        return f"SplitSep({lower_fn(raw_args[0])}, {lower_fn(raw_args[1])})"
    if op == "count":
        base, pat = raw_args
        if _is_zero_slice(base) and _is_singleton_seq(pat):
            s_e, _, hi_e = base["args"]
            return (f"CountCharPrefix({lower_fn(s_e)}, {lower_fn(hi_e)}, "
                    f"{lower_fn(pat['args'][0])})")
        return f"Count({lower_fn(base)}, {lower_fn(pat)})"
    fname = STRLIB_OPS.get(op)
    if fname is None:
        return None
    return f"{fname}(" + ", ".join(lower_fn(a) for a in raw_args) + ")"


def dafny_type(t) -> str:
    """The declared-type string for a param, return or local: TYPES[t] for
    the three base types, Dafny's own built-in tuple type `(T1, T2)` for a
    pair type `{"pair": [T1, T2]}` (SPEC.md "Pairs", 2026-09-10), and
    Dafny's own `seq<seq<int>>` for the nested-seq type `{"seq": "seq"}`
    (SPEC.md "Nested sequences", 2026-09-10). T1/T2 are always base types
    (no pair of pairs, SPEC.md) and a nested seq's row is always the
    elementary "seq" (no three levels, SPEC.md), so neither branch ever
    recurses past one level."""
    if isinstance(t, dict):
        if "pair" in t or "tuple" in t:
            # SPEC.md "Compositional types (v1)" (2026-10-06): Dafny's own tuple type of any arity, each
            # component printed by this same function, so a pair of pairs and a tuple of seqs print themselves.
            return "(%s)" % ", ".join(dafny_type(c) for c in list(t.values())[0])
        if "datatype" in t:
            # SPEC.md "Datatypes (v1)" (2026-09-27): t's datatype IS
            # Dafny's own `datatype` (reference manual 5.14) -- the
            # declared name prints as itself, no wrapping.
            return t["datatype"]
        if "set" in t:
            return f"set<{dafny_type(t['set'])}>"
        if "map" in t:
            return f"map<{dafny_type(t['map'][0])}, {dafny_type(t['map'][1])}>"   # SPEC.md "Maps (v1)" (2026-10-06)
        return f"seq<{dafny_type(t['seq'])}>"
    return TYPES[t]


_QUANT_BOOL_OPS = {"==", "!=", "<", "<=", ">", ">=", "and", "or", "not",
                   "implies"}


def _contains_var(node, v: str) -> bool:
    """True if `v` occurs anywhere (as a `{"var": v}` leaf) inside `node`."""
    if isinstance(node, dict):
        if node.get("var") == v:
            return True
        return any(_contains_var(x, v) for x in node.values())
    if isinstance(node, list):
        return any(_contains_var(x, v) for x in node)
    return False


def _find_trigger_term(node, v: str):
    """Find a Dafny-triggerable subterm of a quantifier body: the first
    non-boolean `op` node (a function/index/slice application, never a
    comparison or connective) that mentions the bound variable `v`. Dafny
    cannot pick a trigger out of a bare comparison like `sub ==
    main_v[j..j+|sub|]` on its own (2026-09-11, isSublist: `exists j ::
    ... && sub == main_v[j..j+|sub|]` warns "Could not find a trigger" and,
    with `--allow-warnings` false by default, that warning alone is dafny's
    exit 2 -- MALFORMED here, not the proof failure it looks like), but the
    `slice` application inside the equality is exactly the term egraph
    matching needs, so callers state that subterm as an explicit
    `{:trigger ...}`. Recurses depth-first through `args` and returns the
    first match (there is exactly one candidate in every task this handles
    today); `None` when nothing containing `v` is an op application at all
    (a body that is only comparisons/connectives over bare variables needs
    no trigger and gets none)."""
    if isinstance(node, dict) and "op" in node:
        if node["op"] not in _QUANT_BOOL_OPS and _contains_var(node, v):
            return node
        for a in node.get("args", []) or []:
            found = _find_trigger_term(a, v)
            if found is not None:
                return found
    return None


def _seq_membership(q: dict):
    """If the `exists` payload `q` has the shape `lo <= v < hi &&
    at(seq, v) == elem` (or the equality flipped), where the bound
    variable `v` occurs only as that one index and nowhere in `elem`,
    return `(seq, elem)`: the whole quantifier is Dafny's own seq
    membership test `elem in seq[lo..hi]`. `None` when the body is not
    exactly this shape.

    2026-09-14 (ROADMAP 16.2, dafny-closure): dafny-synthesis 412/426/436/
    554/629 lower each source's `x in someSeq` (the lifter already turns
    `in` into this exact exists at lift time -- t's IR has no `in` op, so
    nothing upstream of this file can change) into a bare `exists k :: ...
    && seq[k] == elem`. Measured directly: dafny fails to maintain the
    invariant across `evenList := evenList + [arr[i]]` even with an
    explicit `{:trigger}` on the index application (a generic quantifier
    needs the append-preserves-old-indices fact re-derived by hand), while
    the ORIGINAL Dafny source's native `elem in seq` verifies with no
    trigger at all: `in` on a seq is a primitive Dafny operator with its
    own built-in axiom, not sugar the verifier reconstructs at each call
    site. This is not about the spec_fun in the `if` guard at all --
    `arr[i] % 2 == 0` inline fails the same invariant the same way
    (measured in /tmp scratch): the spec_fun call was a correlate of the
    shape in the sweep, not the cause."""
    v = q["var"]
    body = q["body"]
    if body.get("op") != "==" or len(body.get("args", [])) != 2:
        return None

    def _at_v(node):
        return (isinstance(node, dict) and node.get("op") == "at"
                and node.get("args", [None, None])[1] == {"var": v})

    a, b = body["args"]
    if _at_v(a) and not _contains_var(b, v):
        return a["args"][0], b
    if _at_v(b) and not _contains_var(a, v):
        return b["args"][0], a
    return None


def expr(e: dict, self_name: str | None = None) -> str:
    """Lower a spec-position expression. A self-call here is refused: SPEC.md
    puts task self-calls in bodies only, and the twin argument depends on the
    spec never mentioning the task's own (mutable) name."""
    if "int" in e:
        return str(e["int"])
    if "rat" in e:
        return _dafny_rat(*e["rat"])
    if "bool" in e:
        return "true" if e["bool"] else "false"
    if "var" in e:
        return e["var"]
    if "comp" in e:
        return _comp_call(e, lambda x: expr(x, self_name))   # SPEC.md "Comprehensions (v1)" (2026-10-06)
    if "forall" in e:
        q = e["forall"]
        v = q["var"]
        term = _find_trigger_term(q["body"], v)
        # Only a slice application gets the explicit trigger: that is the
        # one shape dafny cannot auto-trigger (isSublist). Stating a
        # trigger on every quantifier overrode dafny's own choice and
        # regressed appendArrayToSeq and interleave from verified to
        # unproved in sweep r22 (caught at the merge, 2026-09-12).
        trig = (f" {{:trigger {expr(term, self_name)}}}"
                if term is not None and term.get("op") == "slice" else "")
        return (f"(forall {v}: int{trig} :: "
                f"({expr(q['lo'], self_name)} <= {v} && "
                f"{v} < {expr(q['hi'], self_name)}) ==> "
                f"{expr(q['body'], self_name)})")
    if "exists" in e:
        q = e["exists"]
        v = q["var"]
        mem = _seq_membership(q)
        if (mem is not None and q["lo"] == {"int": 0}
                and q["hi"] == {"op": "len", "args": [mem[0]]}):
            # Whole-sequence membership only (lo==0, hi==len(seq)): this is
            # exactly Dafny's own `in` primitive, with its own axiom, not a
            # partial-range read whose `lo<=hi<=|seq|` bound would need a
            # fresh proof obligation at the call site. See
            # `_seq_membership`'s docstring for why this beats a
            # generic quantifier here (dafny-synthesis 412 et al,
            # 2026-09-14).
            seq, elemn = mem
            return f"({expr(elemn, self_name)} in {expr(seq, self_name)})"
        term = _find_trigger_term(q["body"], v)
        # Only a slice application gets the explicit trigger: that is the
        # one shape dafny cannot auto-trigger (isSublist). Stating a
        # trigger on every quantifier overrode dafny's own choice and
        # regressed appendArrayToSeq and interleave from verified to
        # unproved in sweep r22 (caught at the merge, 2026-09-12).
        trig = (f" {{:trigger {expr(term, self_name)}}}"
                if term is not None and term.get("op") == "slice" else "")
        return (f"(exists {v}: int{trig} :: "
                f"({expr(q['lo'], self_name)} <= {v} && "
                f"{v} < {expr(q['hi'], self_name)}) && "
                f"{expr(q['body'], self_name)})")
    if "ite" in e:
        c = e["ite"]
        return (f"(if {expr(c['cond'], self_name)} "
                f"then {expr(c['then'], self_name)} "
                f"else {expr(c['else'], self_name)})")
    if "ctor" in e:
        # SPEC.md "Datatypes (v1)" (2026-09-27): `D.C` or `D.C(a1, ...)`,
        # Dafny's own qualified constructor syntax (reference manual 5.14).
        c = e["ctor"]
        if c.get("args"):
            cargs = ", ".join(expr(a, self_name) for a in c["args"])
            return f"{c['dtype']}.{c['name']}({cargs})"
        return f"{c['dtype']}.{c['name']}"
    if "match" in e:
        # `match e case C1 => e1 case C2 => e2` -- Dafny's own match
        # expression (reference manual 8.5.2's statement form has a
        # matching expression form), exhaustive over constructors, which
        # check_wf already proved this match is (SPEC.md "Datatypes (v1)").
        m = e["match"]
        scrut = expr(m["scrutinee"], self_name)
        arms = " ".join(
            "case %s%s => %s" % (
                a["ctor"],
                "(%s)" % ", ".join(a["binders"]) if a.get("binders") else "",
                expr(a["body"], self_name))
            for a in m["arms"])
        return f"(match {scrut} {arms})"
    if "call" in e:
        c = e["call"]
        if c["fun"] == self_name:
            raise ValueError(
                f"self-call of {self_name!r} in spec position: t puts "
                f"self-calls in bodies only (SPEC.md gate 3)")
        args = ", ".join(expr(a, self_name) for a in c["args"])
        return f"{c['fun']}({args})"
    op = e["op"]
    _lower1 = lambda a: expr(a, self_name)
    sc = (_full_self_slice(op, e.get("args", []), _lower1)
          or _strlib_lower(op, e.get("args", []), _lower1))
    if sc is not None:
        return sc
    if op == "len" and _is_empty_seq_lit(e.get("args", [None])[0]):
        return "0"
    args = [expr(a, self_name) for a in e.get("args", [])]
    if op == "neg":
        return f"(-{args[0]})"
    if op == "not":
        return f"(!{args[0]})"
    if op == "len":
        return f"|{args[0]}|"
    if op == "at":
        return f"{args[0]}[{args[1]}]"
    if op == "update":
        return f"{args[0]}[{args[1]} := {args[2]}]"
    if op == "fill":
        return f"seq({args[0]}, _ => {args[1]})"
    if op == "seq":
        return "[" + ", ".join(args) + "]"
    if op == "slice":
        return f"{args[0]}[{args[1]}..{args[2]}]"
    if op == "pair":
        return f"({args[0]}, {args[1]})"
    if op == "fst":
        return f"{args[0]}.0"
    if op == "snd":
        return f"{args[0]}.1"
    if op == "tuple":
        # SPEC.md "Compositional types (v1)" (2026-10-06): Dafny's own tuple display of any arity.
        return "(" + ", ".join(args) + ")"
    if op == "proj":
        return f"{args[0]}.{e['args'][1]['int']}"
    ll = _lib_lower(op, args, e)
    if ll is not None:
        return ll
    rl = _real_lower(op, args)
    if rl is not None:
        return rl
    sl = _set_lower(op, args, e)
    if sl is not None:
        return sl
    ml = _map_lower(op, args, e)   # SPEC.md "Maps (v1)" (2026-10-06)
    if ml is not None:
        return ml
    if op in NARY_OPS:
        return "(" + f" {NARY_OPS[op]} ".join(args) + ")"
    if op in BIN_OPS:
        return f"({args[0]} {BIN_OPS[op]} {args[1]})"
    raise ValueError(f"t has no operator {op!r}")


# SPEC.md "Finite sets" (2026-09-27): the six set operations as Dafny's own
# (`{..}`, `in`, `|s|`, `+`, `*`, `-`), all native and total. The one form
# that needs care is the EMPTY display: a bare `{}` under `|..|` has no
# element to infer its type from ("the type of this expression is
# underspecified", measured on dafny 4.11.0), and the comprehension
# `set i: int | false` is rejected as not provably finite ("Dafny's
# heuristics can't figure out how to produce a bounded set"). A let
# expression carries the type: `(var t_emptyset: set<int> := {};
# t_emptyset)` types and verifies in spec and body positions alike
# (measured, the same file: `|..| == 0` and `x in ..` both proved), so the
# empty display lowers to it; a non-empty display is typed by its elements.
# The name is `t_`-prefixed, a prefix rule 4.8 keeps out of every task
# (lower_rocq's reserved prefix), so it can shadow nothing. Measured in
# the same file: `|a + b| + |a * b| == |a| + |b|`, `|a - b| + |a * b| ==
# |a|`, `|{x, x, 1}|` in [1, 2] and `a == b` against two empty differences
# all verify with no hint; `x in s == (|s * {x}| == 1)` does not (a
# cardinality fact about a singleton intersection Dafny's set axioms leave
# to the user), which is why the membership probe is stated over
# membership alone.
_SET_BIN = {"union": "+", "inter": "*", "diff": "-"}
_EMPTY_SET = "(var t_emptyset: set<int> := {}; t_emptyset)"


def _dafny_rat(n: int, d: int) -> str:
    """SPEC.md "Exact rationals (v1)" (2026-10-06): a t real literal as Dafny's. A finite decimal is Dafny's own
    real literal (`1.5`, negatives in parentheses); a quotient with no finite decimal (a certificate's witness
    value, never a literal the notation wrote) is `((n as real) / (d as real))`."""
    import surface
    try:
        text = surface._decimal_of(n, d)
        return f"({text})" if n < 0 else text
    except surface.SurfaceError:
        return f"((({n}) as real) / (({d}) as real))"


# SPEC.md "The library (v1)" (2026-10-06). `_HINTS` (name -> declared t type) and `_FUNS` (the task's spec_funs) are
# set by lower() so `_arg_type` can read an operand's static type where the Dafny definition is monomorphic (min on
# ints or on reals); `_LIB_USED` collects which definitions the file needs, emitted once each by `_lib_defs`.
_HINTS: dict = {}
_FUNS: dict = {}
_LIB_USED: set = set()
_LIB_INT = frozenset({"min", "max", "abs", "sum", "gcd", "pow", "isqrt", "rev", "sort",
                      "any", "all", "toset"})   # SPEC.md "Reductions (v1)" (2026-10-07)


def _arg_type(e):
    """The static t type of `e` under the task's declared names, or None when it cannot be told here."""
    try:
        import check_wf
        t, errs = check_wf.expression_type(e, dict(_HINTS), functions=_FUNS)
        return None if errs else t
    except Exception:                                       # noqa: BLE001
        return None


def _lib_lower(op: str, args: list, e: dict) -> str | None:
    """A library call as Dafny text, recording the definition it needs; None for any other op."""
    if op not in _LIB_INT:
        return None
    if op in ("min", "max") and len(args) == 1:
        # SPEC.md "Reductions (v1)" (2026-10-07): the Std's Max/Min shape, by element type
        t0 = _arg_type(e["args"][0])
        real = isinstance(t0, dict) and t0.get("seq") == "real"
        name = ("t_r" if real else "t_") + op + "s"
        _LIB_USED.update({name, ("t_r" if real else "t_") + op})
        return f"{name}({args[0]})"
    if op in ("any", "all"):
        _LIB_USED.add("t_" + op)
        return f"t_{op}({args[0]})"
    if op == "toset":
        _LIB_USED.add("t_toset")
        return f"t_toset({args[0]})"
    if op in ("min", "max", "abs"):
        real = _arg_type(e["args"][0]) == "real"
        name = ("t_r" if real else "t_") + op
        _LIB_USED.add(name)
        return f"{name}({', '.join(args)})"
    if op == "sum":
        t0 = _arg_type(e["args"][0])
        real = isinstance(t0, dict) and t0.get("seq") == "real"
        name = "t_rsum" if real else "t_sum"
        _LIB_USED.add(name)
        return f"{name}({args[0]})"
    if op == "gcd":
        _LIB_USED.update({"t_gcd", "t_gcdn", "t_abs"})
        return f"t_gcd({args[0]}, {args[1]})"
    if op == "pow":
        _LIB_USED.add("t_pow")
        return f"t_pow({args[0]}, {args[1]})"
    if op == "isqrt":
        _LIB_USED.add("t_isqrt")
        return f"t_isqrt({args[0]})"
    if op == "rev":
        _LIB_USED.add("t_rev")
        return f"t_rev({args[0]})"
    if op == "sort":
        # SPEC.md "Sorting (v1)" (2026-10-06): Std.Collections.Seq.MergeSortBy's shape, by element type
        t0 = _arg_type(e["args"][0])
        real = isinstance(t0, dict) and t0.get("seq") == "real"
        _LIB_USED.add("t_rsort" if real else "t_sort")
        return f"{'t_rsort' if real else 't_sort'}({args[0]})"
    return None


_LIB_TEXT = {
    # Std.Math's own shapes (fetched 2026-10-06, receipt 54355043298c), over real too
    "t_min": "function t_min(a: int, b: int): int { if a < b then a else b }",
    "t_rmin": "function t_rmin(a: real, b: real): real { if a < b then a else b }",
    "t_max": "function t_max(a: int, b: int): int { if a < b then b else a }",
    "t_rmax": "function t_rmax(a: real, b: real): real { if a < b then b else a }",
    "t_abs": "function t_abs(a: int): int { if a < 0 then -a else a }",
    "t_rabs": "function t_rabs(a: real): real { if a < 0.0 then -a else a }",
    # SPEC.md "The library (v1)": sum([]) == 0, sum(s) == sum(s[0..len(s) - 1]) + s[len(s) - 1]
    # No fuel attribute: verifiers/dafny.py bans every {:...} attribute (an audit rule, since {:axiom} hides in the same
    # braces). Measured 2026-10-06: a two-element display `sum([a, b])` is not unfolded at the default fuel, `sum(s + [x])`
    # is (one unfolding), so the committed task is `sum_tail`.
    "t_sum": "function t_sum(s: seq<int>): int decreases |s| { if |s| == 0 then 0 else t_sum(s[..|s| - 1]) + s[|s| - 1] }",
    "t_rsum": "function t_rsum(s: seq<real>): real decreases |s| { if |s| == 0 then 0.0 else t_rsum(s[..|s| - 1]) + s[|s| - 1] }",
    # Euclid on the absolute values (Lean's Nat.gcd shape); gcd(0, 0) == 0
    "t_gcdn": "function t_gcdn(a: nat, b: nat): nat decreases b { if b == 0 then a else t_gcdn(b, a % b) }",
    "t_gcd": "function t_gcd(a: int, b: int): int { t_gcdn(t_abs(a), t_abs(b)) }",
    # the requires is the definedness obligation (SPEC.md: pow and isqrt are undefined below 0)
    "t_pow": "function t_pow(a: int, n: int): int requires n >= 0 decreases n { if n == 0 then 1 else a * t_pow(a, n - 1) }",
    "t_isqrt": ("function t_isqrt(n: int): (r: int)\n  requires n >= 0\n  ensures 0 <= r && r * r <= n && n < (r + 1) * (r + 1)\n"
                "  decreases n\n{ if n == 0 then 0 else (var r := t_isqrt(n - 1); if (r + 1) * (r + 1) <= n then r + 1 else r) }"),
    # Std.Collections.Seq.Reverse's two ensures
    "t_rev": ("function t_rev<T>(s: seq<T>): (r: seq<T>)\n  ensures |r| == |s|\n"
              "  ensures forall i :: 0 <= i < |s| ==> r[i] == s[|s| - 1 - i]\n  decreases |s|\n"
              "{ if |s| == 0 then [] else [s[|s| - 1]] + t_rev(s[..|s| - 1]) }"),
}
_LIB_ORDER = ["t_min", "t_rmin", "t_max", "t_rmax", "t_mins", "t_rmins", "t_maxs", "t_rmaxs", "t_abs", "t_rabs",
              "t_sum", "t_rsum", "t_gcdn", "t_gcd", "t_pow", "t_isqrt", "t_rev", "t_sort", "t_rsort",
              "t_any", "t_all", "t_toset"]


def _sort_text(suffix: str, ty: str) -> str:
    """SPEC.md "Sorting (v1)" (2026-10-06): Std.Collections.Seq.MergeSortBy and MergeSortedWith specialised to one
    element type (fetched, receipt 8f5b4d0085b5), with the Std's own lemma and asserts, which Dafny proves as the
    Std does (measured 2026-10-06: the function postconditions, the committed tasks and the ground certificates)."""
    p = f"t_{suffix}"
    # a `function ... : bool`, not a `predicate`: verifiers/dafny.py's shape rule admits only function, method and lemma
    return f"""function {p}sorted(s: seq<{ty}>): bool {{ forall i, j :: 0 <= i < j < |s| ==> s[i] <= s[j] }}

lemma {p}lemma_first(x: {ty}, s: seq<{ty}>)
  requires {p}sorted(s)
  requires |s| == 0 || x <= s[0]
  ensures {p}sorted([x] + s)
{{}}

function {p}merge(left: seq<{ty}>, right: seq<{ty}>): (r: seq<{ty}>)
  requires {p}sorted(left) && {p}sorted(right)
  ensures multiset(left + right) == multiset(r)
  ensures {p}sorted(r)
  decreases |left| + |right|
{{
  if |left| == 0 then right
  else if |right| == 0 then left
  else if left[0] <= right[0] then
    {p}lemma_first(left[0], {p}merge(left[1..], right));
    assert left == [left[0]] + left[1..];
    [left[0]] + {p}merge(left[1..], right)
  else
    {p}lemma_first(right[0], {p}merge(left, right[1..]));
    assert right == [right[0]] + right[1..];
    [right[0]] + {p}merge(left, right[1..])
}}

function {p}sort(s: seq<{ty}>): (r: seq<{ty}>)
  ensures multiset(s) == multiset(r)
  ensures {p}sorted(r)
  ensures |r| == |s|
  decreases |s|
{{
  if |s| <= 1 then s
  else
    var mid := |s| / 2;
    var left := s[..mid];
    var right := s[mid..];
    assert s == left + right;
    {p}merge({p}sort(left), {p}sort(right))
}}"""


# SPEC.md "Reductions (v1)" (2026-10-07): the Std's Max/Min (recursive, `requires 0 < |xs|`, in the sequence and
# above/below every element; the Std's own `assert xs == [xs[0]] + xs[1..]` carries the membership), ToSet as the
# set comprehension, any/all as the bounded quantifiers (receipt 4c05105b66f2)
for _nm, _ty, _two, _cmp in (("t_maxs", "int", "t_max", "<="), ("t_rmaxs", "real", "t_rmax", "<="),
                              ("t_mins", "int", "t_min", ">="), ("t_rmins", "real", "t_rmin", ">=")):
    _LIB_TEXT[_nm] = (f"function {_nm}(s: seq<{_ty}>): {_ty}\n  requires |s| > 0\n"
                      f"  ensures forall k :: 0 <= k < |s| ==> s[k] {_cmp} {_nm}(s)\n  ensures {_nm}(s) in s\n"
                      f"  decreases |s|\n{{\n  assert s == [s[0]] + s[1..];\n"
                      f"  if |s| == 1 then s[0] else {_two}(s[0], {_nm}(s[1..]))\n}}")
_LIB_TEXT["t_any"] = "function t_any(s: seq<bool>): bool { exists i :: 0 <= i < |s| && s[i] }"
_LIB_TEXT["t_all"] = "function t_all(s: seq<bool>): bool { forall i :: 0 <= i < |s| ==> s[i] }"
_LIB_TEXT["t_toset"] = "function t_toset<T>(s: seq<T>): set<T> { set x: T | x in s }"
_LIB_TEXT["t_sort"] = _sort_text("", "int")
_LIB_TEXT["t_rsort"] = _sort_text("r", "real")


# SPEC.md "Comprehensions (v1)" (2026-10-06): one recursive function per comprehension in the file, over the source
# (or the two bounds) and every free variable of cond/body but the bound one, recursing from the end as Std's Filter
# does, with the ensures its shape admits (filter: every element satisfies cond and the length does not grow; map:
# the length and the image at every index; range map: the length `hi - lo` and the image at `lo + k`).
_COMP_INDEX: dict = {}      # json key of the comp node -> (k, node)


def _comp_key(e: dict) -> str:
    """The comprehension's SHAPE (SPEC.md "Comprehensions (v1)", the lowering paragraph; 2026-10-06, with the early
    exits): the bound variable, the condition, the body and whether the source is a sequence or a range, so the
    same comprehension over a prefix `s[0..i]` and over `s` is one function and `t_comp1(s[0..|s|])` meets
    `t_comp1(s)` by the slice axiom (the first registered source types the function)."""
    import json
    c = e["comp"]
    return json.dumps({"var": c["var"], "cond": c["cond"], "body": c["body"], "range": "lo" in c}, sort_keys=True)


def _comp_free(node: dict) -> list:
    """Free variable names of a comp's cond and body (binders of inner quantifiers and comps subtracted), sorted."""
    def walk(x, bound: frozenset) -> set:
        if isinstance(x, dict):
            if "var" in x and len(x) == 1:
                return set() if x["var"] in bound else {x["var"]}
            if "comp" in x:
                c = x["comp"]
                inner = bound | {c["var"]}
                out = set()
                for k in ("seq", "lo", "hi"):
                    if k in c:
                        out |= walk(c[k], bound)
                return out | walk(c["cond"], inner) | walk(c["body"], inner)
            if "forall" in x or "exists" in x:
                q = x.get("forall") or x.get("exists")
                return walk(q["lo"], bound) | walk(q["hi"], bound) | walk(q["body"], bound | {q["var"]})
            if "call" in x:
                return set().union(*(walk(a, bound) for a in x["call"]["args"])) if x["call"]["args"] else set()
            return set().union(*(walk(v, bound) for v in x.values())) if x else set()
        if isinstance(x, list):
            return set().union(*(walk(v, bound) for v in x)) if x else set()
        return set()
    c = node["comp"]
    return sorted(walk(c["cond"], frozenset({c["var"]})) | walk(c["body"], frozenset({c["var"]})))


def _comp_register(task: dict, body: list) -> None:
    """Number every comp node of the task in reading order (requires, ensures, spec_funs, body, methods)."""
    _COMP_INDEX.clear()

    def walk(x):
        if isinstance(x, dict):
            if "comp" in x:
                _COMP_INDEX.setdefault(_comp_key(x), (len(_COMP_INDEX) + 1, x))
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(task.get("requires", []))
    walk(task.get("ensures", []))
    walk(task.get("spec_funs", []))
    walk(body or [])
    walk(task.get("methods", []))


def _comp_call(e: dict, render) -> str:
    k, _ = _COMP_INDEX[_comp_key(e)]
    c = e["comp"]
    # the prefix form (SPEC.md "Comprehensions (v1)", the Dafny paragraph; see _comp_defs): a source `s[0..e]` is
    # the first e elements of s, any other source is all of itself, a range [a, b) is a and its length
    if "seq" in c:
        s = c["seq"]
        if isinstance(s, dict) and s.get("op") == "slice" and s["args"][1] == {"int": 0}:
            args = [render(s["args"][0]), render(s["args"][2])]
        else:
            args = [render(s), f"|{render(s)}|"]
    else:
        args = [render(c["lo"]), f"({render(c['hi'])} - {render(c['lo'])})"]
    return f"t_comp{k}({', '.join(args + _comp_free(e))})"


_IX_TEXT = "function t_ix(t_i: int): int { t_i }"


def _mentions_var(e, name: str) -> bool:
    if isinstance(e, dict):
        if e.get("var") == name and len(e) == 1:
            return True
        return any(_mentions_var(v, name) for v in e.values())
    if isinstance(e, list):
        return any(_mentions_var(v, name) for v in e)
    return False


def _ground_true(e) -> bool:
    """A conjunct with no variable that the interpreter evaluates to true (`2 != 0`, a literal divisor's
    definedness): not worth stating."""
    def has_var(x) -> bool:
        if isinstance(x, dict):
            return ("var" in x and len(x) == 1) or any(has_var(v) for v in x.values())
        return isinstance(x, list) and any(has_var(v) for v in x)
    if has_var(e):
        return False
    try:
        return interp.ev(e, {}, {}, interp.St()) is True
    except Exception:                                       # noqa: BLE001
        return False


def _comp_defs(self_name) -> list:
    """The Dafny text of every registered comprehension function, in index order, after `t_ix` when a range
    comprehension is among them (SPEC.md "Comprehensions (v1)", the lowering paragraph; 2026-10-06, T3c and T4).

    PREFIX form, one function per comprehension shape: over a sequence, `t_compK(t_s, t_n)` is the comprehension of
    the first `t_n` elements of `t_s` (`requires 0 <= t_n <= |t_s|`), called as `t_compK(s, |s|)` for a source `s`
    and as `t_compK(s, e)` for a source `s[0..e]`, so the comprehension over a prefix in a loop invariant and the one
    over the whole in the ensures are one function and one unfolding apart (measured on `count_evens_skip`: as calls
    on two sequences, `s[0..i+1][..i]` and `s[0..i]`, the invariant was not maintained); over a range, `t_compK(t_a,
    t_n)` is the comprehension of `t_a, ..., t_a + t_n - 1` (empty when `t_n` is negative), the index written
    `t_a + t_ix(t_di)` through the identity function so that Dafny has a term to match the precondition on (a
    precondition over a bare index had none: `index out of range` inside the function, 19:40Z). The precondition is
    the SPEC's definedness rule for the form -- the condition defined at every element and the body defined where
    the condition holds -- stated over the element as the Std's `Map` requires `f.requires(xs[i])`; the conjuncts
    that do not mention the element are stated once, as `t_n > 0 ==> ...` (the ensures' own well-formedness needs
    them before any element is at hand, measured on `odd_positions`); a ground conjunct that is true (`2 != 0`) and
    a formula that is `true` are not stated, so a total body costs nothing."""
    import check_wf
    import lower_verus as _lv   # the definedness formula is one rule set for every kernel; reused, not restated
    out = []
    need_ix = False
    for key, (k, e) in sorted(_COMP_INDEX.items(), key=lambda kv: kv[1][0]):
        c = e["comp"]
        v = c["var"]
        fvs = _comp_free(e)
        for n in fvs:
            if n not in _HINTS and n not in _FUNS:
                raise NotImplementedError(f"dafny: comprehension over a name whose type is not declared here: {n!r}")
        fvs = [n for n in fvs if n in _HINTS]
        is_seq = "seq" in c
        if is_seq:
            src_t = _arg_type(c["seq"])
            if not (src_t == "seq" or (isinstance(src_t, dict) and "seq" in src_t)):
                raise NotImplementedError("dafny: a comprehension's source could not be typed here")
            elem_t = "int" if src_t == "seq" else src_t["seq"]
        else:
            src_t, elem_t = None, "int"
            need_ix = True
        hints = dict(_HINTS)
        hints[v] = elem_t
        try:
            body_t, errs = check_wf.expression_type(c["body"], hints, functions=_FUNS)
        except Exception:                                   # noqa: BLE001
            body_t, errs = None, ["untypeable"]
        if errs or body_t is None:
            raise NotImplementedError("dafny: a comprehension's body could not be typed here")
        fv_params = [f"{n}: {dafny_type(_HINTS[n])}" for n in fvs]
        params = ([f"t_s: {dafny_type(src_t)}", "t_n: int"] if is_seq else ["t_a: int", "t_n: int"]) + fv_params
        rec_args = ", ".join((["t_s", "t_n - 1"] if is_seq else ["t_a", "t_n - 1"]) + fvs)
        is_filter = c["body"] == {"var": v}
        is_map = c["cond"] == {"bool": True}
        # the element at an index, as a t AST through a placeholder name the Dafny text then spells
        ph_i, ph_di = {"var": "t_ph_i"}, {"var": "t_ph_di"}
        if is_seq:
            el_i, el_di, el_last = "t_s[t_i]", "t_s[t_di]", "t_s[t_n - 1]"
        else:
            el_i, el_di, el_last = "(t_a + t_ix(t_i))", "(t_a + t_ix(t_di))", "t_a + t_ix(t_n - 1)"

        def spell(ast_e, ph: str, text: str) -> str:
            return expr(ast_e, self_name).replace(ph, text)
        size = "t_n" if is_seq else "(if t_n < 0 then 0 else t_n)"
        req = ["  requires 0 <= t_n <= |t_s|"] if is_seq else []
        ens = [f"  ensures |t_r| {'==' if is_map else '<='} {size}"]
        if is_map:
            ens.append(f"  ensures forall t_i :: 0 <= t_i < |t_r| ==> t_r[t_i] == "
                       f"{spell(subst(c['body'], {v: ph_i}), 't_ph_i', el_i)}")
        if is_filter:
            holds = subst(c["cond"], {v: {"op": "at", "args": [{"var": "t_r"}, {"var": "t_i"}]}})
            ens.append(f"  ensures forall t_i :: 0 <= t_i < |t_r| ==> {expr(holds, self_name)}")

        def is_real(y, _h=hints):
            try:
                ty, errs2 = check_wf.expression_type(y, dict(_h), functions=_FUNS)
            except Exception:                               # noqa: BLE001
                return False
            return not errs2 and ty == "real"
        _lv._SCOPE.clear()
        _lv._SCOPE.update(hints)          # the formula's own typer (a map's `at` owes membership, not a bound)
        _lv._SCOPE_FUNS.clear()
        _lv._SCOPE_FUNS.update(_FUNS)
        d_cond = _lv.defined(c["cond"], is_real)
        d_body = _lv.defined(c["body"], is_real)
        guard = d_body if (d_body == _lv.TRUE or is_map) else {"op": "implies", "args": [c["cond"], d_body]}
        pre = _lv._conj([d_cond, guard])

        def flat(x):
            if isinstance(x, dict) and x.get("op") == "and":
                return [y for a in x["args"] for y in flat(a)]
            return [x]
        parts = [x for x in flat(pre) if x != _lv.TRUE and not _ground_true(x)]
        fixed = [x for x in parts if not _mentions_var(x, v)]
        per_el = [x for x in parts if _mentions_var(x, v)]
        if fixed:
            req.append(f"  requires t_n > 0 ==> {expr(_lv._conj(fixed), self_name)}")
        if per_el:
            req.append(f"  requires forall t_di :: 0 <= t_di < t_n ==> "
                       f"{spell(subst(_lv._conj(per_el), {v: ph_di}), 't_ph_di', el_di)}")
        p_txt = expr(c["cond"], self_name)
        e_txt = expr(c["body"], self_name)
        body_txt = (f"  if t_n <= 0 then [] else\n"
                    f"    var t_p := t_comp{k}({rec_args});\n"
                    f"    var {v} := {el_last};\n"
                    f"    if {p_txt} then t_p + [{e_txt}] else t_p")
        out += [f"function t_comp{k}({', '.join(params)}): (t_r: seq<{dafny_type(body_t)}>)"] + req + ens + [
            f"  decreases {size}", "{", body_txt, "}", ""]
    if need_ix:
        out = [_IX_TEXT, ""] + out
    return out


def _lib_defs() -> list:
    """The definitions this file uses, in a fixed order (a dependency before its user), each followed by a blank."""
    out = []
    for name in _LIB_ORDER:
        if name in _LIB_USED:
            out += [_LIB_TEXT[name], ""]
    return out


def _lib_value(op: str, vs: list):
    """The interpreter's own value of a library call (SPEC.md "The library (v1)"); the mirror for `_ev`/`_ev_undef`.
    Raises interp.Undef where the SPEC says UNDEFINED."""
    if op in ("min", "max"):
        if len(vs) == 1:
            # SPEC.md "Reductions (v1)" (2026-10-07)
            if not vs[0]:
                raise interp.Undef(f"{op} of an empty seq")
            return (min if op == "min" else max)(vs[0])
        return (min if op == "min" else max)(vs[0], vs[1])
    if op in ("any", "all"):
        return (any if op == "any" else all)(vs[0])
    if op == "toset":
        return frozenset(vs[0])
    if op == "abs":
        return abs(vs[0])
    if op == "sum":
        xs = vs[0]
        return sum(xs, interp.Fraction(0)) if any(isinstance(x, interp.Fraction) for x in xs) else sum(xs)
    if op == "gcd":
        return interp.math.gcd(vs[0], vs[1])
    if op == "pow":
        if vs[1] < 0:
            raise interp.Undef("pow with a negative exponent")
        return vs[0] ** vs[1]
    if op == "isqrt":
        if vs[0] < 0:
            raise interp.Undef("isqrt of a negative")
        return interp.math.isqrt(vs[0])
    if op == "rev":
        return tuple(reversed(vs[0]))
    if op == "sort":
        return tuple(sorted(vs[0]))
    raise ValueError(op)


def _real_lower(op: str, args: list) -> str | None:
    """SPEC.md "Exact rationals (v1)": real(x) is `x as real`, floor is Dafny's `.Floor`, ceil is floor(x) or floor(x) + 1
    by whether x is integral (see below)."""
    if op == "toreal":
        return f"(({args[0]}) as real)"
    if op == "floor":
        return f"(({args[0]}).Floor)"
    if op == "ceil":
        # Dafny has no Ceil. `-((-x).Floor)` is the textbook form, and Z3 times out on it beside a second
        # `.Floor` (floor_ceil, measured 2026-10-06: 60 s, no verdict); the conditional form, floor(x) when x is
        # integral and floor(x) + 1 otherwise, proves the same task in under a second and is the same function.
        x = args[0]
        return f"(if (({x}).Floor as real) == ({x}) then ({x}).Floor else ({x}).Floor + 1)"
    return None

# SPEC.md "Compositional types (v1)" (2026-10-06): an empty set display of a non-int element type needs its
# type in the let expression above. `lower()` fills this map (id(node) -> t type, tshape.empty_display_types)
# from the declared types the display sits under, for the body it lowers; a display no declared type reaches
# keeps the set-of-ints form, which is every display there was before.
_EMPTIES: dict = {}


def _map_lower(op: str, args: list, node: dict | None = None) -> str | None:
    """SPEC.md "Maps (v1)" (2026-10-06): Dafny's own map<K, V>. A display is `map[]` built up by updates, so the
    rightmost of two equal keys wins whatever Dafny's display rule (the reference marks duplicate keys as likely to
    change); `m[k]`, `m[k := v]`, `k in m` and `|m|` are the polymorphic operators' own text, the same as a seq's;
    `keys` is `.Keys`, `remove` is domain subtraction by a singleton. An empty display takes the type its position
    declares (`tshape.empty_display_types`) where Dafny's inference would not reach it."""
    if op == "mapdisp":
        ty = _EMPTIES.get(id(node)) if node is not None else None
        base = f"(var t_emptymap: {dafny_type(ty)} := map[]; t_emptymap)" if ty is not None else "map[]"
        for i in range(0, len(args), 2):
            base = f"{base}[{args[i]} := {args[i + 1]}]"
        return base
    if op == "keys":
        return f"({args[0]}.Keys)"
    if op == "remove":
        return f"({args[0]} - {{{args[1]}}})"
    return None


def _map_ev(op: str, vs: list):
    """The map operations on evaluated operands (SPEC.md "Maps (v1)"), mirroring interp.ev."""
    if op == "mapdisp":
        return interp.MapV.of(list(zip(vs[0::2], vs[1::2])))
    if op == "keys":
        return frozenset(k for k, _ in vs[0].items)
    if op == "remove":
        return vs[0].drop(vs[1])
    if op == "in":
        return vs[1].has(vs[0])
    if op == "len":
        return len(vs[0])
    if op == "update":
        return vs[0].put(vs[1], vs[2])
    if op == "at":
        if not vs[0].has(vs[1]):
            raise interp.Undef(f"key {interp._j(vs[1])!r} not in the map")
        return vs[0].get(vs[1])
    raise ValueError(op)


def _set_lower(op: str, args: list, node: dict | None = None) -> str | None:
    if op == "set":
        if args:
            return "{" + ", ".join(args) + "}"
        ty = _EMPTIES.get(id(node)) if node is not None else None
        if ty is None or ty == "set":
            return _EMPTY_SET
        return f"(var t_emptyset: {dafny_type(ty)} := {{}}; t_emptyset)"
    if op == "in":
        return f"({args[0]} in {args[1]})"
    if op == "card":
        return f"|{args[0]}|"
    if op in _SET_BIN:
        return f"({args[0]} {_SET_BIN[op]} {args[1]})"
    return None


def _collect_names(obj) -> set[str]:
    """Every string anywhere in the task JSON, a superset of every identifier
    in scope, so a name absent from it is fresh everywhere."""
    out: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            out |= _collect_names(v)
    elif isinstance(obj, list):
        for v in obj:
            out |= _collect_names(v)
    elif isinstance(obj, str):
        out.add(obj)
    return out


class _Ctx:
    """Per-lowering context: the task's own name (self-calls target the
    lowered method and must be hoisted), the method name, a fresh-name
    supply that avoids everything the task ever mentions."""

    def __init__(self, task: dict, method: str):
        self.self_name = task["name"]
        self.method = method
        self._used = _collect_names(task)
        self._n = 0

    def fresh(self) -> str:
        while True:
            cand = f"t{self._n}"
            self._n += 1
            if cand not in self._used:
                self._used.add(cand)
                return cand


def body_expr(e: dict, ctx: _Ctx, pre: list[str], lazy: bool = False) -> str:
    """Lower a body-position expression, hoisting each self-call (left to
    right, innermost first: call-by-value order) into `pre` as a
    `var tmp := Method(...);` statement. `lazy` marks positions Dafny/t do not
    unconditionally evaluate; a self-call there cannot be hoisted without
    evaluating it on paths that never owed its precondition, so it is an
    explicit ABSTAIN, not a wrong program."""
    if "call" in e and e["call"]["fun"] == ctx.self_name:
        if lazy:
            raise NotImplementedError(
                "dafny: self-call under a lazily-evaluated position "
                "(ite branch / short-circuit arg / quantifier body): "
                "hoisting would evaluate it unconditionally")
        args = ", ".join(body_expr(a, ctx, pre) for a in e["call"]["args"])
        tmp = ctx.fresh()
        pre.append(f"var {tmp} := {ctx.method}({args});")
        return tmp
    if "comp" in e:
        return _comp_call(e, lambda x: body_expr(x, ctx, pre, lazy))   # SPEC.md "Comprehensions (v1)"
    if "forall" in e or "exists" in e:
        q = e.get("forall") or e.get("exists")
        kind = "forall" if "forall" in e else "exists"
        v = q["var"]
        lo = body_expr(q["lo"], ctx, pre, lazy)
        hi = body_expr(q["hi"], ctx, pre, lazy)
        b = body_expr(q["body"], ctx, pre, lazy=True)
        glue = "==>" if kind == "forall" else "&&"
        return (f"({kind} {v}: int :: ({lo} <= {v} && {v} < {hi}) "
                f"{glue} {b})")
    if "ite" in e:
        c = e["ite"]
        cond = body_expr(c["cond"], ctx, pre, lazy)
        t = body_expr(c["then"], ctx, pre, lazy=True)
        f = body_expr(c["else"], ctx, pre, lazy=True)
        return f"(if {cond} then {t} else {f})"
    if "call" in e:
        c = e["call"]
        args = ", ".join(body_expr(a, ctx, pre, lazy) for a in c["args"])
        return f"{c['fun']}({args})"
    if "op" in e:
        op = e["op"]
        if op in NARY_OPS or op == "implies":
            # left-to-right short circuit: only the first arg is strict
            parts = [body_expr(a, ctx, pre, lazy if i == 0 else True)
                     for i, a in enumerate(e["args"])]
            if op == "implies":
                return f"({parts[0]} ==> {parts[1]})"
            return "(" + f" {NARY_OPS[op]} ".join(parts) + ")"
        # strict operators: same laziness as the enclosing position
        _lower1 = lambda a: body_expr(a, ctx, pre, lazy)
        sc = (_full_self_slice(op, e.get("args", []), _lower1)
              or _strlib_lower(op, e.get("args", []), _lower1))
        if sc is not None:
            return sc
        args = [body_expr(a, ctx, pre, lazy) for a in e.get("args", [])]
        if op == "len" and _is_empty_seq_lit(e.get("args", [None])[0]):
            return "0"
        if op == "neg":
            return f"(-{args[0]})"
        if op == "not":
            return f"(!{args[0]})"
        if op == "len":
            return f"|{args[0]}|"
        if op == "at":
            return f"{args[0]}[{args[1]}]"
        if op == "update":
            return f"{args[0]}[{args[1]} := {args[2]}]"
        if op == "fill":
            return f"seq({args[0]}, _ => {args[1]})"
        if op == "seq":
            return "[" + ", ".join(args) + "]"
        if op == "slice":
            return f"{args[0]}[{args[1]}..{args[2]}]"
        if op == "pair":
            return f"({args[0]}, {args[1]})"
        if op == "tuple":
            return "(" + ", ".join(args) + ")"
        if op == "proj":
            return f"{args[0]}.{e['args'][1]['int']}"
        ll = _lib_lower(op, args, e)
        if ll is not None:
            return ll
        rl = _real_lower(op, args)
        if rl is not None:
            return rl
        sl = _set_lower(op, args, e)
        if sl is not None:
            return sl
        ml = _map_lower(op, args, e)   # SPEC.md "Maps (v1)" (2026-10-06)
        if ml is not None:
            return ml
        if op == "fst":
            return f"{args[0]}.0"
        if op == "snd":
            return f"{args[0]}.1"
        if op in BIN_OPS:
            return f"({args[0]} {BIN_OPS[op]} {args[1]})"
        raise ValueError(f"t has no operator {op!r}")
    # leaves share the spec lowering
    return expr(e, ctx.self_name)


def stmts(body: list, indent: str, ctx: _Ctx) -> str:
    out = []
    for s in body:
        if "assign" in s:
            name, e = s["assign"]
            pre: list[str] = []
            rhs = body_expr(e, ctx, pre)
            out.extend(indent + p for p in pre)
            out.append(f"{indent}{name} := {rhs};")
        elif "var" in s:
            d = s["var"]
            pre = []
            rhs = body_expr(d["init"], ctx, pre)
            out.extend(indent + p for p in pre)
            out.append(f"{indent}var {d['name']}: {dafny_type(d['type'])} "
                       f":= {rhs};")
        elif "return" in s:
            # Early exit (v1, SPEC.md, added 2026-09-08): `return Expr;`
            # assigns Expr to the out-parameter and ends the method right
            # there. Dafny's `return` takes no expression when the method
            # has out-parameters (they are ordinary locals by then), so
            # this lowers to the assignment followed by a bare `return;`.
            # Dafny checks every `ensures` at each `return`, exactly the
            # obligation SPEC.md states, and does NOT ask for the loop's
            # invariant at a `return` inside it: no lowering is needed to
            # get that for free, the kernel's own return rule already
            # skips it.
            name, e = s["return"]
            pre = []
            rhs = body_expr(e, ctx, pre)
            out.extend(indent + p for p in pre)
            out.append(f"{indent}{name} := {rhs};")
            out.append(f"{indent}return;")
        elif "if" in s:
            c = s["if"]
            pre = []
            cond = body_expr(c["cond"], ctx, pre)
            out.extend(indent + p for p in pre)
            out.append(f"{indent}if {cond} {{")
            out.append(stmts(c["then"], indent + "  ", ctx))
            out.append(f"{indent}}} else {{")
            out.append(stmts(c["else"], indent + "  ", ctx))
            out.append(f"{indent}}}")
        elif "break" in s or "continue" in s:
            # SPEC.md "Early exits (v1)" (2026-10-06): Dafny's own statements; its rule is t's (measured 21:40Z:
            # the invariant is not asked for at a break, it is at a continue, and `while true` takes `decreases`)
            out.append(f"{indent}{'break' if 'break' in s else 'continue'};")
        elif "lemma" in s:
            # SPEC.md "Lemmas (v1)": Dafny's own lemma call statement; the
            # caller owes the lemma's requires here and gets its ensures.
            c = s["lemma"]
            pre = []
            args = [body_expr(a, ctx, pre) for a in c["args"]]
            out.extend(indent + p for p in pre)
            out.append(f"{indent}{c['name']}({', '.join(args)});")
        elif "while" in s:
            w = s["while"]
            # guard/invariants/decreases are spec positions: no self-calls
            out.append(f"{indent}while {expr(w['cond'], ctx.self_name)}")
            for inv in w.get("invariants", []):
                out.append(f"{indent}  invariant {expr(inv, ctx.self_name)}")
            out.append(f"{indent}  decreases "
                       f"{expr(w['decreases'], ctx.self_name)}")
            out.append(f"{indent}{{")
            out.append(stmts(w["body"], indent + "  ", ctx))
            out.append(f"{indent}}}")
        else:
            raise ValueError(f"t has no statement {s!r}")
    return "\n".join(out)


# ------------------------------------------------ the refutation certificate
# Shared certificate protocol (2026-09-02, every column). Dafny's exit 4 is
# could-not-prove, not a countermodel: measured the same day on 4.11.0, the
# truth_fuzz task gt_q_ex_lit (true by construction, ensures r == 0 and an
# existential over [0,3) that i = 2 satisfies, body r := 0) exits 4 because
# Z3 does not instantiate the existential unprompted, and the old adapter
# sold that incompleteness as REFUTED. verifiers/dafny.py therefore no
# longer mints REFUTED from exit 4 at all. What it trusts is a proof it
# asked the kernel for: when lowering a TWIN whose measured witness is
# expressible as a ground formula, this file appends one lemma named
# exactly t_refutation_certificate whose ensures restates the witness as a
# ground theorem, and the adapter mints REFUTED only when dafny accepts that
# lemma in an isolated, targeted run. A file carrying the name can never
# mint VERIFIED.
#
# What each witness kind certifies (the formula is built exactly as
# lower_verus.py _certificate builds it):
#   value (_ens True only): requires holds at the witness input and the
#     ensures conjunction is false at (input, r := the twin's measured
#     result). The kernel checks the formula; it does NOT evaluate the twin
#     (a method is not callable from a lemma, measured: "in a lemma, calls
#     are allowed only to lemmas"), so r is the interpreter's reading of
#     the twin, the same trust lower_verus.py extends.
#   exit: the loop rule's post-loop obligation is false at the witness
#     state: requires and the twin's SURVIVING invariants hold, the guard is
#     false, and the ensures conjunction is false. The kept invariants and
#     guard are read off the twin body's own loop, found by diffing the real
#     body against the twin body, so the certificate speaks about the file
#     it travels in.
#   preservation, undefined: not emitted; such a cell honestly reads
#     unproved.
#
# Three Dafny-specific steps between that formula and the lemma, each one
# measured on 4.11.0 the same day:
#   1. Bounded quantifiers whose bounds are ground after substitution are
#      unrolled into finite conjunction/disjunction (cap 64), because Z3
#      will not instantiate them itself, the very gt_q_ex_lit failure. The
#      bound values are not trusted: `lo == LO` and `hi == HI` are emitted
#      as extra conjuncts the kernel re-proves, so the unrolled formula
#      entails the quantified one by arithmetic alone.
#   2. The formula is then evaluated at the witness by the interpreter
#      below, and every operand t's own short-circuit semantics never
#      evaluated is dropped: the tail of an and/or after its deciding
#      operand, the consequent of an implies with a false antecedent, the
#      untaken branch of an ite. Measured reason: dafny checks the
#      well-formedness of `s[(-1)]` under the (false) guard `(-1) >= 0`,
#      proves it from the contradiction, and --warn-contradictory-assumptions
#      turns that into a warning and exit 2 for the whole file, which is the
#      linear_search twin's shape (r = -1). Dropping is sound because every
#      deciding operand is hoisted as a top-level conjunct the kernel must
#      prove: under those conjuncts each rewritten node is logically equal
#      to the original, so the emitted formula entails the verus-shaped one
#      by propositional logic, never by the interpreter's word. Every
#      subterm that survives was evaluated to a defined value, so its
#      well-formedness is a ground truth dafny proves without contradiction.
#   3. Recursive spec_funs: dafny's default fuel decided `!(1 == fact(2))`
#      and `!(119 == fact(5))` unaided, but the lemma body carries an
#      interpreter-chosen assert ladder anyway (`assert f(args) == v;`,
#      callees before callers, cap 64): the kernel checks every step, so a
#      wrong hint can only lose the certificate.
#      2026-09-27 (SPEC.md "Seq-valued spec_funs (v1)", the review's seeded
#      faults): a SEQ-valued spec_fun's call is laddered the same way, its
#      result bound to a fresh `seq<int>` local (`t_v<k>`, fresh against
#      every name in the task) since an inline literal is type-
#      underspecified; and once the certificate grounds one such call,
#      every seq-typed ground operator subterm of the formula (`+`, slice,
#      update, fill, a string member) gets a rung too, innermost first
#      (`_seq_op_rungs`). Measured on 4.11.0: `dbl(s, 2)` unfolded past
#      the default fuel reads unproved unaided (the seeded swapped-
#      concatenation fault), and so does a literal against a ground
#      append, `[1, 0] != [0] + [0]`, with no spec_fun in sight (nothing
#      relates an append to a display without an index term to trigger
#      on; the seeded slice fault); with the rungs both read refuted. The
#      operator rungs are gated on a seq-valued fact so every committed
#      lowering is byte-identical; the append gap they close is older
#      than the gate (FEATURES-SEQFUN-2026-09-27.md, "The seeded faults").
#      lower_fstar.py takes the same rungs from `seq_ladder` below.
# Seq witness values are let-bound by their own names (`var s: seq<int> :=
# [];`) in the ensures, and again in the lemma body when the assert ladder
# names them: an inline `[]` is "the type of this expression is
# underspecified", exit 2 (measured).
# Anything outside these rules yields no certificate: a missing or rejected
# certificate can only cost a flip (UNPROVED), never fake one. The emitted
# lemma is `lemma t_refutation_certificate()` with exactly one ensures
# clause, no requires, no decreases, no comment, no string, no attribute,
# and the file around it declares only unmodified functions, methods and
# lemmas: verifiers/dafny.py reads that shape back off the kernel's own
# --rprint of the file and refuses any certificate outside it (a requires
# clause would be an assumed fact), so this is the whole vocabulary a
# certificate-carrying file may use.

CERT_NAME = "t_refutation_certificate"
_UNROLL_CAP = 64
_HOIST_CAP = 256
_LADDER_CAP = 64
TRUE = {"bool": True}

_ARITH = {"+": lambda a, b: a + b, "-": lambda a, b: a - b,
          "*": lambda a, b: a * b, "==": lambda a, b: a == b,
          "!=": lambda a, b: a != b, "<": lambda a, b: a < b,
          "<=": lambda a, b: a <= b, ">": lambda a, b: a > b,
          ">=": lambda a, b: a >= b}


def _not(e: dict) -> dict:
    return {"op": "not", "args": [e]}


_RAT_TEXT = __import__("re").compile(r"^-?\d+/\d+$")   # interp._j's rendering of a Fraction


def _tlit(v, ty=None):
    """A measured witness value as a t literal expression. Negative ints
    become neg nodes so they emit parenthesized, `(-1)`, and never fuse
    with a preceding operator. `ty` is the value's own t type when the
    caller knows it (a task's param or return type); it matters for a
    pair (SPEC.md "Pairs", 2026-09-10): interp._j renders a Pair as a plain
    2-list, indistinguishable BY SHAPE from a same-length seq of ints (a
    divmod_pair witness's `r` and a 2-element seq witness both arrive here
    as `[a, b]` with a and b plain ints), so a pair-typed value MUST be
    built from `ty`, never guessed from the Python shape, on pain of
    silently naming it a seq (see `_certificate`'s seq_names guard, same
    fix); and for a nested seq (SPEC.md "Nested sequences", 2026-09-10), a
    problem one level down from the same shape ambiguity: an EMPTY nested
    seq (zero rows) and an EMPTY flat seq are both the Python value `[]`,
    so swap_rows's own witness m=[[]] (ONE empty row, not zero rows) needs
    `ty` to be told apart from a same-shaped flat seq, and is tagged
    `_seq2` rather than `_seq` so `_name_seqs`/`_certificate` never
    conflate the two kinds of seq name. Every other case is still inferred
    from shape alone, unchanged, because int/bool/flat-seq values never
    lie about their shape the way a pair or a nested seq's row count
    does."""
    if isinstance(v, interp.Ctor):
        # SPEC.md "Datatypes (v1)" (2026-09-27): a raw interp.Ctor (from
        # this file's own `_ev` mirror, not from a witness dict) is
        # unmistakable by its Python type, exactly as interp.Pair is for
        # the pair case just below -- needs no `ty` at all.
        return {"ctor": {"dtype": v.dtype, "name": v.ctor,
                         "args": [_tlit(a) for a in v.args]}}
    if isinstance(v, interp.MapV):
        # SPEC.md "Maps (v1)" (2026-10-06): a raw runtime map, unmistakable by its class; its display
        kt, vt = (ty["map"] if isinstance(ty, dict) and "map" in ty else (None, None))
        return {"op": "mapdisp", "args": [x for k, vv in v.items for x in (_tlit(k, kt), _tlit(vv, vt))]}
    if isinstance(ty, dict) and "map" in ty:
        # a map-typed witness arrives as interp._j's list of [key, value] pairs
        kt, vt = ty["map"]
        return {"op": "mapdisp", "args": [x for kv in v for x in (_tlit(kv[0], kt), _tlit(kv[1], vt))]}
    if isinstance(ty, dict):
        if "pair" in ty:
            t1, t2 = ty["pair"]
            return {"op": "pair", "args": [_tlit(v[0], t1), _tlit(v[1], t2)]}
        if "tuple" in ty:
            # SPEC.md "Compositional types (v1)" (2026-10-06): a tuple's witness arrives as the list of its
            # components (interp._j), each rebuilt from its own component type.
            return {"op": "tuple", "args": [_tlit(c, t) for c, t in zip(v, ty["tuple"])]}
        if "set" in ty:
            # a set of a compound type: its sorted list of elements, each rebuilt from the element type
            return {"op": "set", "args": [_tlit(x, ty["set"]) for x in v]}
        if "seq" in ty and ty != {"seq": "seq"}:
            # a seq of any element type but the two the shape-guessing below already tells apart
            return {"op": "seq", "args": [_tlit(x, ty["seq"]) for x in v]}
        if "datatype" in ty:
            # SPEC.md "Datatypes (v1)" (2026-09-27): interp._j renders a
            # Ctor value as "Dtype.Ctor" (v1's nullary constructors carry
            # no fields to show), so, like a pair, the value is rebuilt
            # from `ty` rather than guessed: a bare string has no other
            # shape it could be confused with here (int/bool/seq/set/pair
            # witnesses never arrive as a "Name.Name" string).
            dtype = ty["datatype"]
            if isinstance(v, str) and v.startswith(dtype + "."):
                return {"ctor": {"dtype": dtype, "name": v[len(dtype) + 1:],
                                "args": []}}
            raise ValueError(f"witness value {v!r} is not a {dtype} constructor")
        return {"_seq2": tuple(tuple(row) for row in v)}
    if ty == "set" or isinstance(v, frozenset):
        # SPEC.md "Finite sets" (2026-09-27): interp._j shows a set as its
        # sorted list, the same shape as a seq, so a set-typed name is built
        # from `ty` as a pair is; tagged `_set` so `_name_seqs`/`_certificate`
        # bind it `set<int>` and never as a seq.
        return {"_set": tuple(sorted(v))}
    if isinstance(v, interp.Fraction):
        # SPEC.md "Exact rationals (v1)" (2026-10-06): a rational witness as the literal, its sign carried
        return {"rat": [v.numerator, v.denominator]}
    if isinstance(v, str) and _RAT_TEXT.match(v):
        # interp._j's rendering of a real ("n/d"): no other witness value is a string of this shape (a datatype
        # value renders as "Name.Name"), so the type need not be known here
        n, d = v.split("/")
        return {"rat": [int(n), int(d)]}
    if isinstance(v, bool):
        return {"bool": v}
    if ty == "real" and isinstance(v, int) and not isinstance(v, bool):
        return {"rat": [v, 1]}   # an int-valued real (sum of an empty seq<real> is 0) in a real-typed slot
    if isinstance(v, int):
        return {"int": v} if v >= 0 else {"op": "neg", "args": [{"int": -v}]}
    if isinstance(v, list) and all(
            isinstance(x, int) and not isinstance(x, bool) for x in v):
        return {"_seq": list(v)}
    raise ValueError(f"witness value {v!r} has no t literal")


def subst(e: dict, m: dict) -> dict:
    """Capture-avoiding substitution over a t expression: each mapped name
    is replaced by a whole t expression (dict). Carried here rather than
    imported from lower_verus.py, like lower_spark.py and lower_lean.py
    carry their own, so a verus-side change to literal typing can never
    silently change what this column certifies."""
    if "rat" in e:
        return e                                            # a real literal (SPEC.md "Exact rationals", 2026-10-06)
    if "var" in e:
        v = m.get(e["var"])
        return e if v is None else v
    if "int" in e or "bool" in e or "_seq" in e or "_seq2" in e or "_set" in e:
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
    if "comp" in e:
        # SPEC.md "Comprehensions (v1)" (2026-10-06): the bound variable scopes over cond and body
        c = e["comp"]
        inner = {k: v for k, v in m.items() if k != c["var"]}
        out = {"var": c["var"], "cond": subst(c["cond"], inner), "body": subst(c["body"], inner)}
        if "seq" in c:
            out["seq"] = subst(c["seq"], m)
        else:
            out["lo"], out["hi"] = subst(c["lo"], m), subst(c["hi"], m)
        return {"comp": out}
    if "ctor" in e:
        c = e["ctor"]
        return {"ctor": {"dtype": c["dtype"], "name": c["name"],
                         "args": [subst(a, m) for a in c.get("args", [])]}}
    if "match" in e:
        mm = e["match"]
        return {"match": {
            "scrutinee": subst(mm["scrutinee"], m),
            "arms": [{"ctor": a["ctor"], "binders": a.get("binders", []),
                      "body": subst(a["body"],
                                   {k: v for k, v in m.items()
                                    if k not in a.get("binders", [])})}
                     for a in mm["arms"]]}}
    return {"op": e["op"], "args": [subst(a, m) for a in e.get("args", [])]}


def _conj(parts: list) -> dict:
    parts = [p for p in parts if p != TRUE]
    if not parts:
        return TRUE
    if len(parts) == 1:
        return parts[0]
    return {"op": "and", "args": parts}


FALSE = {"bool": False}


def _nary(op: str, args: list) -> dict:
    """An and/or node over `args`, minus the operands that cannot change
    its value (a true conjunct, a false disjunct)."""
    unit = TRUE if op == "and" else FALSE
    args = [a for a in args if a != unit]
    if not args:
        return unit
    return args[0] if len(args) == 1 else {"op": op, "args": args}


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


def _set_ev(op: str, vs: list):
    """The six set operations on already-evaluated operands (SPEC.md "Finite
    sets", 2026-09-27), mirroring interp.ev; a set operand that arrived as
    a witness's sorted list is read as the set it shows."""
    def as_set(v):
        return v if isinstance(v, frozenset) else frozenset(v)
    if op == "set":
        return frozenset(vs)
    if op == "in":
        return vs[0] in as_set(vs[1])
    if op == "card":
        return len(as_set(vs[0]))
    a, b = as_set(vs[0]), as_set(vs[1])
    return a | b if op == "union" else (a & b if op == "inter" else a - b)


def _key(v):
    """A type-tagged hashable form of a value (True and 1 stay distinct)."""
    if isinstance(v, bool):
        return ("bool", v)
    if isinstance(v, list):
        return ("seq", tuple(v))
    return ("int", v)


def _ev(e: dict, env: dict, funs: dict, st, facts: dict, hoist):
    """Evaluate a t expression under SPEC.md semantics (the dispatch mirrors
    interp.ev) and return (e2, value), where e2 is e with every operand the
    evaluation never reached removed. With `hoist` a list, each removal's
    deciding fact is appended to it (the pruning step of the certificate
    section); with `hoist` None (inside spec_fun bodies) only the value is
    meaningful. Every spec_fun call evaluated is recorded in `facts`,
    callees before callers, for the assert ladder. This evaluator is a
    hint supplier, never an oracle: every value it produces is re-proved by
    the kernel, so an error here can lose a certificate, not fake one."""
    st.tick()
    if "int" in e:
        return e, e["int"]
    if "rat" in e:
        return e, interp.Fraction(e["rat"][0], e["rat"][1])
    if "bool" in e:
        return e, e["bool"]
    if "_seq" in e:
        return e, list(e["_seq"])
    if "_seq2" in e:
        return e, [list(row) for row in e["_seq2"]]
    if "_set" in e:
        return e, frozenset(e["_set"])
    if "var" in e:
        if e["var"] not in env:
            raise interp.Undef(f"unbound {e['var']}")
        return e, env[e["var"]]
    if "ite" in e:
        c = e["ite"]
        ce, cv = _ev(c["cond"], env, funs, st, facts, hoist)
        if hoist is not None:
            hoist.append(ce if cv else _not(ce))
        return _ev(c["then"] if cv else c["else"], env, funs, st, facts,
                   hoist)
    if "ctor" in e:
        # SPEC.md "Datatypes (v1)" (2026-09-27): eager, like `pair` --
        # defined iff every field argument is (always vacuously true this
        # landing, `args` is always empty).
        c = e["ctor"]
        pairs = [_ev(a, env, funs, st, facts, hoist) for a in c.get("args", [])]
        pruned = {"ctor": {"dtype": c["dtype"], "name": c["name"],
                           "args": [x for x, _ in pairs]}}
        return pruned, interp.Ctor(c["dtype"], c["name"],
                                   tuple(v for _, v in pairs))
    if "match" in e:
        # Non-strict, like `ite`: only the chosen arm's body is evaluated,
        # and (with `hoist` a list) the fact "the scrutinee took THIS
        # constructor" is hoisted so the emitted lemma re-derives the same
        # branch a kernel would otherwise have to re-decide from nothing --
        # exactly what `ite`'s own guard hoist does one line up.
        m = e["match"]
        se, sv = _ev(m["scrutinee"], env, funs, st, facts, hoist)
        for a in m["arms"]:
            if a["ctor"] == sv.ctor:
                if hoist is not None:
                    hoist.append({"op": "==", "args": [
                        se, {"ctor": {"dtype": sv.dtype, "name": sv.ctor,
                                     "args": []}}]})
                sub = dict(env)
                for bname, fv in zip(a.get("binders", []), sv.args):
                    sub[bname] = fv
                return _ev(a["body"], sub, funs, st, facts, hoist)
        raise interp.Undef(f"match: no arm for constructor {sv.ctor!r}")
    if "comp" in e:
        # SPEC.md "Comprehensions (v1)": evaluated as interp does; a certificate unrolls it first (`_unroll`)
        if hoist is not None:
            raise ValueError("comprehension survived unrolling")
        c = e["comp"]
        if "seq" in c:
            src = _ev(c["seq"], env, funs, st, facts, None)[1]
        else:
            lo = _ev(c["lo"], env, funs, st, facts, None)[1]
            hi = _ev(c["hi"], env, funs, st, facts, None)[1]
            if hi - lo > interp.MAX_RANGE:
                raise interp.Budget("comprehension range")
            src = tuple(range(lo, hi))
        vals = []
        for x in src:
            sub = dict(env)
            sub[c["var"]] = x
            if _ev(c["cond"], sub, funs, st, facts, None)[1] is True:
                vals.append(_ev(c["body"], sub, funs, st, facts, None)[1])
        return e, tuple(vals)
    if "forall" in e or "exists" in e:
        if hoist is not None:
            raise ValueError("quantifier survived unrolling")
        kind = "forall" if "forall" in e else "exists"
        q = e[kind]
        lo = _ev(q["lo"], env, funs, st, facts, None)[1]
        hi = _ev(q["hi"], env, funs, st, facts, None)[1]
        if hi - lo > interp.MAX_RANGE:
            raise interp.Budget("quantifier range")
        acc = kind == "forall"
        for i in range(lo, hi):
            sub = dict(env)
            sub[q["var"]] = i
            v = _ev(q["body"], sub, funs, st, facts, None)[1]
            acc = (acc and v) if kind == "forall" else (acc or v)
        return e, bool(acc)
    if "call" in e:
        c = e["call"]
        f = funs.get(c["fun"])
        if f is None or "_exec" in f:
            raise interp.Undef(f"no spec_fun {c['fun']}")
        pairs = [_ev(a, env, funs, st, facts, hoist) for a in c["args"]]
        args = [v for _, v in pairs]
        if len(args) != len(f["params"]):
            raise ValueError(f"{c['fun']}: {len(args)} args for "
                             f"{len(f['params'])} params")
        sub = {p["name"]: a for p, a in zip(f["params"], args)}
        st.d += 1
        if st.d > interp.MAX_DEPTH:
            st.d -= 1
            raise interp.Budget("spec_fun depth")
        try:
            v = _ev(f["body"], sub, funs, st, facts, None)[1]
        finally:
            st.d -= 1
        facts.setdefault((c["fun"], tuple(_key(a) for a in args)), v)
        return {"call": {"fun": c["fun"], "args": [x for x, _ in pairs]}}, v
    op = e["op"]
    args = e.get("args", [])
    if op in ("and", "or"):
        stop = op == "or"          # and stops at False, or stops at True
        kept = []
        for i, a in enumerate(args):
            ae, av = _ev(a, env, funs, st, facts, hoist)
            kept.append(ae)
            if bool(av) == stop:
                if hoist is not None and i + 1 < len(args):
                    hoist.append(ae if av else _not(ae))
                return _nary(op, kept), stop
        return _nary(op, kept), not stop
    if op == "implies":
        ae, av = _ev(args[0], env, funs, st, facts, hoist)
        if not av:
            if hoist is not None:
                hoist.append(_not(ae))
            return TRUE, True
        be, bv = _ev(args[1], env, funs, st, facts, hoist)
        return {"op": "implies", "args": [ae, be]}, bool(bv)
    pairs = [_ev(a, env, funs, st, facts, hoist) for a in args]
    vs = [v for _, v in pairs]
    out = {"op": op, "args": [x for x, _ in pairs]}
    if op == "neg":
        return out, -vs[0]
    if op == "not":
        return out, not vs[0]
    if op in ("mapdisp", "keys", "remove") or (op in ("in", "len", "at", "update")
                                               and any(isinstance(v, interp.MapV) for v in vs)):
        return out, _map_ev(op, vs)   # SPEC.md "Maps (v1)" (2026-10-06)
    if op == "len":
        return out, len(vs[0])
    if op == "at":
        s, i = vs
        if not (0 <= i < len(s)):
            raise interp.Undef(f"at index {i} outside [0,{len(s)})")
        return out, s[i]
    if op == "pair":
        # SPEC.md "Pairs" (2026-09-10): defined iff both components are,
        # already true here since vs[0]/vs[1] are already-evaluated values.
        return out, interp.Pair(vs[0], vs[1])
    if op == "tuple":
        # SPEC.md "Compositional types (v1)" (2026-10-06): as the pair, at any arity.
        return out, interp.Tup(tuple(vs))
    if op == "proj":
        return out, vs[0].items[e["args"][1]["int"]]
    if op == "fst":
        return out, vs[0].a if isinstance(vs[0], interp.Pair) else vs[0].items[0]
    if op == "snd":
        return out, vs[0].b if isinstance(vs[0], interp.Pair) else vs[0].items[1]
    if op in ("set", "in", "card", "union", "inter", "diff"):
        # SPEC.md "Finite sets" (2026-09-27): six total operations, the
        # dispatch of interp.ev (a set value is a frozenset there too; a
        # witness's set arrives as its sorted list and is read back here).
        return out, _set_ev(op, vs)
    if op in ("div", "mod"):
        # Same Euclidean law as interp.ev and SPEC.md "Division and modulo":
        # q = x div y, r = x mod y are the unique pair with x == q*y + r and
        # 0 <= r < |y|; y == 0 is undefined, exactly like `at` out of range.
        # On two reals (SPEC.md "Exact rationals") `div` is exact division.
        x, y = vs
        if y == 0:
            raise interp.Undef(f"{op} by zero")
        if isinstance(x, interp.Fraction) or isinstance(y, interp.Fraction):
            return out, interp.Fraction(x) / interp.Fraction(y)
        r = x % abs(y)
        return out, (r if op == "mod" else (x - r) // y)
    if op in _LIB_INT:
        return out, _lib_value(op, vs)   # SPEC.md "The library (v1)" (2026-10-06)
    if op == "toreal":
        return out, interp.Fraction(vs[0])
    if op == "floor":
        return out, interp.math.floor(vs[0])
    if op == "ceil":
        return out, interp.math.ceil(vs[0])
    if op in _ARITH:
        return out, _ARITH[op](vs[0], vs[1])
    if op == "seq":
        return out, list(vs)
    if op == "slice":
        s, lo, hi = vs
        if not (0 <= lo <= hi <= len(s)):
            raise interp.Undef(f"slice [{lo}..{hi}] outside [0,{len(s)}]")
        return out, s[lo:hi]
    if op == "update":
        s, i, x = vs
        if not (0 <= i < len(s)):
            raise interp.Undef(f"update index {i} outside [0,{len(s)})")
        return out, s[:i] + [x] + s[i + 1:]
    if op == "fill":
        n, x = vs
        if n < 0:
            raise interp.Undef(f"fill length {n} < 0")
        return out, [x] * n
    sv = _strlib_ev(op, vs)
    if sv is not None:
        return out, sv
    raise ValueError(f"t has no operator {op!r}")


# SPEC.md "The string library (v1)" (2026-09-11): every member is total (no
# undefined case), so `_strlib_ev` below never raises -- unlike `at`/`div`/
# `update`/`fill` above, which do -- and it delegates to interp.py's own
# `_str_*` helpers (already the ground truth `test_strlib.py`'s parity test
# measures against Python's real `str` methods), converting this file's
# list-of-int/list-of-list-of-int representation to interp.py's tuple-of-
# int/tuple-of-tuple-of-int and back, so the certificate machinery's notion
# of "count"/"split"/etc. is the SAME computation the kernel is being asked
# to verify, never a second, independently-written implementation that
# could silently disagree with it (SPEC.md: "parity is by construction").
# `split`'s arity (1 or 2 args) is the one shape-dependent case; every
# other member takes a fixed arity.
_STRLIB_ARITY1 = {
    "tostr": interp._str_tostr,
    "strip": lambda s: interp._str_strip(s, True, True),
    "lstrip": lambda s: interp._str_strip(s, True, False),
    "rstrip": lambda s: interp._str_strip(s, False, True),
    "lower": interp._str_lower, "upper": interp._str_upper,
    "isdigit": interp._str_isdigit, "isalpha": interp._str_isalpha,
    "isupper": interp._str_isupper, "islower": interp._str_islower,
}
_STRLIB_ARITY2 = {
    "join": lambda rows, sep: interp._str_join(
        tuple(tuple(r) for r in rows), tuple(sep)),
    "count": lambda s, t: interp._str_count(tuple(s), tuple(t)),
    "find": lambda s, t: interp._str_find(tuple(s), tuple(t)),
    "startswith": lambda s, t: interp._str_startswith(tuple(s), tuple(t)),
    "endswith": lambda s, t: interp._str_endswith(tuple(s), tuple(t)),
}


def _to_seq_ret(v):
    """A tuple result from an interp._str_* helper back to this file's list
    representation; an int/bool result is returned unchanged."""
    return list(v) if isinstance(v, tuple) else v


def _strlib_ev(op: str, vs: list):
    """Evaluate a v1 string-library op over already-evaluated argument
    values `vs` (this file's list representation), or None for a non-
    string-library op (never a genuine string-library result: every member
    returns an int, a bool, or a seq/seq-of-seq, none of which is Python
    `None`)."""
    if op == "split":
        if len(vs) == 1:
            return [list(row) for row in interp._str_split_ws(tuple(vs[0]))]
        s, c = vs
        return [list(row) for row in interp._str_split_sep(tuple(s), c)]
    if op == "replace":
        s, t, u = vs
        return list(interp._str_replace(tuple(s), tuple(t), tuple(u)))
    if op in _STRLIB_ARITY1:
        return _to_seq_ret(_STRLIB_ARITY1[op](tuple(vs[0])))
    if op in _STRLIB_ARITY2:
        return _to_seq_ret(_STRLIB_ARITY2[op](vs[0], vs[1]))
    return None


def _gint(e: dict, funs: dict, st) -> int:
    """Ground int value of a quantifier bound after witness substitution.
    Strict: a non-int (or a bool) refuses the certificate."""
    v = _ev(e, {}, funs, st, {}, None)[1]
    if isinstance(v, bool) or not isinstance(v, int):
        raise ValueError(f"quantifier bound not an int: {e!r}")
    return v


def _unroll(e: dict, funs: dict, st, budget: list, bounds: list) -> dict:
    """Replace bounded quantifiers (ground bounds) with finite conjunctions
    or disjunctions. `budget` is a one-element countdown over emitted
    instances; exhausting it raises and the certificate is refused. Each
    bound's value is recorded in `bounds` as an equation the kernel
    re-proves (step 1 of the certificate section)."""
    if "comp" in e:
        # SPEC.md "Comprehensions (v1)" (2026-10-06): a ground comprehension becomes the display it denotes, one
        # `(if cond then [body] else [])` per element, so the kernel checks every instance and no recursive
        # function has to be unfolded; the source's value is recorded as an equation the kernel re-proves
        c = e["comp"]
        if "seq" in c:
            src_e = _unroll(c["seq"], funs, st, budget, bounds)
            src = _ev(src_e, {}, funs, st, {}, None)[1]
            lit = _tlit(src)
            if src_e != lit:
                bounds.append({"op": "==", "args": [src_e, lit]})
            elems = list(src)
        else:
            lo_e = _unroll(c["lo"], funs, st, budget, bounds)
            hi_e = _unroll(c["hi"], funs, st, budget, bounds)
            lo, hi = _gint(lo_e, funs, st), _gint(hi_e, funs, st)
            for b_e, b_v in ((lo_e, lo), (hi_e, hi)):
                if b_e != _tlit(b_v):
                    bounds.append({"op": "==", "args": [b_e, _tlit(b_v)]})
            elems = list(range(lo, hi))
        insts = []
        for x in elems:
            budget[0] -= 1
            if budget[0] < 0:
                raise ValueError("comprehension unroll budget exhausted")
            m = {c["var"]: _tlit(x)}
            inst = {"ite": {"cond": subst(c["cond"], m), "then": {"op": "seq", "args": [subst(c["body"], m)]},
                            "else": {"op": "seq", "args": []}}}
            insts.append(_unroll(inst, funs, st, budget, bounds))
        if not insts:
            return {"op": "seq", "args": []}
        return _nary("+", insts) if len(insts) > 1 else insts[0]
    if "comp" in e:
        # SPEC.md "Comprehensions (v1)": the source defined, cond at every element, body where cond holds
        c = e["comp"]
        if "seq" in c:
            src = _ev_undef(c["seq"], env, funs, st)
        else:
            lo = _ev_undef(c["lo"], env, funs, st)
            hi = _ev_undef(c["hi"], env, funs, st)
            if hi - lo > interp.MAX_RANGE:
                raise interp.Budget("comprehension range")
            src = tuple(range(lo, hi))
        vals = []
        for x in src:
            sub = dict(env)
            sub[c["var"]] = x
            if _ev_undef(c["cond"], sub, funs, st) is True:
                vals.append(_ev_undef(c["body"], sub, funs, st))
        return tuple(vals)
    if "forall" in e or "exists" in e:
        kind = "forall" if "forall" in e else "exists"
        q = e[kind]
        lo_e = _unroll(q["lo"], funs, st, budget, bounds)
        hi_e = _unroll(q["hi"], funs, st, budget, bounds)
        lo, hi = _gint(lo_e, funs, st), _gint(hi_e, funs, st)
        for b_e, b_v in ((lo_e, lo), (hi_e, hi)):
            if b_e != _tlit(b_v):            # a literal bound proves itself
                bounds.append({"op": "==", "args": [b_e, _tlit(b_v)]})
        insts = []
        for k in range(lo, hi):
            budget[0] -= 1
            if budget[0] < 0:
                raise ValueError("quantifier unroll budget exhausted")
            insts.append(_unroll(subst(q["body"], {q["var"]: _tlit(k)}),
                                 funs, st, budget, bounds))
        if not insts:
            return {"bool": kind == "forall"}
        return _nary("and" if kind == "forall" else "or", insts)
    if "ite" in e:
        c = e["ite"]
        return {"ite": {"cond": _unroll(c["cond"], funs, st, budget, bounds),
                        "then": _unroll(c["then"], funs, st, budget, bounds),
                        "else": _unroll(c["else"], funs, st, budget, bounds)}}
    if "ctor" in e:
        c = e["ctor"]
        return {"ctor": {"dtype": c["dtype"], "name": c["name"],
                         "args": [_unroll(a, funs, st, budget, bounds)
                                  for a in c.get("args", [])]}}
    if "match" in e:
        m = e["match"]
        return {"match": {
            "scrutinee": _unroll(m["scrutinee"], funs, st, budget, bounds),
            "arms": [{"ctor": a["ctor"], "binders": a.get("binders", []),
                      "body": _unroll(a["body"], funs, st, budget, bounds)}
                     for a in m["arms"]]}}
    if "call" in e:
        c = e["call"]
        return {"call": {"fun": c["fun"],
                         "args": [_unroll(a, funs, st, budget, bounds)
                                  for a in c["args"]]}}
    if "op" in e:
        return {"op": e["op"],
                "args": [_unroll(a, funs, st, budget, bounds)
                         for a in e.get("args", [])]}
    return e


def _name_seqs(e: dict, names: dict, used: dict,
               nnames: dict, nused: dict, snames: dict = None, sused: dict = None) -> dict:
    """Replace every seq literal by the witness name bound to that value
    (see the certificate section: `[]` needs a typed binding). `_seq`
    (flat) and `_seq2` (nested, SPEC.md "Nested sequences", 2026-09-10)
    are looked up in separate name tables (`names`/`nnames`): a flat and a
    nested witness can both be empty, the same `()` key, so keeping them
    in one table would let a flat name answer for a nested literal or vice
    versa, the exact conflation `_tlit`'s own two tags exist to prevent. A
    value with no name in its own table refuses the certificate
    (KeyError)."""
    if "_seq" in e:
        key = tuple(e["_seq"])
        used[key] = names[key]
        return {"var": names[key]}
    if "_seq2" in e:
        key = e["_seq2"]
        nused[key] = nnames[key]
        return {"var": nnames[key]}
    if "_set" in e:
        # SPEC.md "Finite sets" (2026-09-27): a set witness value gets its
        # own typed binding (`set<int>`) from its own table, as a nested seq
        # does, so `{}` and `[]` never answer for each other.
        key = e["_set"]
        if snames is None or key not in snames:
            raise KeyError(("set", key))
        sused[key] = snames[key]
        return {"var": snames[key]}
    if "ite" in e:
        c = e["ite"]
        return {"ite": {"cond": _name_seqs(c["cond"], names, used, nnames, nused, snames, sused),
                        "then": _name_seqs(c["then"], names, used, nnames, nused, snames, sused),
                        "else": _name_seqs(c["else"], names, used, nnames, nused, snames, sused)}}
    if "ctor" in e:
        c = e["ctor"]
        return {"ctor": {"dtype": c["dtype"], "name": c["name"],
                         "args": [_name_seqs(a, names, used, nnames, nused, snames, sused)
                                  for a in c.get("args", [])]}}
    if "match" in e:
        m = e["match"]
        return {"match": {
            "scrutinee": _name_seqs(m["scrutinee"], names, used, nnames, nused, snames, sused),
            "arms": [{"ctor": a["ctor"], "binders": a.get("binders", []),
                      "body": _name_seqs(a["body"], names, used, nnames, nused, snames, sused)}
                     for a in m["arms"]]}}
    if "call" in e:
        c = e["call"]
        return {"call": {"fun": c["fun"],
                         "args": [_name_seqs(a, names, used, nnames, nused, snames, sused)
                                  for a in c["args"]]}}
    if "op" in e:
        return {"op": e["op"],
                "args": [_name_seqs(a, names, used, nnames, nused, snames, sused)
                         for a in e.get("args", [])]}
    return e


def _seq_op_rungs(e: dict, funs: dict, st) -> list[tuple[dict, list]]:
    """Every seq-typed ground operator subterm of a pruned certificate
    formula, innermost first, paired with the interpreter's value (a flat
    list of ints): the rungs step 3's 2026-09-27 note describes. Calls are
    not listed (the facts ladder states them), nor `seq` displays (already
    the kernel's own literal shape), nor a subterm the evaluator cannot
    value (skipped, not refused: a missing rung can only lose the
    certificate). A subterm the evaluation never reached is absent from a
    pruned formula, so nothing here evaluates an untaken branch."""
    out: list = []
    seen: set = set()

    def walk(n: dict) -> None:
        if "call" in n:
            for a in n["call"]["args"]:
                walk(a)
            return
        if "op" not in n:
            return
        for a in n.get("args", []):
            walk(a)
        if n["op"] == "seq":
            return
        try:
            v = _ev(n, {}, funs, st, {}, None)[1]
        except (ValueError, KeyError, TypeError, IndexError, interp.Undef,
                interp.Budget, RecursionError):
            return
        if not (isinstance(v, list) and all(
                isinstance(x, int) and not isinstance(x, bool) for x in v)):
            return
        key = json.dumps(n, sort_keys=True)
        if key not in seen:
            seen.add(key)
            out.append((n, v))

    walk(e)
    return out


def seq_ladder(formula: dict, funs: dict) -> list[tuple[dict, list]]:
    """The seq rungs of a ground certificate formula, for a column that
    carries no ladder of its own (lower_fstar.py): every seq-valued
    spec_fun call the formula's evaluation reaches, callees before callers
    as `_ev` records them, each as a call node over literal arguments, then
    `_seq_op_rungs` over the pruned formula; each paired with the value the
    kernel is asked to re-prove. Empty when the evaluation reaches no
    seq-valued call, so a column that consults it emits nothing new for a
    task without one (every committed lowering before double_all). Raises
    what `_ev` raises; the caller reads that as "no rungs"."""
    st = interp.St()
    facts: dict = {}
    pruned, _ = _ev(formula, {}, funs, st, facts, [])
    if not any(isinstance(v, list) for v in facts.values()):
        return []
    rungs: list = []
    for (fn, keys), v in facts.items():
        if not isinstance(v, list):
            continue
        args = [{"_seq": list(k)} if tag == "seq" else _tlit(k)
                for tag, k in keys]
        rungs.append(({"call": {"fun": fn, "args": args}}, v))
    return rungs + _seq_op_rungs(pruned, funs, st)
def _set_lit(v: tuple) -> str:
    """A set witness's own Dafny literal under a `set<int>` binding: the
    display of its sorted elements, `{}` for the empty set (typed by the
    binding, so the bare display is fine here)."""
    return "{" + ", ".join(str(x) for x in v) + "}"


def _seq_lit(v: tuple) -> str:
    return "[" + ", ".join(str(x) for x in v) + "]"


def _nseq_lit(v: tuple) -> str:
    """A nested-seq witness's own literal: `_seq_lit` one level up, since
    each row is itself a flat int tuple that `_seq_lit` already renders,
    so `((), (0,))` prints `[[], [0]]`, not `[(), (0,)]`."""
    return "[" + ", ".join(_seq_lit(row) for row in v) + "]"


# ------------------------------------------------- "undefined"-kind witness
# Added 2026-09-09 (SPEC.md "Sequences as values"). The value/exit kinds
# above certify that the ensures conjunction, or the loop-exit obligation,
# comes out FALSE at a ground point. A `_kind == "undefined"` witness
# (harness.py's interp.Reference.witness) is a different shape: the real
# body has a value at the witness input and the twin's does not, because the
# twin's own body hits a definedness obligation (`at`/`update`'s index
# bound, `fill`'s length, `div`/`mod`'s nonzero divisor) unconditionally on
# the taken path. Nothing upstream records WHICH node failed or what its
# guard was, only interp.Undef's message string, so this replays the twin's
# straight-line statements under the witness's concrete values (mirroring
# interp.ev/exec_body exactly) and, instead of raising Undef, raises
# _DefViol carrying the guard as a ground t Expr built from the concrete
# values already in hand: no symbolic reasoning, no unrolling needed, since
# every operand is a literal by construction. Its negation is the certified
# theorem. This is the same treatment `div`/`mod` and `at` get everywhere
# else in this file (Dafny's own well-formedness checking discharges the
# guard in the MAIN run), turned into the ground fact the CERTIFICATE run
# needs, because for this witness kind the main run's exit 4 is a real
# well-formedness violation, not incompleteness, and a ground point makes
# that provable instead of merely observed.
#
# Scope (widened 2026-09-10, nested-sequences residual fz_v1nested_069/150:
# see the dated note below): `var`, `assign`, `return`, `if` AND `while` are
# all replayed. A `while` is exactly as replayable as `interp.exec_body`'s:
# the witness is fully ground (every name in `env` is already a concrete
# value, no symbolic state anywhere), so stepping the condition and body
# with `_ev_undef`/`_exec_undef` themselves, capped at `interp.MAX_LOOP`
# the same way `interp.exec_body` caps it (`interp.Budget`, caught by
# `_certificate`'s outer except same as any other refusal), replays a loop
# no differently than a straight-line run of the same length would. `if`
# and `while` both propagate a `return`'s early exit (the bool
# `_exec_undef` returns, mirroring `interp.exec_body`'s flag) so a
# definedness violation after an early `return` is never replayed past it.
# A spec_fun call or quantifier inside the body still aborts (ValueError,
# caught below): nothing here claims those, only what interp.ev already
# agrees is a plain arithmetic/seq operator or a `while`/`if`/`return`.

class _DefViol(Exception):
    """The definedness obligation that failed during `_exec_undef`'s replay
    of a twin body, as a ground guard Expr (no free variables): the
    condition that SHOULD have held. Its negation, once proved, is the
    refutation certificate's ground fact."""

    def __init__(self, guard: dict):
        self.guard = guard


def _ev_undef(e: dict, env: dict, funs: dict, st):
    """Mirror of interp.ev, raising _DefViol (not interp.Undef) at at's,
    update's, fill's and div/mod's own definedness obligations, with the
    guard built from the concrete values already computed. Every other node
    is evaluated exactly as interp.ev evaluates it; a shape interp.ev has no
    case for is not this mirror's to invent either, so it raises ValueError
    (caught by _certificate's outer except) rather than guess."""
    st.tick()
    if "int" in e:
        return e["int"]
    if "rat" in e:
        return interp.Fraction(e["rat"][0], e["rat"][1])
    if "bool" in e:
        return e["bool"]
    if "var" in e:
        if e["var"] not in env:
            raise interp.Undef(f"unbound {e['var']}")
        return env[e["var"]]
    if "ite" in e:
        c = e["ite"]
        cv = _ev_undef(c["cond"], env, funs, st)
        return _ev_undef(c["then"] if cv else c["else"], env, funs, st)
    if "forall" in e or "exists" in e:
        raise ValueError("undefined-kind certificate: quantifier in body")
    if "call" in e:
        # 2026-09-28: a spec_fun call no longer aborts the replay. Its
        # arguments go through this mirror first, left to right, so an
        # argument's own obligation (`f(s[i])` with i out of range) raises
        # the ground guard exactly as it would outside the call -- the order
        # Dafny's well-formedness checking uses (Reference Manual, well-
        # formedness: arguments before the call they feed). The call's value
        # then comes from interp.ev on the ground arguments; a spec_fun body
        # is total by check_wf, so an interp.Undef here is a refusal of the
        # certificate (ValueError, caught by _certificate), never a guard.
        c = e["call"]
        f = funs.get(c["fun"])
        if f is None or len(c["args"]) != len(f["params"]):
            raise ValueError(f"undefined-kind certificate: call {c['fun']!r} unknown or mis-arity")
        vals = [_ev_undef(a, env, funs, st) for a in c["args"]]
        ground = {"call": {"fun": c["fun"],
                           "args": [_tlit(v, prm.get("type")) for v, prm in zip(vals, f["params"])]}}
        try:
            return interp.ev(ground, {}, funs, st)
        except interp.Undef as u:
            raise ValueError(f"undefined-kind certificate: call {c['fun']!r} undefined on replay: {u}")
    op = e["op"]
    if op == "and":
        for a in e["args"]:
            if not _ev_undef(a, env, funs, st):
                return False
        return True
    if op == "or":
        for a in e["args"]:
            if _ev_undef(a, env, funs, st):
                return True
        return False
    if op == "implies":
        return (not _ev_undef(e["args"][0], env, funs, st)
                or bool(_ev_undef(e["args"][1], env, funs, st)))
    a = [_ev_undef(x, env, funs, st) for x in e["args"]]
    if op == "neg":
        return -a[0]
    if op == "not":
        return not a[0]
    if op == "at" and isinstance(a[0], interp.MapV):
        # SPEC.md "Maps (v1)" (2026-10-06): m[k] owes k in m; the guard is the ground membership
        if not a[0].has(a[1]):
            raise _DefViol({"op": "in", "args": [_tlit(a[1]), _tlit(a[0])]})
        return a[0].get(a[1])
    if op in ("mapdisp", "keys", "remove") or (op in ("in", "len", "update")
                                               and any(isinstance(v, interp.MapV) for v in a)):
        return _map_ev(op, a)
    if op == "len":
        return len(a[0])
    if op == "at":
        s, i = a
        if not (0 <= i < len(s)):
            raise _DefViol({"op": "and", "args": [
                {"op": "<=", "args": [{"int": 0}, _tlit(i)]},
                {"op": "<", "args": [_tlit(i), {"int": len(s)}]}]})
        return s[i]
    if op == "update":
        s, i, v = a
        if not (0 <= i < len(s)):
            raise _DefViol({"op": "and", "args": [
                {"op": "<=", "args": [{"int": 0}, _tlit(i)]},
                {"op": "<", "args": [_tlit(i), {"int": len(s)}]}]})
        return s[:i] + [v] + s[i + 1:]
    if op == "fill":
        n, v = a
        if n < 0:
            raise _DefViol({"op": ">=", "args": [_tlit(n), {"int": 0}]})
        return [v] * n
    if op == "seq":
        # [e1, ..., en]: every element already evaluated above (a itself is
        # the list of results), always defined once its elements are, same
        # as interp.ev's "seq" case.
        return list(a)
    if op == "slice":
        # s[a..b]: DEFINED IFF 0 <= a <= b <= len(s), interp.ev's own rule,
        # a three-part guard (at's/update's is two) because the bound is a
        # range, not a single index.
        s, lo, hi = a
        if not (0 <= lo <= hi <= len(s)):
            raise _DefViol({"op": "and", "args": [
                {"op": "<=", "args": [{"int": 0}, _tlit(lo)]},
                {"op": "and", "args": [
                    {"op": "<=", "args": [_tlit(lo), _tlit(hi)]},
                    {"op": "<=", "args": [_tlit(hi), {"int": len(s)}]}]}]})
        return s[lo:hi]
    if op == "+":
        return a[0] + a[1]
    if op == "-":
        return a[0] - a[1]
    if op == "*":
        return a[0] * a[1]
    if op in ("div", "mod"):
        x, y = a
        if y == 0:
            zero = {"rat": [0, 1]} if isinstance(y, interp.Fraction) else {"int": 0}
            raise _DefViol({"op": "!=", "args": [_tlit(y), zero]})
        if isinstance(x, interp.Fraction) or isinstance(y, interp.Fraction):
            return interp.Fraction(x) / interp.Fraction(y)
        r = x % abs(y)
        return r if op == "mod" else (x - r) // y
    if op in _LIB_INT:
        # SPEC.md "The library (v1)" (2026-10-06): pow and isqrt owe `n >= 0`, the rest are total
        if op == "pow" and a[1] < 0:
            raise _DefViol({"op": ">=", "args": [_tlit(a[1]), {"int": 0}]})
        if op == "isqrt" and a[0] < 0:
            raise _DefViol({"op": ">=", "args": [_tlit(a[0]), {"int": 0}]})
        return _lib_value(op, a)
    if op == "toreal":
        return interp.Fraction(a[0])
    if op == "floor":
        return interp.math.floor(a[0])
    if op == "ceil":
        return interp.math.ceil(a[0])
    if op in ("set", "in", "card", "union", "inter", "diff"):
        return _set_ev(op, a)   # SPEC.md "Finite sets": all six total
    if op == "==":
        return a[0] == a[1]
    if op == "!=":
        return a[0] != a[1]
    if op == "<":
        return a[0] < a[1]
    if op == "<=":
        return a[0] <= a[1]
    if op == ">":
        return a[0] > a[1]
    if op == ">=":
        return a[0] >= a[1]
    sv = _strlib_ev(op, a)
    if sv is not None:
        return sv
    raise ValueError(f"t has no operator {op!r}")


def _exec_undef(body: list, env: dict, funs: dict, st) -> bool:
    """Mirror of interp.exec_body: replays var/assign/return/if/while under
    the witness's concrete values, mutating `env` exactly as an actual run
    would, until `_ev_undef` raises _DefViol. Returns True when a `return`
    ended the run (mirrors interp.exec_body's own flag), so an `if` or a
    `while` that reaches a `return` stops the replay there rather than
    falling through to statements a real execution never runs; see the
    section comment above for what is still out of scope (a spec_fun call
    or a quantifier)."""
    for s in body:
        st.tick()
        if "assign" in s:
            name, e = s["assign"]
            env[name] = _ev_undef(e, env, funs, st)
        elif "return" in s:
            name, e = s["return"]
            env[name] = _ev_undef(e, env, funs, st)
            return True
        elif "var" in s:
            d = s["var"]
            env[d["name"]] = _ev_undef(d["init"], env, funs, st)
        elif "if" in s:
            c = s["if"]
            cv = _ev_undef(c["cond"], env, funs, st)
            if _exec_undef(c["then"] if cv else c["else"], env, funs, st):
                return True
        elif "while" in s:
            w = s["while"]
            it = 0
            while _ev_undef(w["cond"], env, funs, st):
                try:
                    if _exec_undef(w["body"], env, funs, st):
                        return True
                except interp.LoopExit as exc:   # SPEC.md "Early exits (v1)" (2026-10-06)
                    if exc.kind == "break":
                        break
                it += 1
                if it > interp.MAX_LOOP:
                    raise interp.Budget("loop cap")
        elif "break" in s or "continue" in s:
            raise interp.LoopExit("break" if "break" in s else "continue")
        elif "lemma" in s:
            pass                  # SPEC.md "Lemmas (v1)": erased at run time
        else:
            raise ValueError(f"t has no statement {s!r}")
    return False


def _scope_types(task: dict) -> dict:
    """Every name a witness dict can carry, mapped to its declared t type:
    params, the return, and every local `var` anywhere in the body. A
    "value"-kind witness only ever carries params (interp.Reference ranges
    over `_names(task)`, params only), but an "exit"/"preservation" witness
    ranges over "everything in scope at the loop, plus the return"
    (harness.py's `_invariant_candidates`), so `reverse` and `filter_pos`
    (SPEC.md "Sequences as values"), whose loop-carried `r` is the return,
    not a param, need the return's type here too, not params alone. Needed
    so `_tlit` can tell a pair-typed value from a same-shaped seq (SPEC.md
    "Pairs", 2026-09-10) no matter which witness kind names it."""
    out = {p["name"]: p["type"] for p in task["params"]}
    out[task["returns"][0]["name"]] = task["returns"][0]["type"]

    def walk(body: list) -> None:
        for s in body:
            if "var" in s:
                out[s["var"]["name"]] = s["var"]["type"]
            elif "if" in s:
                walk(s["if"]["then"])
                walk(s["if"].get("else") or [])
            elif "while" in s:
                walk(s["while"]["body"])
    walk(task["body"])
    return out


def _witness_env(names: dict, types: dict | None = None) -> dict:
    """A witness dict's values as the mirror evaluates them. interp._j renders a real as "n/d" text (SPEC.md
    "Exact rationals", 2026-10-06), which `_ev_undef`'s arithmetic cannot take, and a map as its list of [key,
    value] pairs (SPEC.md "Maps (v1)"), which is rebuilt as a map where `types` says the name is one; every other
    value keeps the shape the mirror already reads (ints, bools, lists for seqs and pairs)."""
    def conv(v, ty=None):
        if isinstance(v, str) and _RAT_TEXT.match(v):
            n, d = v.split("/")
            return interp.Fraction(int(n), int(d))
        if isinstance(ty, dict) and "map" in ty and isinstance(v, list):
            kt, vt = ty["map"]
            return interp.MapV.of([(conv(kv[0], kt), conv(kv[1], vt)) for kv in v])
        if isinstance(v, list):
            return [conv(x) for x in v]
        return v
    return {k: conv(v, (types or {}).get(k)) for k, v in names.items()}


def _certificate(task: dict, twin_body: list, w: dict) -> str | None:
    """The appended t_refutation_certificate lemma for a measured twin
    witness, or None when the witness is not expressible as a ground
    certificate under the rules in the section comment above."""
    kind = w.get("_kind")
    names = {k: v for k, v in w.items() if not k.startswith("_")}
    funs = {f["name"]: f for f in task.get("spec_funs", [])}
    scope_types = _scope_types(task)
    ret_type = task["returns"][0]["type"]
    st = interp.St()
    # A value/exit-kind witness's own RETURN value (SPEC.md "Nested
    # sequences", 2026-09-10, residual fz_v1nested_078/115/606: see the
    # dated note below), gated the same way `ret_extra` names ANY seq or
    # nested-seq value in scope: `interp.Reference.witness` records only
    # PARAMS in `names` (a "value"-kind witness never carries the return,
    # by construction, per `_scope_types`'s own docstring), so a task whose
    # return is seq/nested-seq-typed and whose ensures is falsified by the
    # twin's computed value (nested_lit, concat_nested) had that value
    # substituted straight into the certificate formula with no witness
    # name to bind it to: `_name_seqs` raised KeyError on its own `_seq`/
    # `_seq2` tag (a refusal, not a wrong lowering, but a needless one).
    # Populated only when the return's name is not ALREADY a witness name
    # (true for every "value"-kind witness, and for "exit"-kind always
    # false since `_invariant_candidates` always includes the return in
    # `names`), so this never touches the exit-kind path at all: no risk of
    # binding the SAME Dafny name to two different values in one lemma.
    ret_extra: tuple[str, object] | None = None
    try:
        # scope_types.get(n) is the value's own t type (SPEC.md "Pairs",
        # 2026-09-10): needed so a pair-typed witness value is built as a
        # pair literal rather than guessed as a same-shaped seq (_tlit).
        m = {n: _tlit(v, scope_types.get(n)) for n, v in names.items()}
        if kind == "value":
            if w.get("_ens") is not True:
                return None      # a drift a sound kernel may still accept
            tw = w.get("_twin")
            # SPEC.md "Exact rationals (v1)" (2026-10-06): a real return's value arrives as interp._j's "n/d"
            # text, the one string that is a ground literal here; any other string (a datatype rendering) is not.
            if isinstance(tw, str) and not (ret_type == "real" and _RAT_TEXT.match(tw)):
                return None
            if not isinstance(tw, (bool, int, list, str)):
                return None
            ret_name = task["returns"][0]["name"]
            m2 = dict(m)
            m2[ret_name] = _tlit(tw, ret_type)
            if ret_name not in names:
                ret_extra = (ret_name, tw)
            parts = [subst(rq, m2) for rq in task.get("requires", [])]
            parts.append(_not(_conj([subst(en, m2)
                                     for en in task["ensures"]])))
        elif kind == "exit":
            loop = _twin_loop(task["body"], twin_body)
            if loop is None:
                return None
            # The obligation is at the RETURN: the loop-exit state run
            # through whatever follows the loop (interp.exit_env, None under
            # an enclosing loop). A tail loop runs nothing and the formula
            # is unchanged. Measured 2026-09-07 (ROADMAP 12.5): slow_max
            # assigns z after its loop, and this lemma, stating not-ensures
            # at the loop's own z, minted REFUTED on a twin dafny proves.
            ret = task["returns"][0]["name"]
            post = interp.exit_env(task, twin_body, loop, names)
            if post is None:
                return None
            m2 = dict(m)
            m2[ret] = _tlit(post[ret], ret_type)
            parts = [subst(rq, m) for rq in task.get("requires", [])]
            parts += [subst(iv, m) for iv in loop.get("invariants", [])]
            parts.append(_not(subst(loop["cond"], m)))
            parts.append(_not(_conj([subst(en, m2)
                                     for en in task["ensures"]])))
        elif kind == "undefined" and w.get("_site") == "ensures":
            # ENSURES-LEVEL undefined witness (added 2026-09-11): the
            # violation is in the postcondition itself, not the body, so
            # there is no twin body to replay -- only `_expr`, the
            # offending sub-expression's AST node (an `at`/`slice`/
            # div-or-mod node), evaluated once under
            # the witness's param values with the SAME `_ev_undef` the
            # body-level path already uses. `_ev_undef`'s own at/slice/
            # div/mod cases already build the ground guard and raise
            # `_DefViol`; reusing them here (rather than re-deriving the
            # guard from `_expr`'s shape by hand) is the only way this
            # agrees with the body-level door byte-for-byte. No violation
            # on replay (our mirror disagreeing with interp.py's, or an
            # `_expr` shape `_ev_undef` still abstains on) refuses the
            # certificate rather than guessing, same as the body-level
            # path.
            env = _witness_env(names, scope_types)
            st2 = interp.St()
            try:
                _ev_undef(w["_expr"], env, funs, st2)
            except _DefViol as dv:
                guard = dv.guard
            else:
                return None
            parts = [subst(rq, m) for rq in task.get("requires", [])]
            parts.append(_not(guard))
        elif kind == "undefined":
            # The twin's own body, replayed under the witness (see the
            # section comment above `_DefViol`): the FIRST definedness
            # obligation it hits unconditionally, as a ground guard. No
            # violation on replay (our mirror disagreeing with interp.py's,
            # a loop that exceeds interp.MAX_LOOP, or a quantifier/call the
            # mirror still abstains on) refuses the certificate rather than
            # guessing.
            env = _witness_env(names, scope_types)
            st2 = interp.St()
            try:
                _exec_undef(twin_body, env, funs, st2)
            except _DefViol as dv:
                guard = dv.guard
            else:
                return None
            parts = [subst(rq, m) for rq in task.get("requires", [])]
            parts.append(_not(guard))
        else:
            return None          # preservation: see above
        bounds: list = []
        unrolled = _unroll(_conj(parts), funs, st, [_UNROLL_CAP], bounds)
        facts: dict = {}
        hoist: list = []
        pruned, val = _ev(_conj(bounds + [unrolled]), {}, funs, st, facts,
                          hoist)
        if val is not True:
            return None          # the interpreter itself rejects it
        if len(hoist) > _HOIST_CAP:
            raise ValueError("hoist cap exceeded")
        seen: dict = {}
        for h in hoist + [pruned]:
            seen.setdefault(json.dumps(h, sort_keys=True), h)
        formula = _conj(list(seen.values()))
        raw_formula = formula          # literals inline, for the seq rungs
        seq_names: dict = {}
        nseq_names: dict = {}
        set_names: dict = {}
        for n, v in (list(names.items())
                     + ([ret_extra] if ret_extra is not None else [])):
            # scope_types-gated (SPEC.md "Pairs", 2026-09-10): a pair-typed
            # name whose two components are both plain ints renders the same
            # 2-list shape as a length-2 seq (interp._j), so
            # "isinstance(v, list)" alone would misname its value as a seq
            # witness and bind it `seq<int>` in the emitted lemma, a wrong
            # lowering, not a refusal. Only an actual seq-typed name is
            # named here (params, the return, or a body local, all covered
            # by `_scope_types`); a pair-typed name is left for `_tlit`/
            # `expr` to render as a tuple literal wherever it occurs. A
            # nested-seq-typed name (SPEC.md "Nested sequences",
            # 2026-09-10) is named into its OWN table, `nseq_names`, keyed
            # by a tuple-of-tuples rather than `seq_names`'s tuple-of-ints,
            # so an empty flat seq and an empty nested seq (both `()`
            # shape-wise, one level apart) never collide in one dict.
            t = scope_types.get(n)
            if t == "seq" and isinstance(v, list):
                seq_names.setdefault(tuple(v), n)
            elif t == {"seq": "seq"} and isinstance(v, list):
                nseq_names.setdefault(tuple(tuple(row) for row in v), n)
            elif t == "set" and isinstance(v, (list, frozenset)):
                # SPEC.md "Finite sets" (2026-09-27): its own table, keyed by
                # the sorted tuple `_tlit` tags `_set`.
                set_names.setdefault(tuple(sorted(v)), n)
        used: dict = {}
        nused: dict = {}
        sused: dict = {}
        formula = _name_seqs(formula, seq_names, used, nseq_names, nused, set_names, sused)
        ladder: list[str] = []
        ladder_seqs: dict = {}
        # Step 3's 2026-09-27 note: a seq-valued fact names its result (and
        # any seq argument no witness name carries) with a fresh `t_v<k>`,
        # bound in the lemma body beside the witness seqs; a task with no
        # seq-valued fact takes the older path unchanged (a seq argument
        # with no witness name skips its rung, as before).
        seq_facts = any(isinstance(v, list) for v in facts.values())
        taken = _collect_names(task) if seq_facts else set()
        fresh = [0]

        def seq_name(val: tuple) -> str:
            n = seq_names.get(val)
            if n is None:
                while f"t_v{fresh[0]}" in taken:
                    fresh[0] += 1
                n = f"t_v{fresh[0]}"
                fresh[0] += 1
                seq_names[val] = n
            ladder_seqs[val] = n
            return n

        def name_rung(e: dict) -> dict:
            if "_seq" in e:
                return {"var": seq_name(tuple(e["_seq"]))}
            if "_seq2" in e:
                raise KeyError("nested literal in a seq rung")
            if "call" in e:
                c = e["call"]
                return {"call": {"fun": c["fun"],
                                 "args": [name_rung(a) for a in c["args"]]}}
            if "op" in e:
                return {"op": e["op"],
                        "args": [name_rung(a) for a in e.get("args", [])]}
            return e

        if len(facts) <= _LADDER_CAP:
            for (fn, keys), v in facts.items():
                args = []
                for tag, val_k in keys:
                    if tag == "seq":
                        if val_k not in seq_names and not seq_facts:
                            break
                        args.append(seq_name(val_k))
                    else:
                        args.append(expr(_tlit(val_k)))
                else:
                    rhs = (seq_name(tuple(v)) if isinstance(v, list)
                           else expr(_tlit(v)))
                    ladder.append(f"  assert {fn}({', '.join(args)}) == "
                                  f"{rhs};")
            if seq_facts:
                ops = _seq_op_rungs(raw_formula, funs, st)
                if len(facts) + len(ops) <= _LADDER_CAP:
                    for node, v in ops:
                        try:
                            lhs = expr(name_rung(node))
                        except KeyError:
                            continue
                        ladder.append(f"  assert {lhs} == "
                                      f"{seq_name(tuple(v))};")
        body = expr(formula)
    except (ValueError, KeyError, TypeError, IndexError, interp.Undef,
            interp.Budget, RecursionError):
        return None
    lets = "".join(f"var {n}: seq<int> := {_seq_lit(v)}; "
                   for v, n in used.items())
    lets += "".join(f"var {n}: seq<seq<int>> := {_nseq_lit(v)}; "
                    for v, n in nused.items())
    lets += "".join(f"var {n}: set<int> := {_set_lit(v)}; "
                    for v, n in sused.items())
    lines = [f"lemma {CERT_NAME}()", f"  ensures {lets}{body}", "{"]
    lines += [f"  var {n}: seq<int> := {_seq_lit(v)};"
              for v, n in ladder_seqs.items()]
    lines += ladder
    lines.append("}")
    return "\n".join(lines) + "\n"


# `witness` is the twin's measured witness (harness.twin_cached). Twin call
# sites pass it; when it is present and ground-certificatable, the lowering
# appends the refutation certificate lemma (see the section above).
def _method_decl(task: dict, m: dict) -> list[str]:
    """One t method as a Dafny method: its own signature, contract and
    body. Its self-calls (whole right-hand sides, check_wf's
    method-call-position rule) name the method itself, so the body is
    lowered with a context whose own name is the method's."""
    pseudo = {"name": m["name"], "params": m["params"],
              "returns": m["returns"], "requires": m["requires"],
              "ensures": m["ensures"], "body": m["body"],
              "spec_funs": task.get("spec_funs", []),
              "methods": task.get("methods", [])}
    mctx = _Ctx(pseudo, m["name"])
    mctx._used |= _collect_names(task)
    name = m["name"]
    ps = ", ".join(f"{p['name']}: {dafny_type(p['type'])}" for p in m["params"])
    r = m["returns"][0]
    out = [f"method {name}({ps}) returns ({r['name']}: {dafny_type(r['type'])})"]
    for e in m["requires"]:
        out.append(f"  requires {expr(e, name)}")
    for e in m["ensures"]:
        out.append(f"  ensures {expr(e, name)}")
    if "decreases" in m:
        out.append(f"  decreases {expr(m['decreases'], name)}")
    out.append("{")
    out.append(stmts(m["body"], "  ", mctx))
    out.append("}")
    return out


def _lemma_stmts(body: list, indent: str, self_name: str) -> list[str]:
    """A t lemma body (only `if` and lemma calls, check_wf's lemma-body
    rule) as Dafny proof statements."""
    out = []
    for s in body:
        if "lemma" in s:
            c = s["lemma"]
            args = ", ".join(expr(a, self_name) for a in c["args"])
            out.append(f"{indent}{c['name']}({args});")
        elif "assert" in s:
            out.append(f"{indent}assert {expr(s['assert'], self_name)};")
        else:
            c = s["if"]
            out.append(f"{indent}if {expr(c['cond'], self_name)} {{")
            out.extend(_lemma_stmts(c["then"], indent + "  ", self_name))
            out.append(f"{indent}}} else {{")
            out.extend(_lemma_stmts(c["else"], indent + "  ", self_name))
            out.append(f"{indent}}}")
    return out


def _lemma_decl(l: dict, self_name: str) -> list[str]:
    """One t lemma as a Dafny lemma (reference manual 6.3.3). The body is
    always emitted, even when empty: a Dafny lemma with no body at all is
    an axiom, and `{}` is an obligation Dafny must discharge."""
    ps = ", ".join(f"{p['name']}: {dafny_type(p['type'])}" for p in l["params"])
    out = [f"lemma {l['name']}({ps})"]
    for e in l["requires"]:
        out.append(f"  requires {expr(e, self_name)}")
    for e in l["ensures"]:
        out.append(f"  ensures {expr(e, self_name)}")
    if "decreases" in l:
        out.append(f"  decreases {expr(l['decreases'], self_name)}")
    out.append("{")
    out.extend(_lemma_stmts(l["body"], "  ", self_name))
    out.append("}")
    return out


def lower(task: dict, body: list, witness: dict | None = None) -> str:
    # NAMES (2026-09-11, ROADMAP 13.2): sanitize away any identifier that
    # collides with a Dafny reserved word, before anything below ever sees
    # the task -- see names.py's module docstring. `task` is returned
    # unchanged (`is`) when nothing needs a rename, which is every
    # previously-committed task, so this costs one extra scan and changes
    # nothing downstream for them. `_certificate` below is called on
    # this SAME renamed task/body, with `witness`'s own keys renamed to
    # match (`names.remap_witness`) rather than on a second, un-renamed
    # task: see that function's own docstring for why (MEASURED on
    # lower_framac.py, a certificate that declares fresh locals spelled
    # after the witness's own keys).
    twin_body = body if body is not task.get("body") else None
    task, renames = names.sanitize(task, names.KEYWORDS["dafny"],
                                    uppercase_ok=True)
    # the twin body renamed under the same mapping, kept a separate
    # object from task["body"] (2026-09-11, names.rename_body's note)
    body = names.rename_body(twin_body, renames) if twin_body is not None else task["body"]
    witness = names.remap_witness(witness, renames)
    if CERT_NAME in _collect_names(task):
        raise ValueError(f"task mentions the protocol name {CERT_NAME!r}")
    self_name = task["name"]
    method = self_name.capitalize()
    ctx = _Ctx(task, method)
    import tshape
    _EMPTIES.clear()
    _EMPTIES.update(tshape.empty_display_types(task, body))
    _HINTS.clear()
    _HINTS.update(tshape._scope_of(task, body))
    _FUNS.clear()
    _FUNS.update({f["name"]: f for f in task.get("spec_funs", [])})
    _LIB_USED.clear()
    _comp_register(task, body)   # SPEC.md "Comprehensions (v1)" (2026-10-06)
    lines = []
    # SPEC.md "The string library (v1)" (2026-09-11): "each kernel lowers a
    # member to a definition in its prelude", but gate (c)'s byte-identical
    # check (every task in t/tasks/*.json that uses no member, unchanged by
    # this wave) means the prelude is NOT emitted unconditionally -- only
    # when the task (its requires/ensures/spec_funs/body, `body` too since
    # a twin's mutated body is what is actually being lowered here) mentions
    # one of the 17 op names. `_collect_names` already walks every string in
    # the JSON (op names included, indistinguishable from any other string),
    # so membership is a cheap, sound test on the op VALUE, not merely on
    # whether the name appears as a string anywhere (count_matches.json's
    # own int-counting spec_fun is named "count" too; see _uses_strlib).
    if _uses_strlib(task) or _uses_strlib(body):
        lines = [STRLIB_PRELUDE.strip("\n"), ""]

    for d in task.get("datatypes", []):
        # SPEC.md "Datatypes (v1)" (2026-09-27): t's datatype IS Dafny's
        # own `datatype` declaration (reference manual 5.14), one
        # constructor per ctor, v1 states nullary constructors only.
        ctors = " | ".join(c["name"] for c in d["ctors"])
        lines.append(f"datatype {d['name']} = {ctors}")
    if task.get("datatypes"):
        lines.append("")

    for f in task.get("spec_funs", []):
        # 2026-09-27 (t/FEATURES-TRACK.md, nested string sequences): a
        # spec_fun PARAMETER may be a nested seq (`{"seq": "seq"}`, SPEC.md
        # "Nested sequences (v1)"), which `dafny_type` spells and the flat
        # `TYPES` table cannot (it raised "unhashable type: 'dict'" on the
        # lifted `seq<string>` helpers, 7 methods of the 2026-09-27
        # re-lift); a flat type prints exactly as before.
        ps = ", ".join(f"{p['name']}: {dafny_type(p['type'])}"
                       for p in f["params"])
        lines.append(f"function {f['name']}({ps}): {TYPES[f['result']]}")
        lines.append(f"  decreases {expr(f['decreases'], self_name)}")
        lines.append("{")
        lines.append(f"  {expr(f['body'], self_name)}")
        lines.append("}")
        lines.append("")

    # SPEC.md "Lemmas (v1)": each lemma is a Dafny lemma, proved in this
    # file; a call statement gives the caller its ensures.
    lib_slot = len(lines)   # SPEC.md "The library (v1)": the definitions the body turns out to use go here
    for l in task.get("lemmas", []):
        if l["name"] == method:
            raise NotImplementedError(
                f"dafny: lemma {l['name']!r} collides with the task's "
                f"lowered method name")
        lines.extend(_lemma_decl(l, self_name))
        lines.append("")

    # SPEC.md "Methods (v1)": each method is a Dafny method of its own,
    # verified against its own contract, and a call `x := m(args);` is
    # Dafny's own call statement, which the verifier reasons about through
    # the callee's requires/ensures only (Dafny reference manual, "Dafny
    # works modularly ... using only the specifications of other methods").
    for m in task.get("methods", []):
        if m["name"] == method:
            raise NotImplementedError(
                f"dafny: method {m['name']!r} collides with the task's "
                f"lowered method name")
        lines.extend(_method_decl(task, m))
        lines.append("")

    ps = ", ".join(f"{p['name']}: {dafny_type(p['type'])}"
                   for p in task["params"])
    ret = task["returns"][0]
    lines.append(f"method {method}({ps}) "
                 f"returns ({ret['name']}: {dafny_type(ret['type'])})")
    for e in task.get("requires", []):
        lines.append(f"  requires {expr(e, self_name)}")
    for e in task["ensures"]:
        lines.append(f"  ensures {expr(e, self_name)}")
    if "decreases" in task:
        lines.append(f"  decreases {expr(task['decreases'], self_name)}")
    lines.append("{")
    lines.append(stmts(body, "  ", ctx))
    lines.append("}")
    lines[lib_slot:lib_slot] = _lib_defs() + _comp_defs(self_name)
    src = "\n".join(lines) + "\n"
    if witness is not None:
        cert = _certificate(task, body, witness)
        if cert:
            src += "\n" + cert
    rc = names.rename_comment(renames)
    if rc:
        src += f"\n// {rc}\n"
    return src


if __name__ == "__main__":
    import harness
    raise SystemExit(harness.run_all(sys.argv[1:], lower, dafny_backend, "dfy"))
