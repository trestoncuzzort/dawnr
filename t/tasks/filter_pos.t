t 1
gate loops
task filter_pos(s: seq) returns (r: seq)
  ensures r == pos(s, len(s))
  ensures len(r) <= len(s)
spec fun pos(s: seq, n: int): seq
  decreases n
= if n <= 0 or n > len(s) then [] else (if s[n - 1] > 0 then pos(s, n - 1) + [s[n - 1]] else pos(s, n - 1))
{
  r := [];
  var i: int := 0;
  while i < len(s)
    invariant 0 <= i
    invariant i <= len(s)
    invariant r == pos(s, i)
    invariant len(r) <= i
    decreases len(s) - i
  {
    if s[i] > 0 {
      r := r + [s[i]];
    } else {
    }
    i := i + 1;
  }
}
