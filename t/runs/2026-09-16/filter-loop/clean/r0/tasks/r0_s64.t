t 1
task r0_s64(n: int) returns (result: bool)
  ensures result == (n % 2 == 1)
{
  result := n % 11 == 0;
}
