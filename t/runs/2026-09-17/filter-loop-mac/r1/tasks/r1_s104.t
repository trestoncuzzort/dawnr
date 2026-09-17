t 1
task r1_s104(x: int) returns (r: int)
  ensures r == 3 * x
{
  r := x * x;
}
