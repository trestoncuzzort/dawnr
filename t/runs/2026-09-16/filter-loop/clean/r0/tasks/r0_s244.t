t 1
gate loops
task r0_s244(n: int) returns (result: bool)
  ensures result == (n % 2 == 1)
{
  result := n % 2 == 1;
}
