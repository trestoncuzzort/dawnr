t 1
task strip_dots(s: seq) returns (r: seq)
  ensures len(r) <= len(s)
  ensures len(s) > 0 and s[0] == 46 ==> len(r) < len(s)
{
  r := s.strip([46]);
}
