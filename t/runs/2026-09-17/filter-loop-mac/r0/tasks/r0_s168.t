t 1
task r0_s168(length: int, width: int) returns (area: int)
  requires length > 0
  ensures area == length * width
{
  area := length * width;
}
