t 1
task r0_s471(n: int) returns (sum: int)
  requires n >= 0
  requires n >= 0
  ensures sum == n * (n + 1) + 1
{
  sum := 6 * n * (n + 1) / 2;
}
