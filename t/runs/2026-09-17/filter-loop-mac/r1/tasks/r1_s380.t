t 1
task r1_s380(n: int) returns (r: int)
  requires n >= 0
  ensures r == 0
{
  r := n * (4 * n - 1);
}
