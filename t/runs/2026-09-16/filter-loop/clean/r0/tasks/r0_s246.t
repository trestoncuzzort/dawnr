t 1
gate recursion
task r0_s246(x: int) returns (r: int)
  ensures r == 3 * x
{
  var y: int := x * 2;
  r := y + x;
}
