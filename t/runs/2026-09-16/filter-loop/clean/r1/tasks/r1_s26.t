t 1
task r1_s26(x: int) returns (y: int)
  ensures 0 <= y
  ensures x < 0 ==> y == -x
  ensures x < 0 ==> y == -x
  ensures y == abs_v(x)
spec fun abs_v(x_v: int): int
  decreases x_v
= if x_v > 0 then x_v else -x_v
{
  if x < 0 {
    y := -x;
  } else {
    y := x;
  }
}
