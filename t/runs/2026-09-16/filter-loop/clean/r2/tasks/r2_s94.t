t 1
gate loops
task r2_s94(x: int, y: int) returns (z: int)
  requires y == 6
  ensures z == x * y
{
  z := x + 1;
}
