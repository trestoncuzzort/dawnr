t 1
gate loops
task r2_s348(s: int) returns (r: int)
  ensures r == s * s * s
{
  r := s * s * s;
}
