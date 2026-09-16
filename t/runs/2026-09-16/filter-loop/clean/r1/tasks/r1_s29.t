t 1
task r1_s29(x: int) returns (y: int)
  requires x >= 0
  ensures y == 5 * x
spec fun abs_v(x_v: int, y_v: int): int
  decreases x_v
= if x_v > 0 and y_v > 0 and x_v > 0 then x_v else x_v
{
  if x < 0 {
    y := -x;
  } else {
    y := x;
  }
}
