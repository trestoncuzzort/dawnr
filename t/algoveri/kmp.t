t 1
gate loops
task kmp(haystack: seq, needle: seq) returns (indices: seq)
  requires len(haystack) < 1000000
  requires len(needle) < 1000000
  ensures forall k in [0, len(indices)) . indices[k] >= 0
  ensures forall i in [0, len(indices)) . matches_at(haystack, needle, indices[i])
  ensures forall i in [0, len(haystack) + 1) . matches_at(haystack, needle, i) ==> (exists k in [0, len(indices)) . indices[k] == i)
spec fun char_eq(hs: seq, nd: seq, start_index: int, i: int): bool
  decreases 0
= 0 <= i and i < len(nd) and 0 <= start_index + i and start_index + i < len(hs) and hs[start_index + i] == nd[i]
spec fun matches_at(hs: seq, nd: seq, start_index: int): bool
  decreases 0
= 0 <= start_index and start_index + len(nd) <= len(hs) and (forall i in [0, len(nd)) . char_eq(hs, nd, start_index, i))
spec fun pref(h: seq, p: seq, e: int, k: int): bool
  decreases k
= if k <= 0 then (k == 0 and 0 <= e and e <= len(h)) else (k <= e and k <= len(p) and e <= len(h) and h[e - 1] == p[k - 1] and pref(h, p, e - 1, k - 1))
spec fun maxl(h: seq, p: seq, e: int, q: int): bool
  decreases 0
= forall k in [q + 1, len(p)) . not pref(h, p, e, k)
spec fun fb3(h: seq, p: seq, e: int, q: int, u: int): bool
  decreases 0
= forall k in [q + 1, u) . pref(h, p, e, k) ==> (e >= len(h) or k >= len(p) or h[e] != p[k])
spec fun fb_inv(h: seq, p: seq, e: int, q: int, u: int): bool
  decreases 0
= 0 <= q and q < u and u <= len(p) and pref(h, p, e, q) and fb3(h, p, e, q, u)
spec fun lps_ok(p: seq, fail: seq, n: int): bool
  decreases 0
= 0 <= n and n <= len(p) and n < len(fail) and (forall q in [1, n + 1) . 0 <= fail[q] and fail[q] < q and pref(p, p, q, fail[q])) and (forall q in [1, n + 1) . forall kk in [fail[q] + 1, q) . not pref(p, p, q, kk))
spec fun idx_sound(h: seq, p: seq, ind: seq): bool
  decreases 0
= forall k in [0, len(ind)) . ind[k] >= 0 and matches_at(h, p, ind[k])
spec fun idx_complete(h: seq, p: seq, ind: seq, n: int): bool
  decreases 0
= forall s in [0, n) . matches_at(h, p, s) ==> (exists k in [0, len(ind)) . ind[k] == s)
spec fun kmp_inv(h: seq, p: seq, i: int, q: int, ind: seq): bool
  decreases 0
= 0 <= i and i <= len(h) and 0 <= q and q < len(p) and pref(h, p, i, q) and maxl(h, p, i, q) and idx_sound(h, p, ind) and idx_complete(h, p, ind, i - len(p) + 1)
lemma pref_zero(h: seq, p: seq, e: int)
  requires 0 <= e and e <= len(h)
  ensures pref(h, p, e, 0)
{
}
lemma pref_ext(h: seq, p: seq, e: int, k: int)
  requires pref(h, p, e, k)
  requires k < len(p) and e < len(h) and h[e] == p[k]
  ensures pref(h, p, e + 1, k + 1)
{
}
lemma pref_trans(h: seq, p: seq, e: int, q: int, b: int)
  requires pref(h, p, e, q)
  requires pref(p, p, q, b)
  ensures pref(h, p, e, b)
  decreases b
{
  if b > 0 {
    pref_trans(h, p, e - 1, q - 1, b - 1);
  } else {
  }
}
lemma pref_nested1(h: seq, p: seq, e: int, q: int, k: int)
  requires pref(h, p, e, q)
  requires pref(h, p, e, k)
  requires 0 <= k and k <= q
  ensures pref(p, p, q, k)
  decreases k
{
  if k > 0 {
    pref_nested1(h, p, e - 1, q - 1, k - 1);
  } else {
  }
}
lemma pref_nested_all(h: seq, p: seq, e: int, q: int, k: int)
  requires pref(h, p, e, q)
  requires 0 <= k
  ensures forall y in [k, q) . pref(h, p, e, y) ==> pref(p, p, q, y)
  decreases q - k
{
  if k < q {
    if pref(h, p, e, k) {
      pref_nested1(h, p, e, q, k);
    } else {
    }
    pref_nested_all(h, p, e, q, k + 1);
  } else {
  }
}
lemma pref_elem(h: seq, p: seq, e: int, k: int)
  requires pref(h, p, e, k)
  ensures forall x in [0, k) . h[e - k + x] == p[x]
  decreases k
{
  if k > 0 {
    pref_elem(h, p, e - 1, k - 1);
  } else {
  }
}
lemma elem_pref(h: seq, p: seq, e: int, k: int)
  requires 0 <= k and k <= e and k <= len(p) and e <= len(h)
  requires forall x in [0, k) . h[e - k + x] == p[x]
  ensures pref(h, p, e, k)
  decreases k
{
  if k > 0 {
    elem_pref(h, p, e - 1, k - 1);
  } else {
  }
}
lemma pref_matches(h: seq, p: seq, e: int)
  requires pref(h, p, e, len(p))
  ensures matches_at(h, p, e - len(p))
{
  pref_elem(h, p, e, len(p));
}
lemma matches_raw(h: seq, p: seq, s: int, x: int)
  requires matches_at(h, p, s)
  requires 0 <= x and x <= len(p)
  ensures forall y in [x, len(p)) . h[s + y] == p[y]
  decreases len(p) - x
{
  if x < len(p) {
    assert char_eq(h, p, s, x);
    matches_raw(h, p, s, x + 1);
  } else {
  }
}
lemma matches_pref(h: seq, p: seq, s: int)
  ensures matches_at(h, p, s) ==> pref(h, p, s + len(p), len(p))
{
  if matches_at(h, p, s) {
    matches_raw(h, p, s, 0);
    elem_pref(h, p, s + len(p), len(p));
  } else {
  }
}
lemma fb_step(h: seq, p: seq, fail: seq, e: int, q: int, u: int)
  requires lps_ok(p, fail, u)
  requires fb_inv(h, p, e, q, u)
  requires 0 < q and e < len(h) and h[e] != p[q]
  ensures 0 <= fail[q] and fail[q] < q
  ensures fb_inv(h, p, e, fail[q], u)
{
  pref_trans(h, p, e, q, fail[q]);
  pref_nested_all(h, p, e, q, 0);
}
lemma lps_fb(p: seq, fail: seq, i: int)
  requires 1 <= i and i <= len(p) and len(fail) == i + 1
  requires lps_ok(p, fail, i)
  ensures fb_inv(p, p, i, fail[i], i)
{
}
lemma lps_ext(p: seq, fail: seq, i: int, k: int)
  requires 1 <= i and i < len(p) and len(fail) == i + 1
  requires lps_ok(p, fail, i)
  requires fb_inv(p, p, i, k, i)
  requires p[i] == p[k]
  ensures lps_ok(p, fail + [k + 1], i + 1)
{
  pref_ext(p, p, i, k);
}
lemma lps_noext(p: seq, fail: seq, i: int, k: int)
  requires 1 <= i and i < len(p) and len(fail) == i + 1
  requires lps_ok(p, fail, i)
  requires fb_inv(p, p, i, k, i)
  requires k == 0 and p[i] != p[0]
  ensures lps_ok(p, fail + [k], i + 1)
{
  pref_zero(p, p, i + 1);
}
lemma idx_sound_append(h: seq, p: seq, ind: seq, x: int)
  requires idx_sound(h, p, ind)
  requires 0 <= x and matches_at(h, p, x)
  ensures idx_sound(h, p, ind + [x])
{
}
lemma idx_complete_append(h: seq, p: seq, ind: seq, n: int)
  requires idx_complete(h, p, ind, n)
  ensures idx_complete(h, p, ind + [n], n + 1)
{
}
lemma full_forced(h: seq, p: seq, i: int, q: int)
  requires 0 <= i and i < len(h) and len(p) >= 1
  requires fb_inv(h, p, i, q, len(p))
  requires matches_at(h, p, i + 1 - len(p))
  ensures q + 1 == len(p) and h[i] == p[q]
{
  matches_pref(h, p, i + 1 - len(p));
}
lemma inv_init(h: seq, p: seq)
  requires len(p) >= 1
  ensures kmp_inv(h, p, 0, 0, [])
{
  pref_zero(h, p, 0);
}
lemma inv_fb(h: seq, p: seq, i: int, q: int, ind: seq)
  requires kmp_inv(h, p, i, q, ind)
  requires i < len(h)
  ensures fb_inv(h, p, i, q, len(p))
{
}
lemma fin_ext(h: seq, p: seq, i: int, q: int, ind: seq)
  requires 0 <= i and i < len(h) and len(p) >= 1
  requires fb_inv(h, p, i, q, len(p))
  requires h[i] == p[q] and q + 1 < len(p)
  requires idx_sound(h, p, ind)
  requires idx_complete(h, p, ind, i - len(p) + 1)
  ensures kmp_inv(h, p, i + 1, q + 1, ind)
{
  pref_ext(h, p, i, q);
  if matches_at(h, p, i + 1 - len(p)) {
    full_forced(h, p, i, q);
  } else {
  }
}
lemma fin_noext(h: seq, p: seq, i: int, q: int, ind: seq)
  requires 0 <= i and i < len(h) and len(p) >= 1
  requires fb_inv(h, p, i, q, len(p))
  requires q == 0 and h[i] != p[0]
  requires idx_sound(h, p, ind)
  requires idx_complete(h, p, ind, i - len(p) + 1)
  ensures kmp_inv(h, p, i + 1, 0, ind)
{
  pref_zero(h, p, i + 1);
  if matches_at(h, p, i + 1 - len(p)) {
    full_forced(h, p, i, q);
  } else {
  }
}
lemma fin_full(h: seq, p: seq, fail: seq, i: int, q: int, ind: seq)
  requires 0 <= i and i < len(h) and len(p) >= 1
  requires lps_ok(p, fail, len(p))
  requires fb_inv(h, p, i, q, len(p))
  requires h[i] == p[q] and q + 1 == len(p)
  requires idx_sound(h, p, ind)
  requires idx_complete(h, p, ind, i - len(p) + 1)
  ensures kmp_inv(h, p, i + 1, fail[len(p)], ind + [i + 1 - len(p)])
{
  pref_ext(h, p, i, q);
  pref_matches(h, p, i + 1);
  pref_trans(h, p, i + 1, len(p), fail[len(p)]);
  pref_nested_all(h, p, i + 1, len(p), 0);
  idx_sound_append(h, p, ind, i + 1 - len(p));
  idx_complete_append(h, p, ind, i - len(p) + 1);
}
method all_positions(h: seq) returns (r: seq)
  ensures forall k in [0, len(r)) . 0 <= r[k] and r[k] <= len(h)
  ensures forall x in [0, len(h) + 1) . x in r
{
  r := [];
  var s: int := 0;
  while s <= len(h)
    invariant 0 <= s and s <= len(h) + 1
    invariant forall k in [0, len(r)) . 0 <= r[k] and r[k] <= len(h)
    invariant forall x in [0, s) . x in r
    decreases len(h) + 1 - s
  {
    r := r + [s];
    s := s + 1;
  }
}
method fallback(h: seq, p: seq, fail: seq, e: int, q0: int, u: int) returns (q: int)
  requires lps_ok(p, fail, u)
  requires fb_inv(h, p, e, q0, u)
  requires 0 <= e and e < len(h)
  ensures fb_inv(h, p, e, q, u)
  ensures q == 0 or h[e] == p[q]
{
  q := q0;
  while q > 0 and h[e] != p[q]
    invariant fb_inv(h, p, e, q, u)
    decreases q
  {
    fb_step(h, p, fail, e, q, u);
    q := fail[q];
  }
}
method compute_fail(p: seq) returns (fail: seq)
  requires len(p) >= 1
  ensures lps_ok(p, fail, len(p))
{
  fail := [0, 0];
  var k: int := 0;
  var i: int := 1;
  pref_zero(p, p, 1);
  while i < len(p)
    invariant 1 <= i and i <= len(p)
    invariant len(fail) == i + 1
    invariant k == fail[i]
    invariant lps_ok(p, fail, i)
    decreases len(p) - i
  {
    lps_fb(p, fail, i);
    k := fallback(p, p, fail, i, k, i);
    if p[k] == p[i] {
      lps_ext(p, fail, i, k);
      k := k + 1;
    } else {
      lps_noext(p, fail, i, k);
    }
    fail := fail + [k];
    i := i + 1;
  }
}
method kmp_search(h: seq, p: seq) returns (ind: seq)
  requires len(p) >= 1
  ensures forall k in [0, len(ind)) . ind[k] >= 0
  ensures forall k in [0, len(ind)) . matches_at(h, p, ind[k])
  ensures forall s in [0, len(h) + 1) . matches_at(h, p, s) ==> (exists k in [0, len(ind)) . ind[k] == s)
{
  ind := [];
  var fail: seq := compute_fail(p);
  var q: int := 0;
  var i: int := 0;
  inv_init(h, p);
  while i < len(h)
    invariant kmp_inv(h, p, i, q, ind)
    decreases len(h) - i
  {
    inv_fb(h, p, i, q, ind);
    q := fallback(h, p, fail, i, q, len(p));
    if h[i] == p[q] {
      if q + 1 == len(p) {
        fin_full(h, p, fail, i, q, ind);
        ind := ind + [i + 1 - len(p)];
        q := fail[len(p)];
      } else {
        fin_ext(h, p, i, q, ind);
        q := q + 1;
      }
    } else {
      fin_noext(h, p, i, q, ind);
    }
    i := i + 1;
  }
}
{
  if len(needle) == 0 {
    indices := all_positions(haystack);
  } else {
    indices := kmp_search(haystack, needle);
  }
}
