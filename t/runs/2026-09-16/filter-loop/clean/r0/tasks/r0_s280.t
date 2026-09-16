t 1
gate loops
task r0_s280(radius: int) returns (r: int)
  ensures r == 2 * radius
{
  r := 2 * radius;
}
