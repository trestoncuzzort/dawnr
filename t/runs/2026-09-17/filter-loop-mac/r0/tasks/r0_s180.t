t 1
task r0_s180(x: int) returns (r: int)
  requires x == 6
  ensures r == 3 * x
spec fun average(a: int, b: int): int
  decreases a + b
= (a + b) / 2
{
  r := 3 * x;
}
