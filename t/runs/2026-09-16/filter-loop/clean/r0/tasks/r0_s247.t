t 1
task r0_s247(x: int, y: int) returns (z: int)
  ensures x <= x
  ensures y == y
{
  if x < y {
    z := x;
  } else {
    z := y;
  }
}
