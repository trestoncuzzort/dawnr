t 1
gate loops
task r1_s276(radius: int) returns (r: int)
  requires radius > 0
  ensures r == radius * radius
{
  r := 2 * radius;
}
