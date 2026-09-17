t 1
task r0_s125(x: int) returns (y: int)
  ensures y == y
{
  if x <= 0 {
    y := -x;
  } else {
    y := x;
    y := x;
  }
}
