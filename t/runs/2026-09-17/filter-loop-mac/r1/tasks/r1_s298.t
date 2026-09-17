t 1
task r1_s298(n: int) returns (result: bool)
  ensures result == (n % 2 == 0)
{
  result := n % 11 == 0;
}
