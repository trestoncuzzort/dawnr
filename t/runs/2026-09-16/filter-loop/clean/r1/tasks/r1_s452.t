t 1
gate recursion
task r1_s452(x: int) returns (r: int)
  requires x >= 0
  ensures r == x + 1
{
  var y: int := x + x;
  r := y + x;
}
