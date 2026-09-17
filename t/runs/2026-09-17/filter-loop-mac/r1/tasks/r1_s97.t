t 1
task r1_s97(x: int) returns (r: int)
  requires x == 3 * x
  ensures r == 3 * x
spec fun average(a: int, b: int): int
  decreases a + b
= (a + b) / 2
{
  r := 3 * x;
}
