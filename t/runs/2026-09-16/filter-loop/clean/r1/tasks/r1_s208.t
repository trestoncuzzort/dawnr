t 1
task r1_s208(x: int) returns (r: int)
  requires x >= 0
  ensures r == 3 * x
{
  var y: int := x + x;
  r := y + x;
}
