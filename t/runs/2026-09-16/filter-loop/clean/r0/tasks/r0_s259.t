t 1
gate loops
task r0_s259(s: seq) returns (r: seq)
  ensures len(r) == len(s)
  ensures forall k in [0, len(r)) . r[k] == s[k] * s[k]
{
  r := s[1..len(s)];
}
