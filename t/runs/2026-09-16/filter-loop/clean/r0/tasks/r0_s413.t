t 1
gate loops
task r0_s413(s: seq) returns (r: seq)
  requires len(s) > 0
  ensures len(r) == len(s)
  ensures forall k in [0, len(r)) . r[k] >= 0
  ensures exists k in [0, len(r)) . r[k] == s[len(s) - 1 - k]
{
  r := s[1..len(s)];
}
