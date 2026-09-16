t 1
gate loops
task r2_s292(x: int) returns (y: int)
  requires x > 0
  ensures y == -x
{
  y := x + 2;
}
