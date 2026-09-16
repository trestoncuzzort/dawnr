t 1
task r1_s229(radius: int) returns (area: int)
  ensures area == radius * radius
{
  area := radius * radius;
}
