t 1
gate loops
task r1_s227(x: int) returns (y: int)
  requires x != 0
  ensures 0 <= x
  ensures y == -x
{
  y := -x;
}
