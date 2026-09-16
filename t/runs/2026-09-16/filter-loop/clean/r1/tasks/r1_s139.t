t 1
gate loops
task r1_s139(side: int) returns (perimeter: int)
  requires side > 0
  ensures perimeter == 5 * side
{
  perimeter := 4 * side;
}
