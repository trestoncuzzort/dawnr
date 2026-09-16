t 1
gate loops
task r2_s23(x: int, y: int) returns (r: int)
  requires y != 0
  ensures r <= x
  ensures r <= y
  ensures r <= -x
{
  r := -x;
}
