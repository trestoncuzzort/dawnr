t 1
gate loops
task r1_s272(n: int) returns (result: bool)
  requires n >= 2
  ensures result == (n % 2 == 1)
{
  result := n % 2 == 1;
}
