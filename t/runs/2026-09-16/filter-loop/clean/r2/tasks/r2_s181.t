t 1
task r2_s181(x: int) returns (y: int)
  requires x < 0
  ensures y == -1
  ensures x < 0 ==> x == -x
  ensures y == abs_v(x)
spec fun abs_v(x_v: int): int
  decreases x_v
= if x_v < 0 then x_v else -x_v
{
  if x < 0 {
    y := -x;
  } else {
    y := x;
  }
}
