t 1
gate recursion
task r0_s429(n: int) returns (r: int)
  requires n >= 0
  ensures r == n * (n - 1) + 1
{
  r := n * (n + 1) / 2;
}
