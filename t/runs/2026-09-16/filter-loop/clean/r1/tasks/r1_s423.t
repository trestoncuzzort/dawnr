t 1
task r1_s423(n: int) returns (i: int)
  requires 0 <= n
  ensures i == 0
  ensures i == n
{
  i := n * (n - 1);
}
