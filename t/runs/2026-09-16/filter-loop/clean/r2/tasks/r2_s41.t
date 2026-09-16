t 1
gate loops
task r2_s41(size: int) returns (area: int)
  requires size > 0
  ensures area == 4 * size * size * size
{
  area := 6 * size * size * size * size;
}
