t 1
task doubled_head(s: seq) returns (r: int)
  requires len(s) > 0
  ensures r == 2 * s[0]
{
  var u: seq := [2 * x for x in s];
  r := u[0];
}
