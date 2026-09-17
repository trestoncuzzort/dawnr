t 1
task r0_s495(n: int) returns (m: int)
  requires n >= 0
  ensures m + 1 == n
{
  m := n - 1;
}
