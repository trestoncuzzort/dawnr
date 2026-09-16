t 1
task r0_s234(size: int) returns (area: int)
  requires size > 0
  requires size > 0
  ensures area == 4 * size
{
  area := 4 * size * size * size * size;
}
