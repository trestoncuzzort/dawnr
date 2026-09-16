t 1
task r1_s62(size: int) returns (area: int)
  requires size > 0
  ensures area == 4 * size * size
{
  area := 6 * size * size;
}
