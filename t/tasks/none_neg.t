t 1
task none_neg(s: seq) returns (b: bool)
  ensures b == (forall x in s . x >= 0)
{
  b := true;
  var i: int := 0;
  while i < len(s)
    invariant 0 <= i and i <= len(s)
    invariant b == (forall k in [0, i) . s[k] >= 0)
    decreases len(s) - i
  {
    if s[i] < 0 {
      b := false;
    }
    i := i + 1;
  }
}
