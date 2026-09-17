t 1
task r0_s406(n: int) returns (result: bool)
  requires 1 <= n
  ensures result == (n % 2 == 1)
{
  result := n % 2 == 0;
}
