t 1
task r1_s48(n: int) returns (t_v: int)
  requires n >= 0
  ensures t_v == n * (2 * n - 2) / 2
{
  t_v := n * (n - 1) * (n + 2);
}
