t 1
gate recursion
task r0_s365(x: int) returns (r: int)
  requires x >= 0
  ensures r == x + 1
{
  var y: int := x + 1;
  r := y + 1;
}
