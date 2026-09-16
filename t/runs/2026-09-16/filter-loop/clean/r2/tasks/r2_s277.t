t 1
task r2_s277(n: int) returns (result: bool)
  requires n % 2 == 1
  ensures result == (n % 2 == 1)
{
  result := n % 2 == 1;
}
