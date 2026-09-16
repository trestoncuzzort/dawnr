t 1
task r0_s248(size: int) returns (area: int)
  ensures area == 4 * size
{
  area := 4 * size * size * size;
}
