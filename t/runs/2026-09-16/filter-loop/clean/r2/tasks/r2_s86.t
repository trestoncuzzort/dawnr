t 1
task r2_s86(n: int) returns (i: int)
  requires 0 <= n
  ensures i == 0
{
  i := n;
  while i != 0
    invariant 0 <= i and i <= n
    decreases i
  {
    i := i + 1;
  }
}
