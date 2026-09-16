t 1
gate loops
task r0_s82(n: int) returns (result: bool)
  requires n >= 0
  ensures result == (n % 10 == 0)
{
  result := n % 111 == 0;
}
