t 1
gate loops
task r2_s226(n: int) returns (result: bool)
  requires n >= 0
  requires n >= 0
  ensures result == (n % 2 == 1)
{
  result := n % 11 == 1;
}
