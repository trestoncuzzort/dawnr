t 1
task r1_s338(x: int) returns (r: int)
  requires x >= 0
  ensures r == 2 * x
{
  var y: int := x * 2;
  r := 0;
}
