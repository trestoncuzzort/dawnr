t 1
gate loops
task linear_search(s: seq, target: int) returns (result: int)
  requires len(s) <= 2147483647
  requires is_sorted(s)
  ensures result >= 0
  ensures result <= len(s)
  ensures forall i in [0, result) . s[i] < target
  ensures forall i in [result, len(s)) . s[i] >= target
spec fun is_sorted(q: seq): bool
  decreases 0
= forall i in [0, len(q)) . forall j in [i, len(q)) . q[i] <= q[j]
{
  var p: int := 0;
  while p < len(s) and s[p] < target
    invariant 0 <= p and p <= len(s)
    invariant forall k in [0, p) . s[k] < target
    decreases len(s) - p
  {
    p := p + 1;
  }
  result := p;
}
