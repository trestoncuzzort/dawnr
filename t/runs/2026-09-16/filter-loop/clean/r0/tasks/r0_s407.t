t 1
gate loops
task r0_s407(n: int) returns (m: int)
  requires n >= 0
  ensures m == n * (4 * n - 3)
{
  m := n * (n - 3);
}
