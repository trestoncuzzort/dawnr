t 1
task quick_sort(v: seq) returns (v_new: seq)
  ensures is_sorted(v_new)
  ensures is_permutation(v, v_new)
  decreases len(v)
inline fun is_sorted(s: seq): bool = forall i in [0, len(s)) . forall j in [i + 1, len(s)) . s[i] <= s[j]
spec fun occn(s: seq, x: int, n: int): int
  decreases n
= if n <= 0 or n > len(s) then 0 else occn(s, x, n - 1) + (if s[n - 1] == x then 1 else 0)
spec fun occ(s: seq, x: int): int
  decreases 0
= occn(s, x, len(s))
spec fun is_permutation(v1: seq, v2: seq): bool
  decreases 0
= len(v1) == len(v2) and (forall i in [0, len(v1)) . occ(v1, v1[i]) == occ(v2, v1[i])) and (forall j in [0, len(v2)) . occ(v1, v2[j]) == occ(v2, v2[j]))
lemma occn_upd(s: seq, i: int, e: int, n: int, w: seq)
  requires 0 <= i and i < len(s)
  requires 0 <= n and n <= len(s)
  ensures forall k in [0, len(w)) . occn(s[i := e], w[k], n) == occn(s, w[k], n) + (if i < n then (if e == w[k] then 1 else 0) - (if s[i] == w[k] then 1 else 0) else 0)
  decreases n
{
  if n > 0 {
    occn_upd(s, i, e, n - 1, w);
  }
}
lemma occ_upd(s: seq, i: int, e: int, w: seq)
  requires 0 <= i and i < len(s)
  ensures forall k in [0, len(w)) . occ(s[i := e], w[k]) == occ(s, w[k]) + (if e == w[k] then 1 else 0) - (if s[i] == w[k] then 1 else 0)
{
  occn_upd(s, i, e, len(s), w);
}
lemma occ_swap(s: seq, i: int, j: int, w: seq)
  requires 0 <= i and i < len(s)
  requires 0 <= j and j < len(s)
  ensures forall k in [0, len(w)) . occ(s[i := s[j]][j := s[i]], w[k]) == occ(s, w[k])
{
  occ_upd(s, i, s[j], w);
  occ_upd(s[i := s[j]], j, s[i], w);
}
lemma occn_zero(s: seq, x: int, n: int)
  requires not (x in s)
  requires 0 <= n and n <= len(s)
  ensures occn(s, x, n) == 0
  decreases n
{
  if n > 0 {
    occn_zero(s, x, n - 1);
  }
}
lemma occ_zero(s: seq, x: int)
  requires not (x in s)
  ensures occ(s, x) == 0
{
  occn_zero(s, x, len(s));
}
lemma perm_occ_pt(a: seq, b: seq, x: int)
  requires is_permutation(a, b)
  ensures occ(a, x) == occ(b, x)
{
  if x in a {
  } else {
    if x in b {
    } else {
      occ_zero(a, x);
      occ_zero(b, x);
    }
  }
}
lemma perm_occ_upto(a: seq, b: seq, w: seq, m: int)
  requires is_permutation(a, b)
  requires 0 <= m and m <= len(w)
  ensures forall k in [0, m) . occ(a, w[k]) == occ(b, w[k])
  decreases m
{
  if m > 0 {
    perm_occ_upto(a, b, w, m - 1);
    perm_occ_pt(a, b, w[m - 1]);
  }
}
lemma perm_swap(v: seq, r: seq, i: int, j: int)
  requires is_permutation(v, r)
  requires 0 <= i and i < len(r)
  requires 0 <= j and j < len(r)
  ensures is_permutation(v, r[i := r[j]][j := r[i]])
{
  occ_swap(r, i, j, v);
  occ_swap(r, i, j, r[i := r[j]][j := r[i]]);
  perm_occ_upto(v, r, r[i := r[j]][j := r[i]], len(r));
}
lemma occn_pre(a: seq, b: seq, n: int, w: seq)
  requires 0 <= n and n <= len(a)
  ensures forall k in [0, len(w)) . occn(a + b, w[k], n) == occn(a, w[k], n)
  decreases n
{
  if n > 0 {
    occn_pre(a, b, n - 1, w);
  }
}
lemma occn_cat(a: seq, b: seq, m: int, w: seq)
  requires 0 <= m and m <= len(b)
  ensures forall k in [0, len(w)) . occn(a + b, w[k], len(a) + m) == occ(a, w[k]) + occn(b, w[k], m)
  decreases m
{
  if m == 0 {
    occn_pre(a, b, len(a), w);
  } else {
    occn_cat(a, b, m - 1, w);
  }
}
lemma occ_cat(a: seq, b: seq, w: seq)
  ensures forall k in [0, len(w)) . occ(a + b, w[k]) == occ(a, w[k]) + occ(b, w[k])
{
  occn_cat(a, b, len(b), w);
}
lemma occ_snoc(m: seq, e: int, w: seq)
  ensures forall k in [0, len(w)) . occ(m + [e], w[k]) == occ(m, w[k]) + (if e == w[k] then 1 else 0)
{
  occn_pre(m, [e], len(m), w);
}
lemma occ_split(s: seq, p: int, w: seq)
  requires 0 <= p and p <= len(s)
  ensures forall k in [0, len(w)) . occ(s, w[k]) == occ(s[0..p], w[k]) + occ(s[p..], w[k])
{
  assert s[0..p] + s[p..] == s;
  occ_cat(s[0..p], s[p..], w);
}
lemma occ_split3(q: seq, m: int, w: seq)
  requires 0 <= m and m < len(q)
  ensures forall k in [0, len(w)) . occ(q, w[k]) == occ(q[0..m], w[k]) + (if q[m] == w[k] then 1 else 0) + occ(q[m + 1..], w[k])
{
  occ_split(q, m + 1, w);
  assert q[0..m + 1] == q[0..m] + [q[m]];
  occ_snoc(q[0..m], q[m], w);
}
lemma occn_nonneg(s: seq, x: int, n: int)
  requires 0 <= n and n <= len(s)
  ensures occn(s, x, n) >= 0
  decreases n
{
  if n > 0 {
    occn_nonneg(s, x, n - 1);
  }
}
lemma occn_self(s: seq, n: int)
  requires 0 <= n and n <= len(s)
  ensures forall k in [0, n) . occn(s, s[k], n) >= 1
  decreases n
{
  if n > 0 {
    occn_self(s, n - 1);
    occn_nonneg(s, s[n - 1], n - 1);
  }
}
lemma perm_member_pt(a: seq, b: seq, x: int)
  requires is_permutation(a, b)
  requires x in b
  ensures x in a
{
  occn_self(b, len(b));
  if x in a {
  } else {
    occ_zero(a, x);
  }
}
lemma perm_members_upto(a: seq, b: seq, m: int)
  requires is_permutation(a, b)
  requires 0 <= m and m <= len(b)
  ensures forall k in [0, m) . b[k] in a
  decreases m
{
  if m > 0 {
    perm_members_upto(a, b, m - 1);
    perm_member_pt(a, b, b[m - 1]);
  }
}
lemma sorted_snoc(m: seq, e: int)
  requires is_sorted(m)
  requires forall k in [0, len(m)) . m[k] <= e
  ensures is_sorted(m + [e])
{
}
lemma sorted_cat(a: seq, b: seq)
  requires is_sorted(a)
  requires is_sorted(b)
  requires forall i in [0, len(a)) . forall j in [0, len(b)) . a[i] <= b[j]
  ensures is_sorted(a + b)
{
}
lemma sorted_pivot(lo: seq, p: int, hi: seq)
  requires is_sorted(lo)
  requires is_sorted(hi)
  requires forall k in [0, len(lo)) . lo[k] <= p
  requires forall k in [0, len(hi)) . p <= hi[k]
  ensures is_sorted(lo + [p] + hi)
{
  sorted_snoc(lo, p);
  sorted_cat(lo + [p], hi);
}
lemma qsort_sorted(q: seq, m: int, lo: seq, hi: seq)
  requires 0 <= m and m < len(q)
  requires forall k in [0, m) . q[k] <= q[m]
  requires forall k in [m + 1, len(q)) . q[m] <= q[k]
  requires is_sorted(lo)
  requires is_sorted(hi)
  requires is_permutation(q[0..m], lo)
  requires is_permutation(q[m + 1..], hi)
  ensures is_sorted(lo + [q[m]] + hi)
{
  perm_members_upto(q[0..m], lo, len(lo));
  perm_members_upto(q[m + 1..], hi, len(hi));
  assert forall k in [0, len(lo)) . lo[k] <= q[m];
  assert forall k in [0, len(hi)) . q[m] <= hi[k];
  sorted_pivot(lo, q[m], hi);
}
lemma qsort_perm(v: seq, q: seq, m: int, lo: seq, hi: seq)
  requires 0 <= m and m < len(q)
  requires is_permutation(v, q)
  requires is_permutation(q[0..m], lo)
  requires is_permutation(q[m + 1..], hi)
  ensures is_permutation(v, lo + [q[m]] + hi)
{
  perm_occ_upto(v, q, v, len(v));
  occ_split3(q, m, v);
  perm_occ_upto(q[0..m], lo, v, len(v));
  perm_occ_upto(q[m + 1..], hi, v, len(v));
  occ_cat(lo + [q[m]], hi, v);
  occ_snoc(lo, q[m], v);
  perm_occ_upto(v, q, lo + [q[m]] + hi, len(lo + [q[m]] + hi));
  occ_split3(q, m, lo + [q[m]] + hi);
  perm_occ_upto(q[0..m], lo, lo + [q[m]] + hi, len(lo + [q[m]] + hi));
  perm_occ_upto(q[m + 1..], hi, lo + [q[m]] + hi, len(lo + [q[m]] + hi));
  occ_cat(lo + [q[m]], hi, lo + [q[m]] + hi);
  occ_snoc(lo, q[m], lo + [q[m]] + hi);
}
method partition(s: seq) returns (res: (seq, int))
  requires len(s) > 0
  ensures len(res.0) == len(s)
  ensures 0 <= res.1 and res.1 < len(s)
  ensures res.0[res.1] == s[0]
  ensures forall k in [0, res.1) . res.0[k] < s[0]
  ensures forall k in [res.1 + 1, len(s)) . res.0[k] >= s[0]
  ensures is_permutation(s, res.0)
{
  var p: seq := s;
  var pivot: int := s[0];
  var store: int := 1;
  var i: int := 1;
  while i < len(s)
    invariant 1 <= store and store <= i and i <= len(s)
    invariant len(p) == len(s)
    invariant p[0] == pivot
    invariant forall k in [1, store) . p[k] < pivot
    invariant forall k in [store, i) . p[k] >= pivot
    invariant is_permutation(s, p)
    decreases len(s) - i
  {
    if p[i] < pivot {
      perm_swap(s, p, i, store);
      p := p[i := p[store]][store := p[i]];
      store := store + 1;
    }
    i := i + 1;
  }
  perm_swap(s, p, 0, store - 1);
  p := p[0 := p[store - 1]][store - 1 := p[0]];
  res := (p, store - 1);
}
{
  if len(v) <= 1 {
    v_new := v;
  } else {
    var pr: (seq, int) := partition(v);
    var q: seq := pr.0;
    var m: int := pr.1;
    var lo: seq := quick_sort(q[0..m]);
    var hi: seq := quick_sort(q[m + 1..]);
    v_new := lo + [q[m]] + hi;
    qsort_sorted(q, m, lo, hi);
    qsort_perm(v, q, m, lo, hi);
  }
}
