t 1
task r1_s62(s: seq, x: int) returns (r: int)
  ensures r == -1 or r >= 0 and r < len(s) and s[r] == x
  ensures r == -1 ==> (forall i in [0, len(s)) . s[i] != x)
{
  r := -1;
  var i: int := 0;
  while i < len(s) and r == -1
    invariant r == -1 ==> (forall j in [0, i) . j < len(s) ==> s[j] != x)
    invariant i >= 0 and i < len(s) and s[r] == x and (forall j in [r + 1, i) . j < len(s) ==> s[j] != x)
    invariant i >= 0 and i <= len(s)
    decreases len(s) - i
  {
    if s[i] == x {
      r := i;
    } else {
    }
    i := i + 1;
  }
}
