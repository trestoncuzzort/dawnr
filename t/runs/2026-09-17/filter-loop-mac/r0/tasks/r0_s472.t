t 1
task r0_s472(n: int) returns (k: int)
  requires n >= 1
  ensures k == n
{
  k := n - 1;
}
