t 1
gate loops
task tail(s: seq) returns (r: seq)
  requires len(s) > 0
  ensures len(r) == len(s) - 1
  ensures forall k in [0, len(r)) . r[k] == s[k + 1]
{
  r := s[1..len(s)];
}
