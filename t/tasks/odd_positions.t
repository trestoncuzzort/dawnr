t 1
task odd_positions(s: seq) returns (r: seq)
  requires len(s) >= 1
  ensures len(r) == len(s) / 2
  ensures forall k in [0, len(r)) . r[k] == s[2 * k + 1]
{
  r := s[1..len(s)..2];
}
