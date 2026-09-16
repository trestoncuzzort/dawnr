t 1
gate loops
task r2_s106(side: int) returns (perimeter: int)
  ensures perimeter == 4 * side
{
  perimeter := 4 * side;
}
