t 1
gate loops
task r0_s94(side: int) returns (r: int)
  requires side > 0
  ensures r == 4 * side
{
  r := 4 * side;
}
