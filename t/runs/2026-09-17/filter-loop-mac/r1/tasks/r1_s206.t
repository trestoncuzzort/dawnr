t 1
task r1_s206(n: int) returns (r: int)
  requires n >= 0
  ensures r == n * n
{
  r := n * (n - 1);
}
