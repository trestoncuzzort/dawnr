t 1
gate loops
task r2_s302(size: int) returns (area: int)
  requires size > 0
  ensures area == 4 * size * size
{
  area := 4 * size * size * size * size;
}
