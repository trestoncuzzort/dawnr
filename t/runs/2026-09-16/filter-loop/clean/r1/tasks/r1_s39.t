t 1
task r1_s39(radius: int) returns (area: int)
  requires radius >= 0
  ensures area == radius * radius
{
  area := radius * radius;
}
