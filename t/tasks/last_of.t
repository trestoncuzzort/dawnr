t 1
task last_of(s: seq) returns (r: int)
  requires len(s) > 0
  ensures r == s[len(s) - 1]
{
  r := s[-1];
}
