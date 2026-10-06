t 1
task merge_sort(v: seq) returns (v_new: seq)
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
spec fun mg_ord(a: seq, b: seq, m: seq, i: int, j: int): bool
  decreases 0
= 0 <= i and 0 <= j and (forall k in [0, len(m)) . (forall l in [i, len(a)) . m[k] <= a[l]) and (forall l in [j, len(b)) . m[k] <= b[l]))
spec fun mg_mem(a: seq, b: seq, m: seq): bool
  decreases 0
= forall k in [0, len(m)) . m[k] in a + b
spec fun mg_cnt(a: seq, b: seq, m: seq, i: int, j: int): bool
  decreases 0
= forall k in [0, len(a) + len(b)) . occ(m, (a + b)[k]) == occn(a, (a + b)[k], i) + occn(b, (a + b)[k], j)
spec fun mg_pre(a: seq, b: seq): bool
  decreases 0
= is_sorted(a) and is_sorted(b)
spec fun mg_inv(a: seq, b: seq, m: seq, i: int, j: int): bool
  decreases 0
= 0 <= i and i <= len(a) and 0 <= j and j <= len(b) and len(m) == i + j and is_sorted(m) and mg_ord(a, b, m, i, j) and mg_mem(a, b, m) and mg_cnt(a, b, m, i, j)
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
lemma sorted_snoc(m: seq, e: int)
  requires is_sorted(m)
  requires forall k in [0, len(m)) . m[k] <= e
  ensures is_sorted(m + [e])
{
}
lemma mg_take_a(a: seq, b: seq, m: seq, i: int, j: int)
  requires mg_pre(a, b)
  requires mg_inv(a, b, m, i, j)
  requires i < len(a)
  requires j >= len(b) or a[i] <= b[j]
  ensures mg_inv(a, b, m + [a[i]], i + 1, j)
{
  sorted_snoc(m, a[i]);
  occ_snoc(m, a[i], a + b);
}
lemma mg_take_b(a: seq, b: seq, m: seq, i: int, j: int)
  requires mg_pre(a, b)
  requires mg_inv(a, b, m, i, j)
  requires j < len(b)
  requires i >= len(a) or b[j] <= a[i]
  ensures mg_inv(a, b, m + [b[j]], i, j + 1)
{
  sorted_snoc(m, b[j]);
  occ_snoc(m, b[j], a + b);
}
lemma mg_done(a: seq, b: seq, m: seq, i: int, j: int)
  requires mg_inv(a, b, m, i, j)
  requires i == len(a) and j == len(b)
  ensures is_permutation(a + b, m)
{
  occ_cat(a, b, a + b);
}
lemma msort_perm(v: seq, mid: int, a: seq, b: seq, r: seq)
  requires 0 <= mid and mid <= len(v)
  requires is_permutation(v[0..mid], a)
  requires is_permutation(v[mid..], b)
  requires is_permutation(a + b, r)
  ensures is_permutation(v, r)
{
  occ_split(v, mid, v);
  occ_cat(a, b, v);
  perm_occ_upto(v[0..mid], a, v, len(v));
  perm_occ_upto(v[mid..], b, v, len(v));
  perm_occ_upto(a + b, r, v, len(v));
  occ_split(v, mid, r);
  occ_cat(a, b, r);
  perm_occ_upto(v[0..mid], a, r, len(r));
  perm_occ_upto(v[mid..], b, r, len(r));
  perm_occ_upto(a + b, r, r, len(r));
}
method merge(a: seq, b: seq) returns (m: seq)
  requires mg_pre(a, b)
  ensures is_sorted(m)
  ensures is_permutation(a + b, m)
{
  m := [];
  var i: int := 0;
  var j: int := 0;
  while i < len(a) or j < len(b)
    invariant mg_inv(a, b, m, i, j)
    decreases len(a) + len(b) - i - j
  {
    if i < len(a) and (j >= len(b) or a[i] <= b[j]) {
      mg_take_a(a, b, m, i, j);
      m := m + [a[i]];
      i := i + 1;
    } else {
      mg_take_b(a, b, m, i, j);
      m := m + [b[j]];
      j := j + 1;
    }
  }
  mg_done(a, b, m, i, j);
}
{
  if len(v) <= 1 {
    v_new := v;
  } else {
    var mid: int := len(v) / 2;
    var a: seq := merge_sort(v[0..mid]);
    var b: seq := merge_sort(v[mid..]);
    v_new := merge(a, b);
    msort_perm(v, mid, a, b, v_new);
  }
}
