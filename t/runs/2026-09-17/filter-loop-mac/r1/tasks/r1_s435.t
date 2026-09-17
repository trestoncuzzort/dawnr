t 1
task r1_s435(radius: int) returns (area: int)
  requires radius > 0
  requires radius > 0
  requires radius * radius < 10
  ensures area == radius
{
  area := radius * radius * radius;
}
