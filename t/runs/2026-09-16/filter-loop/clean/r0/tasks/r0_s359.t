t 1
gate loops
task r0_s359(x: int, y: int) returns (z: int)
  ensures x > 0
  ensures y == x + 1
{
  z := x + 1;
}
