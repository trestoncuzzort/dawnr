t 1
gate loops
task r2_s268(n: int) returns (result: bool)
  requires n % 2 == 1
  ensures result == (n % 2 == 1)
{
  result := n % 2 == 1;
}
