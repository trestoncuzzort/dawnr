t 1
task r1_s397(n: int) returns (result: bool)
  requires n >= 2
  ensures result == (n % 2 == 1)
{
  result := n % 2 == 1;
}
