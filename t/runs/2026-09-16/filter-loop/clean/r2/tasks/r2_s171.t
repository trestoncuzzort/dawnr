t 1
task r2_s171(side: int) returns (r: int)
  requires side > 0
  ensures r == 4 * side
{
  r := 4 * side;
}
