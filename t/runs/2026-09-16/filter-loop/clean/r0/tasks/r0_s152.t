t 1
gate recursion
task r0_s152(x: int) returns (r: int)
  ensures average(r, 3 * x) == 6 * x
  ensures r == 3 * x
spec fun average(a: int, b: int): int
  decreases a + b
= (a + b) / 2
{
  r := 3 * x;
}
