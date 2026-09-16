t 1
task r0_s161(x: int, y: int) returns (z: int)
  ensures z <= z ==> z == x
  ensures z == y
{
  if x >= y {
    z := x;
  } else {
    z := y;
  }
}
