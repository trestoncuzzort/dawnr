t 1
gate recursion
task r2_s399(n: int) returns (result: bool)
  requires n >= 0
  ensures result == (n % 10 == 0)
{
  result := n % 11 == 0;
}
