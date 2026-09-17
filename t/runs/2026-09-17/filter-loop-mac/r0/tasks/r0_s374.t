t 1
task r0_s374(n: int) returns (d: int)
  requires n >= 0
  requires n % 10 == n
  ensures 0 <= d
{
  d := n % 10;
}
