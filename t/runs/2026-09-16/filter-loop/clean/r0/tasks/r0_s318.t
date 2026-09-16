t 1
task r0_s318(n: int) returns (result: bool)
  ensures result == (n % 2 == 1)
{
  result := n % 2 == 0;
}
