t 1
task r1_s92(n: int) returns (i: int)
  requires 0 <= n
  ensures i == n
{
  i := n % 10;
}
