t 1
task r0_s271(n: int) returns (d: int)
  requires n >= 0
  ensures d == 4 * n + 13
{
  d := 4 * n + 13;
}
