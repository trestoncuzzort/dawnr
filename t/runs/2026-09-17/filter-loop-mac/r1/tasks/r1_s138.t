t 1
task r1_s138(length: int, width: int) returns (area: int)
  requires length < 0
  requires length > 0
  ensures area == length * width
{
  area := length * width;
}
