t 1
task r0_s98(n: int) returns (result: bool)
  requires n <= n
  ensures result == (n % 2 == 1)
{
  result := n % 2 == 0;
}
