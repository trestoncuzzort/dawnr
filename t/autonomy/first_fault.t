t 1
task first_fault(s: seq, limit: int) returns (r: int)
  ensures 0 <= r and r <= len(s)
  ensures r < len(s) ==> s[r] > limit
  ensures forall k in [0, r) . s[k] <= limit
{
  var i: int := 0;
  while i < len(s)
    invariant 0 <= i and i <= len(s)
    invariant forall k in [0, i) . s[k] <= limit
    decreases len(s) - i
  {
    if s[i] > limit {
      break;
    }
    i := i + 1;
  }
  r := i;
}
