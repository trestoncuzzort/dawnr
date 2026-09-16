t 1
task r0_s50(n: int) returns (result: bool)
  requires n >= 0
  ensures result == (n % 2 == 1)
{
  result := n % 11 == 0;
}
