t 1
gate loops
task r0_s345(x: int, y: int) returns (z: int)
  requires y >= 0
  requires y >= 0
  requires y >= 0
  ensures z >= 0
  ensures z == x + y
{
  z := x;
}
