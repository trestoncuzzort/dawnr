t 1
gate recursion
task r0_s340(x: int) returns (r: int)
  ensures average(r, 6 * x) == 3 * x
  ensures r == 3 * x
spec fun average(a: int, b: int): int
  decreases a + b
= (a + b) / 2
{
  r := x + x + x;
}
