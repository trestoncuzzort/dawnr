# Lifting ACSL by Example into t, 2026-09-26

ACSL by Example (github.com/fraunhoferfokus/acsl-by-example, MIT, Fraunhofer FOKUS) is 84
C functions, each with an ACSL contract, loop annotations and named logic definitions,
every one proved by the corpus itself with Frama-C/WP (`-wp-rte`, unsigned overflow
checked; `StandardAlgorithms/Config/verify-local.mk`, `Results/*.json`). This is what t's
lifter gets out of it through a new C/ACSL front end, how each lift was checked against
its C source, and what the seven kernels say.

    python3 t/lift_acsl_corpus.py --corpus <checkout>/acsl-by-example \
        --out t/out/lifted-tasks-acsl-by-example --split t/out/loop/split-v5.json --wp-par 2
    python3 t/run_par.py --jobs 16 --tasks t/out/lifted-tasks-acsl-by-example \
        --out <work> --table t/out/COVERAGE-lifted-acsl-by-example.md      # lab, T_CELL_SERIAL=1

Code: `t/lift_acsl.py` (front end: C/ACSL to the Dafny method `t/lifter.py` already
lifts; no shared lifter module changed), `t/lift_acsl_check.py` (equivalence),
`t/lift_acsl_corpus.py` (stage, lift, check, gate), `t/test_lift_acsl.py` (32 tests, one
per construct and refusal, negative controls for every lemma kind). The semantics each rule
relies on are in `t/lift_acsl.py`'s docstring, section by section of the ACSL manual
(github.com/acsl-language/acsl, `speclang_modern.tex`; research receipt 4ba9253bafdb).

## The funnel

| stage | count |
|---|---:|
| C files (`StandardAlgorithms/*/*.c`) | 84 |
| through the front end | 19 |
| lifted by `t/lifter.py` | 19 |
| checked: WP-equivalent and differential agree | 18 |
| refused by the check (`spec-division-unproved`: heap_parent) | 1 |
| refused by the gates (behavioural twins of held-out MBPP 736 and 786: lower_bound, upper_bound) | 2 |
| **accepted** | **16** |
| **clean in all seven kernels** | **2** (count, mismatch) |
| **clean in six** | **5** (find, find2, find_last: rocq alone; clamp: framac alone; accumulate: lean alone) |

Table: `t/COVERAGE-lifted-acsl-by-example.md` (copy of `t/out/COVERAGE-lifted-acsl-by-example.md`,
lab, 2026-09-26, 16 tasks x 7 kernels).

## Refused, by reason

Front end (65 of 84; these counts are the input for t's feature tracking):

| reason | files | what it is |
|---|---:|---|
| `array-write` | 25 | the function writes an array (`\valid`, non-const pointer, `assigns a[..]`): copy, fill, iota, reverse, the sorts, partial_sum, ... |
| `calls-other-method` | 13 | the body calls another C function (any_of calls find, is_sorted calls is_sorted_until, ...) |
| `struct` | 11 | a struct parameter or result (Stack, `size_type_pair`) |
| `ghost-code` | 8 | ghost statements (the permutation proofs of the sorts and heaps) |
| `source-unparseable` | 4 | outside the parsed subset (compound literals, `\from`, multi-declarators) |
| `valid-range-shape` | 3 | a pointer to one cell (swap, shuffle, random_number) |
| `continue` | 1 | search_n: `continue` skips a for loop's step, so `init; while c { s; step }` would be wrong |

Check: 1 (`spec-division-unproved`, heap_parent: its ensures is `\result == (child-1)/2`
with no precondition; at child = 0 C truncates to 0 and t's Euclidean division gives -1, so
the lifted clause is not the source's and the lemma rightly does not prove).
Gates: 2 behavioural twins of held-out problems (the drawn-input rule of `t/lift_corpora.py`).

## How each lift was checked (trust levels)

All 16 accepted tasks, and all 18 that passed the check, are **`wp-equivalent+differential`**:

- **Frama-C/WP proves the specifications equivalent.** One file per task: the source's own
  headers (typedefs and logic definitions verbatim) plus lemmas, every variable quantified at
  its C type, so the lemmas speak about exactly the source's domain: `SRC_PRE <==> LIFT_PRE`,
  `SRC_PRE ==> (SRC_POST <==> LIFT_POST)`, per loop the invariant conjunctions and the
  variants; and for each recursive logic function lifted as a spec function (Count, Find,
  FindNotEqual, Accumulate, InnerProduct) an equation lemma (the source function satisfies the
  lifted definition on its domain), a closure lemma per recursive call and a lemma per call site
  (every call the lifted clauses make is inside that domain), which together identify the two
  functions wherever the task uses them without any lemma needing induction. 2 to 10 lemmas per
  task, 98 in all over the 18, every one proved (alt-ergo/z3, 20 s per goal, two prover processes).
- **Differential.** The corpus's C function compiled as is (`gcc -fsanitize=undefined`) and
  the lifted task in t's interpreter agree on 120 drawn inputs per task that satisfy the
  lifted requires (sorted and constant arrays over-sampled).
- **Negative controls** (`t/test_lift_acsl.py`): a weakened ensures, a spec function adding 2
  per hit and a call outside the function's domain each leave their lemma unproved; a body
  counting 2 per hit disagrees with the C.

No task was admitted at a lower trust level (`differential` alone). The desktop runs every
prover under a 3 GB memory cap (`systemd-run --user --scope -p MemoryMax=3G`).

## C semantics t differs on, and what the lift does

| C/ACSL | t | rule |
|---|---|---|
| machine `int`, `unsigned` wrap | mathematical integers | unsigned is `nat` (wrap becomes a proof obligation); INT_MAX/UINT_MAX are not carried: the lifted theorem is the source's over unbounded integers, re-proved by seven kernels, recorded per task as `machine-int-generalized`; sound on the source's domain because the corpus proves absence of overflow and wrap there |
| `/`, `%` truncate | Euclidean | lifted only on unsigned operands, or with the check required to prove the clause equal (else refused) |
| pointer + length | `seq` | only `const` pointers with `\valid_read(a + (0..n-1))`; n becomes `len(a)`; a second array on the same n gets `requires len(b) == len(a)`; any write refused |
| formals in `ensures` are pre-state | parameters are immutable | an assigned parameter p becomes `p0` plus a local copy `p` |
| behaviors, complete/disjoint | requires/ensures | `A ==> E` per behavior; complete/disjoint dropped with a record (spec obligations) |
| two-valued total logic (`a[i]` out of range is some value) | `at` out of range is undefined | non-recursive predicates expanded at the use; recursive ones become spec functions with guarded reads, proved equal on the domain the task uses |
| `for (init; c; step)` | `while` | `init; while c { s; step }`; `continue` refused |
| `\at(e, L)`, labelled predicates | one state | merged, because the function assigns `\nothing` |

## What the kernels say, and what would unlock more

- **Six of 16 need the corpus's lemmas.** find3, find_if_not, is_heap_until, is_sorted_until
  (and inner_product in verus/lean) are unproved even in dafny: the source proves them with
  its `Find_*`, `Heap_*` lemmas (some by Coq), and t has no lemma or assert construct to carry
  them. Lemma support in t (or lifting the source's lemmas as hints) is the largest lever on
  what is already lifted.
- **rocq** alone keeps find, find2 and find_last out of seven (timeouts on the lab under load),
  **framac** alone keeps clamp out (its twin unproved), **lean** alone keeps accumulate out.
- The early-return rewrite (`if !c { return y; }` before a loop) turned fstar's abstentions on
  max_element, max_element2, min_element and adjacent_find into verified, but **lean reads the
  shape as MALFORMED** and rocq leaves it unproved: a lowering finding, not investigated here.
- Beyond what lifted: **output arrays as `seq` returns** would take most of the 25
  `array-write` refusals (copy, fill, iota, reverse_copy, replace_copy, ... are "a new
  sequence", in-place ones are "the old sequence to a new one"); t has seq results since
  2026-09-09 but the lifter's `seq-return`/`seq-update` rewrites do not produce them yet.
  **Method calls** (13) are the second, structs (11) and ghost code (8) the rest.

## Would the same front end take SoSy-Lab's ACSL-annotated SV-COMP loops?

No, not as they are. Measured (`gitlab.com/sosy-lab/research/data/acsl-benchmarks`, the 340
`.c` files under `acsl/*/`, `lift_acsl.translate(f, dir, "main")`): **0 lift**; 259 are
refused `no-contract` (every program is `int main()` reading `__VERIFIER_nondet_int()`, with
`__VERIFIER_assert` in place of an ensures), 58 `global-variable`, 7 `goto`, 6
`local-array`, the rest parse or type refusals. Only 2 of them carry a requires/ensures. The
loop invariants themselves are in the shape this front end reads (`//@ loop invariant ...`);
what is missing is a harness-to-function stage before it: nondet reads to parameters,
`assume_abort_if_not` to requires, the final assertion to an ensures, `while (1) ... break` to a
guarded loop. That stage is new work, and the result would be tasks written from those
invariants rather than lifted, which is how VERIFIED-CORPORA.md rated them.

## Not measured

- No English heads: the corpus's prose is in `ACSL-by-Example.pdf`, not beside each program.
- The source proofs were not re-run here; the corpus's own `Results/*.json` are the record.
- Corpus builder: the 16 accepted tasks are in `t/out/lifted-tasks-acsl-by-example` (not
  tracked, as the other lifts); `--lifted-set t/out/lifted-tasks-acsl-by-example=t/COVERAGE-lifted-acsl-by-example.md`
  admits the 2 clean in seven.
