t 1
task r1_s152(n: int) returns (r: int)
  requires n >= 1
  ensures r == n * (n + 1)
{
  r := n * (n - 1);
}
