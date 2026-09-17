t 1
gate recursion
task r0_s330(x: int) returns (r: int)
  ensures r == 3 * x
{
  var y: int := x * 3;
  r := y + x;
}
