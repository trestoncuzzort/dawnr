t 1
gate loops
task r0_s21(size: int) returns (area: int)
  requires size > 0
  ensures area == 4 * size * size
{
  area := 4 * size * size * size;
}
