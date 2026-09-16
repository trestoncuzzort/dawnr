t 1
gate recursion
task r0_s132(x: int) returns (r: int)
  requires x > 0
  ensures r == 3 * x
{
  var y: int := x + x;
  r := y + x;
}
