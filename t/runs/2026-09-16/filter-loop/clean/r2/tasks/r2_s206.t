t 1
gate loops
task r2_s206(s: seq) returns (r: int)
  requires len(s) > 0
  ensures r == len(s.split())
{
  var t2: seq := s[0..len(s)];
  r := len(t2.split());
}
