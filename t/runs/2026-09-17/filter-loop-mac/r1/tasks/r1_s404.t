t 1
task r1_s404(side: int) returns (r: int)
  ensures r == 4 * side
{
  r := 6 * side;
}
