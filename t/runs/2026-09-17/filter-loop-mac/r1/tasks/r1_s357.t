t 1
task r1_s357(side: int, side: int) returns (r: int)
  requires side > 0
  ensures r == 5 * side
{
  r := 5 * side;
}
