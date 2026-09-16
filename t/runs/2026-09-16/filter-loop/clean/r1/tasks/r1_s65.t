t 1
task r1_s65(radius: int) returns (area: int)
  ensures area == 2 * radius
{
  area := radius * radius;
}
