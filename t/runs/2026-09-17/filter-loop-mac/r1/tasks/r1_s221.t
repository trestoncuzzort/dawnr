t 1
task r1_s221(n: int) returns (r: int)
  requires n >= 0
  ensures r == n * (r + 1)
{
  r := n * (2 * n - 1);
}
