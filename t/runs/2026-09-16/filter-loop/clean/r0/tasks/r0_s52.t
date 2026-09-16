t 1
gate recursion
task r0_s52(n: int) returns (r: int)
  ensures r == n * (4 * n - 3)
{
  r := n * (4 * n - 3);
}
