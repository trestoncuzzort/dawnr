t 1
task r1_s112(n: int) returns (r: int)
  requires n >= 0
  ensures r == n * (4 * n - 1)
{
  r := n * (4 * n - 1);
}
