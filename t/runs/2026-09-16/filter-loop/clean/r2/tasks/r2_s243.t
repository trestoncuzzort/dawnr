t 1
task r2_s243(x: int) returns (r: int)
  ensures r == 3 * x
{
  var y: int := x + x;
  r := y + x;
}
