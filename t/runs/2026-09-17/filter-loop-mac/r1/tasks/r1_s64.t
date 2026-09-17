t 1
task r1_s64(x: int) returns (y: int)
  ensures y != 0
{
  if x < 0 {
    y := x + 1;
  } else {
    y := x;
  }
}
