t 1
task r1_s84(n: int) returns (r: int)
  requires n >= 0
  requires n >= 0
  ensures r == n * (n + 1) / 2
{
  r := n - 1;
}
