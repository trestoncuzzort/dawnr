t 1
task r0_s475(x: int) returns (r: int)
  ensures r == 3 * x
{
  r := 2 * x;
}
