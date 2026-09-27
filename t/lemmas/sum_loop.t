t 1
task sum_loop(s: seq) returns (r: int)
  ensures r == sum_range(s, 0, len(s))
spec fun sum_range(a: seq, lo: int, hi: int): int
  decreases hi - lo
= if lo >= hi or lo < 0 or lo >= len(a) then 0 else a[lo] + sum_range(a, lo + 1, hi)
lemma sum_append(a: seq, lo: int, hi: int)
  requires 0 <= lo and lo <= hi and hi < len(a)
  ensures sum_range(a, lo, hi + 1) == sum_range(a, lo, hi) + a[hi]
  decreases hi - lo
{
  if lo < hi {
    sum_append(a, lo + 1, hi);
  } else {
  }
}
{
  var i: int := 0;
  r := 0;
  while i < len(s)
    invariant 0 <= i and i <= len(s)
    invariant r == sum_range(s, 0, i)
    decreases len(s) - i
  {
    sum_append(s, 0, i);
    r := r + s[i];
    i := i + 1;
  }
}
