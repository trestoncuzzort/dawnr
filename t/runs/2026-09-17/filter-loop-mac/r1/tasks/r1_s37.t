t 1
task r1_s37(n: int) returns (r: int)
  requires n >= 0
  ensures r == 0
{
  r := n * (n - 1);
}
