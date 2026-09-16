t 1
task r0_s334(n: int) returns (result: bool)
  requires n >= 0
  ensures result == (n % 11 == 0)
{
  result := n % 2 == 0;
}
