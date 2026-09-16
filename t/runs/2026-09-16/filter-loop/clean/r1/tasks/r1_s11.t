t 1
task r1_s11(n: int) returns (t_v: int)
  requires n >= 0
  ensures n > 0
  ensures t_v == n * (2 * n - 1)
{
  t_v := n * (2 * n - 1);
}
