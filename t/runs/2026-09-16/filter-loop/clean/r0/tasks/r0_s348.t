t 1
gate quantifiers
task r0_s348(s: seq) returns (r: seq)
  requires len(s) > 0
  ensures len(r) == len(s)
  ensures forall k in [0, len(r)) . r[k] >= s[k]
{
  r := s[1..len(s)];
}
