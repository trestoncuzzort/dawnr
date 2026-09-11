t 1
task wrong_last(s: seq) returns (r: int)
  requires len(s) >= 2
  ensures r == s[len(s) - 1]
{
  r := s[0];
}
