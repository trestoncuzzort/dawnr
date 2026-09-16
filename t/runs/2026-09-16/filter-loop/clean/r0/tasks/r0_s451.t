t 1
gate quantifiers
task r0_s451(side: int) returns (perimeter: int)
  requires side > 0
  ensures perimeter == 4 * side
{
  perimeter := 4 * side;
}
