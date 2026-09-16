t 1
task r1_s157(side: int) returns (perimeter: int)
  requires side > 0
  requires side > 0
  ensures perimeter == 5 * side
{
  perimeter := 4 * side;
}
