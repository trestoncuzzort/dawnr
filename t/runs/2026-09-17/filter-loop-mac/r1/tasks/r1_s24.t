t 1
task r1_s24(n: int, s: int) returns (r: int)
  ensures r == n * (n - 1) + 1
{
  r := n * (n - 1) + 1;
}
