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
  early exit (added 2026-09-08, SPEC.md "Early exit (v1)"): `return Expr;`
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
from verifiers import Outcome, flake_check          # noqa: E402
from verifiers import dafny as dafny_backend        # noqa: E402

OUT = HERE / "out"

BIN_OPS = {"==": "==", "!=": "!=", "<": "<", "<=": "<=", ">": ">", ">=": ">=",
           "+": "+", "-": "-", "*": "*", "div": "/", "mod": "%",
           "implies": "==>"}
NARY_OPS = {"and": "&&", "or": "||"}
TYPES = {"int": "int", "bool": "bool", "seq": "seq<int>"}


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
        if "pair" in t:
            t1, t2 = t["pair"]
            return f"({TYPES[t1]}, {TYPES[t2]})"
        return f"seq<{TYPES[t['seq']]}>"
    return TYPES[t]


def expr(e: dict, self_name: str | None = None) -> str:
    """Lower a spec-position expression. A self-call here is refused: SPEC.md
    puts task self-calls in bodies only, and the twin argument depends on the
    spec never mentioning the task's own (mutable) name."""
    if "int" in e:
        return str(e["int"])
    if "bool" in e:
        return "true" if e["bool"] else "false"
    if "var" in e:
        return e["var"]
    if "forall" in e:
        q = e["forall"]
        v = q["var"]
        return (f"(forall {v}: int :: "
                f"({expr(q['lo'], self_name)} <= {v} && "
                f"{v} < {expr(q['hi'], self_name)}) ==> "
                f"{expr(q['body'], self_name)})")
    if "exists" in e:
        q = e["exists"]
        v = q["var"]
        return (f"(exists {v}: int :: "
                f"({expr(q['lo'], self_name)} <= {v} && "
                f"{v} < {expr(q['hi'], self_name)}) && "
                f"{expr(q['body'], self_name)})")
    if "ite" in e:
        c = e["ite"]
        return (f"(if {expr(c['cond'], self_name)} "
                f"then {expr(c['then'], self_name)} "
                f"else {expr(c['else'], self_name)})")
    if "call" in e:
        c = e["call"]
        if c["fun"] == self_name:
            raise ValueError(
                f"self-call of {self_name!r} in spec position: t puts "
                f"self-calls in bodies only (SPEC.md gate 3)")
        args = ", ".join(expr(a, self_name) for a in c["args"])
        return f"{c['fun']}({args})"
    op, args = e["op"], [expr(a, self_name) for a in e.get("args", [])]
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
    if op in NARY_OPS:
        return "(" + f" {NARY_OPS[op]} ".join(args) + ")"
    if op in BIN_OPS:
        return f"({args[0]} {BIN_OPS[op]} {args[1]})"
    raise ValueError(f"t has no operator {op!r}")


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
        args = [body_expr(a, ctx, pre, lazy) for a in e.get("args", [])]
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
    if isinstance(ty, dict):
        if "pair" in ty:
            t1, t2 = ty["pair"]
            return {"op": "pair", "args": [_tlit(v[0], t1), _tlit(v[1], t2)]}
        return {"_seq2": tuple(tuple(row) for row in v)}
    if isinstance(v, bool):
        return {"bool": v}
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
    if "var" in e:
        v = m.get(e["var"])
        return e if v is None else v
    if "int" in e or "bool" in e or "_seq" in e or "_seq2" in e:
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
    if "bool" in e:
        return e, e["bool"]
    if "_seq" in e:
        return e, list(e["_seq"])
    if "_seq2" in e:
        return e, [list(row) for row in e["_seq2"]]
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
    if op == "fst":
        return out, vs[0].a
    if op == "snd":
        return out, vs[0].b
    if op in ("div", "mod"):
        # Same Euclidean law as interp.ev and SPEC.md "Division and modulo":
        # q = x div y, r = x mod y are the unique pair with x == q*y + r and
        # 0 <= r < |y|; y == 0 is undefined, exactly like `at` out of range.
        x, y = vs
        if y == 0:
            raise interp.Undef(f"{op} by zero")
        r = x % abs(y)
        return out, (r if op == "mod" else (x - r) // y)
    if op in _ARITH:
        return out, _ARITH[op](vs[0], vs[1])
    raise ValueError(f"t has no operator {op!r}")


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
               nnames: dict, nused: dict) -> dict:
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
    if "ite" in e:
        c = e["ite"]
        return {"ite": {"cond": _name_seqs(c["cond"], names, used, nnames, nused),
                        "then": _name_seqs(c["then"], names, used, nnames, nused),
                        "else": _name_seqs(c["else"], names, used, nnames, nused)}}
    if "call" in e:
        c = e["call"]
        return {"call": {"fun": c["fun"],
                         "args": [_name_seqs(a, names, used, nnames, nused)
                                  for a in c["args"]]}}
    if "op" in e:
        return {"op": e["op"],
                "args": [_name_seqs(a, names, used, nnames, nused)
                         for a in e.get("args", [])]}
    return e


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
    if "forall" in e or "exists" in e or "call" in e:
        raise ValueError("undefined-kind certificate: quantifier/call in body")
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
            raise _DefViol({"op": "!=", "args": [_tlit(y), {"int": 0}]})
        r = x % abs(y)
        return r if op == "mod" else (x - r) // y
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
                if _exec_undef(w["body"], env, funs, st):
                    return True
                it += 1
                if it > interp.MAX_LOOP:
                    raise interp.Budget("loop cap")
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
            if isinstance(tw, str) or not isinstance(tw, (bool, int, list)):
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
        elif kind == "undefined":
            # The twin's own body, replayed under the witness (see the
            # section comment above `_DefViol`): the FIRST definedness
            # obligation it hits unconditionally, as a ground guard. No
            # violation on replay (our mirror disagreeing with interp.py's,
            # a loop that exceeds interp.MAX_LOOP, or a quantifier/call the
            # mirror still abstains on) refuses the certificate rather than
            # guessing.
            env = dict(names)
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
        seq_names: dict = {}
        nseq_names: dict = {}
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
        used: dict = {}
        nused: dict = {}
        formula = _name_seqs(formula, seq_names, used, nseq_names, nused)
        ladder: list[str] = []
        ladder_seqs: dict = {}
        if len(facts) <= _LADDER_CAP:
            for (fn, keys), v in facts.items():
                if isinstance(v, list):
                    continue
                args = []
                for tag, val_k in keys:
                    if tag == "seq":
                        if val_k not in seq_names:
                            break
                        ladder_seqs[val_k] = seq_names[val_k]
                        args.append(seq_names[val_k])
                    else:
                        args.append(expr(_tlit(val_k)))
                else:
                    ladder.append(f"  assert {fn}({', '.join(args)}) == "
                                  f"{expr(_tlit(v))};")
        body = expr(formula)
    except (ValueError, KeyError, TypeError, IndexError, interp.Undef,
            interp.Budget, RecursionError):
        return None
    lets = "".join(f"var {n}: seq<int> := {_seq_lit(v)}; "
                   for v, n in used.items())
    lets += "".join(f"var {n}: seq<seq<int>> := {_nseq_lit(v)}; "
                    for v, n in nused.items())
    lines = [f"lemma {CERT_NAME}()", f"  ensures {lets}{body}", "{"]
    lines += [f"  var {n}: seq<int> := {_seq_lit(v)};"
              for v, n in ladder_seqs.items()]
    lines += ladder
    lines.append("}")
    return "\n".join(lines) + "\n"


# `witness` is the twin's measured witness (harness.twin_cached). Twin call
# sites pass it; when it is present and ground-certificatable, the lowering
# appends the refutation certificate lemma (see the section above).
def lower(task: dict, body: list, witness: dict | None = None) -> str:
    if CERT_NAME in _collect_names(task):
        raise ValueError(f"task mentions the protocol name {CERT_NAME!r}")
    self_name = task["name"]
    method = self_name.capitalize()
    ctx = _Ctx(task, method)
    lines = []

    for f in task.get("spec_funs", []):
        ps = ", ".join(f"{p['name']}: {TYPES[p['type']]}"
                       for p in f["params"])
        lines.append(f"function {f['name']}({ps}): {TYPES[f['result']]}")
        lines.append(f"  decreases {expr(f['decreases'], self_name)}")
        lines.append("{")
        lines.append(f"  {expr(f['body'], self_name)}")
        lines.append("}")
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
    src = "\n".join(lines) + "\n"
    if witness is not None:
        cert = _certificate(task, body, witness)
        if cert:
            src += "\n" + cert
    return src


if __name__ == "__main__":
    import harness
    raise SystemExit(harness.run_all(sys.argv[1:], lower, dafny_backend, "dfy"))
