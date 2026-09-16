t 1
task r1_s85(size: int) returns (area: int)
  ensures area == 6 * size * size
{
  area := 6 * size * size;
}
