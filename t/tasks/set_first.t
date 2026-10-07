t 1
task set_first(s: seq, x: int) returns (r: int)
  requires len(s) > 1
  ensures r == x + s[1]
{
  var u: seq := s[0 := x];
  r := u[0] + u[1];
}
