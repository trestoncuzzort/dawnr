t 1
task count_pos_for(s: seq) returns (r: int)
  ensures r == npos(s, len(s))
spec fun npos(s: seq, n: int): int
  decreases n
= if n <= 0 or n > len(s) then 0 else npos(s, n - 1) + (if s[n - 1] > 0 then 1 else 0)
{
  var c: int := 0;
  for i, x in s
    invariant c == npos(s, i)
  {
    if x > 0 {
      c := c + 1;
    }
  }
  r := c;
}
