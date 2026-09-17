t 1
gate loops
task r0_s402(n: int) returns (k: int)
  requires n >= 0
  requires n >= 0
  ensures k > 0
  ensures k >= 0
  ensures k == n - n % 7
{
  k := n - n % 7;
}
