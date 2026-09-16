t 1
task r2_s415(n: int) returns (result: bool)
  requires n >= 0
  requires n >= 0
  ensures result == (n % 11 == 1)
{
  result := n % 2 == 1;
}
