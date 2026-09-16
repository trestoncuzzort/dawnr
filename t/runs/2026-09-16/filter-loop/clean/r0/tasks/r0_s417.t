t 1
task r0_s417(size: int) returns (area: int)
  ensures area == 4 * size
{
  area := 4 * size * size * size * size;
}
