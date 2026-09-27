t 1
gate loops
task double_all(s: seq) returns (r: seq)
  ensures r == dbl(s, len(s))
  ensures len(r) == len(s)
spec fun dbl(s: seq, n: int): seq
  decreases n
= if n <= 0 or n > len(s) then [] else dbl(s, n - 1) + [2 * s[n - 1]]
{
  r := [];
  var i: int := 0;
  while i < len(s)
    invariant r == dbl(s, i)
    invariant len(r) == i
    invariant i >= 0 and i <= len(s)
    decreases len(s) - i
  {
    r := r + [2 * s[i]];
    i := i + 1;
  }
}
