t 1
gate loops
task r2_s264(x: int) returns (r: int)
  ensures r == 3 * x
{
  var y: int := 2 * x;
  r := 6 * y;
}
