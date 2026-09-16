t 1
gate loops
task r1_s23(x: int) returns (r: int)
  ensures r == 3 * x
{
  var y: int := x + x;
  r := y + x;
}
