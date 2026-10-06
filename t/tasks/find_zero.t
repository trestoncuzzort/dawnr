t 1
task find_zero(s: seq) returns (r: int)
  ensures 0 <= r and r <= len(s)
  ensures r < len(s) ==> s[r] == 0
  ensures forall k in [0, r) . s[k] != 0
{
  var i: int := 0;
  while true
    invariant 0 <= i and i <= len(s)
    invariant forall k in [0, i) . s[k] != 0
    decreases len(s) - i
  {
    if i == len(s) {
      break;
    }
    if s[i] == 0 {
      break;
    }
    i := i + 1;
  }
  r := i;
}
