t 1
task r1_s75(n: int) returns (r: int)
  requires n >= 0
  ensures r == n * (2 * n - 1)
{
  r := n * (2 * n - 1);
}
