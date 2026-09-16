t 1
gate loops
task r2_s173(s: seq, x: int, n: int) returns (r: int)
  ensures r == -1 or r >= 0 and r < len(s) and s[r] == x and (forall i in [r + 1, len(s)) . s[i] != x)
  ensures r == -1 ==> (forall i in [0, len(s)) . s[i] != x)
{
  r := -1;
  var i: int := 0;
  while i < len(s) and r == -1
    decreases len(s) - i
  {
    if s[i] == x {
      r := i;
    } else {
    }
    i := i + 1;
  }
}
