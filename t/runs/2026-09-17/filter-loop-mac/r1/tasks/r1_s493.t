t 1
gate loops
task r1_s493(length: int, width: int) returns (area: int)
  ensures area == length * width
{
  area := length * width;
}
