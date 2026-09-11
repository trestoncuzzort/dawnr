t 1
gate loops
task first_even(s: seq) returns (r: int)
  ensures r == -1 or r >= 0 and r < len(s) and s[r] % 2 == 0
  ensures r == -1 ==> (forall i in [0, len(s)) . s[i] % 2 != 0)
  ensures r != -1 ==> (forall i in [0, r) . s[i] % 2 != 0)
{
  var i: int := 0;
  while i < len(s)
    invariant i >= 0 and i <= len(s)
    invariant forall j in [0, i) . s[j] % 2 != 0
    decreases len(s) - i
  {
    if s[i] % 2 == 0 {
      return i;
    } else {
    }
    i := i + 1;
  }
  r := -1;
}
