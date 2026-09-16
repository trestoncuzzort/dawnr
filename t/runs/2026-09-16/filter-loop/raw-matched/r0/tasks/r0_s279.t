t 1
gate loops
task r0_s279(s: seq) returns (r: int)
  requires len(s) > 0
  ensures r == s[0]
{
  r := s[0];
}
