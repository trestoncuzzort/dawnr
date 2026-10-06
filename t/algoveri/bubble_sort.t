t 1
task bubble_sort(v: seq) returns (v_new: seq)
  ensures is_sorted(v_new)
  ensures is_permutation(v, v_new)
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
{
  v_new := v;
  var n: int := len(v);
  var i: int := 0;
  while i < n
    invariant 0 <= i and i <= n
    invariant len(v_new) == n
    invariant is_permutation(v, v_new)
    invariant forall k in [0, n) . forall l in [k + 1, n) . n - i <= l ==> v_new[k] <= v_new[l]
    decreases n - i
  {
    var j: int := 0;
    while j < n - 1 - i
      invariant 0 <= j and j <= n - 1 - i
      invariant len(v_new) == n
      invariant is_permutation(v, v_new)
      invariant forall k in [0, n) . forall l in [k + 1, n) . n - i <= l ==> v_new[k] <= v_new[l]
      invariant forall k in [0, j + 1) . v_new[k] <= v_new[j]
      decreases n - 1 - i - j
    {
      if v_new[j] > v_new[j + 1] {
        perm_swap(v, v_new, j, j + 1);
        v_new := v_new[j := v_new[j + 1]][j + 1 := v_new[j]];
      }
      j := j + 1;
    }
    i := i + 1;
  }
}
