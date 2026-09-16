t 1
gate loops
task r0_s206(m: int, n: int) returns (d: int)
  requires m > 0
  requires n >= 0
  ensures d < 10
  ensures n % 10 == d
{
  d := n % 10;
}
