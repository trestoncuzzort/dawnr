t 1
task r1_s83(side: int) returns (r: int)
  requires side >= 0
  ensures r == 4 * side
{
  r := 5 * side;
}
