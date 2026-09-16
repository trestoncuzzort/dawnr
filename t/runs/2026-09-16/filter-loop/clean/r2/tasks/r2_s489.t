t 1
gate loops
task r2_s489(n: int) returns (i: int)
  requires 0 <= n
  ensures i == 0
{
  i := n;
  while i != 0
    invariant 0 <= i and i <= n
    decreases n - i
  {
    i := i - 1;
  }
}
