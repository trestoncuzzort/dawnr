t 1
task r0_s89(y: int, x: int) returns (z: int)
  requires y >= 0
  ensures z >= 0
  ensures z == x + y
{
  z := x;
}
