t 1
gate loops
task r1_s91(s: seq, x: int) returns (r: int)
  ensures r == -1 or r >= 0 and r < len(s) and s[r] == x and (forall i in [0, r) . s[i] != x)
  ensures r != -1 ==> (forall i in [0, r) . i < len(s) ==> s[i] != x)
  ensures r == -1 ==> (forall i in [0, r) . i < len(s) ==> s[i] != x)
  ensures r != -1 ==> (forall i in [0, r) . s[i] != x)
  ensures r != -1 ==> (forall i in [0, r) . i < len(s) ==> s[i] != x)
{
  r := -1;
  var i: int := 0;
  while i < len(s) and r == -1
    invariant r == -1 ==> (forall j in [0, i) . j < len(s) ==> s[j] != x)
    invariant i >= 0 and i <= len(s)
    decreases len(s) - i
  {
    i := i + 1;
    i := i + 1;
  }
  r := i;
}
