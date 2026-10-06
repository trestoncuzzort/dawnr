t 1
task every_other(s: seq) returns (r: seq)
  ensures len(r) == (len(s) + 1) / 2
  ensures forall k in [0, len(r)) . r[k] == s[2 * k]
{
  r := s[0..len(s)..2];
}
