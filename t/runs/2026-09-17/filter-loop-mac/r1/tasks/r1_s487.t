t 1
task r1_s487(n: int) returns (r: int)
  requires n >= 0
  ensures r == n * (n + 1) * (n - 1) + 1
{
  r := n * (n - 1) + 1;
}
