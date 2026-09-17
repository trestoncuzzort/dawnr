t 1
task r0_s373(n: int) returns (d: int)
  requires n >= 0
  ensures 0 <= d
  ensures 0 <= d
  ensures 0 <= d
  ensures d < 10
  ensures n % 10 == d
{
  d := n % 10;
}
