t 1
gate loops
task count_matches(s: seq, x: int) returns (r: int)
  ensures r == count(s, x, len(s))
spec fun count(s: seq, x: int, n: int): int
  decreases n
= if n <= 0 or n > len(s) then 0 else count(s, x, n - 1) + (if s[n - 1] == x then 1 else 0)
{
  r := 0;
  var i: int := 0;
  while i < len(s)
    invariant r == count(s, x, i)
    invariant i >= 0 and i <= len(s)
    decreases len(s) - i
  {
    if s[i] == x {
      r := r + 1;
    } else {
    }
    i := i + 1;
  }
}
