t 1
gate loops
task r2_s294(n: int) returns (result: bool)
  requires n >= 2
  requires n >= 0
  ensures result == (n % 2 == 1)
{
  result := n % 2 == 1;
}
