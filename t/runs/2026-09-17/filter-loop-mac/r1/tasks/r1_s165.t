t 1
gate recursion
task r1_s165(s: seq, x: int, n: int) returns (r: int)
  requires n >= 0
  ensures r == -1 ==> (forall i in [0, len(s)) . s[i] != x)
  ensures r != -1 ==> (forall i in [0, r) . i < len(s) ==> s[i] != x)
{
  r := -1;
  var i: int := 0;
  while i < len(s) and r == -1
    invariant r != -1 ==> (forall j in [0, i) . j < len(s) ==> s[j] != x)
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
