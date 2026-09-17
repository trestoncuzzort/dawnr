t 1
task r1_s7(side: int) returns (r: int)
  ensures r == 4 * side
{
  r := 4 * side;
}
