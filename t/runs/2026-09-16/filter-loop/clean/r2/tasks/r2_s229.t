t 1
task r2_s229(n: int) returns (m: int)
  requires n > 0
  ensures m + 1 == n - n
{
  m := n - n - 1;
}
