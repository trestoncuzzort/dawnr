t 1
task r1_s6(side: int) returns (r: int)
  requires side > 0
  ensures r == 4 * side
{
  r := 4 * side;
}
