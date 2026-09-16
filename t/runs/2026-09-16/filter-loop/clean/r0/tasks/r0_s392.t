t 1
task r0_s392(x: int) returns (y: int)
  ensures x > 0
  ensures y == -x
{
  if x >= 0 {
    y := x;
  } else {
    y := y;
  }
}
