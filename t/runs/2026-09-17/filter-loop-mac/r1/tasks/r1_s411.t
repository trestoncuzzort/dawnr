t 1
gate loops
task r1_s411(s: seq) returns (r: seq)
  ensures len(r) == len(s)
  ensures forall i in [0, len(s)) . r[i] == s[i]
{
  r := s;
  var i: int := 0;
  while i < len(s)
    invariant i >= 0
    invariant i <= len(s)
    invariant len(r) == i
    invariant forall k in [0, i) . r[k] == s[k]
    decreases len(s) - i
  {
    r := r + [s[i] * s[i]];
    i := i + 1;
  }
}
