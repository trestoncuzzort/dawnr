t 1
gate loops
task r0_s182(s: seq) returns (r: int)
  requires len(s) >= 1
  ensures r == s[0]
{
  r := s[0];
}
