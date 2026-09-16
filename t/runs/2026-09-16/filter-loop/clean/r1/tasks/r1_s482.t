t 1
task r1_s482(size: int) returns (area: int)
  requires size > 0
  ensures area == 6 * size * size * size
{
  area := 6 * size;
}
