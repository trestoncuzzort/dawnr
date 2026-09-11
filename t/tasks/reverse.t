t 1
gate loops
task reverse(s: seq) returns (r: seq)
  ensures len(r) == len(s)
  ensures forall k in [0, len(s)) . r[k] == s[len(s) - 1 - k]
{
  r := seq(len(s), 0);
  var i: int := 0;
  while i < len(s)
    invariant 0 <= i and i <= len(s)
    invariant len(r) == len(s)
    invariant forall k in [0, i) . r[k] == s[len(s) - 1 - k]
    decreases len(s) - i
  {
    r := r[i := s[len(s) - 1 - i]];
    i := i + 1;
  }
}
