t 1
task r2_s122(n: int) returns (result: bool)
  requires n >= 0
  requires n >= 0
  ensures result == (n % 2 == 1)
{
  result := n % 2 == 1;
}
