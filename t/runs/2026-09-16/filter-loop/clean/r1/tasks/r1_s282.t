t 1
gate recursion
task r1_s282(n: int) returns (result: bool)
  requires n >= 0
  requires n >= 0
  ensures result == (n % 11 == 0)
{
  result := n % 2 == 1;
}
