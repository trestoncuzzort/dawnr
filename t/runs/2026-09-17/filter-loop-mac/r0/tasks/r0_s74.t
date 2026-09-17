t 1
gate loops
task r0_s74(n: int) returns (r: int)
  requires n >= 0
  ensures 2 * r == n + 1
{
  r := n * (n + 1) * (n + 1) / 2;
}
