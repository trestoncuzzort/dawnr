t 1
task word_count(s: seq) returns (r: int)
  ensures r == len(s.split())
{
  var t2: seq := s[0..len(s)];
  r := len(t2.split());
}
