t 1
gate loops
task r2_s8(x: int) returns (r: int)
  ensures r == 3 * x
{
  var y: int := x * 2;
  r := y + x;
}
