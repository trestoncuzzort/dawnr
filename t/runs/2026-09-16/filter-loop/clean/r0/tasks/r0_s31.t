t 1
gate loops
task r0_s31(n: int) returns (r: int)
  requires n >= 0
  ensures r == n * (4 * n - 3)
{
  r := n * (4 * n - 3);
}
