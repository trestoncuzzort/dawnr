t 1
task r0_s439(x: int) returns (y: int)
  ensures x >= 0 ==> x == y
{
  if x > 0 {
    y := x;
  } else {
    y := y;
  }
}
