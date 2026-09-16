t 1
task r1_s66(length: int, width: int) returns (r: int)
  ensures r == length * width
{
  r := length * width;
}
