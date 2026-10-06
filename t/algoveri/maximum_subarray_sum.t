t 1
gate loops
task max_subarray_sum(s: seq) returns (result: int)
  requires len(s) > 0
  requires len(s) <= 100000
  ensures forall i in [0, len(s) + 1) . sums_le(s, i, len(s), result)
  ensures exists i in [0, len(s) + 1) . sums_hit(s, i, len(s), result)
spec fun spec_sum(s: seq, start: int, end: int): int
  decreases end - start
= if start >= end or start < 0 or end > len(s) then 0 else s[end - 1] + spec_sum(s, start, end - 1)
spec fun sums_le(s: seq, i: int, e: int, v: int): bool
  decreases 0
= forall j in [i, e + 1) . spec_sum(s, i, j) <= v
spec fun sums_hit(s: seq, i: int, e: int, v: int): bool
  decreases 0
= exists j in [i, e + 1) . spec_sum(s, i, j) == v
lemma sum_snoc_all(s: seq, j: int, k: int)
  requires 0 <= j and j < len(s) and k == j + 1
  ensures forall a in [0, j + 1) . spec_sum(s, a, k) == spec_sum(s, a, j) + s[j]
{
}
lemma extend_starts(s: seq, n: int, e: int, e2: int, v: int, w: int)
  requires 0 <= n and v <= w and e2 == e + 1
  requires forall a in [0, n) . sums_le(s, a, e, v)
  requires forall a in [0, n) . spec_sum(s, a, e2) <= w
  ensures forall a in [0, n) . sums_le(s, a, e2, w)
  decreases n
{
  if n > 0 {
    extend_starts(s, n - 1, e, e2, v, w);
    assert sums_le(s, n - 1, e, v);
    assert sums_le(s, n - 1, e2, w);
  } else {
  }
}
lemma hit_intro(s: seq, a: int, b: int, v: int)
  requires 0 <= a and a <= b and b <= len(s)
  requires spec_sum(s, a, b) == v
  ensures exists i in [0, len(s) + 1) . sums_hit(s, i, len(s), v)
{
  assert sums_hit(s, a, len(s), v);
}
{
  var cur: int := 0;
  var ca: int := 0;
  var best: int := 0;
  var ba: int := 0;
  var bb: int := 0;
  var j: int := 0;
  while j < len(s)
    invariant 0 <= j and j <= len(s)
    invariant 0 <= ca and ca <= j
    invariant spec_sum(s, ca, j) == cur
    invariant forall a in [0, j + 1) . spec_sum(s, a, j) <= cur
    invariant 0 <= ba and ba <= bb and bb <= j
    invariant spec_sum(s, ba, bb) == best
    invariant forall a in [0, j + 1) . sums_le(s, a, j, best)
    decreases len(s) - j
  {
    var k: int := j + 1;
    sum_snoc_all(s, j, k);
    var nc: int := max(0, cur + s[j]);
    var na: int := if cur + s[j] >= 0 then ca else k;
    var nb: int := max(best, nc);
    extend_starts(s, k, j, k, best, nb);
    ba := if nc > best then na else ba;
    bb := if nc > best then k else bb;
    cur := nc;
    ca := na;
    best := nb;
    j := k;
  }
  hit_intro(s, ba, bb, best);
  result := best;
}
