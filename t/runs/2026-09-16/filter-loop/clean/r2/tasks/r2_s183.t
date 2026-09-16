t 1
gate recursion
task r2_s183(x: int) returns (r: int)
  ensures r == 3 * x
{
  var y: int := x + x;
  r := y + x;
}
