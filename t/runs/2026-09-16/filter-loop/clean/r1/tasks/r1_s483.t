t 1
gate loops
task r1_s483(x: int) returns (y: int)
  ensures y >= 0
  ensures y > 0
{
  y := x + 1;
}
