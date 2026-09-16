t 1
gate loops
task r1_s364(size: int) returns (area: int)
  requires size > 0
  ensures area == 6 * size * size
{
  area := 6 * size * size;
}
