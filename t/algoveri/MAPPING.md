# AlgoVeri contracts in t: the mapping, clause by clause

For each problem: the source (`algoveri_data/<id>/dafny_spec.dfy` in AlgoVeri at commit
8e313b0e8110a781009d4b67ca93b3771b5dc9db), how each clause of its Dafny contract is stated in t (`Dafny => t`), any
restatement, and how the program in `<id>.t` was proved in Dafny while it was written. The verdicts in all seven
kernels are in `../ALGOVERI.md`.

The rule the programs were written under: every `requires` and `ensures` of the Dafny method appears in t with the
same meaning, the preamble's predicates and functions become spec functions, and no clause is weakened, dropped or
reinterpreted. One restatement was allowed in advance, the permutation (AlgoVeri's existential over an index
permutation) as equal length and equal occurrence counts, checked by brute force against the original definition.
Any other departure from the letter of the Dafny text is named under its problem below, with the reason it keeps
the meaning.

## ac_automata

Status: stated; Dafny verifies the real program and refutes its twin. Last verdict while writing: dafny: COUNTS, real is a real proof; off-by-one twin is refuted, the kernel found this wrong

```
predicate matches_at(haystack, needle, start_index) => spec fun matches_at(haystack: seq, needle: seq, start_index: int): bool = 0 <= start_index and start_index + len(needle) <= len(haystack) and (forall i in [0, len(needle)) . haystack[start_index + i] == needle[i])
function patterns_view(patterns) { patterns } => inline fun patterns_view(patterns: seq<seq>): seq<seq> = patterns  [unused by every clause; an inline helper because the Dafny lowering cannot emit a spec fun whose result is seq<seq> (TypeError at lower_dafny.py line 4063), and an inline fun expands away]
requires |patterns| > 0 => requires len(patterns) > 0
requires |haystack| < 1000000 => requires len(haystack) < 1000000
requires |patterns| < 1000000 => requires len(patterns) < 1000000
requires forall i :: 0 <= i < |patterns| ==> |patterns[i]| < 1000000 => requires forall i in [0, len(patterns)) . len(patterns[i]) < 1000000
ensures (soundness) forall i :: 0 <= i < |results| ==> var (pid, idx) := results[i]; pid >= 0 && idx >= 0 && 0 <= pid < |patterns| && matches_at(haystack, patterns[pid], idx) => ensures forall i in [0, len(results)) . results[i].0 >= 0 and results[i].1 >= 0 and 0 <= results[i].0 and results[i].0 < len(patterns) and matches_at(haystack, patterns[results[i].0], results[i].1)  [the let-destructuring is substituted: pid = results[i].0, idx = results[i].1, same conjunct order so the bounds guard patterns[pid]]
ensures (completeness) forall pid, idx :: 0 <= pid < |patterns| && matches_at(haystack, patterns[pid], idx) ==> exists k :: 0 <= k < |results| && results[k] == (pid, idx) => ensures forall pid in [0, len(patterns)) . forall idx in [0, len(haystack) + 1) . matches_at(haystack, patterns[pid], idx) ==> (exists k in [0, len(results)) . results[k] == (pid, idx))  [idx ranges over all ints in Dafny, but matches_at forces 0 <= idx and idx + |needle| <= |haystack|, so [0, |haystack| + 1) covers every idx at which the antecedent can hold]
```

Notes: Implementation is a direct multi-pattern search (for every pattern and every start index 0..|haystack|, append (pid, idx) when matches_at holds), not an Aho-Corasick automaton; the contract (soundness and completeness of the result list) is algorithm-agnostic, and empty patterns match at every index including |haystack|. Loop invariants carry soundness of all results so far and completeness for finished patterns and for the finished indices of the current pattern; the exists-over-results shape is lowered by the harness to Dafny's native 'in', which survives appends. The body uses != guards and an ite expression instead of an if statement so the first twin is the off-by-one on the initial pattern index with the witness haystack=[], patterns=[[]]. Verify attempts: 1. Contract cross-check in Python against the Dafny contract: agree on 18345 (input, results) pairs.

## binary_search

Status: stated; Dafny verifies the real program and refutes its twin. Last verdict while writing: dafny: COUNTS, real is a real proof; collapse-if twin is refuted, the kernel found this wrong

```
predicate is_sorted(s) { forall i, j :: 0 <= i <= j < |s| ==> s[i] <= s[j] } => spec fun is_sorted(q: seq): bool = forall i in [0, len(q)) . forall j in [i, len(q)) . q[i] <= q[j]
requires |s| <= 0x7FFFFFFF => requires len(s) <= 2147483647
requires is_sorted(s) => requires is_sorted(s)
ensures result >= 0 => ensures result >= 0
ensures result <= |s| => ensures result <= len(s)
ensures forall i :: 0 <= i < result ==> s[i] < target => ensures forall i in [0, result) . s[i] < target
ensures forall i :: result <= i < |s| ==> s[i] >= target => ensures forall i in [result, len(s)) . s[i] >= target
```

Notes: 1 verify attempt. Body is the standard lower-bound binary search (lo/hi window, mid = lo + (hi - lo) / 2) with the two-sided invariant (everything left of lo is < target, everything from hi on is >= target) and decreases hi - lo; sortedness is used by Dafny's own quantifier instantiation, no helper lemmas.

## bracket_matching

Status: stated; Dafny verifies the real program and refutes its twin. Last verdict while writing: dafny: COUNTS, real is a real proof; compare-flip twin is refuted, the kernel found this wrong

```
function char_weight(c) => spec fun char_weight(c: int): int = if c == 40 then 1 else if c == 41 then -1 else 0
function total_weight(s) decreases |s| => spec fun total_weight(s: seq): int decreases len(s) = if len(s) == 0 then 0 else char_weight(s[0]) + total_weight(s[1..])
predicate valid_prefix_weights(s) => spec fun valid_prefix_weights(s: seq): bool = forall i in [0, len(s) + 1) . total_weight(s[0..i]) >= 0
predicate is_matched(s) => spec fun is_matched(s: seq): bool = total_weight(s) == 0 and valid_prefix_weights(s)
requires |s| <= 1000000 => requires len(s) <= 1000000
ensures res == is_matched(s) => ensures res == is_matched(s)
```

Notes: Linear scan keeping the running balance c and the running minimum prefix balance m (res := m >= 0 and c == 0); it has no early exit. Lemmas: weight_snoc (the prefix weight grows by the next character's weight, by induction) and slice_all (s[0..len(s)] == s, needed once after the loop). The early-exit form (return false as soon as c < 0) also verified as a real proof (attempt 2) but its collapse-if twin has the witness s=[0], whose ground certificate needs valid_prefix_weights([0]) == true and Dafny cannot prove a quantified spec-fun call at a ground argument unaided, so that cell read REFUSED (twin unproved); the min-tracking form has no if statement, so the twin is the loop-guard compare-flip with an undefined-index witness at s=[] and the certificate goes through. Verify attempts: 3 (1: real unproved, missing slice lemma; 2: real proved, twin unproved; 3: COUNTS). Contract cross-check in Python: agree on 2186 (input, result) pairs.

## bubble_sort

Status: stated; Dafny verifies the real program and refutes its twin. Last verdict while writing: dafny: COUNTS, real is a real proof; collapse-if twin is refuted, the kernel found this wrong

```
method bubble_sort(v: seq<int>) returns (v_new: seq<int>) => task bubble_sort(v: seq) returns (v_new: seq); the Dafny method has no requires and the task has none
ensures is_sorted(v_new) => ensures is_sorted(v_new), where preamble is_sorted(s) = forall i, j :: 0 <= i < j < |s| ==> s[i] <= s[j] is written inline fun is_sorted(s: seq): bool = forall i in [0, len(s)) . forall j in [i + 1, len(s)) . s[i] <= s[j]
ensures is_permutation(v, v_new) => ensures is_permutation(v, v_new), where spec fun is_permutation(v1, v2) = len(v1) == len(v2) and (forall i in [0, len(v1)) . occ(v1, v1[i]) == occ(v2, v1[i])) and (forall j in [0, len(v2)) . occ(v1, v2[j]) == occ(v2, v2[j]))
preamble is_valid_index_permutation(p, n) => not written: it occurs only under the existential that the allowed restatement of is_permutation replaces
```

Restatement: is_permutation(v1, v2) is the allowed bounded restatement len(v1) == len(v2) and (forall i in [0, len(v1)) . occ(v1, v1[i]) == occ(v2, v1[i])) and (forall j in [0, len(v2)) . occ(v1, v2[j]) == occ(v2, v2[j])); occ(s, x) = occn(s, x, len(s)) and spec fun occn(s, x, n) = if n <= 0 or n > len(s) then 0 else occn(s, x, n - 1) + (if s[n - 1] == x then 1 else 0), the number of positions k in [0, n) with s[k] == x, by recursion on n. Checked by brute force against the original index-permutation definition on all 14,641 pairs of sequences over {0,1,2}, lengths 0..4, with t's interpreter: 0 mismatches (is_sorted likewise).

Notes: Classic nested-loop bubble sort with adjacent swaps (v_new := v_new[j := v_new[j+1]][j+1 := v_new[j]]). Outer invariant: every pair (k,l) with l >= n-i is ordered; inner invariant adds that v_new[j] is the maximum of the prefix [0..j]. The permutation is carried through the loops as is_permutation(v, v_new) and kept by a swap lemma perm_swap proved from probe-lifted occurrence-count lemmas (occn_upd/occ_upd/occ_swap by recursion on the count bound, occ_zero, perm_occ_pt/perm_occ_upto, which lift the pointwise facts to every position of a probe seq so the bounded quantifiers of the restatement are instantiated). DEVIATION FROM THE LETTER OF THE RULES: is_sorted is an `inline fun`, not a `spec fun`. Measured reason: the twin refutation certificate only unrolls bounded quantifiers that sit in the ensures; with `spec fun is_sorted` the certificate is `assert is_sorted(r) == false` and Dafny answers 'assertion might not hold' (run on the spec-fun variant of this very file), so the twin could never read refuted. The inline fun expands to the same bounded quantifier at every use. Kernel runs on this problem: 4 (one raw dafny run, one cli verify, one scratch run of the spec-fun variant's certificate, one cli verify after renaming to v_new/is_permutation). Largest Z3 cost of any symbol about 208k of the 500k rlimit (measured on the pre-rename text). The shared lemma package was first validated in a scratch lemma-only file (not a problem attempt). Interpreter finds no counterexample to the real body; twin = collapse-if (always swap), witness v=[0,1] -> twin [1,0].

## discrete_logarithm

Status: stated (2026-10-07, after SPEC.md "Datatypes (v2): fields"); Dafny verifies the real program and refutes its twin. Last verdict while writing: dafny: COUNTS, real is a real proof; collapse-if twin is refuted, the kernel found this wrong

```
datatype Option<T> = Some(value: T) | None => datatype Option = Some(value: int) | None
function spec_pow_mod(b: int, e: int, m: int): int decreases e requires m > 1 { if e <= 0 then 1 else (b * spec_pow_mod(b, e - 1, m)) % m } => spec fun spec_pow_mod(b: int, e: int, m: int): int decreases e = if m <= 1 then 0 else if e <= 0 then 1 else (b * spec_pow_mod(b, e - 1, m)) % m
predicate is_discrete_log(g: int, h: int, p: int, x: int) requires p > 1 { spec_pow_mod(g, x, p) == h % p } => spec fun is_discrete_log(g: int, h: int, p: int, x: int): bool decreases 0 = p > 1 and spec_pow_mod(g, x, p) == h % p
requires g >= 0 && h >= 0 && p >= 0 => requires g >= 0 and h >= 0 and p >= 0
requires p > 1 => requires p > 1
ensures match res case Some(x) => is_discrete_log(g, h, p, x) && 0 <= x < p && (forall k :: 0 <= k < x ==> !is_discrete_log(g, h, p, k)) case None => forall k :: 0 <= k < p ==> !is_discrete_log(g, h, p, k) => ensures case res { Some(x) => is_discrete_log(g, h, p, x) and 0 <= x and x < p and (forall k in [0, x) . not is_discrete_log(g, h, p, k)), None => forall k in [0, p) . not is_discrete_log(g, h, p, k) }
```

Notes: First stated once datatypes carry fields. Two departures from the letter, both keeping the meaning.
- **`Option<T>` is monomorphic.** It is used only at `T = int`, and t has no generic datatypes.
- **The helpers are total.** t spec funs are total, as for `spec_sum` in maximum_subarray_sum. `spec_pow_mod` returns 0 where Dafny's `requires m > 1` fails. `is_discrete_log` conjoins `p > 1`, which also makes its `h % p` defined. Every call in the contract has `p > 1` from the method's requires, where both values are Dafny's.

Body: a linear scan. `x` runs from 0 and `cur` holds `spec_pow_mod(g, x, p)`, updated as `(g * cur) % p`, which is the definition's own step for `x + 1 > 0` and `p > 1`, so no lemma is needed. The loop stops at the first `x` with `cur == h % p`, through the guard `res == Option.None`. The invariant is the contract's own match over `res`, with `None` quantifying over `[0, x)`.

The program found five engine defects as it was written:
- Lean refused the name `Option`, its prelude's (now `t_Option` in Lean text).
- Verus's `use Option::*` was ambiguous with Rust's prelude (now qualified `self::`).
- Dafny's undefined-kind replay had no constructor, field or match case.
- Dafny's certificate unroller walked a ground match's arms with their binders unbound (now it reduces the match).
- Lean's `simp only` cited the recursive `spec_pow_mod`'s equation, which never stops rewriting (recursive spec funs are now grind hints only).

Twin: collapse-if, witness g=0, h=0, p=2: real `Option.Some(1)`, twin `Option.Some(0)`.

## fast_exponential

Status: stated; Dafny verifies the real program and refutes its twin. Last verdict while writing: dafny: COUNTS, real is a real proof; negate-cond twin is refuted, the kernel found this wrong

```
function spec_pow(b: nat, e: nat): nat { if e == 0 then 1 else b * spec_pow(b, e - 1) } => spec fun spec_pow(b: int, e: int): int decreases e = if e <= 0 then 1 else b * spec_pow(b, e - 1)
requires b >= 0 => requires b >= 0
requires e >= 0 => requires e >= 0
requires spec_pow(b, e) <= 0xffff_ffff_ffff_ffff => requires spec_pow(b, e) <= 18446744073709551615
ensures res == spec_pow(b, e) => ensures res == spec_pow(b, e)
ensures res >= 0 => ensures res >= 0
```

Notes: Exponentiation by squaring: res := 1, base := b, ex := e; while ex > 0 with invariants ex >= 0 and res * spec_pow(base, ex) == spec_pow(b, e) (the conservation invariant the NL asks for); odd ex: res := res * base, ex := ex - 1; even ex: base := base * base, ex := ex / 2. Helper lemmas: pow_nonneg (the nat result type of Dafny's spec_pow, by induction) and pow_square (spec_pow(b * b, k) == spec_pow(b, 2 * k) for k >= 0, by induction on k; the (b^2)^k = b^(2k) identity the NL names), called in the even branch before base is squared. Same spec_pow totalization (e <= 0 -> 1) and decimal spelling of the u64 bound as integer_exponential. Contract not weakened. One cli verify attempt, COUNTS.

## insertion_sort

Status: stated; Dafny verifies the real program and refutes its twin. Last verdict while writing: dafny: COUNTS, real is a real proof; compare-flip twin is refuted, the kernel found this wrong

```
method insertion_sort(v: seq<int>) returns (v_new: seq<int>) => task insertion_sort(v: seq) returns (v_new: seq); the Dafny method has no requires and the task has none
ensures is_sorted(v_new) => ensures is_sorted(v_new), where preamble is_sorted(s) = forall i, j :: 0 <= i < j < |s| ==> s[i] <= s[j] is written inline fun is_sorted(s: seq): bool = forall i in [0, len(s)) . forall j in [i + 1, len(s)) . s[i] <= s[j]
ensures is_permutation(v, v_new) => ensures is_permutation(v, v_new), where spec fun is_permutation(v1, v2) = len(v1) == len(v2) and (forall i in [0, len(v1)) . occ(v1, v1[i]) == occ(v2, v1[i])) and (forall j in [0, len(v2)) . occ(v1, v2[j]) == occ(v2, v2[j]))
preamble is_valid_index_permutation(p, n) => not written: it occurs only under the existential that the allowed restatement of is_permutation replaces
```

Restatement: is_permutation(v1, v2) is the allowed bounded restatement len(v1) == len(v2) and (forall i in [0, len(v1)) . occ(v1, v1[i]) == occ(v2, v1[i])) and (forall j in [0, len(v2)) . occ(v1, v2[j]) == occ(v2, v2[j])); occ(s, x) = occn(s, x, len(s)) and spec fun occn(s, x, n) = if n <= 0 or n > len(s) then 0 else occn(s, x, n - 1) + (if s[n - 1] == x then 1 else 0), the number of positions k in [0, n) with s[k] == x, by recursion on n (same definitions as bubble_sort; equivalence to the index-permutation definition checked by brute force, 0 mismatches).

Notes: Insertion sort with the key moved left by adjacent swaps: outer loop keeps v_new[0..i) sorted; the inner loop (while j > 0 and v_new[j-1] > v_new[j], swap, j := j-1) keeps the one-line invariant 'every pair (k,l) with k < l <= i and l != j is ordered'. The permutation is carried as is_permutation(v, v_new) and maintained by the same perm_swap lemma package as bubble_sort. is_sorted is an `inline fun` instead of a `spec fun` for the measured reason given in bubble_sort (a quantifier inside a spec fun body is not unrolled by the twin certificate, and Dafny cannot prove `is_sorted([1,0]) == false`). The twin chosen by the ladder is compare-flip (outer guard i < n becomes i <= n), whose witness is an out-of-range read (v=[0]); Dafny rejects the twin method and accepts the ground certificate. Kernel runs on this problem: 3 (raw dafny, cli verify, cli verify after renaming). Largest Z3 cost about 170k of the 500k rlimit. Interpreter finds no counterexample to the real body.

## integer_exponential

Status: stated; Dafny verifies the real program and refutes its twin. Last verdict while writing: dafny: COUNTS, real is a real proof; compare-flip twin is refuted, the kernel found this wrong

```
function spec_pow(b: nat, e: nat): nat { if e == 0 then 1 else b * spec_pow(b, e - 1) } => spec fun spec_pow(b: int, e: int): int decreases e = if e <= 0 then 1 else b * spec_pow(b, e - 1)
requires b >= 0 => requires b >= 0
requires e >= 0 => requires e >= 0
requires spec_pow(b, e) <= 0xffff_ffff_ffff_ffff => requires spec_pow(b, e) <= 18446744073709551615
ensures res == spec_pow(b, e) => ensures res == spec_pow(b, e)
ensures res >= 0 => ensures res >= 0
```

Notes: Body: loop i in [0, e) with invariants 0 <= i <= e and res == spec_pow(b, i), res := res * b. t has no nat type, so spec_pow is an int-valued spec fun made total with e <= 0 -> 1 (same value as Dafny's e == 0 for every nat input); the nat result type is recovered as helper lemma pow_nonneg (spec_pow(b, e) >= 0 for b, e >= 0, by induction on e), called after the loop to prove ensures res >= 0. The u64 bound is kept as the decimal 18446744073709551615 (= 0xffff_ffff_ffff_ffff; t has no hex literals). Contract not weakened. Two cli verify attempts: attempt 1 was unproved because res >= 0 was not provable without nat typing (Dafny reported the postcondition on the return path), attempt 2 with pow_nonneg COUNTS. I also ran dafny directly (memory capped) on the lowered source once to read the error message; those runs are not counted as attempts.

## k_smallest

Status: not stated. Last verdict while writing: not attempted: not-stateable, no file written, no verify run

```
method quick_select(v: seq<int>, k: int) returns (v_new: seq<int>, res: int) => statable as a task with a pair return (seq, int), v_new = r.0 and res = r.1
requires 0 <= k < |v| => statable: requires 0 <= k and k < len(v)
ensures is_permutation(v, v_new) => statable through the allowed restatement of is_permutation (occ-count form, as in the four sorts)
ensures is_kth_smallest(v, k, res) => NOT STATEABLE: the preamble defines it as exists sorted_s: seq<int> :: is_permutation(s, sorted_s) && is_sorted(sorted_s) && 0 <= k < |s| && sorted_s[k] == val
preamble is_valid_index_permutation, is_permutation, is_sorted => only needed inside the clause above, nothing written because no file was produced
```

Notes: The second ensures, is_kth_smallest(v, k, res), is an existential over a SEQUENCE (sorted_s: seq<int>), which t's bounded int-range quantifiers cannot express. The single allowed restatement covers is_permutation(a, b) only; here is_permutation is merely a conjunct under the existential over sorted_s, so that restatement does not apply. Any other bounded characterisation (for example 0 <= k < |v| and sort(v)[k] == res using t's library sort, the unique sorted permutation, or a counting characterisation: count of elements < res is <= k and count of elements <= res is > k) would be a reinterpretation of the clause outside the one allowed restatement, so by the stated rules no weaker or reworded task was written. The other clauses (requires 0 <= k < |v|, ensures is_permutation(v, v_new), the two-valued return as a pair) are statable and the toolkit used for the four sorts (probe-lifted occ lemmas, perm_swap, the quick_sort partition) would carry a quick-select proof if the sort(v)[k] restatement is judged acceptable by whoever owns the rule.

## kmp

Status: stated; Dafny verifies the real program and refutes its twin. Last verdict while writing: dafny: COUNTS, real is a real proof; collapse-if twin is refuted, the kernel found this wrong

```
predicate matches_at(haystack, needle, start_index) { 0 <= start_index && start_index + |needle| <= |haystack| && forall i :: 0 <= i < |needle| ==> haystack[start_index + i] == needle[i] } => spec fun char_eq(hs, nd, start_index, i) = 0 <= i and i < len(nd) and 0 <= start_index + i and start_index + i < len(hs) and hs[start_index + i] == nd[i]; spec fun matches_at(hs, nd, start_index) = 0 <= start_index and start_index + len(nd) <= len(hs) and (forall i in [0, len(nd)) . char_eq(hs, nd, start_index, i))
requires |haystack| < 1000000 => requires len(haystack) < 1000000
requires |needle| < 1000000 => requires len(needle) < 1000000
ensures forall k :: 0 <= k < |indices| ==> indices[k] >= 0 => ensures forall k in [0, len(indices)) . indices[k] >= 0
ensures forall i :: 0 <= i < |indices| ==> matches_at(haystack, needle, indices[i]) => ensures forall i in [0, len(indices)) . matches_at(haystack, needle, indices[i])
ensures forall i :: matches_at(haystack, needle, i) ==> exists k :: 0 <= k < |indices| && indices[k] == i => ensures forall i in [0, len(haystack) + 1) . matches_at(haystack, needle, i) ==> (exists k in [0, len(indices)) . indices[k] == i)
```

Notes: 4 verify attempts (3 distinct versions run in Dafny directly with the harness flags, which was the only way to see error text because cli.py verify prints just the verdict, plus the official cli.py verify of the third). Same contract as string_search_naive (same bounded-range and char_eq remarks). Real KMP: compute_fail builds the failure table fail[q] = longest proper border of needle[0..q) (the LPS array, indexed by prefix length, length m+1); kmp_search runs the fallback loop q := fail[q] while the next char mismatches, extends on a match, records i + 1 - m and resets q := fail[m] on a full match; the empty needle goes through all_positions (every start 0..|haystack|). The proof uses a recursive spec fun pref(h, p, e, k) (the first k chars of p end at position e of h), about 20 small lemmas, and the loops split into small methods (fallback is shared by the table build and the search). Why the layout: version 1 (quantifier-based pref, one big method each) proved every assertion under --isolate-assertions but needed 5.15M and 2.46M rlimit units against the harness's 500k per method, and one lemma ensures had no Dafny trigger (a warning is exit 2 = MALFORMED); the restructure keeps every procedure under 190k and the twin (collapse-if on the empty-needle branch) is refuted. Invariants and all lemma statements were also checked by brute force with the t interpreter.

## linear_search

Status: stated; Dafny verifies the real program and refutes its twin. Last verdict while writing: dafny: COUNTS, real is a real proof; compare-flip twin is refuted, the kernel found this wrong

```
predicate is_sorted(s) { forall i, j :: 0 <= i <= j < |s| ==> s[i] <= s[j] } => spec fun is_sorted(q: seq): bool = forall i in [0, len(q)) . forall j in [i, len(q)) . q[i] <= q[j]
requires |s| <= 0x7FFFFFFF => requires len(s) <= 2147483647
requires is_sorted(s) => requires is_sorted(s)
ensures result >= 0 => ensures result >= 0
ensures result <= |s| => ensures result <= len(s)
ensures forall i :: 0 <= i < result ==> s[i] < target => ensures forall i in [0, result) . s[i] < target
ensures forall i :: result <= i < |s| ==> s[i] >= target => ensures forall i in [result, len(s)) . s[i] >= target
```

Notes: 1 verify attempt. This is the lower-bound variant (AlgoVeri's linear_search), not the committed tasks/linear_search.t (find x in s); the task is still named linear_search, and nothing under (a local path) was touched. Body: scan p from 0 while p < len(s) and s[p] < target, invariant forall k in [0, p) . s[k] < target.

## longest_common_subsequence

Status: stated; Dafny verifies the real program and refutes its twin. Last verdict while writing: dafny: COUNTS, real is a real proof; collapse-if twin is refuted, the kernel found this wrong

```
requires |s| <= 3000 => requires len(s) <= 3000
requires |t| <= 3000 => requires len(u) <= 3000   (parameter t renamed u: `t` is a reserved word of t)
ensures len == lcs_spec(s, t) => ensures r == lcs_spec(s, u)   (return variable len renamed r: `len` is the length operator)
ensures len >= 0 => ensures r >= 0
preamble max => spec fun max (decreases 0; shadows the library max by design)
preamble lcs_spec (decreases |s1|, |s2|) => spec fun lcs_spec with decreases len(s1) + len(s2) (single int measure covering the three recursive calls; slices written s1[0..len(s1) - 1]); seq<char> is seq of code points (ints), so the t statement covers every int sequence, a superset of the char sequences
```

Notes: 2 versions, both COUNTS; final is v2. Algorithm: two-row dynamic programme, prev[j] == lcs_spec(s[0..i], u[0..j]) for all j in 0..len(u), inner loop builds cur for row i+1 with cur[x] == lcs_spec(s[0..i+1], u[0..x]); each step calls lemma lcs_step(s, u, i+1, j), the one-step unfolding of lcs_spec on prefixes (its proof asserts the slice-of-slice equalities s[0..i][0..i-1] == s[0..i-1]). v1 carried two extra nonnegativity invariants (main method 332k of the 500k limit); v2 replaced them by the inductive lemma lcs_nonneg (main method 162k). Final step uses full_slice(s, m) with requires m == len(s): the lowering folds the literal shape s[0..len(s)] to s, so the lemma is stated with a variable bound to give Dafny the real slice equality. Interpreter check: 400 random pairs, all invariants and ensures hold; lemma statements true on random instances. Twin: collapse-if (the match test in the inner loop), witness s=[0], u=[1]: real 0, twin 1.

## longest_palindrome_substring

Status: stated; Dafny verifies the real program and refutes its twin. Last verdict while writing: dafny: COUNTS, real is a real proof; off-by-one twin is refuted, the kernel found this wrong

```
predicate is_palindrome(s) => spec fun is_palindrome(s: seq): bool = forall i in [0, len(s)) . s[i] == s[len(s) - 1 - i]
predicate is_valid_subrange(s, start, len) => spec fun is_valid_subrange(s: seq, start: int, n: int): bool = 0 <= start and 0 <= n and start + n <= len(s)  [parameter 'len' renamed 'n' because len is a t keyword]
requires |s| <= 1000000 => requires len(s) <= 1000000
ensures res.0 >= 0 && res.1 >= 0 => ensures res.0 >= 0 and res.1 >= 0
ensures is_valid_subrange(s, res.0, res.1) => ensures is_valid_subrange(s, res.0, res.1)
ensures is_palindrome(s[res.0 .. res.0 + res.1]) => ensures is_palindrome(s[res.0..res.0 + res.1])
ensures forall i, len :: is_valid_subrange(s, i, len) && is_palindrome(s[i .. i + len]) ==> len <= res.1 => ensures forall i in [0, len(s) + 1) . no_longer(s, i, len(s), res.1), with spec fun no_longer(s, i, e, m) = forall n in [0, e + 1) . (is_valid_subrange(s, i, n) and is_palindrome(s[i..i + n])) ==> n <= m  [Dafny's i and len range over all ints, but the antecedent is_valid_subrange confines both to [0, |s|], so the bounded ranges lose nothing; the antecedent is kept verbatim; inner quantifier curried into a spec fun for the Dafny trigger reason]
```

Notes: Implementation is an exhaustive scan over all (start, length) pairs with a running best (bi, bl), not Manacher's algorithm; the contract is algorithm-agnostic. Proof helpers: nl_extend (extend the length range of one start) and nl_mono_all (a larger best keeps the bound for all earlier starts, by induction). The body deliberately uses != loop guards and max/ite expressions instead of if statements and order comparisons so that the twin ladder reaches an off-by-one twin whose witness is the empty string; the twins picked by if/compare rungs had witnesses whose ground certificates (an existential palindrome witness) Dafny cannot prove. Verify attempts: 1. Contract cross-check against the Dafny contract in Python: agree on 5929 (input, result) pairs.

## matrix_multiplication

Status: stated; Dafny verifies the real program and refutes its twin. Last verdict while writing: dafny: COUNTS, real is a real proof; compare-flip twin is refuted, the kernel found this wrong

```
requires |A| > 0 && |B| > 0 => requires len(A) > 0 and len(B) > 0
requires |A[0]| == |B| => requires len(A[0]) == len(B)
requires |A| <= 10 => requires len(A) <= 10
requires |B| <= 10 => requires len(B) <= 10
requires |B[0]| <= 10 => requires len(B[0]) <= 10
requires forall i :: 0 <= i < |A| ==> |A[i]| == |B| => requires forall i in [0, len(A)) . len(A[i]) == len(B)
requires forall i :: 0 <= i < |B| ==> |B[i]| == |B[0]| => requires forall i in [0, len(B)) . len(B[i]) == len(B[0])
requires forall i, j :: 0 <= i < |A| && 0 <= j < |A[i]| ==> 0 <= A[i][j] <= 100 => requires forall i in [0, len(A)) . forall j in [0, len(A[i])) . 0 <= A[i][j] and A[i][j] <= 100
requires forall i, j :: 0 <= i < |B| && 0 <= j < |B[i]| ==> 0 <= B[i][j] <= 100 => requires forall i in [0, len(B)) . forall j in [0, len(B[i])) . 0 <= B[i][j] and B[i][j] <= 100
ensures |C| == |A| => ensures len(C) == len(A)
ensures |C| > 0 ==> |C[0]| == |B[0]| => ensures len(C) > 0 ==> len(C[0]) == len(B[0])
ensures is_valid_matrix(C, |A|, |B[0]|) => ensures is_valid_matrix(C, len(A), len(B[0]))
ensures forall i, j :: (0 <= i < |C| && 0 <= j < |C[0]| ==> C[i][j] == dot_product(A[i], B, j, |B|)) => ensures forall i in [0, len(C)) . forall j in [0, len(C[0])) . C[i][j] == dot_product(A[i], B, j, len(B))
preamble predicate is_valid_matrix => spec fun is_valid_matrix(m, rows, cols) = len(m) == rows and (forall i in [0, rows) . len(m[i]) == cols), same body
preamble function dot_product (its 3 requires: 0<=k<=|row_vals|, k<=|B_vals|, 0<=c<|B_vals[i]| for all i<k) => spec fun dot_product, total as t requires: 0 when k<=0 or k>len(row_vals) or k>len(B_vals) or c<0 or c>=len(B_vals[k-1]), else row_vals[k-1]*B_vals[k-1][c] + dot_product(row_vals, B_vals, c, k-1); equal to the Dafny function wherever its requires hold, which includes the only call in the ensures (len(B) <= len(A[i]), c < len(B[0]) = len(B[i]))
```

Notes: 1 version, verified first try (Dafny run directly on the lowered source for diagnostics, then the official verify). Body: three nested while loops (rows of A, columns of B, dot product), invariants acc == dot_product(A[i], B, j, k), row[y] == dot_product(A[i], B, y, len(B)), and the C-prefix invariants; no lemmas needed. Interpreter check: 300 random matrices (sizes up to 4x4x4, including 0 columns), all invariants and ensures hold and C equals the textbook product. Twin: compare-flip (outer guard i < len(A) becomes i <= len(A)), witness A=[[0]], B=[[]]: real [[]], twin [[], []] (value witness falsifying len(C) == len(A)). Dafny resource use of the main method 138k of the 500k limit. Deviations from the Dafny text: none in the contract beyond the total-function form of dot_product noted in the mapping.

## maximum_subarray_sum

Status: stated; Dafny verifies the real program and refutes its twin. Last verdict while writing: dafny: COUNTS, real is a real proof; compare-flip twin is refuted, the kernel found this wrong

```
function spec_sum(s, start, end) requires 0 <= start <= end <= |s| => spec fun spec_sum(s: seq, start: int, end: int): int = if start >= end or start < 0 or end > len(s) then 0 else s[end - 1] + spec_sum(s, start, end - 1)  [t spec funs are total: the Dafny precondition becomes 'returns 0 outside 0 <= start <= end <= len(s)'; the value inside that range is identical]
requires |s| > 0 => requires len(s) > 0
requires |s| <= 100000 => requires len(s) <= 100000
ensures forall i: int, j: int :: 0 <= i <= j <= |s| ==> spec_sum(s, i, j) <= result => ensures forall i in [0, len(s) + 1) . sums_le(s, i, len(s), result), with spec fun sums_le(s, i, e, v) = forall j in [i, e + 1) . spec_sum(s, i, j) <= v  [the inner quantifier is curried into a spec fun; same pairs (i, j) with 0 <= i <= j <= len(s)]
ensures exists i: int, j: int :: 0 <= i <= j <= |s| && spec_sum(s, i, j) == result => ensures exists i in [0, len(s) + 1) . sums_hit(s, i, len(s), result), with spec fun sums_hit(s, i, e, v) = exists j in [i, e + 1) . spec_sum(s, i, j) == v
```

Notes: Kadane's algorithm with explicit witness indices (ca for the best suffix, ba/bb for the best subarray), invariants on suffix bound and prefix bound, and helper lemmas sum_snoc_all, extend_starts (induction over the start index) and hit_intro. Why the double quantifiers are curried into sums_le / sums_hit: written nested, Dafny prints 'Could not find a trigger for this quantifier' (no term mentions the outer variable alone), and the harness scores a run that verifies but warns as unproved. Measured in isolation with a trivially true task carrying only that nested quantifier: dafny 2 verified, 0 errors, exit 2, cli verify REFUSED real unproved. Also arithmetic in a call argument inside a quantifier body (hi + 1) kills the trigger, hence the inclusive upper-bound parameter e. Verify attempts: 2 (first used nested quantifiers and exists-invariants without witnesses: unproved; second COUNTS), plus two scratch probes outside the deliverable. Contract cross-check: the t requires/ensures and the Dafny contract transcribed to Python agree on 46860 (input, result) pairs.

## merge_sort

Status: stated; Dafny verifies the real program and refutes its twin. Last verdict while writing: dafny: COUNTS, real is a real proof; collapse-if twin is refuted, the kernel found this wrong

```
method merge_sort(v: seq<int>) returns (v_new: seq<int>) => task merge_sort(v: seq) returns (v_new: seq) with decreases len(v) for the recursion; the Dafny method has no requires and the task has none
ensures is_sorted(v_new) => ensures is_sorted(v_new), where preamble is_sorted(s) = forall i, j :: 0 <= i < j < |s| ==> s[i] <= s[j] is written inline fun is_sorted(s: seq): bool = forall i in [0, len(s)) . forall j in [i + 1, len(s)) . s[i] <= s[j]
ensures is_permutation(v, v_new) => ensures is_permutation(v, v_new), where spec fun is_permutation(v1, v2) = len(v1) == len(v2) and (forall i in [0, len(v1)) . occ(v1, v1[i]) == occ(v2, v1[i])) and (forall j in [0, len(v2)) . occ(v1, v2[j]) == occ(v2, v2[j]))
preamble is_valid_index_permutation(p, n) => not written: it occurs only under the existential that the allowed restatement of is_permutation replaces
```

Restatement: is_permutation(v1, v2) is the allowed bounded restatement len(v1) == len(v2) and (forall i in [0, len(v1)) . occ(v1, v1[i]) == occ(v2, v1[i])) and (forall j in [0, len(v2)) . occ(v1, v2[j]) == occ(v2, v2[j])); occ(s, x) = occn(s, x, len(s)) and spec fun occn(s, x, n) = if n <= 0 or n > len(s) then 0 else occn(s, x, n - 1) + (if s[n - 1] == x then 1 else 0), the number of positions k in [0, n) with s[k] == x, by recursion on n (same definitions as bubble_sort; equivalence to the index-permutation definition checked by brute force, 0 mismatches).

Notes: Recursive merge sort: base case len(v) <= 1, otherwise split at mid = len(v)/2, two self-calls on v[0..mid] and v[mid..], then a helper method merge(a, b) (requires both sorted, ensures is_sorted(m) and is_permutation(a + b, m)) implemented as a two-index loop. The merge loop invariant is bundled in one spec fun mg_inv (bounds, len(m) == i+j, is_sorted(m), m <= every remaining element of a and b, every element of m is in a + b, and for every position of the probe a + b the count identity occ(m,x) == occn(a,x,i) + occn(b,x,j)); the step lemmas mg_take_a / mg_take_b and the exit lemma mg_done prove it, and msort_perm combines is_permutation of the two halves and of the merge into is_permutation(v, v_new) through probe-lifted lemmas (occ_cat, occ_split, occ_snoc, perm_occ_upto, occ_zero). is_sorted is an `inline fun` instead of a `spec fun` for the measured reason given in bubble_sort. Twin = collapse-if (only the base case survives), witness v=[1,0] -> twin [1,0]. Kernel runs on this problem: 8 counting every diagnostic (first raw run with the invariants written inline passed but the merge method used 472k of the 500k rlimit; four diagnostic dafny runs located the cost; bundling the invariants into mg_inv cut it to about 238k; then raw run, cli verify, cli verify after renaming). Interpreter finds no counterexample to the real body.

## polymul_karatsuba

The t task is named `poly_multiply_karatsuba`. AlgoVeri names both polynomial problems' methods `poly_multiply`, and t keys a
table row and the lowered files by the task's name, so the two need distinct names.

Status: stated; Dafny verifies the real program and refutes its twin. Last verdict while writing: dafny: COUNTS, real is a real proof; collapse-if twin is refuted, the kernel found this wrong

```
requires |a| > 0 => requires len(a) > 0
requires |b| > 0 => requires len(b) > 0
requires |a| == |b| => requires len(a) == len(b)
requires exists k :: 0 <= k <= 10 && |a| == (1 << k) => requires exists k in [0, 11) . len(a) == pow(2, k)   (1 << k read as 2^k; see notes)
requires |a| + |b| <= 1000 => requires len(a) + len(b) <= 1000
requires coeffs_bounded(a) => requires coeffs_bounded(a)
requires coeffs_bounded(b) => requires coeffs_bounded(b)
ensures |res| == |a| + |b| - 1 => ensures len(res) == len(a) + len(b) - 1
ensures forall k :: 0 <= k < |res| ==> res[k] == spec_poly_mul_coeff(a, b, k) => ensures forall k in [0, len(res)) . res[k] == spec_poly_mul_coeff(a, b, k)
preamble to_int, coeffs_bounded, spec_convolution_sum, spec_poly_mul_coeff => spec funs with the same bodies as in polymul_naive.t (to_int identity and unused)
```

Notes: 3 versions. v1 (Dafny run directly): all algebra lemmas verified but cs_addL and cs_addR (nonlinear step (x[i]+x2[i])*y[k-i]) and the single big method kmul ran out of the 500000 resource limit (they pass at 5M: 2.1M, 1.0M, 2.2M). v2: distributivity helper lemmas mul_dist_l/mul_dist_r, kmul split into methods vadd and combine, internal contracts stated with a predicate is_prod(z, x, y) (len(z) == len(x)+len(y)-1 and z[j] == spec_poly_mul_coeff(x, y, j)); verified, official COUNTS. v3 (final): kara_coeff split into kara_d1 and kara_d2 for headroom; official COUNTS again; largest method is now 143k of the 500k limit, all 48 symbols verify, no warnings. Structure: the task cannot recurse on itself because z1 = (A0+A1)(B0+B1) has coefficients up to 2,000,000 and violates coeffs_bounded, so the recursion lives in method kmul(a, b) with requires len(a) == len(b) and p2(len(a)) (p2 = power of two, recursive spec fun) and no coefficient bound. kmul is the full Karatsuba: base case scalar product; else split a, b at m = len(a)/2, sa = a0+a1 and sb = b0+b1 (method vadd), z0 = kmul(a0,b0), z2 = kmul(a1,b1), z1 = kmul(sa,sb), result coefficient k = z0[k] + (z1[k-m]-z0[k-m]-z2[k-m]) + z2[k-2m] with out-of-range reads as 0 (spec fun kc over at0), assembled in method combine by a loop calling lemma kara_coeff each k. The ghost proof of the algebraic equivalence is lemma-only: tail lemma conv_tail, conv_last/conv_last_n/conv_out, cs_pre/cs_catL/cs_catR/cs_addL/cs_addR (induction on the sum index), conv_catL/conv_catR (concatenation in either argument), conv_addL/conv_addR (bilinearity), at0_conv, kara_d1 (four-way split), kara_d2 ((a0+a1)(b0+b1) expansion), kara_coeff. The task body is exists_p2(len(a)) (bridges the original exists/pow requirement to p2 via p2_pow induction) then `if len(a) == 1 { conv_single; res := [a[0]*b[0]] } else { res := kmul(a, b) }`. Twin: collapse-if on that top-level base-case branch (twins never mutate methods, so kmul's body is the fixed instrument), witness a=[0,0], b=[0,0]: real [0,0,0], twin [0]. Caveat 1: in the installed Dafny 4.11 the original `1 << k` on ints is a resolution error (`type of << must be a bitvector type (instead got int)`), so the Dafny spec as shipped does not type-check; its evident meaning 2^k for k in 0..10 is what the t requires states. Caveat 2: the interpreter step cap (60,000) is exceeded for len(a) >= 16 because the method requires is_prod(...) is evaluated at run time; lengths 1, 2, 4, 8 run correctly (150 random runs match the textbook product), the cap does not affect Dafny verification or the twin search (domain lengths <= 5). All lemma statements were also checked true on thousands of random instances before the kernel run.

## polymul_naive

The t task is named `poly_multiply_naive`. AlgoVeri names both polynomial problems' methods `poly_multiply`, and t keys a
table row and the lowered files by the task's name, so the two need distinct names.

Status: stated; Dafny verifies the real program and refutes its twin. Last verdict while writing: dafny: COUNTS, real is a real proof; compare-flip twin is refuted, the kernel found this wrong

```
requires |a| > 0 => requires len(a) > 0
requires |b| > 0 => requires len(b) > 0
requires |a| + |b| <= 1000 => requires len(a) + len(b) <= 1000
requires coeffs_bounded(a) => requires coeffs_bounded(a)
requires coeffs_bounded(b) => requires coeffs_bounded(b)
ensures |res| == |a| + |b| - 1 => ensures len(res) == len(a) + len(b) - 1
ensures forall k :: 0 <= k < |res| ==> res[k] == spec_poly_mul_coeff(a, b, k) => ensures forall k in [0, len(res)) . res[k] == spec_poly_mul_coeff(a, b, k)
preamble to_int => spec fun to_int(s) = s (identity, unused by the contract)
preamble predicate coeffs_bounded => spec fun coeffs_bounded(s) = forall i in [0, len(s)) . -1000000 <= s[i] and s[i] <= 1000000
preamble function spec_convolution_sum (decreases if current_i < 0 then 0 else current_i + 1) => spec fun spec_convolution_sum with the same decreases; the Dafny let-binding `term` is inlined as the parenthesised if-expression, same guards in the same order
preamble function spec_poly_mul_coeff => spec fun spec_poly_mul_coeff(a, b, k) = spec_convolution_sum(a, b, k, k)
```

Notes: 2 versions. v1 (Dafny run directly) failed: my lemma conv_tail had a quantified requires over p whose body is pure arithmetic, so Dafny found no trigger and could not use it. v2 replaced it by the quantifier-free sufficient condition `lo >= len(a) - 1 or k <= lo or k - hi >= len(b)`; verified (7 symbols, 0 errors, no warnings), then the official verify counted. Implementation is the faithful naive algorithm from the NL: res := seq(len(a)+len(b)-1, 0), outer loop over a, inner loop over b, res := res[i+j := res[i+j] + a[i]*b[j]]. Accumulation invariants: outer res[k] == spec_convolution_sum(a, b, k, i-1); inner res[k] == spec_convolution_sum(a, b, k, i-1) + (if k-i >= 0 and k-i < j then a[i]*b[k-i] else 0). Helper lemmas conv_tail (induction), conv_last, conv_last_all (spec_poly_mul_coeff(a,b,k) == spec_convolution_sum(a,b,k,len(a)-1) for every k below n) bridge the final sum bound to the spec's k-indexed one. Interpreter check: 500 random inputs, invariants and ensures hold, equals the textbook product; the lemma statements were also checked true on thousands of random instances. Twin: compare-flip (outer guard to <=), witness a=[0], b=[0], twin undefined at index 1 outside [0,1); the kernel refuted it. Main method 171k of the 500k resource limit. The 64-bit overflow remarks of the NL are not modelled (t integers are mathematical), the coeffs_bounded and size requires are kept as written.

## quick_sort

Status: stated; Dafny verifies the real program and refutes its twin. Last verdict while writing: dafny: COUNTS, real is a real proof; collapse-if twin is refuted, the kernel found this wrong

```
method quick_sort(v: seq<int>) returns (v_new: seq<int>) => task quick_sort(v: seq) returns (v_new: seq) with decreases len(v) for the recursion; the Dafny method has no requires and the task has none
ensures is_sorted(v_new) => ensures is_sorted(v_new), where preamble is_sorted(s) = forall i, j :: 0 <= i < j < |s| ==> s[i] <= s[j] is written inline fun is_sorted(s: seq): bool = forall i in [0, len(s)) . forall j in [i + 1, len(s)) . s[i] <= s[j]
ensures is_permutation(v, v_new) => ensures is_permutation(v, v_new), where spec fun is_permutation(v1, v2) = len(v1) == len(v2) and (forall i in [0, len(v1)) . occ(v1, v1[i]) == occ(v2, v1[i])) and (forall j in [0, len(v2)) . occ(v1, v2[j]) == occ(v2, v2[j]))
preamble is_valid_index_permutation(p, n) => not written: it occurs only under the existential that the allowed restatement of is_permutation replaces
```

Restatement: is_permutation(v1, v2) is the allowed bounded restatement len(v1) == len(v2) and (forall i in [0, len(v1)) . occ(v1, v1[i]) == occ(v2, v1[i])) and (forall j in [0, len(v2)) . occ(v1, v2[j]) == occ(v2, v2[j])); occ(s, x) = occn(s, x, len(s)) and spec fun occn(s, x, n) = if n <= 0 or n > len(s) then 0 else occn(s, x, n - 1) + (if s[n - 1] == x then 1 else 0), the number of positions k in [0, n) with s[k] == x, by recursion on n (same definitions as bubble_sort; equivalence to the index-permutation definition checked by brute force, 0 mismatches).

Notes: Deterministic quick sort with the first element as pivot, as in the natural-language statement. Helper method partition(s) (requires len(s) > 0) is an in-place Lomuto partition on the seq value using swaps: ensures len(res.0) == len(s), 0 <= res.1 < len(s), res.0[res.1] == s[0], everything before res.1 is < s[0], everything after is >= s[0], is_permutation(s, res.0); it returns the pair (reordered seq, pivot index). The driver calls partition, recurses on q[0..m] and q[m+1..] (decreases len(v); the pivot index is strictly inside, so both parts are shorter) and returns lo + [q[m]] + hi. Lemmas qsort_sorted (uses perm_members_upto: elements of a permutation of q[0..m] are elements of q[0..m], so lo[k] <= q[m]; then sorted_pivot) and qsort_perm (probe-lifted occ_split3, occ_cat, occ_snoc, perm_occ_upto) close the recursion; perm_swap (from occ_upd/occ_swap) carries the permutation through the partition loop. is_sorted is an `inline fun` instead of a `spec fun` for the measured reason given in bubble_sort. Twin = collapse-if (only the base case survives), witness v=[1,0] -> twin [1,0]. Kernel runs on this problem: 3 (raw dafny, cli verify, cli verify after renaming). Largest Z3 cost about 186k of the 500k rlimit (the partition method). Interpreter finds no counterexample to the real body.

## sieve_method

Status: stated; Dafny verifies the real program and refutes its twin. Last verdict while writing: dafny: COUNTS, real is a real proof; negate-cond twin is refuted, the kernel found this wrong

```
predicate divides(d, n) requires d != 0 { n % d == 0 } => spec fun divides(d: int, m: int): bool = d != 0 and m % d == 0
predicate is_prime(n) { n > 1 && forall d :: 1 < d < n ==> !divides(d, n) } => spec fun is_prime(m: int): bool = m > 1 and (forall d in [2, m) . not divides(d, m))
requires 0 <= n <= 100_000 => requires 0 <= n and n <= 100000
ensures |primes| == n => ensures len(primes) == n
ensures forall i :: 0 <= i < n ==> primes[i] == is_prime(i) => ensures forall i in [0, n) . primes[i] == is_prime(i)
```

Notes: 3 verify attempts (2 versions run in Dafny directly, plus the official cli.py verify). (a) divides carries the guard d != 0 as a conjunct because a t spec fun has no requires; it agrees with the Dafny predicate wherever that is defined, and is_prime only calls it with d in [2, m). (b) The chained 0 <= n <= 100_000 is the conjunction 0 <= n and n <= 100000; 1 < d < n is d in [2, n). Body: the optimized sieve: array built as [z >= 2] per index, then while i * i < n, if primes[i] mark j = i*i, i*i + i, ... false (the inner loop is the method mark_step), else nothing. Proof: invariant sieve_ok(p, n, i) = p[k] == (k >= 2 and no divisor d in [2, i) with d < k); lemmas cover the nonlinear steps (monotonicity by induction, quotient/remainder uniqueness, no multiple of i strictly between i*c and i*c + i, a k in (i, i*i) with i | k already has a smaller divisor, divisibility is transitive so skipping a composite i is safe, a composite k < i*i has a divisor below i). Version 1 failed in mod_unique (14M rlimit units of nonlinear search) and its infeasible `if` branches drew --warn-contradictory-assumptions warnings (exit 2 = MALFORMED); version 2 uses atom-only lemmas and implication-form monotonicity lemmas, all procedures under 111k rlimit units.

## string_search_naive

Status: stated; Dafny verifies the real program and refutes its twin. Last verdict while writing: dafny: COUNTS, real is a real proof; collapse-if twin is refuted, the kernel found this wrong

```
predicate matches_at(haystack, needle, start_index) { 0 <= start_index && start_index + |needle| <= |haystack| && forall i :: 0 <= i < |needle| ==> haystack[start_index + i] == needle[i] } => spec fun char_eq(hs, nd, start_index, i) = 0 <= i and i < len(nd) and 0 <= start_index + i and start_index + i < len(hs) and hs[start_index + i] == nd[i]; spec fun matches_at(hs, nd, start_index) = 0 <= start_index and start_index + len(nd) <= len(hs) and (forall i in [0, len(nd)) . char_eq(hs, nd, start_index, i))
requires |haystack| < 1000000 => requires len(haystack) < 1000000
requires |needle| < 1000000 => requires len(needle) < 1000000
ensures forall k :: 0 <= k < |indices| ==> indices[k] >= 0 => ensures forall k in [0, len(indices)) . indices[k] >= 0
ensures forall i :: 0 <= i < |indices| ==> matches_at(haystack, needle, indices[i]) => ensures forall i in [0, len(indices)) . matches_at(haystack, needle, indices[i])
ensures forall i :: matches_at(haystack, needle, i) ==> exists k :: 0 <= k < |indices| && indices[k] == i => ensures forall i in [0, len(haystack) + 1) . matches_at(haystack, needle, i) ==> (exists k in [0, len(indices)) . indices[k] == i)
```

Notes: 2 verify attempts. (a) The unbounded `forall i` of the third ensures is the bounded range [0, len(haystack) + 1): matches_at forces 0 <= i and i + |needle| <= |haystack|, so no i with matches_at true is lost; the clause is equivalent, not weaker. (b) char_eq only factors the preamble's equality hs[start_index + i] == nd[i] into a spec fun with index guards; on the quantifier's range every guard is true, so matches_at is the preamble predicate. Reason: attempt 1 wrote the quantifier literally and the real proved, but the twin certificate (assert matches_at(..) == false) could not instantiate the quantifier (no ground term), so the twin read unproved; with the spec-fun call in the quantifier body the certificate ladder supplies the ground term and the twin is refuted. Body: outer loop over starts while pos + len(needle) <= len(haystack), inner char-by-char loop, append pos on a full match.

## trial_division_naive

Status: stated; Dafny verifies the real program and refutes its twin. Last verdict while writing: dafny: COUNTS, real is a real proof; collapse-if twin is refuted, the kernel found this wrong

```
predicate divides(d: int, n: int) requires d != 0 { n % d == 0 } => spec fun divides(d: int, n: int): bool decreases 0 = d != 0 and n % d == 0
predicate is_prime(n: int) { n > 1 && forall d :: 1 < d < n ==> !divides(d, n) } => spec fun is_prime(n: int): bool decreases 0 = n > 1 and (forall d in [2, n) . not divides(d, n))
requires n >= 0 => requires n >= 0
ensures res == is_prime(n) => ensures res == is_prime(n)
```

Notes: Task is named trial_division_naive (the id); the Dafny method name was check_prime. Two judgment calls on the preamble, neither touching the method contract. (1) t spec funs are total and carry no requires, and an unguarded n % d in a spec fun body is rejected by Dafny (possible division by zero), so divides is d != 0 and n % d == 0: identical to the Dafny predicate wherever its precondition d != 0 holds, and is_prime only calls it with d in [2, n). (2) forall d :: 1 < d < n ==> ... is over ints guarded by 1 < d < n, which is exactly the bounded range [2, n), so it is written as the bounded quantifier (no non-int quantification involved). Body: n < 2 -> false; else i from 2 while i < n with invariants 2 <= i <= n and forall k in [2, i) . not divides(k, n), return false at the first divisor, true after the loop. Helper lemma divisor_makes_composite (2 <= d < n and n % d == 0 implies not is_prime(n), proved by assert divides(d, n) so the solver instantiates the quantifier), called before the early return. One cli verify attempt, COUNTS (before it I ran dafny directly, memory capped, twice to see that the early-return path needed that lemma; not counted as attempts).

## trial_division_optimized

Status: stated; Dafny verifies the real program and refutes its twin. Last verdict while writing: dafny: COUNTS, real is a real proof; collapse-if twin is refuted, the kernel found this wrong

```
predicate divides(d: int, n: int) requires d != 0 { n % d == 0 } => spec fun divides(d: int, n: int): bool decreases 0 = d != 0 and n % d == 0
predicate is_prime(n: int) { n > 1 && forall d :: 1 < d < n ==> !divides(d, n) } => spec fun is_prime(n: int): bool decreases 0 = n > 1 and (forall d in [2, n) . not divides(d, n))
requires n >= 0 => requires n >= 0
ensures res == is_prime(n) => ensures res == is_prime(n)
```

Notes: Task is named trial_division_optimized (the id); the Dafny method name was check_prime. Same preamble translation as trial_division_naive (divides totalized with d != 0; the bounded forall over [2, n) is exactly 1 < d < n). Body: n < 2 -> false; else i from 2 while i * i <= n, invariants 2 <= i and forall k in [2, i) . not divides(k, n), decreases n - i; return false at the first divisor; after the loop (i * i > n) call prime_beyond_root and return true. The sqrt-bound proof is a chain of t lemmas, each with only if/assert/lemma calls: mul_mono (a <= b, c >= 0 implies a*c <= b*c, by induction on c), quotient_unique, mod_of_multiple ((q*d) % q == 0, from the two, because Z3 cannot do that nonlinear step unaided), no_divisor_above_root (a divisor d >= i with i*i > n has cofactor n/d in [2, i) that also divides n, contradicting the invariant), no_divisors_above_root (range version by recursion on d, which lifts the pointwise fact to a bounded forall without a forall statement), prime_beyond_root (is_prime(n)), plus divisor_makes_composite for the early return. One cli verify attempt, COUNTS (I prototyped the lemma chain by running dafny directly, memory capped, before the cli attempt; those runs are not counted).
