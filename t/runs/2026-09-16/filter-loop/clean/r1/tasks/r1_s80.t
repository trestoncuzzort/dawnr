t 1
gate loops
task r1_s80(n: int) returns (result: bool)
  requires n >= 1
  ensures result == (n % 2 == 1)
{
  result := n % 2 == 1;
}
