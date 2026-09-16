t 1
gate loops
task r0_s131(side: int) returns (perimeter: int)
  requires side > 0
  ensures perimeter == 4 * side
{
  perimeter := 4 * side;
}
