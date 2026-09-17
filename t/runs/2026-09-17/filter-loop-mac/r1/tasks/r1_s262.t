t 1
task r1_s262(x: int) returns (r: int)
  ensures average(2 * r, 6 * x) == 6 * x
  ensures r == 3 * x
spec fun average(a: int, b: int): int
  decreases a + b
= (a + b) / 2
{
  r := 3 * x;
}
