t 1
task r1_s121(x: int) returns (r: int)
  ensures r == 3 * x
{
  var y: int := x + x;
  r := x + x;
}
