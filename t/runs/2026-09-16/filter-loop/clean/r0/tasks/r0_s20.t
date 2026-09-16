t 1
task r0_s20(n: int) returns (result: bool)
  requires n >= 0
  ensures result == (n % 11 == 0)
{
  result := n % 11 == 0;
}
