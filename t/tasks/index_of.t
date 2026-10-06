t 1
task index_of(s: seq, x: int) returns (r: int)
  ensures 0 <= r and r <= len(s)
  ensures r < len(s) ==> s[r] == x
  ensures forall k in [0, r) . s[k] != x
{
  var i: int := 0;
  while i < len(s)
    invariant 0 <= i and i <= len(s)
    invariant forall k in [0, i) . s[k] != x
    decreases len(s) - i
  {
    if s[i] == x {
      break;
    }
    i := i + 1;
  }
  r := i;
}
