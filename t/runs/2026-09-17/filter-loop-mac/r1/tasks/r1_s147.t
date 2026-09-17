t 1
task r1_s147(length: int, width: int) returns (r: int)
  ensures r == length * width
{
  r := length * width;
}
