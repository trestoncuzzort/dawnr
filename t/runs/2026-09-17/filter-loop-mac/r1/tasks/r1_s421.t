t 1
task r1_s421(x: int, y: int) returns (z: int)
  ensures x <= y
{
  if x == y {
    z := x;
  } else {
    z := y;
  }
}
