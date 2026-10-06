# Expanding t: the plan of record (2026-10-06)

The operator's direction, 2026-10-06 08:10Z: t is the ceiling. Everything stops until the language has everything
it needs and more; no training, no speed work, no assistant features meanwhile. This page is the plan, the data
it rests on, and the order; the registrations with their numbers are in `t/PREDICT-2026-10-06-t-expansion.md`.

## 1. Where the ceiling is (measured)

`t/nl_census.py` over the 24,748 problems of `nl/` (re-run 2026-10-06 08:15Z on the language as it stands; the
numbers are the committed `t/COVERAGE-nl.md`'s, since the census's detectors predate the finite sets of 09-27
and over-count that one gap):

| | function-shaped | in t's fragment today |
|---|---:|---:|
| MBPP | 974 | 263 (27%) |
| HumanEval | 164 | 12 (7%) |
| APPS (function-shaped) | 3,101 | 497 (16%) |
| all function-shaped | 4,239 | 772 (18.2%) |

What keeps the rest out, by problems that need it, with the census's own greedy order of which gate opens the
most next (whole corpus / MBPP):

| gap | problems | greedy rank (all / MBPP) | feasible in t | kernels that can carry it |
|---|---:|---|---|---|
| real numbers (float literal, true `/`, sqrt, float()) | 3,517 | 1 / 1 | **yes, as exact rationals** | Dafny `real`, SPARK `Big_Reals`, Frama-C ACSL `real`, Lean `Rat`, Rocq `QArith`, F* `FStar.Real` (all six probed 2026-10-06: a `1/2 + 1/2 == 1` lemma proved); Verus has no reals: abstain by name |
| tuple (arity ≥ 3, nested, with a string component, list of tuples) | 3,872 | 9 / 3 | **yes**: n-tuples of any component type | every kernel has tuples or records |
| nested-seq (int/bool rows, deeper nesting) | 3,606 | 3 / 4 | **yes**: `seq<T>` for any `T` | every kernel |
| set of non-ints | 1,604 | 10 / 8 | **yes**: `set<T>` | Dafny/Verus/Lean/Rocq/F* native; SPARK and Frama-C abstain today for sets of ints already |
| map / dict | 2,463 | 6 / 6 | **yes**: `map<K, V>` as a finite function | Dafny `map`, Verus `Map`, F* `FStar.Map`, Lean/Rocq as an association list with a stated semantics; SPARK formal containers or abstain; Frama-C abstain |
| string-lib (members not in v1) | 1,288 | 7 / 11 | **yes**: the named missing members | all, as the v1 library is lowered |
| seq-slice-step, seq-slice-negative | 852 + 489 | 11, 15 / 10, 12 | **yes**: notation over existing ops | all (sugar) |
| unbounded-loop (`while True`, `break`, `continue`) | 4,403 | 12 / 9 | **yes**: `break`/`continue` with the loop's `decreases` kept | all |
| none-type (Optional), multi-return | 99 + 43 | 17, 20 / 13 | **yes**: field-carrying constructors (records, `Option`), a tuple return | all |
| closure (lambda, nested def, map/filter) | 2,243 | 8 / 7 | partly: inline helpers (landed), comprehensions as sugar | all |
| generator (lazy evaluation) | 1,686 | 5 / 5 | as eager comprehensions and `sum`/`any`/`all` builtins | all |
| import (an unmodelled library) | 3,932 | 4 / 2 | partly: `math` as builtins (`gcd`, `isqrt`, `floor`, `ceil`, `pow`, `comb`?) | all |
| class, global, io, exception | 1,641, 316, 30, 502 | — | **no**, by design (no heap, no aliasing, no I/O; an exception is an `Option` or a `requires`) | — |

Burdens the census counts as expressible but costly for the writer (the syntax gate is the project's largest
loss, ROADMAP WS-21): `min`/`max`/`sum`/`abs` with no builtin (6,624 problems), comprehensions written as loops
(5,920), `sorted` with no builtin (2,908), negative indices, `for` loops written as `while` with an explicit
`decreases`. "And more" means these too: what a model can write without inventing a form.

## 2. The order

The gates fall into one foundation and five landings. Each landing is one registration with a census bar.

| | landing | what it opens | work in `t/` |
|---|---|---|---|
| **G1** | **Compositional types**: `Type ::= int | bool | real | seq<T> | (T1, …, Tn) | set<T> | map<K, V> | D`, with `T` any type; tuples of any arity, `seq<T>` of any element, `set<T>`, spec_fun parameters and results of any type; `==`, `len`/`at`/`slice`/`update`/`fill`/`+` polymorphic by the static type; `.0 … .n` projections | tuple, nested-seq (all three), nested-seq-pair, multi-return, set of non-ints | SPEC, SYNTAX, `surface.py` (types, literals, projections), `t.gbnf`, `check_wf.py` (a type algebra replacing the fixed list), `interp.py` (values), `twin*` (WRONG-VAR on same type, projection swaps), the seven `lower_*.py` (type declarations generated per shape in SPARK and Frama-C), `to_python.py`, `spec_check.py`, the lifter |
| **G2** | **Exact rationals**: type `real`, decimal literals, `/` as true division on reals (int `/` stays Euclidean), `floor`, `ceil`, `round`, `abs`, comparisons, `tostr`? (no: decimal expansion is not finite), conversion `real(n)`; sqrt only as `isqrt` on ints and `r * r == x` in specifications | real (the largest gap) | the same files; Verus abstains by name until an int-pair encoding is measured |
| **G3** | **Builtins and notation for the writer**: `min`, `max`, `sum`, `abs`, `gcd`, `pow`, `isqrt`, `x in s` on seqs (element or substring), negative indices and slices, slice step, `reversed`, `for x in s` / `for i in [a, b)` as sugar over `while` with the `decreases` written for it, seq comprehensions `[e for x in s if p]` as a derived recursive spec_fun, `sorted(s)` with a permutation-and-order specification | the burdens; closure/generator uses that are comprehensions | SPEC "The library", surface, check_wf, interp, twins (OFF-BY-ONE on new bounds), lowerings (each builtin as a spec function the kernel proves about) |
| **G4** | **`break` and `continue`**, `while true` with `break` | unbounded-loop | SPEC frame rule extended, interp, twins (DROP-GUARD on a break's condition), lowerings (Lean/Rocq/F* loop encodings return early) |
| **G5** | **Maps**: `map<K, V>`, literals, `m[k]`, `k in m`, `m[k := v]`, `keys(m)`, `len(m)`, `remove` | map | all files; SPARK and Frama-C abstain by name at first |
| **G6** | **Records and options**: constructors with fields, `Option<T>`-style `None`/`Some(x)` as a library datatype, `case` with binders | none-type, exception, part of class | all files |
| **G7** | **The string library's missing members**: `isalnum`, `isspace`, `title`, `capitalize`, `swapcase`, `zfill`, `center`, `ljust`, `rjust`, `index`, `rindex`, `rfind`, `partition`, `splitlines`, lexicographic `<` on strings, `int(s)` parsing | string-lib | the v1 library's files |

Out of scope, stated once: classes and the heap, aliasing, first-class functions, lazy evaluation, exceptions as
control flow, global state, I/O. A problem that needs one of these is written another way or is not for t.

## 3. The rules each landing keeps

1. **SPEC first.** Every construct gets its normative section (semantics, definedness, the twin moves) before a
   lowering is touched; SYNTAX.md and `t.gbnf` follow, and `surface.py --check` round-trips every example.
2. **Seven lowerings or an abstain by name.** A kernel that cannot carry a construct abstains with the construct
   named (AGENTS rule 2); a landing counts when every present kernel verifies the real task and refutes its twin on
   the committed tasks, and `AGREEMENT.md` is regenerated from a clean clone.
3. **Witnesses.** `interp.py` evaluates every new value and operator; a twin without a witness is refused as today.
4. **Measured by the census.** The detectors in `nl_census.py` are updated with each landing (what is now in the
   fragment stops being a gap), and the bar is the count of function-shaped problems in fragment.
5. **The writer's side.** `to_python.py` hands each construct back as Python; `spec_check.py` evaluates it at the
   reference; the lifter learns the forms it meets in the corpora.
6. **Research before each construct** (AGENTS rule 5): how Dafny, Verus, Why3, Viper, Lean and Rocq state the
   same thing, fetched and filed, before SPEC is written.

## 4. What this supersedes

The teaching rounds (F and its planned F2), the speed items left in `internal/RESEARCH-2026-10-06-speed-and-steal.md`,
the Windows and twins items owed after F, and the assistant's open items in `internal/ROADMAP-LOG.md` are paused,
not closed. The F reading that was already running finishes by itself and is recorded in one line.
