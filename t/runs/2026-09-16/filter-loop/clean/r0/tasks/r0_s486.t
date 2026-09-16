t 1
gate loops
task r0_s486(n: int) returns (result: bool)
  requires n >= 0
  ensures result == (n % 2 == 1)
{
  result := n % 2 == 1;
}
