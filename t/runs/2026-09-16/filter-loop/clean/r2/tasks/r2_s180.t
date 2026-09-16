t 1
task r2_s180(x: int, y: int) returns (z: int)
  requires y != 0
  ensures z == x / (42 - y)
{
  z := x / y;
}
