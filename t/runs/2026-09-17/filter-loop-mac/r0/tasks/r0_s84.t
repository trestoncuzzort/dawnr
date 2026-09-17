t 1
gate loops
task r0_s84(x: int, y: int) returns (z: int)
  requires x >= 0
  ensures z == x + y
{
  z := x + 1;
}
