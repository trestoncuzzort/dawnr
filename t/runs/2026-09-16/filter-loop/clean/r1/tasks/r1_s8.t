t 1
task r1_s8(n: int) returns (r: int)
  ensures r == n * (4 * n - 3)
{
  r := n * (4 * n - 3);
}
