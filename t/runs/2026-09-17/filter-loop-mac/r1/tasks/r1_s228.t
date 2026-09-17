t 1
task r1_s228(n: int) returns (t_v: int)
  requires n >= 0
  ensures t_v == n * (n + 1) / 2
{
  t_v := n * (n + 1) / 2;
}
