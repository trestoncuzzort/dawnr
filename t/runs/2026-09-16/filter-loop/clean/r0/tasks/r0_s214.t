t 1
gate loops
task r0_s214(n: int) returns (m: int)
  requires n > 0
  ensures m + 1 == n
{
  m := n - 1;
}
