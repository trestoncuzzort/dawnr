t 1
task r1_s58(n: int) returns (result: bool)
  requires n >= 0
  ensures result == (n % 2 == 1)
{
  result := n % 2 == 1;
}
