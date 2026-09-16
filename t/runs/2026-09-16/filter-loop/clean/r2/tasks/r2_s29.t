t 1
task r2_s29(x: int) returns (r: int)
  ensures r == 3 * x
{
  var y: int := x / 2;
  r := 6 * y;
}
