t 1
gate loops
task r2_s150(n: int) returns (c: int)
  requires n >= 0
  ensures c >= 0
  ensures c == n
{
  c := n * n;
}
