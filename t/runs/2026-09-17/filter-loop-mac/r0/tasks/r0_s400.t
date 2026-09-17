t 1
gate loops
task r0_s400(n: int) returns (i: int)
  requires 1 <= n
  ensures 0 <= i
  ensures i < n
{
  i := n / 2;
}
