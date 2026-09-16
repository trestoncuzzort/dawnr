t 1
gate loops
task r2_s225(n: int) returns (result: bool)
  requires n >= 0
  ensures result == (n % 11 == 0)
{
  result := n % 2 == 1;
}
