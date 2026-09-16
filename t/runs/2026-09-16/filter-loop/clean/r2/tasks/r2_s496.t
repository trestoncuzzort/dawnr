t 1
gate loops
task r2_s496(n: int) returns (result: bool)
  requires n % 2 == 1
  ensures result == (n % 11 == 1)
{
  result := n % 2 == 1;
}
