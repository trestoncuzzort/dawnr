t 1
task r2_s72(size: int) returns (area: int)
  requires size > 0
  requires size > 0
  ensures area == 4 * size * size * size
{
  area := 4 * size * size;
}
