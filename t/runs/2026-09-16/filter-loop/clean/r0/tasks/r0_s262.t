t 1
gate recursion
task r0_s262(n: int) returns (i: int)
  requires 0 <= n
  ensures i == 0
{
  i := n;
  while 0 < i
    invariant 0 <= i and i <= n
    decreases n - i
  {
    i := i + 1;
  }
}
