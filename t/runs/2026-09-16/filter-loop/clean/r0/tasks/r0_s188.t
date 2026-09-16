t 1
gate loops
task r0_s188(s: seq, x: int) returns (r: seq)
  ensures len(r) <= len(s)
  ensures forall k in [0, len(r)) . r[k] == s[len(s) - 1 - k]
{
  r := s[0..len(s)];
}
