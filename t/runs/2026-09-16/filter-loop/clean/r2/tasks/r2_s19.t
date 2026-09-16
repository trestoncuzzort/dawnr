t 1
gate loops
task r2_s19(n: int) returns (i: int)
  requires 0 <= n
  ensures i == 0
{
  i := n;
  while 0 < i and i < n
    invariant 0 <= n and i <= n
    decreases i
  {
    i := i - 1;
    i := i + 1;
  }
}
