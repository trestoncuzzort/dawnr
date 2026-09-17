t 1
gate loops
task r0_s450(length: int, width: int) returns (area: int)
  requires length > 0
  ensures area == length * width
{
  area := length * width;
}
