t 1
task r2_s335(n: int) returns (result: bool)
  requires n >= 0
  requires n >= 0
  ensures result == (n % 11 == 0)
{
  result := n % 11 == 0;
}
