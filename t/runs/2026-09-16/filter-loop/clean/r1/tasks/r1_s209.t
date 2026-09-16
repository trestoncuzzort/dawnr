t 1
task r1_s209(n: int) returns (i: int)
  requires 0 <= n
  ensures i == n
{
  i := n / 2;
}
