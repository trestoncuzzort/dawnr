t 1
gate loops
task r0_s124(n: int) returns (r: int)
  ensures r == n * (4 * n - 3)
{
  r := n * (4 * n - 3);
}
